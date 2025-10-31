# Valro Deployment Guide

Complete end-to-end deployment instructions for the Valro home services concierge POC.

## Architecture Overview

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│ React UI    │─────▶│ API Gateway  │─────▶│ Lambda Backend  │
│ (Amplify/   │      │ (HTTP API)   │      │ (Python 3.11)   │
│  S3+CF)     │      └──────────────┘      └─────────────────┘
└─────────────┘                                      │
                                                     ▼
                                          ┌─────────────────┐
                                          │ AgentCore       │
                                          │ Runtime         │
                                          │ (Strands Agent) │
                                          └─────────────────┘
```

## Prerequisites

Before deploying, ensure you have:

- ✅ AWS CLI configured with appropriate credentials
- ✅ AWS account with permissions for:
  - Lambda, API Gateway, IAM, S3, Amplify (or CloudFront)
  - Bedrock AgentCore services
- ✅ Node.js 18+ installed (for frontend)
- ✅ Python 3.11+ installed (for agent/lambda)
- ✅ Git repository (for Amplify deployment)

## Deployment Steps

### Phase 1: Deploy AgentCore Agent

The agent code is already created in `agentcore-basic-demo/agent-code/basic_agent.py`.

#### Option A: Using AgentCore CLI (Recommended)

```bash
# Navigate to agent directory
cd agentcore-basic-demo/agent-code

# If agentcore CLI is not installed, install it
pip install bedrock-agentcore-starter-toolkit

# Configure the agent (if not already done)
agentcore configure \
  --entrypoint basic_agent.py \
  --name home_owner_concierge \
  --region us-east-1

# Launch/update the agent to AWS
agentcore launch

# Get the agent runtime ARN (save this for Lambda)
agentcore status --verbose
```

**Save the output:**
- Agent Runtime ARN: `arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/home_owner_concierge-XXXXX`

#### Option B: Manual Docker Deployment

If AgentCore CLI doesn't work:

```bash
# Build Docker image
cd agentcore-basic-demo/agent-code
docker build -t valro-agent .

# Push to ECR (requires ECR repository)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
docker tag valro-agent:latest ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/valro-agent:latest
docker push ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/valro-agent:latest
```

Then create the agent runtime through AWS console or API.

### Phase 2: Deploy Lambda Backend

#### Step 1: Create IAM Role

```bash
# Create trust policy
cat > lambda-trust-policy.json << EOF
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
  --role-name valro-lambda-role \
  --assume-role-policy-document file://lambda-trust-policy.json

# Attach permissions policy
aws iam put-role-policy \
  --role-name valro-lambda-role \
  --policy-name ValroLambdaPolicy \
  --policy-document file://lambda-backend/iam-policy.json

# Wait for role to propagate
sleep 10
```

#### Step 2: Package and Deploy Lambda

```bash
cd lambda-backend

# Package Lambda
./deploy.sh

# Deploy Lambda function
aws lambda create-function \
  --function-name valro-backend \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/valro-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://valro-lambda.zip \
  --timeout 60 \
  --memory-size 512 \
  --environment Variables="{
    AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/home_owner_concierge-XXXXX,
    AWS_REGION=us-east-1
  }"
```

**Or update existing function:**

```bash
aws lambda update-function-code \
  --function-name valro-backend \
  --zip-file fileb://valro-lambda.zip
```

#### Step 3: Test Lambda

```bash
# Create test event
cat > test-event.json << EOF
{
  "httpMethod": "GET",
  "path": "/tasks",
  "body": null
}
EOF

# Invoke Lambda
aws lambda invoke \
  --function-name valro-backend \
  --payload file://test-event.json \
  response.json

# Check response
cat response.json
```

### Phase 3: Create API Gateway

#### Option A: Using AWS Console

1. Go to API Gateway console
2. Click "Create API" → "HTTP API"
3. Add integration:
   - Integration type: Lambda
   - Lambda function: `valro-backend`
   - Version: 2.0
4. Configure routes:
   - `POST /tasks`
   - `GET /tasks`
   - `GET /tasks/{id}`
5. Configure CORS:
   - Access-Control-Allow-Origin: `*` (or specific domain)
   - Access-Control-Allow-Methods: `GET, POST, OPTIONS`
   - Access-Control-Allow-Headers: `Content-Type`
6. Create $default stage with auto-deploy
7. Save the API endpoint URL

#### Option B: Using AWS CLI

```bash
# Create API
API_ID=$(aws apigatewayv2 create-api \
  --name valro-api \
  --protocol-type HTTP \
  --cors-configuration AllowOrigins="*",AllowMethods="GET,POST,OPTIONS",AllowHeaders="*" \
  --query 'ApiId' \
  --output text)

echo "API ID: $API_ID"

# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function \
  --function-name valro-backend \
  --query 'Configuration.FunctionArn' \
  --output text)

# Create integration
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
  --api-id $API_ID \
  --integration-type AWS_PROXY \
  --integration-uri $LAMBDA_ARN \
  --payload-format-version 2.0 \
  --query 'IntegrationId' \
  --output text)

echo "Integration ID: $INTEGRATION_ID"

# Create routes
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "POST /tasks" \
  --target integrations/$INTEGRATION_ID

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /tasks" \
  --target integrations/$INTEGRATION_ID

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /tasks/{id}" \
  --target integrations/$INTEGRATION_ID

# Create stage
aws apigatewayv2 create-stage \
  --api-id $API_ID \
  --stage-name '$default' \
  --auto-deploy

# Grant API Gateway permission to invoke Lambda
aws lambda add-permission \
  --function-name valro-backend \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:ACCOUNT_ID:$API_ID/*/*"

# Get API endpoint
API_ENDPOINT="https://${API_ID}.execute-api.us-east-1.amazonaws.com"
echo "API Endpoint: $API_ENDPOINT"
```

**Save this URL for the frontend!**

#### Test API Gateway

```bash
# Test GET /tasks
curl $API_ENDPOINT/tasks

# Test POST /tasks
curl -X POST $API_ENDPOINT/tasks \
  -H "Content-Type: application/json" \
  -d '{"description": "Find me a landscaper in Charlotte under $300"}'
```

### Phase 4: Deploy Frontend

You have three deployment options:

#### Option A: AWS Amplify (Easiest, Recommended)

1. **Commit and push code to GitHub:**

```bash
git add .
git commit -m "Add Valro POC"
git push origin main
```

2. **Connect to Amplify:**
   - Go to [AWS Amplify Console](https://console.aws.amazon.com/amplify/)
   - Click "New app" → "Host web app"
   - Connect GitHub repository
   - Select branch (`main`)
   - If monorepo, set app root to `valro-ui`

3. **Configure build settings:**

```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - cd valro-ui  # If monorepo
        - npm install
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: valro-ui/dist  # Or just dist if not monorepo
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
```

4. **Add environment variable:**
   - App Settings → Environment variables
   - Key: `VITE_API_BASE`
   - Value: `https://your-api-id.execute-api.us-east-1.amazonaws.com`

5. **Save and deploy**

Your app will be live at: `https://main.xxxxx.amplifyapp.com`

#### Option B: S3 + CloudFront

```bash
cd valro-ui

# Create .env file
cat > .env << EOF
VITE_API_BASE=https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com
EOF

# Install and build
npm install
npm run build

# Create S3 bucket
BUCKET_NAME="valro-ui-$(date +%s)"
aws s3 mb s3://$BUCKET_NAME

# Configure for static hosting
aws s3 website s3://$BUCKET_NAME --index-document index.html

# Upload build
aws s3 sync dist/ s3://$BUCKET_NAME --delete

# Make public (or use CloudFront)
aws s3api put-bucket-policy \
  --bucket $BUCKET_NAME \
  --policy '{
    "Version": "2012-10-17",
    "Statement": [{
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::'$BUCKET_NAME'/*"
    }]
  }'

echo "Website URL: http://$BUCKET_NAME.s3-website-us-east-1.amazonaws.com"
```

For CloudFront, see [valro-ui/README.md](valro-ui/README.md#option-2-s3--cloudfront).

#### Option C: Vercel

```bash
cd valro-ui

# Install Vercel CLI
npm install -g vercel

# Deploy
vercel

# Add environment variable
vercel env add VITE_API_BASE
# Enter your API Gateway URL when prompted

# Production deployment
vercel --prod
```

### Phase 5: Verify End-to-End

1. **Open the frontend URL** in your browser

2. **Create a test task:**
   - Click "Create New Task"
   - Enter: "Find me a landscaper in Charlotte under $300"
   - Click "Create Task"

3. **Verify the flow:**
   - Task appears in sidebar with "processing" status
   - After a few seconds, status changes to "completed"
   - Agent response appears in the detail view
   - Check that vendors were contacted (check emails in Lambda logs)

4. **Check CloudWatch Logs:**

```bash
# Lambda logs
aws logs tail /aws/lambda/valro-backend --follow

# AgentCore logs (if enabled)
aws logs tail /aws/bedrock-agentcore/home_owner_concierge --follow
```

## Post-Deployment Configuration

### Update Agent (if needed)

```bash
cd agentcore-basic-demo/agent-code

# Modify basic_agent.py
# Then redeploy
agentcore launch --auto-update-on-conflict
```

### Update Lambda

```bash
cd lambda-backend
./deploy.sh

aws lambda update-function-code \
  --function-name valro-backend \
  --zip-file fileb://valro-lambda.zip
```

### Update Frontend

**Amplify:** Just push to GitHub, auto-deploys

**S3:** Re-run `npm run build && aws s3 sync dist/ s3://bucket-name`

**Vercel:** Run `vercel --prod`

## Monitoring

### View Lambda Logs

```bash
aws logs tail /aws/lambda/valro-backend --follow
```

### View API Gateway Metrics

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiId,Value=YOUR_API_ID \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### View AgentCore Status

```bash
agentcore status --agent home_owner_concierge --verbose
```

## Troubleshooting

### Agent not responding

```bash
# Check agent status
agentcore status

# View agent logs
aws logs tail /aws/bedrock-agentcore/home_owner_concierge --follow

# Test agent directly
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn YOUR_ARN \
  --payload $(echo -n '{"prompt": "test"}' | base64) \
  /tmp/output.json
```

### Lambda errors

```bash
# Check Lambda logs
aws logs tail /aws/lambda/valro-backend --follow

# Test Lambda directly
aws lambda invoke \
  --function-name valro-backend \
  --payload '{"httpMethod":"GET","path":"/tasks"}' \
  response.json && cat response.json
```

### Frontend CORS errors

- Check API Gateway CORS configuration
- Verify Lambda returns CORS headers
- Check browser console for specific error

### API Gateway 403/404 errors

- Verify routes are created correctly
- Check Lambda permission for API Gateway
- Verify API is deployed to $default stage

## Security Considerations

For production, consider:

1. **Authentication:**
   - Add Cognito for user auth
   - Use API Gateway authorizers

2. **API Security:**
   - Enable API keys or OAuth
   - Add rate limiting
   - Restrict CORS to specific domains

3. **Data Persistence:**
   - Migrate from in-memory to DynamoDB
   - Add encryption at rest

4. **IAM:**
   - Use least-privilege policies
   - Enable CloudTrail logging
   - Rotate credentials

## Cost Estimates (POC)

Approximate monthly costs for light usage:

- AgentCore Runtime: $0 (free tier during preview)
- Lambda: ~$1 (generous free tier)
- API Gateway: ~$1 (1M requests free)
- S3 + CloudFront: ~$1
- **Total: ~$3/month**

Amplify adds ~$12/month for hosting.

## Cleanup

To remove all resources:

```bash
# Delete frontend
aws amplify delete-app --app-id YOUR_APP_ID
# Or delete S3 bucket
aws s3 rb s3://bucket-name --force

# Delete API Gateway
aws apigatewayv2 delete-api --api-id YOUR_API_ID

# Delete Lambda
aws lambda delete-function --function-name valro-backend

# Delete IAM role
aws iam delete-role-policy --role-name valro-lambda-role --policy-name ValroLambdaPolicy
aws iam delete-role --role-name valro-lambda-role

# Delete AgentCore agent
agentcore destroy --agent home_owner_concierge
```

## Next Steps

- ✅ Test with real user scenarios
- Add DynamoDB for persistence
- Implement WebSocket for real-time updates
- Add user authentication
- Implement actual email sending (SES)
- Add vendor database integration
- Implement quote collection workflow
