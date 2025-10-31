# Valro Lambda Backend

Serverless API backend for the Valro home services concierge with asynchronous agent processing.

## Architecture

**Asynchronous Processing Pattern:**

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│ API Gateway │─────▶│  API Lambda  │─────▶│   DynamoDB      │
│             │      │  (30s)       │      │  (valro-tasks)  │
└─────────────┘      └──────────────┘      └─────────────────┘
                             │
                             │ Async Invoke
                             ▼
                      ┌──────────────┐      ┌─────────────────┐
                      │Worker Lambda │─────▶│  AgentCore      │
                      │  (10 min)    │      │  Runtime        │
                      └──────────────┘      └─────────────────┘
                             │
                             ▼
                      ┌─────────────────┐
                      │   DynamoDB      │
                      │  (update status)│
                      └─────────────────┘
```

### Components

1. **API Lambda** (`lambda_function.py`):
   - Handles HTTP API requests
   - Creates tasks in DynamoDB
   - Invokes Worker Lambda asynchronously
   - Returns immediately (202 Accepted)
   - Timeout: 30 seconds

2. **Worker Lambda** (`worker_lambda.py`):
   - Processes long-running agent invocations
   - Updates task status in DynamoDB
   - Handles agent responses and errors
   - Timeout: 10 minutes

3. **DynamoDB** (`valro-tasks` table):
   - Persistent task storage
   - Status tracking (pending → processing → completed/error)
   - Event timeline for each task

4. **Shared Module** (`dynamodb_helpers.py`):
   - Common DynamoDB operations
   - Used by both Lambdas

### Tech Stack

- **Runtime**: Python 3.11+
- **AWS Services**: Lambda, API Gateway HTTP API, DynamoDB, Bedrock AgentCore
- **Storage**: DynamoDB (persistent, scalable)

## API Endpoints

### POST /tasks
Create a new home service task and start async processing.

**Request:**
```json
{
  "description": "Find me a landscaper in Charlotte under $300"
}
```

**Response (202 Accepted):**
```json
{
  "id": "uuid-here",
  "status": "pending",
  "message": "Task created and processing started"
}
```

**Behavior:**
- Creates task in DynamoDB with status `pending`
- Invokes Worker Lambda asynchronously
- Returns immediately with HTTP 202 (Accepted)
- Frontend should poll `GET /tasks/{id}` for status updates

### GET /tasks
List all tasks (sorted by newest first).

**Response:**
```json
[
  {
    "id": "uuid",
    "description": "Find me a landscaper...",
    "status": "completed",
    "vendors": [],
    "quotes": [],
    "events": [...],
    "created_at": "2025-10-31T...",
    "updated_at": "2025-10-31T..."
  }
]
```

### GET /tasks/{id}
Get details for a specific task (used for polling).

**Response:**
```json
{
  "id": "uuid",
  "description": "Find me a landscaper...",
  "status": "completed",
  "agent_response": "I've contacted 3 landscaping vendors...",
  "vendors": [],
  "quotes": [],
  "emails_sent": 3,
  "events": [
    {"ts": "...", "message": "Task created", "type": "info"},
    {"ts": "...", "message": "Worker Lambda invoked - processing started", "type": "info"},
    {"ts": "...", "message": "Agent processing started", "type": "info"},
    {"ts": "...", "message": "Agent completed task successfully", "type": "success"}
  ],
  "created_at": "2025-10-31T...",
  "updated_at": "2025-10-31T..."
}
```

**Status Flow:**
- `pending` → Task created, worker not started yet
- `processing` → Worker Lambda is invoking the agent
- `completed` → Agent finished successfully
- `error` → An error occurred (check `error_message` field)

## Deployment

### Prerequisites

1. AWS CLI configured with appropriate credentials
2. AgentCore agent deployed (you'll need the ARN)
3. Python 3.11+ installed locally (for packaging)
4. Appropriate AWS permissions to create:
   - DynamoDB tables
   - Lambda functions
   - IAM roles and policies

### Automated Deployment (Recommended)

The fastest way to deploy the entire infrastructure:

```bash
# Package both Lambda functions
./deploy.sh

# Create all infrastructure (DynamoDB, IAM roles, Lambdas)
./create-infrastructure.sh
```

The script will prompt you for your AgentCore Runtime ARN and automatically:
- Create DynamoDB table (`valro-tasks`)
- Create IAM roles with appropriate permissions
- Deploy both API and Worker Lambda functions
- Configure all environment variables

### Manual Deployment

If you prefer manual control:

#### Step 1: Package Lambda functions

```bash
./deploy.sh
```

This creates:
- `valro-api-lambda.zip` (API Lambda)
- `valro-worker-lambda.zip` (Worker Lambda)

#### Step 2: Create DynamoDB table

```bash
aws dynamodb create-table \
  --table-name valro-tasks \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

#### Step 3: Create IAM Roles

**Worker Lambda Role:**
```bash
# Create trust policy
cat > /tmp/lambda-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create role
aws iam create-role \
  --role-name valro-worker-role \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json

# Attach policy
aws iam put-role-policy \
  --role-name valro-worker-role \
  --policy-name ValroWorkerPolicy \
  --policy-document file://worker-iam-policy.json
```

**API Lambda Role:**
```bash
aws iam create-role \
  --role-name valro-lambda-role \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json

aws iam put-role-policy \
  --role-name valro-lambda-role \
  --policy-name ValroAPIPolicy \
  --policy-document file://iam-policy.json
```

#### Step 4: Deploy Lambda Functions

**Worker Lambda:**
```bash
aws lambda create-function \
  --function-name valro-worker \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/valro-worker-role \
  --handler worker_lambda.lambda_handler \
  --zip-file fileb://valro-worker-lambda.zip \
  --timeout 600 \
  --memory-size 1024 \
  --environment Variables='{
    DYNAMODB_TABLE_NAME=valro-tasks,
    AGENT_RUNTIME_ARN=YOUR_AGENT_ARN,
    AWS_REGION=us-east-1
  }'
```

**API Lambda:**
```bash
aws lambda create-function \
  --function-name valro-backend \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/valro-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://valro-api-lambda.zip \
  --timeout 30 \
  --memory-size 512 \
  --environment Variables='{
    DYNAMODB_TABLE_NAME=valro-tasks,
    WORKER_LAMBDA_ARN=arn:aws:lambda:REGION:ACCOUNT:function:valro-worker,
    AWS_REGION=us-east-1
  }'
```

### Create API Gateway

```bash
# Create HTTP API
aws apigatewayv2 create-api \
  --name valro-api \
  --protocol-type HTTP \
  --cors-configuration AllowOrigins="*",AllowMethods="GET,POST,OPTIONS",AllowHeaders="*"

# Get API ID from output, then create integration
aws apigatewayv2 create-integration \
  --api-id YOUR_API_ID \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:us-east-1:ACCOUNT_ID:function:valro-backend \
  --payload-format-version 2.0

# Create routes
aws apigatewayv2 create-route \
  --api-id YOUR_API_ID \
  --route-key "POST /tasks" \
  --target integrations/YOUR_INTEGRATION_ID

aws apigatewayv2 create-route \
  --api-id YOUR_API_ID \
  --route-key "GET /tasks" \
  --target integrations/YOUR_INTEGRATION_ID

aws apigatewayv2 create-route \
  --api-id YOUR_API_ID \
  --route-key "GET /tasks/{id}" \
  --target integrations/YOUR_INTEGRATION_ID

# Create default stage
aws apigatewayv2 create-stage \
  --api-id YOUR_API_ID \
  --stage-name '$default' \
  --auto-deploy
```

Your API will be available at: `https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com`

### Updating Existing Deployment

To update existing Lambda functions after code changes:

```bash
# Package new code
./deploy.sh

# Update both functions
aws lambda update-function-code \
  --function-name valro-backend \
  --zip-file fileb://valro-api-lambda.zip

aws lambda update-function-code \
  --function-name valro-worker \
  --zip-file fileb://valro-worker-lambda.zip
```

Or use the automated script which handles updates:
```bash
./create-infrastructure.sh
```

## Environment Variables

### API Lambda (`valro-backend`)
- `DYNAMODB_TABLE_NAME`: Name of the DynamoDB table (default: `valro-tasks`)
- `WORKER_LAMBDA_ARN`: Full ARN of the Worker Lambda function
- `AWS_REGION`: AWS region (default: `us-east-1`)

### Worker Lambda (`valro-worker`)
- `DYNAMODB_TABLE_NAME`: Name of the DynamoDB table (default: `valro-tasks`)
- `AGENT_RUNTIME_ARN`: Full ARN of the AgentCore runtime
- `AWS_REGION`: AWS region (default: `us-east-1`)

## Local Testing

### Test API Lambda

```bash
# Test locally (requires AWS credentials and DynamoDB setup)
python lambda_function.py
```

Or invoke the deployed Lambda directly:

```bash
aws lambda invoke \
  --function-name valro-backend \
  --payload '{"httpMethod":"GET","path":"/tasks"}' \
  /tmp/response.json && cat /tmp/response.json
```

### Test Worker Lambda

```bash
# Test worker directly with a task ID
aws lambda invoke \
  --function-name valro-worker \
  --payload '{"task_id":"test-123","description":"Find me a painter"}' \
  /tmp/worker-response.json && cat /tmp/worker-response.json
```

## Monitoring

### View Lambda Logs

**API Lambda:**
```bash
aws logs tail /aws/lambda/valro-backend --follow
```

**Worker Lambda:**
```bash
aws logs tail /aws/lambda/valro-worker --follow
```

**Both simultaneously:**
```bash
# In separate terminal windows
aws logs tail /aws/lambda/valro-backend --follow
aws logs tail /aws/lambda/valro-worker --follow
```

### Check DynamoDB

```bash
# Get a specific task
aws dynamodb get-item \
  --table-name valro-tasks \
  --key '{"id": {"S": "YOUR_TASK_ID"}}'

# Scan all tasks (limit 10)
aws dynamodb scan \
  --table-name valro-tasks \
  --max-items 10
```

### Monitor Lambda Metrics

```bash
# API Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=valro-backend \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Worker Lambda duration
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=valro-worker \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

## Troubleshooting

### API Lambda Issues

**Error: "WORKER_LAMBDA_ARN not set"**
- Set the `WORKER_LAMBDA_ARN` environment variable in API Lambda configuration
- Should be: `arn:aws:lambda:REGION:ACCOUNT:function:valro-worker`

**Error: "Task not found in DynamoDB"**
- Verify DynamoDB table exists and is named correctly
- Check `DYNAMODB_TABLE_NAME` environment variable
- Ensure API Lambda has DynamoDB permissions in IAM policy

**Error: "Access Denied" when invoking Worker Lambda**
- Check API Lambda IAM role has `lambda:InvokeFunction` permission
- Verify the Worker Lambda ARN in environment variables

### Worker Lambda Issues

**Error: "AGENT_RUNTIME_ARN not set"**
- Set the environment variable in Worker Lambda configuration

**Error: "Access Denied" when invoking agent**
- Check Worker Lambda IAM role has `bedrock-agentcore:InvokeAgentRuntime` permission
- Verify the agent ARN is correct and agent is deployed

**Tasks stuck in "pending" status**
- Check Worker Lambda logs for errors
- Verify Worker Lambda was invoked (check CloudWatch logs)
- Check if Worker Lambda has DynamoDB UpdateItem permissions

**Worker Lambda timing out**
- Increase Worker Lambda timeout (currently 600s/10min)
- Check if AgentCore agent is responding
- Review agent logs for performance issues

### Frontend Issues

**CORS errors in browser**
- Verify API Gateway has CORS enabled
- Check API Lambda response includes CORS headers
- Ensure frontend is using correct API Gateway URL

**Tasks not updating**
- Frontend should poll GET /tasks/{id} every few seconds
- Check that status transitions from pending → processing → completed
- Verify events array shows progress

### General Debugging

1. **Check the full flow:**
   ```bash
   # Create a task
   TASK_RESPONSE=$(curl -X POST https://YOUR_API.execute-api.us-east-1.amazonaws.com/tasks \
     -H "Content-Type: application/json" \
     -d '{"description": "Test task"}')

   TASK_ID=$(echo $TASK_RESPONSE | jq -r '.id')

   # Poll for status
   watch -n 2 "curl -s https://YOUR_API.execute-api.us-east-1.amazonaws.com/tasks/$TASK_ID | jq ."
   ```

2. **Check CloudWatch Logs** for both Lambdas

3. **Verify DynamoDB** has the task and shows status updates

4. **Check IAM permissions** for both Lambda roles
