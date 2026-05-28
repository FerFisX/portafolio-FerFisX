"""
ApiStack — Lambdas + API Gateway HTTP API.

Lambdas:
  - chat       → POST /chat       (conversational agent w/ tool use + RAG)
  - router     → POST /router     (multi-model comparator)
  - contact    → POST /contact    (form → SES email)
  - ingest     → S3 trigger       (KB doc → embed → numpy index in S3)

Design choices:
  - HTTP API (not REST) — cheaper, faster, simpler CORS.
  - One Lambda per endpoint — clear cost attribution, independent scaling.
  - Shared layer for boto3 + numpy.
  - Bedrock access via IAM with least-privilege (only the models we use).
"""

from pathlib import Path

from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_logs as logs,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_dynamodb as ddb,
)
from constructs import Construct


LAMBDA_ROOT = Path(__file__).parent.parent.parent / "backend" / "lambdas"


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        prefix: str,
        sessions_table: ddb.Table,
        kb_bucket: s3.Bucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Shared layer ──────────────────────────────────────────────
        shared_layer = lambda_.LayerVersion(
            self,
            "SharedLayer",
            code=lambda_.Code.from_asset(str(LAMBDA_ROOT)),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="Shared utilities: Bedrock client, prompts, retrieval, observability",
        )

        # AWS-managed numpy layer (saves bundling numpy ourselves)
        numpy_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "NumpyLayer",
            # Klayers community-maintained ARN for numpy on py3.12 us-east-1.
            # See https://github.com/keithrozario/Klayers for other regions/versions.
            f"arn:aws:lambda:{self.region}:770693421928:layer:Klayers-p312-numpy:8",
        )

        # ── Common env ────────────────────────────────────────────────
        common_env = {
            "LOG_LEVEL": "INFO",
            "DEFAULT_MODEL_ID": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "SESSIONS_TABLE": sessions_table.table_name,
            "KB_BUCKET": kb_bucket.bucket_name,
        }

        # ── Common IAM: Bedrock invoke ────────────────────────────────
        bedrock_invoke = iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0",
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0",
                f"arn:aws:bedrock:{self.region}::foundation-model/meta.llama3-1-70b-instruct-v1:0",
            ],
        )

        # ── Chat Lambda ───────────────────────────────────────────────
        chat_fn = lambda_.Function(
            self,
            "ChatFn",
            function_name=f"{prefix}-chat",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="chat.handler.lambda_handler",
            code=lambda_.Code.from_asset(str(LAMBDA_ROOT)),
            layers=[shared_layer, numpy_layer],
            timeout=Duration.seconds(30),
            memory_size=1024,
            environment=common_env,
            log_retention=logs.RetentionDays.ONE_MONTH,
            tracing=lambda_.Tracing.ACTIVE,
        )
        chat_fn.add_to_role_policy(bedrock_invoke)
        sessions_table.grant_read_write_data(chat_fn)
        kb_bucket.grant_read(chat_fn)

        # ── Router Lambda ─────────────────────────────────────────────
        router_fn = lambda_.Function(
            self,
            "RouterFn",
            function_name=f"{prefix}-router",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="router.handler.lambda_handler",
            code=lambda_.Code.from_asset(str(LAMBDA_ROOT)),
            layers=[shared_layer],
            timeout=Duration.seconds(45),
            memory_size=1024,
            environment=common_env,
            log_retention=logs.RetentionDays.ONE_MONTH,
            tracing=lambda_.Tracing.ACTIVE,
        )
        router_fn.add_to_role_policy(bedrock_invoke)

        # ── Contact Lambda ────────────────────────────────────────────
        contact_fn = lambda_.Function(
            self,
            "ContactFn",
            function_name=f"{prefix}-contact",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="contact.handler.lambda_handler",
            code=lambda_.Code.from_asset(str(LAMBDA_ROOT)),
            layers=[shared_layer],
            timeout=Duration.seconds(15),
            memory_size=512,
            environment={
                **common_env,
                "FROM_EMAIL": "arviziosoft@gmail.com",
                "TO_EMAIL": "arviziosoft@gmail.com",
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
        )
        contact_fn.add_to_role_policy(bedrock_invoke)
        contact_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )

        # ── Ingest Lambda (S3 → numpy index in S3) ────────────────────
        ingest_fn = lambda_.Function(
            self,
            "IngestFn",
            function_name=f"{prefix}-ingest",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="rag.ingest.lambda_handler",
            code=lambda_.Code.from_asset(str(LAMBDA_ROOT)),
            layers=[shared_layer, numpy_layer],
            timeout=Duration.minutes(5),
            memory_size=1024,
            environment=common_env,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )
        ingest_fn.add_to_role_policy(bedrock_invoke)
        kb_bucket.grant_read_write(ingest_fn)

        # Trigger ingest on new doc upload
        kb_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(ingest_fn),
            s3.NotificationKeyFilter(suffix=".md"),
        )
        kb_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(ingest_fn),
            s3.NotificationKeyFilter(suffix=".txt"),
        )

        # ── HTTP API ──────────────────────────────────────────────────
        http_api = apigw.HttpApi(
            self,
            "HttpApi",
            api_name=f"{prefix}-api",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigw.CorsHttpMethod.POST, apigw.CorsHttpMethod.OPTIONS],
                allow_headers=["Content-Type", "Authorization"],
                max_age=Duration.hours(1),
            ),
        )

        http_api.add_routes(
            path="/chat",
            methods=[apigw.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration("ChatInt", chat_fn),
        )
        http_api.add_routes(
            path="/router",
            methods=[apigw.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration("RouterInt", router_fn),
        )
        http_api.add_routes(
            path="/contact",
            methods=[apigw.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration("ContactInt", contact_fn),
        )

        self.api_url = http_api.api_endpoint
        CfnOutput(self, "ApiUrl", value=self.api_url, description="Base URL for the HTTP API")
