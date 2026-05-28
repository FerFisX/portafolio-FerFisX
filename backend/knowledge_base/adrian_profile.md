# Adrian — AI Engineer Profile

## Resumen ejecutivo

Soy AI Engineer enfocado en **llevar IA a producción real**, no en construir notebooks que nadie corre dos veces. Trabajo en el cruce entre LLMs, arquitectura serverless en AWS y producto. Mido el éxito por **adopción**, no por accuracy en benchmarks.

## Experiencia técnica

### LLMs en producción
- Integraciones con **Claude (Anthropic)**, **GPT-4/4o (OpenAI)**, **Gemini**, modelos open vía **AWS Bedrock**.
- **Prompt engineering** versionado: system prompts en código, evaluación automática en CI, A/B testing entre versiones.
- **Prompt caching** agresivo (Bedrock + Anthropic): reducciones típicas de 80% en latencia y 90% en costo para conversaciones largas.
- Tool use / function calling para agentes multi-step.
- Streaming de respuestas (SSE) para UX percibida.

### RAG (Retrieval-Augmented Generation)
- Embeddings con **Titan v2** y **Voyage**.
- **Hybrid search** (BM25 + vector) sobre **OpenSearch Serverless** y **pgvector**.
- Semantic chunking paragraph-aware con overlap controlado.
- Reranking con modelos cheap (Cohere Rerank, o LLM-as-reranker para top-K corto).
- Citaciones obligatorias en outputs — el modelo no inventa, cita.

### Agentes
- ReAct loops bounded (max-3 rounds para no explotar costo).
- Tool registry con schemas Pydantic.
- Manejo de errores en tools (errores capturados, devueltos al modelo, no crashean el agente).
- Patrones de orquestación: planning → execution → reflection.

### Stack AWS
- **Lambda (Python 3.12)** con SnapStart para minimizar cold starts.
- **API Gateway HTTP** para endpoints (más barato y rápido que REST API).
- **Bedrock** para LLMs (Claude principal, Haiku para clasificación, Llama para casos open).
- **OpenSearch Serverless** para vector DB.
- **DynamoDB** para sesiones y estado conversacional (TTL automático).
- **Step Functions** para workflows visuales tipo n8n/Make.
- **EventBridge** para event-driven automations.
- **SES** para email transaccional.
- **CloudWatch** + **X-Ray** + **EMF metrics** para observabilidad de IA (tokens, costo, latencia, eval-score por prompt-version).
- **CDK (Python)** para todo el IaC.

### No-code / Low-code
- **n8n** para automatizaciones internas rápidas (sobre todo cuando hay que conectar 4+ servicios sin escribir glue code).
- **Make (Integromat)** para flujos visuales con usuarios no técnicos.
- **Zapier** para integraciones simples y rápidas.
- **Slack bots / Discord bots / WhatsApp Business API** para distribución de IA en canales donde la gente ya vive.

## Forma de trabajar

### Ownership
- No espero el ticket. Detecto procesos manuales, los automatizo, y los presento andando.
- Trabajo cerca de los usuarios finales (operaciones, soporte, RRHH, ventas) para validar adopción real.
- Si un bot no se usa, asumo el error es mío, no del usuario.

### Calidad
- **Evals como tests**: golden sets de 50-100 casos por feature de IA. Score automático con LLM-as-judge. Si baja el score, no mergea.
- **Prompts como código**: viven en repo, diff en PR, versionados con tag.
- **Observabilidad first**: trackeo tokens, latencia, costo y calidad. Sin eso, "prompt engineering" es vibes.

### Producto
- Foco en **adopción**, no en demos. Métricas semanales: ¿cuántos lo usan? ¿qué tickets deflectó?
- Iteración basada en logs reales y entrevistas con usuarios.
- "Lo simple primero, lo elegante después". Tres líneas similares > abstracción prematura.

## Lenguajes y frameworks

- **Python** (uso diario): asyncio, FastAPI, Pydantic, SQLAlchemy, pytest.
- **TypeScript / Node** para frontends y algunos servicios.
- **LangChain / LangGraph** cuando aporta (no por defecto — muchas veces 50 líneas de Python ganan).
- **Bedrock Agents** y **Bedrock Knowledge Bases** para casos donde la abstracción de AWS conviene.

## Por qué Meru

- Meru construye sobre **stablecoins + IA**: la intersección más interesante de fintech ahora mismo.
- El rol está enmarcado como "infraestructura de IA, no proyecto paralelo" — eso es exactamente cómo pienso.
- Latitud para detectar oportunidades sin esperar tickets — mi modo natural.
- Equipo global, operaciones en +150 países, +1M de descargas — escala que obliga a hacer las cosas bien desde el inicio.

## Primeros 90 días en Meru — plan

### Día 1-30: Detectar y mapear
- Shadow a ops, support, RRHH, ventas. Identificar los 10 procesos manuales más dolorosos.
- Auditar herramientas actuales (Make / n8n / Zapier). Mapear qué pasos puede colapsar IA.
- Setear infra base: Bedrock + observabilidad + eval framework + prompt management layer.

### Día 31-60: Primer producto interno
- Bot interno de soporte sobre WhatsApp o Slack: deflexión Tier-1 con RAG sobre KB de Meru.
- Automatización de conciliación on-chain ↔ off-chain: LLM extrayendo de hashes, memos, comprobantes.
- Métricas claras desde el día 1: tickets deflectados, tiempo ahorrado, costo por interacción, NPS interno.

### Día 61-90: Escalar y abrir camino
- Plataforma interna de "AI tools" reusables: cualquier área puede instanciar un agente sin AI Engineer en el medio.
- Pipeline de evals continuos: cada cambio se valida contra casos dorados de cada producto.
- Documentar la "Meru AI playbook" para que el próximo AI Engineer (o yo mismo en 6 meses) no parta de cero.

## Lo que NO soy
- No soy data scientist clásico — no me obsesiona el último paper de arxiv ni los benchmarks académicos.
- No soy ML engineer de modelos custom — no entreno modelos desde cero, los compongo y los integro.
- No soy un perfil "demo only" — me importa el código que se mantiene, los costos que escalan, la operación que aguanta.

## Contacto y stack disponible

- **Disponibilidad**: full-time, modo remoto / LATAM.
- **AWS account**: con créditos para experimentar e iterar libremente.
- **GitHub**: repos públicos con ejemplos de prompts, eval frameworks, agentes.

## Filosofía corta

> "La IA no es un feature: es infraestructura. Y la infraestructura se diseña para durar."
