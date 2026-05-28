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


## Contacto y stack disponible

- **Disponibilidad**: full-time, modo remoto / hibrido.
- **AWS account**: con créditos para experimentar e iterar libremente.
- **GitHub**: repos públicos con ejemplos de prompts, eval frameworks, agentes.
- **LinkedIn**: https://www.linkedin.com/in/adrian-fernando-acarapi-roca-a543a0270/

## Filosofía corta

> "La IA no es un feature: es infraestructura. Y la infraestructura se diseña para durar."
