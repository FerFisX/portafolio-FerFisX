/**
 * main.js — Portfolio interactions
 * Adrian.AI
 */

(() => {
    'use strict';

    // ============ Navbar scroll effect ============
    const navbar = document.getElementById('navbar');
    const onScroll = () => {
        if (window.scrollY > 20) navbar.classList.add('scrolled');
        else navbar.classList.remove('scrolled');
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    // ============ Smooth scroll for anchor links ============
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', e => {
            const href = anchor.getAttribute('href');
            if (href === '#' || href.length < 2) return;
            const target = document.querySelector(href);
            if (target) {
                e.preventDefault();
                const offset = 80;
                const top = target.getBoundingClientRect().top + window.scrollY - offset;
                window.scrollTo({ top, behavior: 'smooth' });
            }
        });
    });

    // ============ Typed text in hero terminal ============
    const typedEl = document.getElementById('typed-text');
    if (typedEl) {
        const phrases = [
            'adrian deploy --service=bedrock-agent --region=us-east-1',
            'adrian build --rag --vector-store=s3+numpy',
            'adrian ship --bot=meru-ops --channel=slack',
            'adrian eval --prompt-version=v3 --golden-set=42-cases',
            'adrian iterate --feedback=production --adoption=87%'
        ];
        let phraseIdx = 0;
        let charIdx = 0;
        let isDeleting = false;

        const tick = () => {
            const current = phrases[phraseIdx];
            if (!isDeleting) {
                typedEl.textContent = current.slice(0, ++charIdx);
                if (charIdx === current.length) {
                    isDeleting = true;
                    setTimeout(tick, 1800);
                    return;
                }
                setTimeout(tick, 40 + Math.random() * 40);
            } else {
                typedEl.textContent = current.slice(0, --charIdx);
                if (charIdx === 0) {
                    isDeleting = false;
                    phraseIdx = (phraseIdx + 1) % phrases.length;
                }
                setTimeout(tick, 20);
            }
        };
        tick();
    }

    // ============ Footer year ============
    document.querySelectorAll('p').forEach(p => {
        if (p.textContent.includes('{{año}}')) {
            p.textContent = p.textContent.replace('{{año}}', new Date().getFullYear());
        }
    });

    // ============ Reveal on scroll ============
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

    document.querySelectorAll('.section-header, .stack-card, .project-card, .decision, .arch-layer, .meru-card').forEach(el => {
        el.classList.add('reveal');
        observer.observe(el);
    });

    // ============ Mobile menu toggle ============
    const mobileToggle = document.getElementById('mobile-toggle');
    const navLinks = document.querySelector('.nav-links');
    if (mobileToggle && navLinks) {
        mobileToggle.addEventListener('click', () => {
            navLinks.classList.toggle('open');
        });
    }

    // ============ Demo placeholders for non-chat demos ============
    const demoMessages = {
        rag: '📚 Demo RAG abierto en el chat — preguntale "¿qué es USDC?" o "diferencias entre USDT y DAI".',
        router: '🔀 El router multimodelo está activo. Activá el chat y comparalo.',
        workflow: '⚡ El workflow Step Functions vive en infrastructure/stacks/workflow_stack.py — abrí docs/ARCHITECTURE.md para ver el state machine.',
        eval: '✅ Los evals viven en backend/evals/. Mirá el golden_set.jsonl.',
        meru: '💎 La propuesta para Meru está más abajo, sección 05. Y el bot fintech está disponible en el chat — preguntale "armá un bot de conciliación on-chain".'
    };

    document.querySelectorAll('[data-demo]').forEach(btn => {
        btn.addEventListener('click', () => {
            const demo = btn.dataset.demo;
            const msg = demoMessages[demo];
            if (msg && window.openChatWithMessage) {
                window.openChatWithMessage(msg);
            } else if (msg) {
                alert(msg);
            }
        });
    });

    // ============ Contact form ============
    const form = document.getElementById('contact-form');
    const status = document.getElementById('form-status');
    if (form && status) {
        form.addEventListener('submit', async e => {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(form));
            status.textContent = 'Enviando...';
            status.classList.remove('error');

            try {
                // Esta URL será reemplazada por la salida de CDK al desplegar
                const apiUrl = window.__ADRIAN_API_URL__ || '';
                if (!apiUrl) {
                    // Modo dev sin API
                    await new Promise(r => setTimeout(r, 800));
                    status.textContent = '✓ (Modo dev) Mensaje listo para enviar. Desplegá la stack para activar.';
                    form.reset();
                    return;
                }

                const res = await fetch(`${apiUrl}/contact`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (!res.ok) throw new Error('Network error');
                status.textContent = '✓ Mensaje enviado. Te respondo en menos de 24h.';
                form.reset();
            } catch (err) {
                status.textContent = '✗ No se pudo enviar. Mandá un mail directo.';
                status.classList.add('error');
            }
        });
    }

    // ============ Chat triggers ============
    const openButtons = ['open-chat-nav', 'open-chat-hero', 'open-chat-card'];
    openButtons.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.addEventListener('click', () => window.openChat && window.openChat());
    });

})();
