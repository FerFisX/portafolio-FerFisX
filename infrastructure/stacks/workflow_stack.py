"""
WorkflowStack — Step Functions + EventBridge demo.

This is the "n8n / Make" equivalent built natively on AWS.

State machine flow:
  1. Receive event (webhook or EventBridge).
  2. Lambda extracts structured data with LLM (entity extraction).
  3. Conditional branch by confidence score (route to ops/compliance/human-review).
  4. Notify Slack channel.

The state machine definition lives in backend/lambdas/workflow/step_definition.json
and CDK substitutes ${...} placeholders with the real ARNs.
"""

import json
from pathlib import Path

from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
)
from constructs import Construct


LAMBDA_ROOT = Path(__file__).parent.parent.parent / "backend" / "lambdas"
STEP_DEF = LAMBDA_ROOT / "workflow" / "step_definition.json"


class WorkflowStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, prefix: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Lambda: extraction with LLM
        extract_fn = lambda_.Function(
            self,
            "ExtractFn",
            function_name=f"{prefix}-extract",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="workflow.extract_lambda.lambda_handler",
            code=lambda_.Code.from_asset(str(LAMBDA_ROOT)),
            timeout=Duration.seconds(30),
            memory_size=1024,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )
        extract_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[f"arn:aws:bedrock:{self.region}::foundation-model/*"],
            )
        )

        # Lambda: stub for Slack notifications (replace with real webhook in prod)
        slack_fn = lambda_.Function(
            self,
            "SlackFn",
            function_name=f"{prefix}-slack-notify",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline(
                "import json\n"
                "def handler(event, context):\n"
                "    print('SLACK NOTIFY:', json.dumps(event))\n"
                "    # In prod: requests.post(SLACK_WEBHOOK_URL, json={...})\n"
                "    return {'ok': True, 'event': event}\n"
            ),
            timeout=Duration.seconds(10),
            memory_size=256,
        )

        # Load and substitute the state machine definition
        definition_raw = STEP_DEF.read_text(encoding="utf-8")
        definition_str = (
            definition_raw
            .replace("${EXTRACT_LAMBDA_ARN}", extract_fn.function_arn)
            .replace("${SLACK_LAMBDA_ARN}", slack_fn.function_arn)
        )

        # Validate JSON
        json.loads(definition_str)

        # Role for the state machine
        sfn_role = iam.Role(
            self,
            "SfnRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
        )
        extract_fn.grant_invoke(sfn_role)
        slack_fn.grant_invoke(sfn_role)

        state_machine = sfn.CfnStateMachine(
            self,
            "ExtractWorkflow",
            state_machine_name=f"{prefix}-extract-workflow",
            definition_string=definition_str,
            role_arn=sfn_role.role_arn,
            state_machine_type="STANDARD",
            logging_configuration=sfn.CfnStateMachine.LoggingConfigurationProperty(
                level="ALL",
                include_execution_data=True,
                destinations=[
                    sfn.CfnStateMachine.LogDestinationProperty(
                        cloud_watch_logs_log_group=sfn.CfnStateMachine.CloudWatchLogsLogGroupProperty(
                            log_group_arn=logs.LogGroup(
                                self,
                                "SfnLogs",
                                log_group_name=f"/aws/vendedlogs/states/{prefix}-extract",
                                retention=logs.RetentionDays.ONE_MONTH,
                            ).log_group_arn,
                        )
                    )
                ],
            ),
        )

        # EventBridge rule — triggers workflow on a custom event bus
        bus = events.EventBus(self, "EventBus", event_bus_name=f"{prefix}-events")
        events.Rule(
            self,
            "OnTransactionEvent",
            event_bus=bus,
            event_pattern=events.EventPattern(
                source=["meru.transactions"],
                detail_type=["TransactionRecorded"],
            ),
            targets=[targets.SfnStateMachine(
                sfn.StateMachine.from_state_machine_arn(self, "ImportedSm", state_machine.attr_arn)
            )],
        )

        CfnOutput(self, "StateMachineArn", value=state_machine.attr_arn)
        CfnOutput(self, "EventBusName", value=bus.event_bus_name)
