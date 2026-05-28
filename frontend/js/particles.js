/**
 * particles.js — Animated network background
 * Lightweight, no dependencies
 */

(() => {
    'use strict';

    const canvas = document.getElementById('particles-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let width = 0, height = 0;
    let particles = [];
    let mouse = { x: -1000, y: -1000 };

    const CONFIG = {
        count: 60,
        maxDistance: 140,
        speed: 0.3,
        size: 1.6,
        color: 'rgba(0, 212, 255, ',
        lineColor: 'rgba(168, 85, 247, '
    };

    const resize = () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        // Adapt particle count to viewport
        const target = Math.floor(width * height / 24000);
        CONFIG.count = Math.min(80, Math.max(30, target));
        seed();
    };

    const seed = () => {
        particles = [];
        for (let i = 0; i < CONFIG.count; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * CONFIG.speed,
                vy: (Math.random() - 0.5) * CONFIG.speed,
                r: Math.random() * CONFIG.size + 0.5
            });
        }
    };

    const step = () => {
        ctx.clearRect(0, 0, width, height);

        // Update + draw particles
        for (const p of particles) {
            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0 || p.x > width) p.vx *= -1;
            if (p.y < 0 || p.y > height) p.vy *= -1;

            // Mouse repulsion
            const dx = p.x - mouse.x;
            const dy = p.y - mouse.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 120) {
                const force = (120 - dist) / 120 * 0.3;
                p.x += (dx / dist) * force;
                p.y += (dy / dist) * force;
            }

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = CONFIG.color + '0.6)';
            ctx.fill();
        }

        // Draw connecting lines
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const a = particles[i], b = particles[j];
                const dx = a.x - b.x, dy = a.y - b.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < CONFIG.maxDistance) {
                    const opacity = (1 - dist / CONFIG.maxDistance) * 0.18;
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.strokeStyle = CONFIG.lineColor + opacity + ')';
                    ctx.lineWidth = 0.6;
                    ctx.stroke();
                }
            }
        }

        requestAnimationFrame(step);
    };

    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', e => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });
    window.addEventListener('mouseleave', () => {
        mouse.x = -1000; mouse.y = -1000;
    });

    resize();
    step();
})();
