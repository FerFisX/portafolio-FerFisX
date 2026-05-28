# RAG Patterns — Lo que aprendí construyendo sistemas RAG en producción

## Por qué hybrid > pure vector

Vector-only retrieval falla en queries con términos exactos: tickers (USDC, USDT), IDs, nombres propios, código.
BM25 los atrapa. Vector atrapa intención semántica.

**Hybrid + RRF (reciprocal rank fusion)** es la baseline mínima viable. Sin reranking siquiera, gana al pure-vector en ~80% de los benchmarks de RAG fintech/legal/técnico.

## Chunking — qué hacer y qué no

### Lo que NO funciona
- Fixed-size chunks (500 tokens, hard cut): corta oraciones, rompe contexto.
- Chunking por línea: pierde estructura.
- Chunks demasiado chicos (<200 tokens): el vector se vuelve ambiguo.

### Lo que SÍ funciona
- **Semantic / paragraph-aware**: respetar dobles newlines, listas, code blocks.
- **Overlap controlado** (50-100 tokens): continuidad entre chunks.
- **Metadata por chunk**: source, position, title del heading parent. Ayuda al ranking y al filtering.
- **Markdown-aware**: nunca cortar dentro de un code block o de un heading.

## Embeddings

- **Titan v2** (1024 dim): default para AWS-native. Bueno y barato.
- **Voyage v3 / Cohere v3**: mejor en multilingual y dominio técnico. Pagás un poco más.
- **Normalizar** los vectores (norm=L2) si la métrica es cosine.
- **Dimensión > 1024 rara vez ayuda** en el dominio típico — chequealo con tus evals antes de pagar.

## Reranking

- Top-K del retrieval suele ser ruidoso. Rerankear top-20 → top-5 con un modelo más pesado mejora notablemente la precisión.
- **Cohere Rerank** es la opción más simple. **LLM-as-reranker** funciona pero es caro.
- Si tu eval no muestra mejora con rerank, no lo agregues. Latencia y costo extra solo se justifican con datos.

## Citations — no es opcional

El modelo **debe** citar la fuente. Reglas:
- System prompt explícito: "Solo respondé desde `<kb_context>`. Si no está ahí, decí 'no sé'."
- Devolver al usuario las fuentes recuperadas para que pueda verificar.
- Si el modelo cita algo que no está en el contexto recuperado, es alucinación. Loguealo y alertá.

## Patrones de fallo comunes

### 1. "Lost in the middle"
Cuando el contexto es muy largo, el modelo ignora la información del medio. **Solución**: top-K corto (4-6), o reranking agresivo, o usar Anthropic prompt caching y dividir queries.

### 2. Citación de fuente equivocada
El modelo "ve" la fuente pero responde de su pre-training. **Solución**: forzar al modelo a copiar literalmente un fragmento antes de parafrasear ("antes de responder, transcribí la oración relevante del contexto").

### 3. Conflicto entre fuentes
Dos chunks dicen cosas distintas. **Solución**: prompt que indica explícitamente "si hay conflicto, presentá ambas y citalas".

### 4. "Drift" semántico en chunks largos
Un chunk de 2000 chars puede tener 3 temas. El embedding promedia y pierde foco.
**Solución**: chunks más cortos, o late chunking (embedear chunks pequeños pero retornar contexto extendido).

## Métricas que importan

- **Hit rate @ K**: % de queries donde el chunk correcto está en top-K.
- **MRR (Mean Reciprocal Rank)**: posición del primer chunk relevante.
- **Faithfulness**: el output del modelo está respaldado por el contexto (binary o LLM-as-judge).
- **Answer relevance**: ¿la respuesta contesta la pregunta? (subjetivo, mejor con LLM-as-judge o user feedback).

## Costo

Para un RAG típico con Bedrock:
- Embedding: ~$0.00002 por query (Titan v2, 1024 dim).
- OpenSearch Serverless: ~$0.24/OCU/hora. Para tráfico bajo, dos OCUs = ~$350/mes.
- Generation: Claude Sonnet ~$0.003/$0.015 in/out per 1K tokens. Con prompt caching, ~80% más barato.

Optimizaciones:
1. **Cachear embeddings** de queries repetidas.
2. **Reuso del system prompt** con cache_control.
3. **Modelo más chico** (Haiku) para queries simples; routing dinámico.
4. **Pre-filtro por metadata** antes del vector search (categoría, idioma, fecha).

## Cuándo NO usar RAG

- Cuando la respuesta es deterministica y vive en una DB: usá SQL + tool calling, no RAG.
- Cuando el corpus cabe en el contexto del modelo (<200k tokens): pasalo entero con prompt caching.
- Cuando la query no es de "preguntar a un documento" sino de "ejecutar una acción": agente con tools > RAG.
