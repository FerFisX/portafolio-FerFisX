# deploy.ps1 — Windows-friendly version of the deploy script.
# Usage:  .\scripts\deploy.ps1

$ErrorActionPreference = "Stop"

function Green($msg) { Write-Host $msg -ForegroundColor Green }
function Yellow($msg) { Write-Host $msg -ForegroundColor Yellow }
function Red($msg) { Write-Host $msg -ForegroundColor Red }

$Root = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $Root

# Prereqs
Green "▶ Checking prerequisites..."
foreach ($cmd in @("aws", "cdk", "python")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Red "$cmd not found in PATH"; exit 1
    }
}

$Account = (aws sts get-caller-identity --query Account --output text)
$Region = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }
Green "✓ AWS account: $Account · region: $Region"

# CDK deps
Green "▶ Installing CDK Python deps..."
Set-Location "$Root\infrastructure"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -q -r requirements.txt
Green "✓ Deps installed"

# Bootstrap
Green "▶ Bootstrapping CDK..."
cdk bootstrap "aws://$Account/$Region" | Out-Null
Green "✓ Bootstrapped"

# Diff
Yellow "▶ Showing diff:"
cdk diff

$ans = Read-Host "Continue with deploy? [y/N]"
if ($ans -notmatch "^[yY]") { Red "Aborted."; exit 0 }

# Deploy
Green "▶ Deploying all stacks (~10 min)..."
cdk deploy --all --require-approval never

# Outputs
$SiteUrl = aws cloudformation describe-stacks `
    --stack-name adrian-ai-frontend `
    --query 'Stacks[0].Outputs[?OutputKey==`SiteURL`].OutputValue' `
    --output text
$KbBucket = aws cloudformation describe-stacks `
    --stack-name adrian-ai-data `
    --query 'Stacks[0].Outputs[?OutputKey==`KBBucketName`].OutputValue' `
    --output text

# Upload KB
Set-Location $Root
Green "▶ Uploading knowledge base to s3://$KbBucket/ ..."
aws s3 cp backend/knowledge_base/ "s3://$KbBucket/" `
    --recursive --exclude "*" --include "*.md"

Green @"

═══════════════════════════════════════════════════
   Deploy completo
═══════════════════════════════════════════════════
   Sitio: $SiteUrl
   KB:    s3://$KbBucket/
═══════════════════════════════════════════════════
"@
