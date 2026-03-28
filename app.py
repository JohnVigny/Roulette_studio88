from flask import Flask, render_template, request, redirect, url_for, flash, abort
import sqlite3
import random
import os
import secrets
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "studio88-admin-secret"

DB_NAME = "database.db"
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

TEST_UNLIMITED_EMAIL = "contact@lestudio88.fr"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def save_uploaded_file(file_obj):
    if not file_obj or not file_obj.filename:
        return ""

    filename = secure_filename(file_obj.filename)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    final_name = f"{timestamp}_{filename}"
    save_path = os.path.join(UPLOAD_FOLDER, final_name)
    file_obj.save(save_path)
    return f"/static/uploads/{final_name}"


def split_title_for_wheel(title):
    words = title.strip().split()
    if len(words) <= 1:
        return title

    mid = (len(words) + 1) // 2
    line1 = " ".join(words[:mid])
    line2 = " ".join(words[mid:])
    return f"{line1}<br>{line2}"


def get_active_gift_list(selected_list_id=None):
    conn = get_db()
    c = conn.cursor()

    if selected_list_id:
        c.execute("""
            SELECT * FROM gift_lists
            WHERE id = ? AND is_active = 1
        """, (selected_list_id,))
        gift_list = c.fetchone()
        if gift_list:
            conn.close()
            return gift_list

    c.execute("""
        SELECT * FROM gift_lists
        WHERE is_active = 1
        ORDER BY id ASC
        LIMIT 1
    """)
    gift_list = c.fetchone()
    conn.close()
    return gift_list


def get_gift_list_by_id(list_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM gift_lists WHERE id = ?", (list_id,))
    gift_list = c.fetchone()
    conn.close()
    return gift_list


def get_active_gifts_for_list(gift_list_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT *
        FROM gifts
        WHERE gift_list_id = ? AND is_active = 1
        ORDER BY id ASC
    """, (gift_list_id,))
    gifts = c.fetchall()
    conn.close()
    return gifts


def build_wheel_data(gifts):
    if not gifts:
        return [], ""

    segment_count = len(gifts)
    segment_angle = 360 / segment_count

    colors = [
        "#151515",
        "#5f4720",
        "#111111",
        "#80602b",
        "#171717",
        "#b68d43",
        "#101010",
        "#8d6a2d",
    ]

    gradient_parts = []
    wheel_items = []

    for i, gift in enumerate(gifts):
        start = i * segment_angle
        end = (i + 1) * segment_angle
        center_angle = start + (segment_angle / 2)
        color = colors[i % len(colors)]

        gradient_parts.append(f"{color} {start:.4f}deg {end:.4f}deg")

        wheel_items.append({
            "id": gift["id"],
            "index": i,
            "title": gift["title"],
            "title_html": split_title_for_wheel(gift["title"]),
            "icon_path": gift["icon_path"],
            "center_angle": round(center_angle, 4),
            "segment_angle": round(segment_angle, 4),
        })

    wheel_gradient = f"conic-gradient(from -90deg, {', '.join(gradient_parts)})"
    return wheel_items, wheel_gradient


def choose_weighted_gift(gifts):
    if not gifts:
        return None

    weighted = []
    for gift in gifts:
        weight = int(gift["weight"] or 0)
        if weight < 0:
            weight = 0
        weighted.append(weight)

    if sum(weighted) <= 0:
        return random.choice(gifts)

    return random.choices(gifts, weights=weighted, k=1)[0]


def get_expiration_days(gift):
    title = (gift["title"] or "").lower()

    if "séance" in title:
        return 90
    if "réduction" in title or "%" in title or "remise" in title:
        return 365
    if "tirage" in title:
        return 180
    if "identité" in title:
        return 365

    return 90


def save_play_history(first_name, last_name, email, gift_list, gift, access_link_id=None, source=None):
    conn = get_db()
    c = conn.cursor()

    result_type = "lose" if gift["title"].strip().lower() == "rien" else "win"

    expires_at = None
    if result_type == "win":
        days = get_expiration_days(gift)
        expires_at = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
        INSERT INTO play_history (
            first_name,
            last_name,
            email,
            destination_id,
            gift_list_id,
            gift_id,
            reward_title,
            reward_code,
            access_link_id,
            played_at,
            result_type,
            expires_at,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        first_name,
        last_name,
        email,
        gift_list["destination_id"],
        gift_list["id"],
        gift["id"],
        gift["title"],
        gift["code"],
        access_link_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        result_type,
        expires_at,
        source
    ))

    play_id = c.lastrowid
    conn.commit()
    conn.close()
    return play_id


def generate_unique_token():
    while True:
        token = secrets.token_urlsafe(16)
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM access_links WHERE token = ?", (token,))
        exists = c.fetchone()
        conn.close()
        if not exists:
            return token


@app.route("/spin", methods=["POST"])
def spin():
    list_id = request.form.get("list_id", type=int)
    first_name = request.form.get("prenom", "").strip()
    last_name = request.form.get("nom", "").strip()
    email = request.form.get("email", "").strip()

    gift_list = get_active_gift_list(list_id)

    if not gift_list:
        return redirect(url_for("home"))

    gifts = get_active_gifts_for_list(gift_list["id"])
    if not gifts:
        return redirect(url_for("home", list_id=gift_list["id"]))

    chosen_gift = choose_weighted_gift(gifts)
    wheel_items, wheel_gradient = build_wheel_data(gifts)

    chosen_angle = 0
    chosen_segment_angle = 0
    chosen_index = 0

    for item in wheel_items:
        if item["id"] == chosen_gift["id"]:
            chosen_angle = item["center_angle"]
            chosen_segment_angle = item["segment_angle"]
            chosen_index = item["index"]
            break

    source = "review" if request.form.get("review_mode") == "1" else None

    play_id = save_play_history(
        first_name=first_name,
        last_name=last_name,
        email=email,
        gift_list=gift_list,
        gift=chosen_gift,
        source=source
    )

    return render_template(
        "index.html",
        gift_list=gift_list,
        wheel_items=wheel_items,
        wheel_gradient=wheel_gradient,
        can_spin=True,
        preview_mode=False,
        spin_result=chosen_gift["title"],
        spin_angle=chosen_angle,
        spin_segment_angle=chosen_segment_angle,
        spin_index=chosen_index,
        spin_play_id=play_id,
        nom=last_name,
        prenom=first_name,
        email=email
    )


@app.route("/result")
def result():
    play_id = request.args.get("play_id", type=int)

    if not play_id:
        return redirect(url_for("home"))

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT
            ph.*,
            g.image_path,
            g.icon_path,
            g.description
        FROM play_history ph
        LEFT JOIN gifts g ON ph.gift_id = g.id
        WHERE ph.id = ?
    """, (play_id,))
    play = c.fetchone()
    conn.close()

    if not play:
        return redirect(url_for("home"))

    expires_in_days = None

    if play["expires_at"]:
        try:
            expires_dt = datetime.strptime(play["expires_at"], "%Y-%m-%d %H:%M:%S")
            now_dt = datetime.now()
            delta = expires_dt - now_dt
            expires_in_days = delta.days

            if delta.total_seconds() > 0 and expires_in_days < 0:
                expires_in_days = 0
        except Exception:
            expires_in_days = None

    return render_template(
        "result.html",
        play=play,
        expires_in_days=expires_in_days
    )


@app.route("/admin")
def admin_home():
    return render_template("admin_home.html")


@app.route("/admin/gifts", methods=["GET", "POST"])
def admin_gifts():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create_list":
            list_name = request.form.get("list_name", "").strip()
            if list_name:
                c.execute("INSERT INTO gift_lists (name) VALUES (?)", (list_name,))
                conn.commit()

        elif action == "delete_list":
            list_id = request.form.get("list_id")
            if list_id:
                c.execute("DELETE FROM gift_lists WHERE id = ?", (list_id,))
                conn.commit()

        conn.close()
        return redirect(url_for("admin_gifts"))

    c.execute("SELECT * FROM gift_lists ORDER BY id ASC")
    lists = c.fetchall()

    conn.close()
    return render_template("admin_gifts.html", lists=lists)


@app.route("/admin/gifts/<int:list_id>", methods=["GET", "POST"])
def admin_gift_list(list_id):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM gift_lists WHERE id = ?", (list_id,))
    gift_list = c.fetchone()

    if not gift_list:
        conn.close()
        return redirect(url_for("admin_gifts"))

    if request.method == "POST":
        action = request.form.get("action", "")
        return_after_save = request.form.get("return_after_save") == "1"

        if action == "create_gift":
            new_title = request.form.get("new_title", "").strip()
            new_code = request.form.get("new_code", "").strip()
            new_description = request.form.get("new_description", "").strip()
            new_weight = request.form.get("new_weight", "10")
            new_active = 1 if request.form.get("new_active") == "on" else 0

            new_image_path = save_uploaded_file(request.files.get("new_image_file"))
            new_icon_path = save_uploaded_file(request.files.get("new_icon_file"))

            if new_title:
                c.execute("""
                    INSERT INTO gifts (
                        gift_list_id, title, code, description, weight, image_path, icon_path, is_active
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    list_id,
                    new_title,
                    new_code,
                    new_description,
                    int(new_weight or 0),
                    new_image_path,
                    new_icon_path,
                    new_active
                ))
                conn.commit()
                flash("Cadeau ajouté avec succès")

            conn.close()
            return redirect(url_for("admin_gift_list", list_id=list_id))

        if action == "save_list":
            gift_ids = request.form.getlist("gift_id[]")
            titles = request.form.getlist("title[]")
            codes = request.form.getlist("code[]")
            descriptions = request.form.getlist("description[]")
            weights = request.form.getlist("weight[]")
            current_images = request.form.getlist("current_image_path[]")
            current_icons = request.form.getlist("current_icon_path[]")
            delete_ids = set([x for x in request.form.getlist("delete_id[]") if x])
            active_ids = set(request.form.getlist("active_ids[]"))

            for i, gift_id in enumerate(gift_ids):
                title = titles[i].strip() if i < len(titles) else ""
                code = codes[i].strip() if i < len(codes) else ""
                description = descriptions[i].strip() if i < len(descriptions) else ""
                weight = weights[i] if i < len(weights) else "0"
                current_image = current_images[i] if i < len(current_images) else ""
                current_icon = current_icons[i] if i < len(current_icons) else ""

                if gift_id in delete_ids:
                    c.execute("DELETE FROM gifts WHERE id = ?", (gift_id,))
                    continue

                image_path = current_image
                icon_path = current_icon

                new_image_path = save_uploaded_file(request.files.get(f"image_file_{gift_id}"))
                new_icon_path = save_uploaded_file(request.files.get(f"icon_file_{gift_id}"))

                if new_image_path:
                    image_path = new_image_path
                if new_icon_path:
                    icon_path = new_icon_path

                is_active = 1 if gift_id in active_ids else 0

                c.execute("""
                    UPDATE gifts
                    SET title = ?, code = ?, description = ?, weight = ?, image_path = ?, icon_path = ?, is_active = ?
                    WHERE id = ?
                """, (
                    title,
                    code,
                    description,
                    int(weight or 0),
                    image_path,
                    icon_path,
                    is_active,
                    gift_id
                ))

            conn.commit()
            conn.close()

            flash("Liste enregistrée avec succès")

            if return_after_save:
                return redirect(url_for("admin_gifts"))

            return redirect(url_for("admin_gift_list", list_id=list_id))

    c.execute("SELECT * FROM gifts WHERE gift_list_id = ? ORDER BY id ASC", (list_id,))
    gifts = c.fetchall()

    conn.close()
    return render_template("admin_gift_list.html", gift_list=gift_list, gifts=gifts)


@app.route("/admin/gifts/<int:list_id>/preview")
def admin_gift_list_preview(list_id):
    gift_list = get_gift_list_by_id(list_id)

    if not gift_list:
        return redirect(url_for("admin_gifts"))

    gifts = get_active_gifts_for_list(list_id)
    wheel_items, wheel_gradient = build_wheel_data(gifts)

    return render_template(
        "wheel_preview.html",
        gift_list=gift_list,
        wheel_items=wheel_items,
        wheel_gradient=wheel_gradient
    )


@app.route("/admin/links", methods=["GET", "POST"])
def admin_links():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        if action == "create_access":
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            destination_id = request.form.get("destination_id", type=int)
            gift_list_id = request.form.get("gift_list_id", type=int)

            if first_name and last_name and email and destination_id and gift_list_id:
                token = generate_unique_token()

                c.execute("""
                    INSERT INTO access_links (
                        token,
                        destination_id,
                        gift_list_id,
                        first_name,
                        last_name,
                        email,
                        is_active,
                        is_used,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?)
                """, (
                    token,
                    destination_id,
                    gift_list_id,
                    first_name,
                    last_name,
                    email,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
                conn.commit()
                flash("Accès client créé avec succès")

        elif action == "cleanup_tests":
            c.execute("""
                DELETE FROM play_history
                WHERE email = ?
                   OR access_link_id IN (
                        SELECT id FROM access_links WHERE email = ?
                   )
            """, (TEST_UNLIMITED_EMAIL, TEST_UNLIMITED_EMAIL))

            c.execute("""
                DELETE FROM access_links
                WHERE email = ?
            """, (TEST_UNLIMITED_EMAIL,))

            conn.commit()
            flash("Les accès et historiques de test ont été supprimés")

        elif action == "reset_reviews":
            c.execute("""
                DELETE FROM play_history
                WHERE source = 'review'
            """)
            conn.commit()
            flash("Historique des avis Google réinitialisé")
    
        elif action == "toggle_access":
            access_id = request.form.get("access_id", type=int)

            if access_id:
                c.execute("""
                    SELECT is_active
                    FROM access_links
                    WHERE id = ?
                """, (access_id,))
                row = c.fetchone()

                if row:
                    new_state = 0 if int(row["is_active"]) == 1 else 1

                    c.execute("""
                        UPDATE access_links
                        SET is_active = ?
                        WHERE id = ?
                    """, (new_state, access_id))
                    conn.commit()

                    if new_state == 1:
                        flash("Accès réactivé")
                    else:
                        flash("Accès désactivé")

        elif action == "reset_access":
            access_id = request.form.get("access_id", type=int)

            if access_id:
                c.execute("""
                    UPDATE access_links
                    SET is_used = 0, used_at = NULL
                    WHERE id = ?
                """, (access_id,))
                conn.commit()
                flash("Accès réinitialisé")

        elif action == "delete_access":
            access_id = request.form.get("access_id", type=int)

            if access_id:
                c.execute("""
                    DELETE FROM play_history
                    WHERE access_link_id = ?
                """, (access_id,))

                c.execute("""
                    DELETE FROM access_links
                    WHERE id = ?
                """, (access_id,))

                conn.commit()
                flash("Accès supprimé")

        conn.close()
        return redirect(url_for("admin_links"))

    c.execute("""
        SELECT id, label
        FROM destinations
        WHERE slug IN ('facture', 'parrainage')
        ORDER BY id ASC
    """)
    destinations = c.fetchall()

    c.execute("""
        SELECT id, name
        FROM gift_lists
        WHERE is_active = 1
        ORDER BY id ASC
    """)
    gift_lists = c.fetchall()

    c.execute("""
        SELECT
            al.*,
            d.label AS destination_label,
            gl.name AS gift_list_name
        FROM access_links al
        LEFT JOIN destinations d ON al.destination_id = d.id
        LEFT JOIN gift_lists gl ON al.gift_list_id = gl.id
        ORDER BY al.created_at DESC
    """)
    access_links = c.fetchall()

    conn.close()

    return render_template(
        "admin_links.html",
        destinations=destinations,
        gift_lists=gift_lists,
        access_links=access_links,
        test_unlimited_email=TEST_UNLIMITED_EMAIL
    )


@app.route("/play/<token>")
def private_spin(token):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT
            al.*,
            d.label AS destination_label,
            gl.name AS gift_list_name
        FROM access_links al
        LEFT JOIN destinations d ON al.destination_id = d.id
        LEFT JOIN gift_lists gl ON al.gift_list_id = gl.id
        WHERE al.token = ?
    """, (token,))
    access_link = c.fetchone()

    if not access_link:
        conn.close()
        abort(404)

    email_is_unlimited = (
        (access_link["email"] or "").strip().lower() == TEST_UNLIMITED_EMAIL.lower()
    )

    if int(access_link["is_active"]) != 1:
        conn.close()
        return render_template("private_spin.html", access_link=access_link, status="inactive")

    if int(access_link["is_used"]) == 1 and not email_is_unlimited:
        conn.close()
        return render_template("private_spin.html", access_link=access_link, status="used")

    gifts = get_active_gifts_for_list(access_link["gift_list_id"])
    wheel_items, wheel_gradient = build_wheel_data(gifts)

    conn.close()
    return render_template(
        "private_spin.html",
        access_link=access_link,
        status="ready",
        wheel_items=wheel_items,
        wheel_gradient=wheel_gradient
    )


@app.route("/play/<token>/spin", methods=["POST"])
def private_spin_action(token):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT
            al.*,
            d.label AS destination_label,
            gl.name AS gift_list_name
        FROM access_links al
        LEFT JOIN destinations d ON al.destination_id = d.id
        LEFT JOIN gift_lists gl ON al.gift_list_id = gl.id
        WHERE al.token = ?
    """, (token,))
    access_link = c.fetchone()

    if not access_link:
        conn.close()
        abort(404)

    email_is_unlimited = (
        (access_link["email"] or "").strip().lower() == TEST_UNLIMITED_EMAIL.lower()
    )

    if int(access_link["is_active"]) != 1:
        conn.close()
        return redirect(url_for("private_spin", token=token))

    if int(access_link["is_used"]) == 1 and not email_is_unlimited:
        conn.close()
        return redirect(url_for("private_spin", token=token))

    gift_list = get_gift_list_by_id(access_link["gift_list_id"])
    gifts = get_active_gifts_for_list(access_link["gift_list_id"])

    if not gift_list or not gifts:
        conn.close()
        return redirect(url_for("private_spin", token=token))

    chosen_gift = choose_weighted_gift(gifts)
    wheel_items, wheel_gradient = build_wheel_data(gifts)

    chosen_angle = 0
    chosen_segment_angle = 0
    chosen_index = 0

    for item in wheel_items:
        if item["id"] == chosen_gift["id"]:
            chosen_angle = item["center_angle"]
            chosen_segment_angle = item["segment_angle"]
            chosen_index = item["index"]
            break

    play_id = save_play_history(
        first_name=access_link["first_name"],
        last_name=access_link["last_name"],
        email=access_link["email"],
        gift_list=gift_list,
        gift=chosen_gift,
        access_link_id=access_link["id"]
    )

    # Adresse illimitée : on n'épuise jamais le lien
    if not email_is_unlimited:
        c.execute("""
            UPDATE access_links
            SET is_used = 1, used_at = ?
            WHERE id = ?
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            access_link["id"]
        ))
        conn.commit()

    conn.close()

    return render_template(
        "private_spin.html",
        access_link=access_link,
        status="ready",
        wheel_items=wheel_items,
        wheel_gradient=wheel_gradient,
        spin_result=chosen_gift["title"],
        spin_angle=chosen_angle,
        spin_segment_angle=chosen_segment_angle,
        spin_index=chosen_index,
        spin_play_id=play_id
    )


@app.route("/admin/history")
def admin_history():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT
            ph.first_name,
            ph.last_name,
            ph.email,
            ph.played_at,
            ph.reward_title,
            ph.reward_code,
            ph.result_type,
            ph.expires_at,
            gl.name AS gift_list_name
        FROM play_history ph
        LEFT JOIN gift_lists gl ON ph.gift_list_id = gl.id
        ORDER BY ph.played_at DESC
    """)
    data = c.fetchall()

    total_plays = len(data)
    total_wins = len([x for x in data if x["result_type"] == "win"])
    total_losses = total_plays - total_wins
    win_rate = round((total_wins / total_plays) * 100, 1) if total_plays else 0

    c.execute("""
        SELECT
            reward_title,
            COUNT(*) as total
        FROM play_history
        WHERE result_type = 'win'
        GROUP BY reward_title
        ORDER BY total DESC, reward_title ASC
        LIMIT 5
    """)
    top_gifts = c.fetchall()

    c.execute("""
        SELECT
            first_name,
            last_name,
            email,
            COUNT(*) as total
        FROM play_history
        GROUP BY first_name, last_name, email
        ORDER BY total DESC, last_name ASC, first_name ASC
        LIMIT 5
    """)
    top_clients = c.fetchall()

    c.execute("""
        SELECT
            gl.name AS gift_list_name,
            COUNT(ph.rowid) AS total_plays,
            SUM(CASE WHEN ph.result_type = 'win' THEN 1 ELSE 0 END) AS total_wins,
            SUM(CASE WHEN ph.result_type = 'lose' THEN 1 ELSE 0 END) AS total_losses
        FROM gift_lists gl
        LEFT JOIN play_history ph ON ph.gift_list_id = gl.id
        GROUP BY gl.id, gl.name
        ORDER BY gl.name ASC
    """)
    list_stats_raw = c.fetchall()

    list_stats = []
    for row in list_stats_raw:
        plays = row["total_plays"] or 0
        wins = row["total_wins"] or 0
        losses = row["total_losses"] or 0
        rate = round((wins / plays) * 100, 1) if plays else 0

        list_stats.append({
            "gift_list_name": row["gift_list_name"],
            "total_plays": plays,
            "total_wins": wins,
            "total_losses": losses,
            "win_rate": rate,
        })

    conn.close()

    return render_template(
        "admin_history.html",
        data=data,
        total_plays=total_plays,
        total_wins=total_wins,
        total_losses=total_losses,
        win_rate=win_rate,
        top_gifts=top_gifts,
        top_clients=top_clients,
        list_stats=list_stats,
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@app.route("/")
def home():
    list_id = request.args.get("list_id", type=int)
    gift_list = get_active_gift_list(list_id)

    review_mode = request.args.get("review", type=int) == 1
    first_name = request.args.get("first_name", "").strip()
    last_name = request.args.get("last_name", "").strip()
    email = request.args.get("email", "").strip().lower()

    if not gift_list:
        return render_template(
            "index.html",
            gift_list=None,
            wheel_items=[],
            wheel_gradient="",
            can_spin=False,
            preview_mode=False,
            review_mode=review_mode,
            nom=last_name,
            prenom=first_name,
            email=email
        )

    gifts = get_active_gifts_for_list(gift_list["id"])
    wheel_items, wheel_gradient = build_wheel_data(gifts)

    return render_template(
        "index.html",
        gift_list=gift_list,
        wheel_items=wheel_items,
        wheel_gradient=wheel_gradient,
        can_spin=len(gifts) > 0,
        preview_mode=False,
        review_mode=review_mode,
        nom=last_name,
        prenom=first_name,
        email=email
    )

@app.route("/review")
def review_page():
    return render_template("review.html")


@app.route("/review/play", methods=["POST"])
def review_play():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()

    conn = get_db()
    c = conn.cursor()

    # Blocage si déjà joué via avis, sauf ton email de test illimité
    if email != TEST_UNLIMITED_EMAIL.lower():
        c.execute("""
            SELECT id
            FROM play_history
            WHERE email = ? AND source = 'review'
        """, (email,))
        existing = c.fetchone()

        if existing:
            conn.close()
            return "Vous avez déjà participé à la roulette des avis Google."

    conn.close()

    # On redirige vers la roue sans la lancer automatiquement
    return redirect(
        url_for(
            "home",
            review=1,
            first_name=first_name,
            last_name=last_name,
            email=email
        )
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)