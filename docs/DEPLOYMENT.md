# Deployment Guide

## Pre-requisitos

1. **Cuenta AWS** con créditos (los $500 que tenés alcanzan tranquilo para experimentar varias semanas).
2. **AWS CLI** configurado: `aws configure`.
3. **Node.js 18+** (CDK requiere npm para algunas operaciones).
4. **Python 3.10+**.
5. **AWS CDK CLI**: `npm install -g aws-cdk`.

## Habilitar Bedrock

Bedrock requiere habilitar acceso a cada modelo en la consola:

1. https://console.aws.amazon.com/bedrock/home#/modelaccess
2. "Manage model access" → "Modify model access"
3. Marcar:
   - Anthropic · Claude 3.5 Sonnet v2
   - Anthropic · Claude 3.5 Haiku
   - Anthropic · Claude 3 Haiku
   - Amazon · Titan Embeddings v2
   - Meta · Llama 3.1 70B
4. "Submit". Aprobación es instantánea para modelos de uso general.

## Verificar SES (para el form de contacto)

SES está en sandbox por defecto: solo podés mandar a emails verificados.

1. https://console.aws.amazon.com/ses/home#/verified-identities
2. "Create identity" → Email address → tu email.
3. Confirmá el email que te llega.
4. Para producción: pedir "production access" en SES (24h aprox).

Mientras tanto, en `infrastructure/stacks/api_stack.py` cambiá:
```python
"FROM_EMAIL": "noreply@adrian.ai",  # → tu email verificado
"TO_EMAIL": "adrian@example.com",   # → tu email verificado
```

## Deploy

```bash
cd infrastructure

# 1. virtual env + deps
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. bootstrap (una sola vez por cuenta/región)
cdk bootstrap

# 3. ver qué va a crear (opcional pero recomendado)
cdk synth
cdk diff

# 4. deploy todo
cdk deploy --all --require-approval never
```

Tiempo total: ~10 minutos.

## Outputs esperados

Al final del deploy CDK imprime:

```
Outputs:
  adrian-ai-frontend.SiteURL = https://xxxx.cloudfront.net
  adrian-ai-api.ApiUrl       = https://xxxx.execute-api.us-east-1.amazonaws.com
  adrian-ai-data.KBBucketName = adrian-ai-kb-<ACCOUNT>
  adrian-ai-data.SessionsTableName = adrian-ai-sessions
  adrian-ai-workflow.StateMachineArn = arn:aws:states:...
```

**Andá a `SiteURL` — tu portafolio está vivo.**

## Cargar la KB

```bash
# desde la raíz del repo
aws s3 cp backend/knowledge_base/ s3://adrian-ai-kb-<ACCOUNT>/ \
    --recursive \
    --exclude "*" \
    --include "*.md"
```

Cada `.md` dispara la Lambda `ingest`, que walkea todos los docs del bucket, chunkea, embedea con Titan y sube `_index/vectors.npy` + `_index/chunks.json`. Tarda ~10-20s total.

Verificá los logs:
```bash
aws logs tail /aws/lambda/adrian-ai-ingest --follow
```

## Correr evals (después del deploy)

```bash
cd backend
pip install boto3 numpy
python -m evals.run_evals
```

Esto:
1. Carga `evals/golden_set.jsonl`.
2. Por cada caso, invoca el agente real (con RAG sobre la KB indexada).
3. Score con LLM-as-judge (Claude Sonnet, temperature 0).
4. Imprime promedios + escribe `evals/report.json`.
5. Exit code 0 si overall ≥ 4.0/5.

Costo aproximado de una corrida completa: ~$0.05.

## Probar el workflow

```bash
aws events put-events --entries '[
  {
    "Source": "meru.transactions",
    "DetailType": "TransactionRecorded",
    "EventBusName": "adrian-ai-events",
    "Detail": "{\"payload\":\"Transferencia recibida de 1500 USDC desde 0xabc...123 — memo: pago de servicio mensual\"}"
  }
]'
```

Después en la consola: Step Functions → `adrian-ai-extract-workflow` → ver la última ejecución.

## Limpiar todo

```bash
cd infrastructure
cdk destroy --all
```

Tarda ~5 minutos. Limpia todos los recursos. **Heads up**: si dejaste objetos en S3, CDK los borra (configurado con `auto_delete_objects=True`).

## Troubleshooting

### "Access denied invoking model"
- Verificá que habilitaste el modelo en Bedrock console.
- Verificá que la región del CDK matchea la región donde habilitaste el modelo.

### "Email address is not verified"
- En sandbox SES, ambos sender y recipient deben estar verificados.
- O pedí production access.

### "Index not built yet" en logs del chat
- El bucket todavía no tiene `_index/vectors.npy`. Subí algún `.md` a la raíz del bucket para disparar el ingest.
- Verificá con: `aws s3 ls s3://<KB_BUCKET>/_index/`

### Cold starts altos en Lambda
- Activá SnapStart: `lambda_.Function(..., snap_start=lambda_.SnapStartConf.ON_PUBLISHED_VERSIONS)`.
- O usá Provisioned Concurrency para el chat endpoint si la demanda lo justifica.

### Costos inesperados
- El recurso más caro de esta stack es Bedrock (Claude Sonnet). Limitalo con `max_tokens` en `bedrock_client.py` y prompt caching.
- Mirá Cost Explorer: filtros por tag `project=adrian-ai-portfolio`.
