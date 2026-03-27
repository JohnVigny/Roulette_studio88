import sqlite3

DB_NAME = "database.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Active les clés étrangères SQLite
    c.execute("PRAGMA foreign_keys = ON;")

    # Nettoyage optionnel des anciennes tables si elles existent
    # On garde plays_old en sauvegarde éventuelle
    c.execute("""
    CREATE TABLE IF NOT EXISTS plays_old AS
    SELECT * FROM plays
    """)
    c.execute("DROP TABLE IF EXISTS plays")

    c.execute("DROP TABLE IF EXISTS play_history")
    c.execute("DROP TABLE IF EXISTS access_links")
    c.execute("DROP TABLE IF EXISTS gifts")
    c.execute("DROP TABLE IF EXISTS gift_lists")
    c.execute("DROP TABLE IF EXISTS destinations")
    c.execute("DROP TABLE IF EXISTS email_permissions")

    # 1. Destinations de roulette
    c.execute("""
    CREATE TABLE destinations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        label TEXT NOT NULL,
        requires_form INTEGER NOT NULL DEFAULT 0,
        one_time_email INTEGER NOT NULL DEFAULT 0,
        access_mode TEXT NOT NULL DEFAULT 'public'
    )
    """)

    # 2. Listes de cadeaux
    c.execute("""
    CREATE TABLE gift_lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        destination_id INTEGER,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE SET NULL
    )
    """)

    # 3. Cadeaux d'une liste
    c.execute("""
    CREATE TABLE gifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gift_list_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        code TEXT,
        weight INTEGER NOT NULL DEFAULT 1,
        image_path TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        display_order INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (gift_list_id) REFERENCES gift_lists(id) ON DELETE CASCADE
    )
    """)

    # 4. Liens d'accès privés pour facture / parrainage
    c.execute("""
    CREATE TABLE access_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT NOT NULL UNIQUE,
        destination_id INTEGER NOT NULL,
        gift_list_id INTEGER,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        is_used INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        used_at TEXT,
        expires_at TEXT,
        notes TEXT,
        FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE,
        FOREIGN KEY (gift_list_id) REFERENCES gift_lists(id) ON DELETE SET NULL
    )
    """)

    # 5. Permissions / blocages par email et par destination
    c.execute("""
    CREATE TABLE email_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        destination_id INTEGER NOT NULL,
        is_blocked INTEGER NOT NULL DEFAULT 0,
        is_unlimited INTEGER NOT NULL DEFAULT 0,
        can_be_unlocked INTEGER NOT NULL DEFAULT 1,
        note TEXT,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(email, destination_id),
        FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
    )
    """)

    # 6. Historique complet des participations
    c.execute("""
    CREATE TABLE play_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL,
        destination_id INTEGER NOT NULL,
        gift_list_id INTEGER,
        gift_id INTEGER,
        reward_title TEXT NOT NULL,
        reward_code TEXT,
        access_link_id INTEGER,
        played_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        result_type TEXT NOT NULL DEFAULT 'win',
        FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE,
        FOREIGN KEY (gift_list_id) REFERENCES gift_lists(id) ON DELETE SET NULL,
        FOREIGN KEY (gift_id) REFERENCES gifts(id) ON DELETE SET NULL,
        FOREIGN KEY (access_link_id) REFERENCES access_links(id) ON DELETE SET NULL
    )
    """)

    # Données de base : destinations
    c.execute("""
    INSERT INTO destinations (slug, label, requires_form, one_time_email, access_mode)
    VALUES
        ('avis', 'Avis Google', 1, 1, 'public'),
        ('facture', 'Facture', 0, 0, 'private'),
        ('parrainage', 'Parrainage', 0, 0, 'private')
    """)

    # Exception : ton email illimité sur toutes les destinations
    c.execute("SELECT id FROM destinations")
    destination_ids = [row[0] for row in c.fetchall()]

    for destination_id in destination_ids:
        c.execute("""
        INSERT INTO email_permissions (
            email, destination_id, is_blocked, is_unlimited, can_be_unlocked, note
        )
        VALUES (?, ?, 0, 1, 1, ?)
        """, (
            "contact@lestudio88.fr",
            destination_id,
            "Adresse de test illimitée"
        ))

    # Exemple de listes de départ
    c.execute("SELECT id FROM destinations WHERE slug = 'avis'")
    avis_id = c.fetchone()[0]

    c.execute("SELECT id FROM destinations WHERE slug = 'facture'")
    facture_id = c.fetchone()[0]

    c.execute("SELECT id FROM destinations WHERE slug = 'parrainage'")
    parrainage_id = c.fetchone()[0]

    c.execute("""
    INSERT INTO gift_lists (name, destination_id, is_active)
    VALUES
        ('Liste Avis Google', ?, 1),
        ('Liste Facture', ?, 1),
        ('Liste Parrainage', ?, 1)
    """, (avis_id, facture_id, parrainage_id))

    # Quelques cadeaux de démonstration
    c.execute("SELECT id FROM gift_lists WHERE name = 'Liste Avis Google'")
    liste_avis_id = c.fetchone()[0]

    c.execute("SELECT id FROM gift_lists WHERE name = 'Liste Facture'")
    liste_facture_id = c.fetchone()[0]

    demo_gifts_avis = [
        ("Rien", "", 30, "", 1, 1),
        ("Remise 10%", "S88-XXXX", 12, "", 1, 2),
        ("Remise 20%", "S88-YYYY", 8, "", 1, 3),
        ("Photo identité", "S88-ID", 10, "", 1, 4),
        ("Séance IRIS", "S88-IRIS", 15, "", 1, 5),
    ]

    demo_gifts_facture = [
        ("Rien", "", 30, "", 1, 1),
        ("Remise 10%", "S88-XXXX", 12, "", 1, 2),
        ("Remise 20%", "S88-YYYY", 8, "", 1, 3),
        ("Séance solo", "S88-SOLO", 8, "", 1, 4),
        ("Séance famille", "S88-FAM", 12, "", 1, 5),
        ("Séance IRIS", "S88-IRIS", 15, "", 1, 6),
    ]

    for gift in demo_gifts_avis:
        c.execute("""
        INSERT INTO gifts (gift_list_id, title, code, weight, image_path, is_active, display_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (liste_avis_id, *gift))

    for gift in demo_gifts_facture:
        c.execute("""
        INSERT INTO gifts (gift_list_id, title, code, weight, image_path, is_active, display_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (liste_facture_id, *gift))

    conn.commit()
    conn.close()
    print("Base de données V2 créée avec succès ✅")


if __name__ == "__main__":
    init_db()

cursor.execute("""
CREATE TABLE IF NOT EXISTS client_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    code TEXT UNIQUE,
    gift_list_id INTEGER,
    has_played INTEGER DEFAULT 0,
    created_at TEXT
)
""")