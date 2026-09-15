/**
 * Effects: synthesized sounds (WebAudio), confetti, haptics.
 * No external assets. Sound preference persisted in localStorage.
 * Version: 1.0
 */
window.Effects = (function () {
    'use strict';

    const SOUND_KEY = 'rps-sound-enabled';
    let audioCtx = null;
    let enabled = null;

    function isEnabled() {
        if (enabled === null) {
            const stored = localStorage.getItem(SOUND_KEY);
            enabled = stored === null ? true : stored === '1';
        }
        return enabled;
    }

    function setEnabled(value) {
        enabled = !!value;
        try {
            localStorage.setItem(SOUND_KEY, enabled ? '1' : '0');
        } catch (e) { /* private mode */ }
        if (enabled) ensureCtx();
    }

    function toggle() {
        setEnabled(!isEnabled());
        if (isEnabled()) play('tick');
        return isEnabled();
    }

    function ensureCtx() {
        if (!audioCtx) {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return null;
            audioCtx = new Ctx();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume().catch(() => {});
        }
        return audioCtx;
    }

    // One enveloped oscillator note
    function note(freq, start, duration, type, gainValue) {
        const ctx = ensureCtx();
        if (!ctx) return;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type || 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime + start);
        gain.gain.setValueAtTime(0.0001, ctx.currentTime + start);
        gain.gain.exponentialRampToValueAtTime(gainValue || 0.12, ctx.currentTime + start + 0.015);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + start + duration);
        osc.connect(gain).connect(ctx.destination);
        osc.start(ctx.currentTime + start);
        osc.stop(ctx.currentTime + start + duration + 0.05);
    }

    const SOUNDS = {
        tick:   () => { note(660, 0, 0.09, 'square', 0.06); },
        shoot:  () => { note(880, 0, 0.12, 'square', 0.08); note(1320, 0.02, 0.14, 'square', 0.05); },
        // Shake 2 of 3: a short rising two-note tone, between `tick` and `lock`.
        charge: () => { note(740, 0, 0.09, 'square', 0.08); note(988, 0.07, 0.12, 'square', 0.08); },
        lock:   () => { note(523, 0, 0.1, 'sine', 0.1); note(784, 0.09, 0.16, 'sine', 0.1); },
        win:    () => { [523, 659, 784, 1047].forEach((f, i) => note(f, i * 0.11, 0.22, 'triangle', 0.12)); },
        lose:   () => { note(392, 0, 0.25, 'sawtooth', 0.07); note(311, 0.18, 0.3, 'sawtooth', 0.07); note(233, 0.36, 0.45, 'sawtooth', 0.07); },
        tie:    () => { note(440, 0, 0.12, 'sine', 0.09); note(440, 0.14, 0.18, 'sine', 0.09); },
        join:   () => { note(587, 0, 0.1, 'sine', 0.09); note(880, 0.1, 0.2, 'sine', 0.09); },
        reveal: () => { note(196, 0, 0.5, 'triangle', 0.08); },
    };

    function play(name) {
        if (!isEnabled() || !SOUNDS[name]) return;
        try {
            SOUNDS[name]();
        } catch (e) { /* audio unavailable */ }
    }

    function buzz(pattern) {
        if (navigator.vibrate) {
            try { navigator.vibrate(pattern); } catch (e) { /* unsupported */ }
        }
    }

    /* ---------- Confetti ---------- */
    let canvas = null;
    let particles = [];
    let rafId = null;

    function getCanvas() {
        if (canvas && document.body.contains(canvas)) return canvas;
        canvas = document.createElement('canvas');
        canvas.id = 'confetti-canvas';
        canvas.setAttribute('aria-hidden', 'true');
        document.body.appendChild(canvas);
        return canvas;
    }

    function reducedMotion() {
        return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function confetti(originX, originY, count) {
        if (reducedMotion()) return;
        const cv = getCanvas();
        cv.width = window.innerWidth;
        cv.height = window.innerHeight;
        const ctx = cv.getContext('2d');
        const colors = ['#4f46e5', '#818cf8', '#ec4899', '#10b981', '#f59e0b', '#f43f5e'];

        for (let i = 0; i < (count || 160); i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 4 + Math.random() * 9;
            particles.push({
                x: originX !== undefined ? originX : cv.width / 2,
                y: originY !== undefined ? originY : cv.height * 0.35,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed - 5,
                size: 5 + Math.random() * 6,
                color: colors[Math.floor(Math.random() * colors.length)],
                rot: Math.random() * Math.PI,
                vr: (Math.random() - 0.5) * 0.3,
                life: 90 + Math.random() * 50,
                shape: Math.random() > 0.5 ? 'rect' : 'circle',
            });
        }
        if (!rafId) rafId = requestAnimationFrame(step);
    }

    function step() {
        const cv = getCanvas();
        const ctx = cv.getContext('2d');
        ctx.clearRect(0, 0, cv.width, cv.height);

        particles = particles.filter(p => p.life > 0 && p.y < cv.height + 40);
        for (const p of particles) {
            p.vy += 0.22;           // gravity
            p.vx *= 0.985;          // drag
            p.x += p.vx;
            p.y += p.vy;
            p.rot += p.vr;
            p.life--;

            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rot);
            ctx.globalAlpha = Math.min(1, p.life / 30);
            ctx.fillStyle = p.color;
            if (p.shape === 'rect') {
                ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
            } else {
                ctx.beginPath();
                ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.restore();
        }

        if (particles.length > 0) {
            rafId = requestAnimationFrame(step);
        } else {
            rafId = null;
            ctx.clearRect(0, 0, cv.width, cv.height);
        }
    }

    function celebrate() {
        play('win');
        buzz([60, 60, 60, 60, 120]);
        confetti();
    }

    return { isEnabled, setEnabled, toggle, play, buzz, celebrate, confetti };
})();
