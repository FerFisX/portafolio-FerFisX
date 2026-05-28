#!/usr/bin/env python3
"""
CDK app — Adrian.AI portfolio infrastructure.

Stacks:
  - DataStack          → DynamoDB sessions table, S3 KB bucket (contains numpy index too)
  - ApiStack           → Lambda functions (chat, router, contact, ingest), API Gateway HTTP API
  - FrontendStack      → S3 static site, CloudFront distribution
  - WorkflowStack      → Step Functions state machine + EventBridge

Deploy:
    cd infrastructure
    pip install -r requirements.txt
    cdk bootstrap          # first time only
    cdk deploy --all
"""

import os
import aws_cdk as cdk

from stacks.data_stack import DataStack
from stacks.api_stack import ApiStack
from stacks.frontend_stack import FrontendStack
from stacks.workflow_stack import WorkflowStack


app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
)

PREFIX = app.node.try_get_context("prefix") or "adrian-ai"

# Layer 1: data
data = DataStack(app, f"{PREFIX}-data", env=env, prefix=PREFIX)

# Layer 2: api (consumes data)
api = ApiStack(
    app,
    f"{PREFIX}-api",
    env=env,
    prefix=PREFIX,
    sessions_table=data.sessions_table,
    kb_bucket=data.kb_bucket,
)

# Layer 3: workflow (independent)
workflow = WorkflowStack(app, f"{PREFIX}-workflow", env=env, prefix=PREFIX)

# Layer 4: frontend (knows about api for env injection)
frontend = FrontendStack(
    app,
    f"{PREFIX}-frontend",
    env=env,
    prefix=PREFIX,
    api_url=api.api_url,
)

for stack in [data, api, frontend, workflow]:
    cdk.Tags.of(stack).add("project", "adrian-ai-portfolio")
    cdk.Tags.of(stack).add("owner", "adrian")
    cdk.Tags.of(stack).add("env", os.environ.get("CDK_ENV", "prod"))

app.synth()
