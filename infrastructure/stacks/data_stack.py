"""
DataStack — Persistent storage layer.

Resources:
  - DynamoDB table for chat sessions (TTL'd at 7 days)
  - S3 bucket for KB docs + numpy vector index (under `_index/`)

Cost notes:
  - DynamoDB on-demand: <$1/mes a esta escala.
  - S3: pennies/mes (<$0.10 con la KB completa).
  - Total: prácticamente $0 idle.

Trade-off vs OpenSearch Serverless:
  - Pierdo BM25 nativo (lo reemplazo con keyword scoring en memoria).
  - Pierdo escala (>50k chunks no entra en RAM Lambda).
  - Gano ~$350/mes de ahorro y latencia ~50ms más rápida en queries.
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_dynamodb as ddb,
    aws_s3 as s3,
)
from constructs import Construct


class DataStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, prefix: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── DynamoDB: chat sessions ────────────────────────────────────
        self.sessions_table = ddb.Table(
            self,
            "Sessions",
            table_name=f"{prefix}-sessions",
            partition_key=ddb.Attribute(name="session_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ── S3: Knowledge Base docs + index ────────────────────────────
        self.kb_bucket = s3.Bucket(
            self,
            "KBBucket",
            bucket_name=f"{prefix}-kb-{self.account}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            event_bridge_enabled=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ── Outputs ───────────────────────────────────────────────────
        CfnOutput(self, "SessionsTableName", value=self.sessions_table.table_name)
        CfnOutput(self, "KBBucketName", value=self.kb_bucket.bucket_name)
