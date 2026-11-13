# Serverless Items API — Lambda + Terraform + DynamoDB

Personal lab project. Built to demonstrate hands-on AWS Lambda, Terraform, API Gateway, DynamoDB, IAM, and CloudWatch for Intermediate Cloud / DevOps roles. This is lab work, not production work, and it uses no customer data.

## What it does

A small JSON API for items, with one Lambda function behind API Gateway HTTP API and one DynamoDB table:

- `POST /items` — create an item (`name` required, `description` optional)
- `GET /items` — list items, sorted by creation time
- `GET /items/{id}` — get one item, or 404
- `DELETE /items/{id}` — delete one item, or 404 if it does not exist

The handler validates input, returns structured JSON errors (400 / 404 / 500), logs failures to CloudWatch without leaking internal details, and uses a least-privilege IAM role that can only write its own logs and use this one table.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the diagram and trade-offs.

## Architecture (summary)

```
curl / client
  -> API Gateway HTTP API ($default stage, payload 2.0)
  -> Lambda (Python 3.12, handler.lambda_handler)
  -> DynamoDB (PAY_PER_REQUEST, hash key: id)
  -> CloudWatch Logs + Lambda Errors alarm
```

Everything is deployed with Terraform. No click-ops. Terraform state is local for this first project on purpose; remote state with locking is Project 2.

## Prerequisites

- A personal AWS account (never a work account), with MFA on root and a billing alarm set
- Git, Python 3.11+, AWS CLI v2, Terraform 1.5+
- AWS CLI configured for your personal account and one region, for example `us-east-1`:

```bash
aws sts get-caller-identity
```

Confirm that command shows your personal lab account before deploying anything. Never commit AWS keys.

## Run the tests (no AWS needed)

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Tests mock DynamoDB, so they run without credentials or network access. GitHub Actions also runs them on every push (see `.github/workflows/test.yml`). CI runs tests only; deploys are manual from your laptop for this lab.

## Deploy

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Review the plan before applying. After apply, note the outputs:

```bash
terraform output api_endpoint
terraform output lambda_function_name
terraform output dynamodb_table_name
```

## Verify it works

Set the endpoint from the Terraform output, then run the smoke test:

```bash
export API_ENDPOINT="https://<api-id>.execute-api.<region>.amazonaws.com"
bash ../scripts/smoke-test.sh
```

Or run the calls by hand:

```bash
# Create
curl -s -X POST "$API_ENDPOINT/items" \
  -H "Content-Type: application/json" \
  -d '{"name": "Widget", "description": "First item"}'

# List (copy the id from the create response for the next calls)
curl -s "$API_ENDPOINT/items"

# Get one
curl -s "$API_ENDPOINT/items/<id>"

# Bad input: expect 400 with a JSON error
curl -s -X POST "$API_ENDPOINT/items" \
  -H "Content-Type: application/json" \
  -d '{"description": "missing name"}'

# Delete
curl -s -X DELETE "$API_ENDPOINT/items/<id>"
```

Check logs and metrics:

```bash
aws logs tail "/aws/lambda/$(terraform output -raw lambda_function_name)" --follow
aws cloudwatch describe-alarms --alarm-names "$(terraform output -raw lambda_error_alarm_name)"
```

### My verification run
- Date and region: Nov 13, 2026, us-east-1
- `terraform apply` result: 17 resources created. First apply created 16/17; the $default stage failed because the access-log format used `$context.http.*` variables, which API Gateway rejected. Fixed the format to `$context.httpMethod`, `$context.path`, `$context.status` and re-applied; stage created, 1 added, 0 changed, 0 destroyed.
- Smoke test / curl result: pytest 11 passed. Live: POST created an item (201), GET list showed count 1, GET one returned the item, DELETE returned deleted true, GET one after delete returned 404 Item not found, GET list returned count 0. POST via curl.exe first failed with "Request body must be valid JSON" because PowerShell stripped the quotes; used Invoke-RestMethod instead.
- CloudWatch log line seen: not captured before destroy.


## Destroy

```bash
cd terraform
terraform destroy
```

Confirm the destroy completes, then check Cost Explorer. Do not leave resources running after your demo.

## Failure handling

- Invalid JSON, missing body, or invalid `name`/`description` returns 400 with a JSON `{"error": "..."}` message and does not touch DynamoDB.
- Unknown routes return 404.
- Getting or deleting a missing item returns 404. Delete uses a conditional expression (`attribute_exists(id)`) so a missing item is not reported as deleted.
- DynamoDB errors are logged with a stack trace in CloudWatch and return a generic 500 message. Internal error details are never sent to the caller.
- The Lambda Errors CloudWatch alarm fires if Errors > 0 in 5 minutes. No SNS action is wired up in this lab; that is a deliberate scope limit, noted in `terraform/alarms.tf`.

## Cost notes
- Observed cost for my test run: $10.00 as of Nov 13, 2026 (Cost Explorer; spend data can lag up to 24 hours)
- How I checked Cost Explorer / Budgets page for Lab-Monthly-10-USD


## Trade-offs and what I learned
- Why HTTP API instead of REST API: cheaper and simpler; this lab needs no usage plans, API keys, or WAF features that REST adds.
- Why `Scan` is acceptable for this small lab list endpoint, and what would replace it at scale: the table holds a handful of items; at scale I would Query on a key or GSI and paginate instead of scanning.
- Why local Terraform state is acceptable here, and what Project 2 changes: single user, single environment, short-lived lab. Project 2 moves state to an S3 backend with DynamoDB locking.
- What broke during my build/deploy, and how I debugged it: (1) access-log variables rejected by API Gateway, checked the AWS error and docs, fixed the three variable names; (2) PowerShell mangled JSON passed to curl.exe, switched the POST to Invoke-RestMethod; (3) aws.cmd launcher picked the wrong Python, a known awscli bug, bypassed with `py -3.12` and a session function; (4) first re-apply failed identically because the file edit hadn't been saved, patched via PowerShell and verified the file contents before re-applying. Also used AWS CLI v1 (pip) because the v2 MSI install was blocked by organization policy on this laptop.
- What I would change next: remote state with locking, an SNS action on the Errors alarm, auth on the API, and pagination on the list endpoint.

## Repo layout

```
lambda/           handler.py (deployed code only)
tests/            pytest unit tests with a mocked DynamoDB table
terraform/        versions, variables, DynamoDB, IAM, Lambda, API Gateway, alarms, outputs
scripts/          smoke-test.sh for live verification
.github/workflows/ CI: run pytest on push
```

## Safety

- Personal AWS account only. Billing alarm on. Destroy after demo.
- No secrets in git. No `.tfstate` files in git. See `.gitignore`.
- The Lambda role is least-privilege for this table and its own logs only. Your Terraform deploy identity in your personal lab account is separate from the Lambda execution role.
