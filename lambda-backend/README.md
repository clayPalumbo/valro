# Valro Lambda Backend

Serverless API backend for the Valro home services concierge POC.

## Architecture

- **Runtime**: Python 3.11+
- **AWS Services**: Lambda, API Gateway HTTP API, Bedrock AgentCore
- **Storage**: In-memory (for POC) - ready for DynamoDB migration

## API Endpoints

### POST /tasks
Create a new home service task.

**Request:**
```json
{
  "description": "Find me a landscaper in Charlotte under $300"
}
```

**Response:**
```json
{
  "id": "uuid-here",
  "status": "processing",
  "message": "Task created successfully"
}
```

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
Get details for a specific task.

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
    {"ts": "...", "message": "Agent invoked successfully", "type": "info"},
    {"ts": "...", "message": "Agent completed task", "type": "success"}
  ],
  "created_at": "2025-10-31T...",
  "updated_at": "2025-10-31T..."
}
```

## Deployment

### Prerequisites

1. AWS CLI configured
2. IAM role with permissions (see `iam-policy.json`)
3. AgentCore agent deployed (ARN required)

### Quick Deploy

```bash
# Package the Lambda
./deploy.sh

# Create Lambda function
aws lambda create-function \
  --function-name valro-backend \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/valro-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://valro-lambda.zip \
  --timeout 60 \
  --memory-size 512 \
  --environment Variables='{
    AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:975150127262:runtime/home_owner_concierge-tBcmf45NFO,
    AWS_REGION=us-east-1
  }'
```

### Create IAM Role

```bash
# Create the role
aws iam create-role \
  --role-name valro-lambda-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach the policy
aws iam put-role-policy \
  --role-name valro-lambda-role \
  --policy-name ValroLambdaPolicy \
  --policy-document file://iam-policy.json
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

## Local Testing

```python
# Test the Lambda locally
python lambda_function.py
```

Or test with sample events:

```bash
# Create task
python -c "
import json
from lambda_function import lambda_handler

event = {
    'httpMethod': 'POST',
    'path': '/tasks',
    'body': json.dumps({'description': 'Find a painter in Charlotte under $500'})
}

result = lambda_handler(event, None)
print(json.dumps(result, indent=2))
"
```

## Environment Variables

- `AGENT_RUNTIME_ARN`: Full ARN of the AgentCore runtime (required)
- `AWS_REGION`: AWS region (default: us-east-1)

## Migrating to DynamoDB

To make this production-ready, replace the in-memory `TASKS` dict with DynamoDB:

1. Create a DynamoDB table:
   ```bash
   aws dynamodb create-table \
     --table-name valro-tasks \
     --attribute-definitions \
       AttributeName=id,AttributeType=S \
     --key-schema AttributeName=id,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST
   ```

2. Update Lambda code to use `boto3.resource('dynamodb')`:
   ```python
   dynamodb = boto3.resource('dynamodb')
   table = dynamodb.Table('valro-tasks')

   # Replace TASKS[task_id] = task with:
   table.put_item(Item=task)

   # Replace TASKS.get(task_id) with:
   response = table.get_item(Key={'id': task_id})
   task = response.get('Item')
   ```

3. Add DynamoDB permissions to IAM policy

## Monitoring

View Lambda logs:
```bash
aws logs tail /aws/lambda/valro-backend --follow
```

## Troubleshooting

**Error: "AGENT_RUNTIME_ARN not set"**
- Set the environment variable in Lambda configuration

**Error: "Access Denied" when invoking agent**
- Check IAM role has `bedrock-agentcore:InvokeAgentRuntime` permission
- Verify the agent ARN is correct

**CORS errors in browser**
- Verify API Gateway has CORS enabled
- Check Lambda response includes CORS headers
