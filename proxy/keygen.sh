#!/usr/bin/env bash
# keygen.sh — create a virtual key for a new paper-organizer user
#
# Usage:
#   ./keygen.sh <username> [monthly_budget_usd]
#
# Examples:
#   ./keygen.sh alice          # $2.00/month (default)
#   ./keygen.sh bob 5.0        # $5.00/month
#
# Required env vars:
#   LITELLM_MASTER_KEY   — your proxy master key
#   PROXY_URL            — e.g. https://your-proxy.up.railway.app

set -euo pipefail

PROXY_URL="${PROXY_URL:-https://your-proxy.up.railway.app}"
USER="${1:?Usage: $0 <username> [monthly_budget_usd]}"
BUDGET="${2:-2.0}"

if [[ -z "${LITELLM_MASTER_KEY:-}" ]]; then
  echo "Error: LITELLM_MASTER_KEY is not set." >&2
  exit 1
fi

echo "Generating virtual key for user '${USER}' with \$${BUDGET}/month budget..."
echo ""

curl -s -X POST "${PROXY_URL}/key/generate" \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"key_alias\": \"user_${USER}\",
    \"max_budget\": ${BUDGET},
    \"budget_duration\": \"monthly\",
    \"hard_budget_limit\": true,
    \"metadata\": {
      \"user\": \"${USER}\",
      \"team\": \"paper-organizer\",
      \"created_by\": \"keygen.sh\"
    }
  }" \
  | python3 -m json.tool

echo ""
echo "Share the 'key' value above with ${USER}."
echo "They use it as the API key against: ${PROXY_URL}"
