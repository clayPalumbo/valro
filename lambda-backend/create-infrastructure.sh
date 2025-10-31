#!/bin/bash

# Valro Infrastructure Setup Script
# This script creates all AWS resources needed for the async architecture:
# - DynamoDB table
# - IAM roles and policies
# - Lambda functions (API and Worker)

set -e

echo "========================================="
echo "Valro Infrastructure Setup"
echo "========================================="
echo ""

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TABLE_NAME="valro-tasks"
API_LAMBDA_NAME="valro-backend"
WORKER_LAMBDA_NAME="valro-worker"
API_ROLE_NAME="valro-lambda-role"
WORKER_ROLE_NAME="valro-worker-role"

# Check if deployment packages exist
if [ ! -f "valro-api-lambda.zip" ] || [ ! -f "valro-worker-lambda.zip" ]; then
    echo "❌ Deployment packages not found. Running deploy.sh first..."
    ./deploy.sh
fi

echo "Configuration:"
echo "  AWS Region: $AWS_REGION"
echo "  Account ID: $ACCOUNT_ID"
echo "  DynamoDB Table: $TABLE_NAME"
echo "  API Lambda: $API_LAMBDA_NAME"
echo "  Worker Lambda: $WORKER_LAMBDA_NAME"
echo ""

# Prompt for Agent Runtime ARN
read -p "Enter your AgentCore Runtime ARN: " AGENT_RUNTIME_ARN
if [ -z "$AGENT_RUNTIME_ARN" ]; then
    echo "❌ Agent Runtime ARN is required"
    exit 1
fi

echo ""
echo "========================================="
echo "Step 1: Creating DynamoDB Table"
echo "========================================="

if aws dynamodb describe-table --table-name $TABLE_NAME --region $AWS_REGION >/dev/null 2>&1; then
    echo "✓ DynamoDB table '$TABLE_NAME' already exists"
else
    echo "Creating DynamoDB table '$TABLE_NAME'..."
    aws dynamodb create-table \
        --table-name $TABLE_NAME \
        --attribute-definitions AttributeName=id,AttributeType=S \
        --key-schema AttributeName=id,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region $AWS_REGION \
        --tags Key=Project,Value=Valro

    echo "Waiting for table to be active..."
    aws dynamodb wait table-exists --table-name $TABLE_NAME --region $AWS_REGION
    echo "✓ DynamoDB table created successfully"
fi

echo ""
echo "========================================="
echo "Step 2: Creating IAM Roles"
echo "========================================="

# Create trust policy for Lambda
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

# Create Worker Lambda Role
echo "Creating Worker Lambda IAM role..."
if aws iam get-role --role-name $WORKER_ROLE_NAME >/dev/null 2>&1; then
    echo "✓ Worker role '$WORKER_ROLE_NAME' already exists"
else
    aws iam create-role \
        --role-name $WORKER_ROLE_NAME \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json

    echo "Attaching policy to Worker role..."
    aws iam put-role-policy \
        --role-name $WORKER_ROLE_NAME \
        --policy-name ValroWorkerPolicy \
        --policy-document file://worker-iam-policy.json

    echo "✓ Worker role created successfully"
    echo "Waiting 10 seconds for role to propagate..."
    sleep 10
fi

# Create API Lambda Role
echo "Creating API Lambda IAM role..."
if aws iam get-role --role-name $API_ROLE_NAME >/dev/null 2>&1; then
    echo "✓ API role '$API_ROLE_NAME' already exists"
else
    aws iam create-role \
        --role-name $API_ROLE_NAME \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json

    echo "Attaching policy to API role..."
    aws iam put-role-policy \
        --role-name $API_ROLE_NAME \
        --policy-name ValroAPIPolicy \
        --policy-document file://iam-policy.json

    echo "✓ API role created successfully"
    echo "Waiting 10 seconds for role to propagate..."
    sleep 10
fi

WORKER_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${WORKER_ROLE_NAME}"
API_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${API_ROLE_NAME}"
WORKER_LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${WORKER_LAMBDA_NAME}"

echo ""
echo "========================================="
echo "Step 3: Creating Lambda Functions"
echo "========================================="

# Create Worker Lambda
echo "Creating Worker Lambda function..."
if aws lambda get-function --function-name $WORKER_LAMBDA_NAME --region $AWS_REGION >/dev/null 2>&1; then
    echo "Worker Lambda already exists. Updating code..."
    aws lambda update-function-code \
        --function-name $WORKER_LAMBDA_NAME \
        --zip-file fileb://valro-worker-lambda.zip \
        --region $AWS_REGION

    echo "Updating Worker Lambda configuration..."
    aws lambda update-function-configuration \
        --function-name $WORKER_LAMBDA_NAME \
        --timeout 600 \
        --memory-size 1024 \
        --environment "Variables={DYNAMODB_TABLE_NAME=${TABLE_NAME},AGENT_RUNTIME_ARN=${AGENT_RUNTIME_ARN},AWS_REGION=${AWS_REGION}}" \
        --region $AWS_REGION

    echo "✓ Worker Lambda updated successfully"
else
    aws lambda create-function \
        --function-name $WORKER_LAMBDA_NAME \
        --runtime python3.11 \
        --role $WORKER_ROLE_ARN \
        --handler worker_lambda.lambda_handler \
        --zip-file fileb://valro-worker-lambda.zip \
        --timeout 600 \
        --memory-size 1024 \
        --environment "Variables={DYNAMODB_TABLE_NAME=${TABLE_NAME},AGENT_RUNTIME_ARN=${AGENT_RUNTIME_ARN},AWS_REGION=${AWS_REGION}}" \
        --region $AWS_REGION \
        --tags Project=Valro

    echo "✓ Worker Lambda created successfully"
fi

# Create API Lambda
echo ""
echo "Creating API Lambda function..."
if aws lambda get-function --function-name $API_LAMBDA_NAME --region $AWS_REGION >/dev/null 2>&1; then
    echo "API Lambda already exists. Updating code..."
    aws lambda update-function-code \
        --function-name $API_LAMBDA_NAME \
        --zip-file fileb://valro-api-lambda.zip \
        --region $AWS_REGION

    echo "Updating API Lambda configuration..."
    aws lambda update-function-configuration \
        --function-name $API_LAMBDA_NAME \
        --timeout 30 \
        --memory-size 512 \
        --environment "Variables={DYNAMODB_TABLE_NAME=${TABLE_NAME},WORKER_LAMBDA_ARN=${WORKER_LAMBDA_ARN},AWS_REGION=${AWS_REGION}}" \
        --region $AWS_REGION

    echo "✓ API Lambda updated successfully"
else
    aws lambda create-function \
        --function-name $API_LAMBDA_NAME \
        --runtime python3.11 \
        --role $API_ROLE_ARN \
        --handler lambda_function.lambda_handler \
        --zip-file fileb://valro-api-lambda.zip \
        --timeout 30 \
        --memory-size 512 \
        --environment "Variables={DYNAMODB_TABLE_NAME=${TABLE_NAME},WORKER_LAMBDA_ARN=${WORKER_LAMBDA_ARN},AWS_REGION=${AWS_REGION}}" \
        --region $AWS_REGION \
        --tags Project=Valro

    echo "✓ API Lambda created successfully"
fi

echo ""
echo "========================================="
echo "Step 4: Checking API Gateway"
echo "========================================="

echo "Note: API Gateway setup is not automated in this script."
echo "If you haven't created an API Gateway yet, please create one manually or use the AWS Console."
echo ""
echo "Quick API Gateway setup:"
echo "  1. Create HTTP API in API Gateway"
echo "  2. Add integration to '$API_LAMBDA_NAME' Lambda"
echo "  3. Create routes: POST /tasks, GET /tasks, GET /tasks/{id}"
echo "  4. Enable CORS"
echo "  5. Deploy to \$default stage"
echo ""

# Check if there's an existing API Gateway that points to this Lambda
API_ID=$(aws apigatewayv2 get-apis --region $AWS_REGION --query "Items[?Name=='valro-api'].ApiId" --output text 2>/dev/null || echo "")

if [ ! -z "$API_ID" ]; then
    API_ENDPOINT="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com"
    echo "✓ Found existing API Gateway:"
    echo "  API ID: $API_ID"
    echo "  Endpoint: $API_ENDPOINT"
else
    echo "No existing 'valro-api' found. You'll need to create one."
fi

echo ""
echo "========================================="
echo "✓ Infrastructure Setup Complete!"
echo "========================================="
echo ""
echo "Resources Created:"
echo "  ✓ DynamoDB Table: $TABLE_NAME"
echo "  ✓ Worker Lambda: $WORKER_LAMBDA_NAME"
echo "  ✓ API Lambda: $API_LAMBDA_NAME"
echo "  ✓ IAM Roles: $WORKER_ROLE_NAME, $API_ROLE_NAME"
echo ""
echo "Environment Variables Set:"
echo "  API Lambda:"
echo "    - DYNAMODB_TABLE_NAME=$TABLE_NAME"
echo "    - WORKER_LAMBDA_ARN=$WORKER_LAMBDA_ARN"
echo "    - AWS_REGION=$AWS_REGION"
echo ""
echo "  Worker Lambda:"
echo "    - DYNAMODB_TABLE_NAME=$TABLE_NAME"
echo "    - AGENT_RUNTIME_ARN=$AGENT_RUNTIME_ARN"
echo "    - AWS_REGION=$AWS_REGION"
echo ""
echo "Next Steps:"
echo "  1. If you haven't set up API Gateway, create it now"
echo "  2. Test the API Lambda: aws lambda invoke --function-name $API_LAMBDA_NAME /tmp/response.json"
echo "  3. Update your frontend with the API Gateway URL"
echo ""
echo "Monitor logs:"
echo "  API Lambda:    aws logs tail /aws/lambda/$API_LAMBDA_NAME --follow"
echo "  Worker Lambda: aws logs tail /aws/lambda/$WORKER_LAMBDA_NAME --follow"
echo ""
echo "========================================="
