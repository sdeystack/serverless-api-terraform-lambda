#!/usr/bin/env bash
# Smoke test for the deployed serverless API.
# Usage:
#   export API_ENDPOINT="https://<api-id>.execute-api.<region>.amazonaws.com"
#   bash scripts/smoke-test.sh
# Requires: curl and python3 (used to parse JSON, so jq is not required).
set -euo pipefail

if [ -z "${API_ENDPOINT:-}" ]; then
  echo "API_ENDPOINT is not set."
  echo "Set it from: terraform output -raw api_endpoint"
  echo "Example: export API_ENDPOINT=\"https://abc123.execute-api.us-east-1.amazonaws.com\""
  exit 1
fi

API_ENDPOINT="${API_ENDPOINT%/}"
echo "Testing: $API_ENDPOINT"

echo ""
echo "1) POST /items (expect 201)"
CREATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_ENDPOINT/items" \
  -H "Content-Type: application/json" \
  -d '{"name": "Smoke test item", "description": "Created by scripts/smoke-test.sh"}')
CREATE_BODY=$(echo "$CREATE_RESPONSE" | head -n -1)
CREATE_CODE=$(echo "$CREATE_RESPONSE" | tail -n 1)
echo "$CREATE_BODY"
echo "Status: $CREATE_CODE"
if [ "$CREATE_CODE" != "201" ]; then
  echo "FAIL: expected 201 for POST /items"
  exit 1
fi

ITEM_ID=$(echo "$CREATE_BODY" | python3 -c "import json,sys; print(json.load(sys.stdin)['item']['id'])")
echo "Created id: $ITEM_ID"

echo ""
echo "2) GET /items (expect 200)"
curl -s -w "\nStatus: %{http_code}\n" "$API_ENDPOINT/items"

echo ""
echo "3) GET /items/$ITEM_ID (expect 200)"
curl -s -w "\nStatus: %{http_code}\n" "$API_ENDPOINT/items/$ITEM_ID"

echo ""
echo "4) POST /items with missing name (expect 400)"
curl -s -w "\nStatus: %{http_code}\n" -X POST "$API_ENDPOINT/items" \
  -H "Content-Type: application/json" \
  -d '{"description": "missing name"}'

echo ""
echo "5) DELETE /items/$ITEM_ID (expect 200)"
curl -s -w "\nStatus: %{http_code}\n" -X DELETE "$API_ENDPOINT/items/$ITEM_ID"

echo ""
echo "6) GET /items/$ITEM_ID after delete (expect 404)"
curl -s -w "\nStatus: %{http_code}\n" "$API_ENDPOINT/items/$ITEM_ID"

echo ""
echo "Smoke test finished. Check CloudWatch logs for the Lambda invocations."
