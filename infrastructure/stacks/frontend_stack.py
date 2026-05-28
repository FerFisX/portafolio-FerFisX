"""
FrontendStack — S3 bucket + CloudFront distribution for the static site.

Design choices:
  - S3 with public access blocked; CloudFront uses Origin Access Identity.
  - CloudFront pricing class 100 (US/EU/CA only) keeps cost low.
  - Cache static assets aggressively, no cache for index.html (so deploys are immediate).
  - Inject API URL via build-time config injection (writes a small config.js).
"""

from pathlib import Path

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    CfnOutput,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cf,
    aws_cloudfront_origins as cf_origins,
)
from constructs import Construct


FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


class FrontendStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        prefix: str,
        api_url: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        site_bucket = s3.Bucket(
            self,
            "SiteBucket",
            bucket_name=f"{prefix}-site-{self.account}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        oai = cf.OriginAccessIdentity(self, "OAI")
        site_bucket.grant_read(oai)

        distribution = cf.Distribution(
            self,
            "SiteDist",
            default_root_object="index.html",
            default_behavior=cf.BehaviorOptions(
                origin=cf_origins.S3Origin(site_bucket, origin_access_identity=oai),
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cf.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
            ),
            additional_behaviors={
                "/index.html": cf.BehaviorOptions(
                    origin=cf_origins.S3Origin(site_bucket, origin_access_identity=oai),
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,
                )
            },
            price_class=cf.PriceClass.PRICE_CLASS_100,
            error_responses=[
                cf.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                )
            ],
        )

        # Deploy site contents. Generates a runtime config.js that injects API URL.
        config_js = f'window.__ADRIAN_API_URL__ = "{api_url}";'

        s3deploy.BucketDeployment(
            self,
            "DeploySite",
            sources=[
                s3deploy.Source.asset(str(FRONTEND_DIR)),
                s3deploy.Source.data("config.js", config_js),
            ],
            destination_bucket=site_bucket,
            distribution=distribution,
            distribution_paths=["/index.html", "/config.js"],
        )

        self.site_url = f"https://{distribution.distribution_domain_name}"
        CfnOutput(self, "SiteURL", value=self.site_url, description="Visit your portfolio here")
        CfnOutput(self, "DistributionId", value=distribution.distribution_id)
