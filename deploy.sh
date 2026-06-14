#!/usr/bin/env bash
# Deploy Cuckoo Chat to AWS:
#   backend  -> Lambda (FastAPI via Web Adapter, streaming Function URL)
#   frontend -> S3, served through CloudFront (which also routes /api/* to Lambda)
#
# Requires: aws cli (configured), sam cli, node/npm, and Docker — Docker is used
# ONLY by `sam build --use-container` to compile native deps (pydantic-core,
# uvloop, ...) for Lambda's arm64 Linux. Day-to-day local dev needs no Docker.
#
# Usage:  ./deploy.sh          (reads secrets from backend/.env)
# Env overrides: STACK_NAME, AWS_REGION, LWA_LAYER_ARN
set -euo pipefail
cd "$(dirname "$0")"

STACK_NAME="${STACK_NAME:-cuckoo-chat}"
REGION="${AWS_REGION:-us-east-1}"

# Load OPENROUTER_* from backend/.env if present.
if [ -f backend/.env ]; then
  set -a; . ./backend/.env; set +a
fi
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY (in backend/.env or the environment)}"
OPENROUTER_MODEL="${OPENROUTER_MODEL:-google/gemma-4-31b-it:free}"

PARAM_OVERRIDES=(OpenRouterApiKey="$OPENROUTER_API_KEY" OpenRouterModel="$OPENROUTER_MODEL")
[ -n "${LWA_LAYER_ARN:-}" ] && PARAM_OVERRIDES+=(LwaLayerArn="$LWA_LAYER_ARN")

echo "==> Building backend (sam build --use-container)…"
sam build --use-container -t infra/template.yaml

echo "==> Deploying stack '$STACK_NAME' to $REGION…"
sam deploy \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --no-confirm-changeset \
  --parameter-overrides "${PARAM_OVERRIDES[@]}"

echo "==> Reading stack outputs…"
get_output () {
  aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
BUCKET="$(get_output SiteBucket)"
DIST_ID="$(get_output DistributionId)"
CF_URL="$(get_output CloudFrontUrl)"
API_URL="$(get_output FunctionUrl)"; API_URL="${API_URL%/}"   # drop trailing slash

echo "==> Building frontend (API base: $API_URL)…"
( cd frontend && npm install && VITE_API_BASE_URL="$API_URL" npm run build )

echo "==> Syncing frontend to s3://$BUCKET …"
aws s3 sync frontend/dist "s3://$BUCKET" --delete --region "$REGION"

echo "==> Invalidating CloudFront cache…"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths '/*' >/dev/null

echo ""
echo "✅ Deployed:  $CF_URL"
