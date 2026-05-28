#!/usr/bin/env bash
#
# deploy.sh — One-shot bootstrap + deploy script.
#
# Usage:  ./scripts/deploy.sh
#
# Steps:
#   1. Verify prereqs (aws cli, cdk, python)
#   2. Install CDK deps
#   3. Synth + diff (so you see what's coming)
#   4. Deploy all stacks
#   5. Upload KB docs (triggers ingest)
#   6. Print site URL

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

green() { printf '\033[0;32m%s\033[0m\n' "$1"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$1"; }
red() { printf '\033[0;31m%s\033[0m\n' "$1"; }

# ── Prereqs ────────────────────────────────────────────────
green "▶ Checking prerequisites..."
command -v aws >/dev/null || { red "aws CLI missing"; exit 1; }
command -v cdk >/dev/null || { red "cdk CLI missing (npm install -g aws-cdk)"; exit 1; }
command -v python3 >/dev/null || { red "python3 missing"; exit 1; }

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-us-east-1}
green "✓ AWS account: $ACCOUNT · region: $REGION"

# ── CDK deps ──────────────────────────────────────────────
green "▶ Installing CDK Python deps..."
cd infrastructure
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
green "✓ Deps installed"

# ── Bootstrap (idempotent) ────────────────────────────────
green "▶ Bootstrapping CDK in $REGION..."
cdk bootstrap "aws://$ACCOUNT/$REGION" >/dev/null
green "✓ Bootstrapped"

# ── Diff + deploy ─────────────────────────────────────────
yellow "▶ Showing diff (review carefully):"
cdk diff || true

read -r -p "Continue with deploy? [y/N] " ans
case "$ans" in
    [yY]*) ;;
    *) red "Aborted."; exit 0 ;;
esac

green "▶ Deploying all stacks (~10 min)..."
cdk deploy --all --require-approval never

# ── Capture outputs ───────────────────────────────────────
OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name adrian-ai-frontend \
    --query 'Stacks[0].Outputs[?OutputKey==`SiteURL`].OutputValue' \
    --output text)
KB_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name adrian-ai-data \
    --query 'Stacks[0].Outputs[?OutputKey==`KBBucketName`].OutputValue' \
    --output text)

# ── Upload KB ─────────────────────────────────────────────
cd "$ROOT"
green "▶ Uploading knowledge base to s3://$KB_BUCKET/ ..."
aws s3 cp backend/knowledge_base/ "s3://$KB_BUCKET/" \
    --recursive --exclude "*" --include "*.md"
green "✓ KB uploaded — ingest Lambdas processing in background"

# ── Done ──────────────────────────────────────────────────
green "
═══════════════════════════════════════════════════
   Deploy completo
═══════════════════════════════════════════════════
   Sitio: $OUTPUTS
   KB:    s3://$KB_BUCKET/
═══════════════════════════════════════════════════
"
