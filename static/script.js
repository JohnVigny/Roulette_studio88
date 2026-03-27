document.addEventListener("DOMContentLoaded", function () {
    const wheel = document.getElementById("wheel");
    const launchButton = document.getElementById("launchButton");
    const spinData = window.spinData || {};
    const wheelShell = document.querySelector(".wheel-shell");

    const spinSound = document.getElementById("spinSound");
    const winSound = document.getElementById("winSound");
    const loseSound = document.getElementById("loseSound");

    if (!wheel) return;

    const SPIN_DURATION_MS = 6200;
    const RESULT_REDIRECT_DELAY_MS = 6900;

    function safePlay(audio, volume = 1, loop = false) {
        if (!audio) return;
        audio.pause();
        audio.currentTime = 0;
        audio.volume = volume;
        audio.loop = loop;
        audio.play().catch(() => {});
    }

    function safeStop(audio) {
        if (!audio) return;
        audio.pause();
        audio.currentTime = 0;
        audio.loop = false;
    }

    function fadeOutAudio(audio, duration = 500) {
        if (!audio) return;

        const startVolume = audio.volume;
        const steps = 10;
        const stepDuration = duration / steps;
        let currentStep = 0;

        const fadeInterval = setInterval(() => {
            currentStep += 1;
            const progress = currentStep / steps;
            audio.volume = Math.max(0, startVolume * (1 - progress));

            if (currentStep >= steps) {
                clearInterval(fadeInterval);
                safeStop(audio);
                audio.volume = startVolume;
            }
        }, stepDuration);
    }

    function addFlashEffect() {
        if (!wheelShell) return;
        wheelShell.classList.add("wheel-win-flash");
        setTimeout(() => {
            wheelShell.classList.remove("wheel-win-flash");
        }, 700);
    }

    function addFinalTick() {
        if (!wheelShell) return;
        wheelShell.classList.add("wheel-final-tick");
        setTimeout(() => {
            wheelShell.classList.remove("wheel-final-tick");
        }, 260);
    }

    function playResultSound(reward) {
        if (String(reward).trim().toLowerCase() === "rien") {
            safePlay(loseSound, 0.65, false);
        } else {
            safePlay(winSound, 0.75, false);
        }
    }

    if (spinData.reward && spinData.index !== null && spinData.playId) {
        if (launchButton) {
            launchButton.disabled = true;
            launchButton.textContent = "La roue tourne...";
        }

        const turns = 7;
        const targetAngle = Number(spinData.angle || 0);
        const segmentAngle = Number(spinData.segmentAngle || 0);

        let randomInSegment = 0;
        if (segmentAngle > 0) {
            const safeMargin = Math.min(segmentAngle * 0.18, 6);
            const min = -((segmentAngle / 2) - safeMargin);
            const max = ((segmentAngle / 2) - safeMargin);
            randomInSegment = Math.random() * (max - min) + min;
        }

        const wheelVisualOffset = 90;
        const stopAngle = 360 - (targetAngle + randomInSegment + wheelVisualOffset);
        const finalRotation = (turns * 360) + stopAngle;

        safePlay(spinSound, 0.42, false);

        requestAnimationFrame(() => {
            wheel.classList.add("is-spinning");
            wheel.style.transition = `transform ${SPIN_DURATION_MS}ms cubic-bezier(0.08, 0.82, 0.17, 1)`;
            wheel.style.transform = `rotate(${finalRotation}deg)`;
            wheel.style.transition = `transform 6200ms cubic-bezier(0.12, 0.85, 0.18, 1)`;
        });

        setTimeout(() => {
            addFinalTick();
            addFlashEffect();
            fadeOutAudio(spinSound, 320);

            setTimeout(() => {
                playResultSound(spinData.reward);
            }, 180);
        }, SPIN_DURATION_MS - 280);

        setTimeout(() => {
            wheel.style.transform += " rotate(2deg)";
            setTimeout(() => {
                wheel.style.transform += " rotate(-2deg)";
            }, 120);
        }, SPIN_DURATION_MS - 200);

        setTimeout(() => {
            window.location.href = `/result?play_id=${encodeURIComponent(spinData.playId)}`;
        }, RESULT_REDIRECT_DELAY_MS);
    }
});