/**
 * chat.js — Conversational AI agent widget
 * Talks to a Lambda+Bedrock backend (or a local mock if no API URL is set)
 */

(() => {
    'use strict';

    const widget = document.getElementById('chat-widget');
    const overlay = document.getElementById('chat-overlay');
    const closeBtn = document.getElementById('chat-close');
    const form = document.getElementById('chat-form');
    const input = document.getElementById('chat-input');
    const messagesEl = document.getElementById('chat-messages');

    if (!widget || !form) return;

    // Session id (kept in sessionStorage so refresh starts fresh after tab close)
    let sessionId = sessionStorage.getItem('adrian_session') || crypto.randomUUID();
    sessionStorage.setItem('adrian_session', sessionId);

    // ============ Open / close ============
    const openChat = () => {
        widget.classList.add('open');
        setTimeout(() => input?.focus(), 250);
    };
    const closeChat = () => widget.classList.remove('open');

    overlay.addEventListener('click', closeChat);
    closeBtn.addEventListener('click', closeChat);
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && widget.classList.contains('open')) closeChat();
    });

    window.openChat = openChat;
    window.openChatWithMessage = (preset) => {
        openChat();
        setTimeout(() => {
            input.value = preset;
            input.focus();
        }, 250);
    };

    // ============ Suggestions click ============
    document.addEventListener('click', e => {
        if (e.target.classList.contains('suggestion')) {
            input.value = e.target.textContent;
            form.requestSubmit();
        }
    });

    // ============ UI helpers ============
    const renderMd = (text) => {
        // Minimal markdown: code, bold, links, line breaks
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/```([\s\S]*?)```/g, (_, c) => `<pre><code>${c.trim()}</code></pre>`)
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
            .replace(/\n/g, '<br>');
    };

    const addMessage = (role, text, meta = null, citations = null) => {
        const wrap = document.createElement('div');
        wrap.className = `chat-msg ${role}`;
        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        bubble.innerHTML = renderMd(text);
        wrap.appendChild(bubble);

        if (meta) {
            const m = document.createElement('div');
            m.className = 'msg-meta';
            m.textContent = meta;
            wrap.appendChild(m);
        }
        if (citations && citations.length) {
            const c = document.createElement('div');
            c.className = 'msg-citations';
            citations.forEach(cit => {
                const tag = document.createElement('span');
                tag.className = 'citation';
                tag.textContent = `📄 ${cit}`;
                c.appendChild(tag);
            });
            wrap.appendChild(c);
        }
        messagesEl.appendChild(wrap);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return bubble;
    };

    const showTyping = () => {
        const wrap = document.createElement('div');
        wrap.className = 'chat-msg bot';
        wrap.id = 'typing';
        wrap.innerHTML = `
            <div class="typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
            </div>
        `;
        messagesEl.appendChild(wrap);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    };
    const hideTyping = () => document.getElementById('typing')?.remove();

    // ============ API call ============
    const callAPI = async (message) => {
        const apiUrl = window.__ADRIAN_API_URL__ || '';
        if (!apiUrl) {
            // Mock for local/dev
            return mockResponse(message);
        }
        const res = await fetch(`${apiUrl}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                message
            })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    };

    // ============ Local mock for dev / when API not deployed ============
    const mockKnowledge = {
        meru: `Sí, te respondo directo:

**Meru construye sobre stablecoins + IA = mi sweet spot.** Tengo experiencia llevando LLMs a producción con AWS Bedrock, RAG con vector stores (desde OpenSearch hasta soluciones custom en S3), y agentes con tool use. Y entiendo blockchain lo suficiente para no caer en buzzwords.

Lo que aporto a Meru:
- **Ownership total**: detecto procesos manuales, los automatizo y los presento andando.
- **Mentalidad de adopción, no de demos**: si no se usa, no existe.
- **Stack alineado**: Python, Bedrock, n8n / Make, prompt engineering, evals.

¿Querés que entre en detalle sobre algún proyecto específico?`,

        llm: `Mi experiencia con LLMs:

- **Providers**: Claude (Anthropic), GPT-4/4o (OpenAI), Gemini, Llama vía Bedrock.
- **Prompt engineering**: system prompts versionados, few-shot dinámico, prompt caching agresivo (~80% de reducción de latencia en conversaciones largas).
- **Patterns**: ReAct, tool use, multi-step agents, self-reflection loops.
- **Evals**: golden sets + LLM-as-judge corriendo en CI antes de mergear cambios de prompt.

¿Querés un ejemplo concreto de un agente que construí?`,

        arquitectura: `Este portafolio corre sobre:

\`\`\`
CloudFront → S3 (static)
           ↓
       API Gateway → Lambda (Python 3.12)
                       ↓
                  ┌────┴────┐
                  ↓         ↓
              Bedrock   S3 (_index/vectors.npy)
              (Claude)   numpy in-RAM cosine
                  ↓
              DynamoDB (sesiones)
\`\`\`

Todo desplegado con **AWS CDK** en Python. Reproducible, code-reviewable.

Decisiones que me importan:
- **Serverless por defecto**: escala a cero, paga por uso.
- **Prompt caching**: el system prompt se cachea, ahorro 80%+ de latencia.
- **Observabilidad**: trackeo tokens, costo, latencia y calidad por prompt-version.

Mirá la sección **Arquitectura** del portfolio para ver el diagrama completo.`,

        bot: `Cómo construyo un bot de soporte con RAG (steps reales que aplicaría en Meru):

**1. Ingesta de KB**
- S3 bucket con docs, FAQs, políticas.
- Lambda trigger que chunkea (semantic chunking, no fixed-size) y embedea con Titan/Voyage.
- Guardo el índice como `vectors.npy` + `chunks.json` en S3 (con metadatos: versión, categoría, idioma). Para tráfico bajo gana en latencia y costo a OpenSearch Serverless.

**2. Capa de retrieval**
- Hybrid search: BM25 + vector. El BM25 atrapa términos exactos (tickers, monedas), el vector atrapa intención.
- Reranking con un modelo cheap (Cohere Rerank) para top-K final.

**3. Generación**
- System prompt con persona + reglas estrictas ("solo respondé desde el contexto").
- Tool use: si la query requiere data en vivo (precio, status de tx), llama una función.
- Streaming de respuesta vía SSE para UX rápida.

**4. Evals**
- Golden set de 50-100 casos representativos.
- Scoring automático con LLM-as-judge en CI.
- Métricas en CloudWatch: deflection rate, latencia p95, costo por interacción.

**5. Adopción**
- Lo despliego en el canal donde el equipo ya vive (Slack/WhatsApp).
- Métricas semanales: ¿se usa? ¿qué porcentaje de tickets deflectó?
- Iteración basada en logs reales, no en mi intuición.

¿Querés ver el código de alguna parte?`,

        default: `Buena pregunta. Soy un mock corriendo en tu navegador — la versión real consulta Claude 3.5 vía Bedrock con RAG sobre un índice numpy cargado desde S3.

Para activar el agente real:

\`\`\`
cd infrastructure
cdk deploy --all
\`\`\`

Probá preguntas como:
- "¿Por qué Adrian para Meru?"
- "¿Qué experiencia tiene con LLMs?"
- "¿Cómo funciona este portafolio?"
- "Construí un bot de soporte con RAG"`
    };

    const mockResponse = async (message) => {
        await new Promise(r => setTimeout(r, 600 + Math.random() * 800));
        const lower = message.toLowerCase();
        let body = mockKnowledge.default;
        let citations = [];

        if (/meru|fintech|stablecoin|crypto/.test(lower)) {
            body = mockKnowledge.meru;
            citations = ['adrian_profile.md', 'meru_research.md'];
        } else if (/llm|claude|openai|gpt|gemini|modelo/.test(lower)) {
            body = mockKnowledge.llm;
            citations = ['adrian_profile.md'];
        } else if (/arquitectura|aws|bedrock|infra|stack|portafolio/.test(lower)) {
            body = mockKnowledge.arquitectura;
            citations = ['ARCHITECTURE.md'];
        } else if (/bot|rag|soporte|chatbot|construí|construir|paso a paso/.test(lower)) {
            body = mockKnowledge.bot;
            citations = ['adrian_profile.md', 'rag_patterns.md'];
        }

        return {
            response: body,
            citations,
            model: 'claude-3-5-sonnet-v2 (mock)',
            tokens: { input: 1240, output: 380 },
            latency_ms: 720,
            cost_usd: 0.00342
        };
    };

    // ============ Form submit ============
    form.addEventListener('submit', async e => {
        e.preventDefault();
        const message = input.value.trim();
        if (!message) return;

        addMessage('user', message);
        input.value = '';
        input.disabled = true;
        showTyping();

        try {
            const result = await callAPI(message);
            hideTyping();
            const meta = result.model
                ? `${result.model} · ${result.latency_ms || '—'}ms · in:${result.tokens?.input || '?'} out:${result.tokens?.output || '?'} · $${(result.cost_usd || 0).toFixed(5)}`
                : null;
            addMessage('bot', result.response, meta, result.citations);
        } catch (err) {
            hideTyping();
            addMessage('bot', `⚠️ Error al consultar el agente: ${err.message}\n\nSi estás corriendo local sin la stack desplegada, esto es esperable. El frontend cae a un mock automático.`);
        } finally {
            input.disabled = false;
            input.focus();
        }
    });

})();
