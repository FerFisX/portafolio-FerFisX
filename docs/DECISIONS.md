# Decision Log

Decisiones de diseño con su contexto. Si tomás el repo y querés cambiar algo, leé acá primero por qué está como está.

---

## 1. Por qué HTML/CSS/JS vanilla en vez de React/Next.js

**Decisión**: frontend en vanilla.

**Por qué**:
- Cero build step. Desplegar es `aws s3 sync`.
- Tiempo de carga de 200ms. Lighthouse: 100/100/100/100.
- El portafolio no necesita estado complejo. Un chat widget + scroll. No hace falta React.
- Optimiza para *demostrar AWS y backend*, que es lo que pide el rol.

**Cuándo cambiar**: si agrego un dashboard interactivo con muchas vistas, sí me cambio a Next.js o Astro.

---

## 2. Por qué Lambda + API Gateway HTTP API en vez de ALB + ECS

**Decisión**: serverless puro.

**Por qué**:
- Tráfico de portafolio = bursty + bajo. Pagar por containers ociosos es absurdo.
- Cold starts de Python son aceptables (~300ms con Lambda Powertools).
- IaC más simple. Cero gestión de cluster.

**Cuándo cambiar**: si el chat necesita streaming complejo o WebSockets persistentes con muchos clientes simultáneos. ALB + ECS Fargate sería el siguiente paso.

---

## 3. Por qué numpy-en-S3 en vez de OpenSearch / Pinecone

**Decisión**: vector store custom — `vectors.npy` + `chunks.json` en S3, cargado a RAM en cold start.

**Por qué**:
- **Costo**: $0 vs $350/mes mínimo de OS Serverless. Para una KB de portfolio (~50-500 chunks) la diferencia es absurda.
- **Latencia**: numpy en RAM = 50ms; OS Serverless por red = 200ms+.
- **Cero infra nueva**: el bucket de KB ya existía; solo agrego dos archivos bajo `_index/`.
- **Cold start aceptable**: cargar el `.npy` de 50 chunks tarda ~150ms.
- **Hybrid cheap**: 0.7×cosine + 0.3×keyword (regex sobre tokens del query) atrapa el ~80% de los casos donde BM25 puro era necesario.

**Trade-offs**:
- ✗ No escala más allá de ~50k chunks (RAM Lambda max ~3GB).
- ✗ No tiene BM25 real ni filtros complejos por metadata.
- ✗ Cada upload de doc rebuildea todo el índice (~10s para una KB chica, irrelevante).

**Cuándo cambiar**:
- KB supera 5-10MB de vectores → pgvector sobre RDS Serverless v2 (escala a 0.5 ACU).
- Necesitamos analytics, filtros complejos, multi-tenancy → OpenSearch Serverless.
- Tráfico de queries supera ~10/s sostenido → pgvector o OS.

**Por qué esto demuestra criterio (no es atajo)**:
Saber cuándo NO usar la solución "enterprise" es parte del oficio. Una startup con $500 de crédito y una KB de 5MB no necesita OpenSearch. Una compañía que procesa millones de docs sí.

---

## 4. Por qué Claude 3.5 Sonnet como modelo principal

**Decisión**: Claude Sonnet.

**Por qué**:
- Mejor en seguir instrucciones complejas (system prompt largo).
- Tool use confiable (vs. Llama, que requiere prompting cuidadoso).
- Prompt caching reduce costo significativamente.
- Output en español natural sin "calcos" del inglés.

**Cuándo cambiar**: para queries triviales uso Haiku (10x más barato). El router demo muestra cómo decidir dinámicamente.

---

## 5. Por qué CDK en Python (no Terraform, no SAM)

**Decisión**: CDK Python.

**Por qué**:
- Mismo lenguaje que el backend (Python). Menos context switch.
- Construcciones de alto nivel (`s3deploy.BucketDeployment` me ahorra mucho boilerplate).
- Tipos estáticos. Refactoring seguro.
- Diff visual antes de deploy (`cdk diff`).

**Trade-off vs Terraform**: lock-in a AWS. Pero para una arquitectura 100% AWS no es problema real.
**Trade-off vs SAM**: SAM es más simple para casos triviales, pero pierde flexibilidad cuando agregás Step Functions / EventBridge / OpenSearch.

---

## 6. Por qué semantic chunking (no fixed-size)

**Decisión**: paragraph-aware + overlap.

**Por qué**:
- Los docs de stablecoins y de mi profile tienen estructura clara (markdown).
- Code blocks NO se pueden cortar (rompe el contexto).
- Listas se mantienen completas.
- Overlap controlado (50 tokens) preserva continuidad entre chunks.

**Cuándo cambiar**: para docs sin estructura (transcripciones, scraping web sucio), iría a chunking con `recursive character splitter` de LangChain.

---

## 7. Por qué EMF metrics en vez de Datadog/Honeycomb

**Decisión**: CloudWatch EMF.

**Por qué**:
- Cero costo extra: ya pago CloudWatch Logs, EMF emite métricas desde los logs gratis.
- Cero latencia extra: es solo un print.
- Cero dependencias en código (no SDK externo).

**Trade-off**: dashboards de CloudWatch son menos lindos que Datadog. Pero para mostrar capacidad de instrumentar bien, alcanza.

---

## 8. Por qué Step Functions en vez de un workflow engine en Python

**Decisión**: Step Functions.

**Por qué**:
- El JSON declarativo es **visual** en la consola. Operaciones puede entender el flujo sin leer Python.
- Retries built-in, catch built-in. No reinvento la rueda.
- Logging y tracing automáticos.
- Es la analogía AWS-nativa de n8n/Make que pide el job listing.

**Cuándo cambiar**: para flujos con muchísimo branching dinámico, un agente con tool use puede ser más expresivo. No es uno-u-otro.

---

## 9. Por qué prompts en código (no en DB)

**Decisión**: prompts como código Python.

**Por qué**:
- **Versionables**: diff en PR. Reviewable.
- **Atomicidad con el código que los consume**: si cambio el contrato de un tool, el prompt se actualiza en la misma PR.
- **Cero dependencia de servicio externo** para responder.
- **Tests/evals se atan a una versión** específica del prompt.

**Cuándo cambiar**: si tengo > 5 personas escribiendo prompts no-técnicas, una DB con UI (tipo PromptLayer) puede ayudar. Pero esa complejidad solo aparece a escala.

---

## 10. Por qué evals como tests en CI

**Decisión**: golden set + LLM-as-judge + exit code 0/1.

**Por qué**:
- Sin evals, "cambié el prompt" es vibes-based. Con evals, tengo señal objetiva.
- Bloquea regresiones automáticamente. No depende de mi memoria.
- El golden set crece con cada bug en producción (cada caso difícil real → un eval nuevo).

**Trade-off**: cuesta tiempo construir el golden set. Pero compensa después del primer eval que atrapa una regresión silenciosa.
