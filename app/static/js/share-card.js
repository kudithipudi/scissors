/**
 * Share card: draws the final result of a match onto a 600x800 canvas so a
 * player can share it as an image.
 *
 * Colors are lifted verbatim from app/static/css/styles.css custom properties
 * (light theme) so the card matches the app:
 *   --color-primary      #4f46e5   --color-success   #059669
 *   --color-primary-light#6366f1   --color-danger    #e11d48
 *   --gradient-primary   #4f46e5 -> #818cf8
 *   --color-bg           #f8fafc   --color-bg-light  #ffffff
 *   --color-bg-lighter   #e2e8f0   --color-text      #0f172a
 *   --color-text-muted   #64748b
 *
 * A match can only be won or lost — `calculate_game_winner()` never returns a
 * tie — so there is deliberately no tie headline here. Individual *rounds*
 * can still tie, and those are drawn in the per-round strip.
 *
 * Usage: window.renderShareCard(canvasEl, {
 *   outcome: 'you' | 'opponent',
 *   yourWins, opponentWins,
 *   rounds: [{ you: 'rock', opponent: 'paper', outcome: 'win'|'loss'|'tie' }],
 *   gameCode: 'ABC123',
 *   siteUrl: 'https://lab.example.org/scissors'
 * });
 */
(function () {
    'use strict';

    var WIDTH = 600;
    var HEIGHT = 800;

    var C = {
        primary: '#4f46e5',
        primaryLight: '#818cf8',
        success: '#059669',
        danger: '#e11d48',
        bg: '#f8fafc',
        bgLight: '#ffffff',
        bgLighter: '#e2e8f0',
        text: '#0f172a',
        textMuted: '#64748b'
    };

    var STACK = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
    var EMOJI = { rock: '✊', paper: '✋', scissors: '✌️' };

    function font(weight, size) {
        return weight + ' ' + size + 'px ' + STACK;
    }

    function roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    }

    function renderShareCard(canvas, data) {
        if (!canvas || typeof canvas.getContext !== 'function') return null;
        var ctx = canvas.getContext('2d');
        if (!ctx) return null;

        var opts = data || {};
        var won = opts.outcome === 'you';
        var rounds = Array.isArray(opts.rounds) ? opts.rounds.slice(0, 5) : [];
        var accent = won ? C.success : C.danger;

        canvas.width = WIDTH;
        canvas.height = HEIGHT;

        /* ---- page ---- */
        ctx.fillStyle = C.bg;
        ctx.fillRect(0, 0, WIDTH, HEIGHT);

        /* ---- header band (--gradient-primary) ---- */
        var band = ctx.createLinearGradient(0, 0, WIDTH, 170);
        band.addColorStop(0, C.primary);
        band.addColorStop(1, C.primaryLight);
        ctx.fillStyle = band;
        ctx.fillRect(0, 0, WIDTH, 170);

        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        ctx.fillStyle = '#ffffff';
        ctx.font = font(800, 34);
        ctx.fillText('ROCK PAPER SCISSORS', WIDTH / 2, 74);

        ctx.font = font(600, 19);
        ctx.globalAlpha = 0.85;
        ctx.fillText('Shake-to-play multiplayer', WIDTH / 2, 116);
        ctx.globalAlpha = 1;

        /* ---- headline ---- */
        ctx.font = font(800, 76);
        ctx.fillStyle = accent;
        ctx.fillText(won ? 'VICTORY' : 'DEFEAT', WIDTH / 2, 268);

        ctx.font = font(700, 100);
        ctx.fillStyle = C.text;
        ctx.fillText(
            String(opts.yourWins || 0) + '  –  ' + String(opts.opponentWins || 0),
            WIDTH / 2,
            386
        );

        ctx.font = font(600, 20);
        ctx.fillStyle = C.textMuted;
        ctx.fillText('YOU' + '        ' + 'OPPONENT', WIDTH / 2, 444);

        /* ---- per-round strip ---- */
        var panelY = 486;
        var rowH = 52;
        var panelH = Math.max(rowH, rounds.length * rowH) + 28;

        ctx.fillStyle = C.bgLight;
        roundRect(ctx, 60, panelY, WIDTH - 120, panelH, 16);
        ctx.fill();
        ctx.strokeStyle = C.bgLighter;
        ctx.lineWidth = 2;
        ctx.stroke();

        if (!rounds.length) {
            ctx.font = font(600, 20);
            ctx.fillStyle = C.textMuted;
            ctx.fillText('No rounds recorded', WIDTH / 2, panelY + panelH / 2);
        }

        for (var i = 0; i < rounds.length; i++) {
            var r = rounds[i] || {};
            var y = panelY + 28 + i * rowH;

            ctx.textAlign = 'left';
            ctx.font = font(700, 18);
            ctx.fillStyle = C.textMuted;
            ctx.fillText('R' + (i + 1), 96, y);

            ctx.textAlign = 'center';
            ctx.font = font(400, 32);
            ctx.fillStyle = C.text;
            ctx.fillText(EMOJI[r.you] || '❓', 232, y);

            ctx.font = font(700, 16);
            ctx.fillStyle = C.textMuted;
            ctx.fillText('vs', WIDTH / 2, y);

            ctx.font = font(400, 32);
            ctx.fillStyle = C.text;
            ctx.fillText(EMOJI[r.opponent] || '❓', WIDTH - 232, y);

            ctx.textAlign = 'right';
            ctx.font = font(700, 16);
            if (r.outcome === 'win') {
                ctx.fillStyle = C.success;
                ctx.fillText('WON', WIDTH - 96, y);
            } else if (r.outcome === 'loss') {
                ctx.fillStyle = C.danger;
                ctx.fillText('LOST', WIDTH - 96, y);
            } else {
                ctx.fillStyle = C.textMuted;
                ctx.fillText('TIE', WIDTH - 96, y);
            }
            ctx.textAlign = 'center';
        }

        /* ---- footer ---- */
        ctx.font = font(700, 22);
        ctx.fillStyle = C.text;
        ctx.fillText('Game ' + (opts.gameCode || ''), WIDTH / 2, HEIGHT - 86);

        ctx.font = font(600, 17);
        ctx.fillStyle = C.textMuted;
        ctx.fillText(opts.siteUrl || '', WIDTH / 2, HEIGHT - 48);

        return canvas;
    }

    window.renderShareCard = renderShareCard;
})();
