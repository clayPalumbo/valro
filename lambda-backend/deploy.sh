#!/bin/bash

# Valro Lambda Deployment Script
# This script packages and prepares both API and Worker Lambda functions for deployment

set -e

echo "========================================="
echo "Valro Lambda Deployment Package Creator"
echo "========================================="

# Package directories and files
API_PACKAGE_DIR="package-api"
WORKER_PACKAGE_DIR="package-worker"
API_ZIP_FILE="valro-api-lambda.zip"
WORKER_ZIP_FILE="valro-worker-lambda.zip"

echo ""
echo "Step 1: Cleaning previous builds..."
rm -rf $API_PACKAGE_DIR $WORKER_PACKAGE_DIR
rm -f $API_ZIP_FILE $WORKER_ZIP_FILE

echo ""
echo "Step 2: Installing dependencies..."
mkdir -p $API_PACKAGE_DIR
mkdir -p $WORKER_PACKAGE_DIR

echo "  Installing dependencies for API Lambda..."
pip3 install -r requirements.txt -t $API_PACKAGE_DIR/ --quiet

echo "  Installing dependencies for Worker Lambda..."
pip3 install -r requirements.txt -t $WORKER_PACKAGE_DIR/ --quiet

echo ""
echo "Step 3: Adding Lambda function code..."

echo "  Packaging API Lambda..."
cp lambda_function.py $API_PACKAGE_DIR/
cp dynamodb_helpers.py $API_PACKAGE_DIR/

echo "  Packaging Worker Lambda..."
cp worker_lambda.py $WORKER_PACKAGE_DIR/
cp dynamodb_helpers.py $WORKER_PACKAGE_DIR/

echo ""
echo "Step 4: Creating deployment packages..."

echo "  Creating API Lambda package..."
cd $API_PACKAGE_DIR
zip -r ../$API_ZIP_FILE . -q
cd ..

echo "  Creating Worker Lambda package..."
cd $WORKER_PACKAGE_DIR
zip -r ../$WORKER_ZIP_FILE . -q
cd ..

echo ""
echo "✓ Deployment packages created:"
echo "  - $API_ZIP_FILE (API Lambda)"
echo "  - $WORKER_ZIP_FILE (Worker Lambda)"
echo ""
echo "Next steps:"
echo ""
echo "1. Use the create-infrastructure.sh script to set up all AWS resources:"
echo "   ./create-infrastructure.sh"
echo ""
echo "Or manually deploy:"
echo ""
echo "2. Create DynamoDB table:"
echo "   aws dynamodb create-table \\"
echo "     --table-name valro-tasks \\"
echo "     --attribute-definitions AttributeName=id,AttributeType=S \\"
echo "     --key-schema AttributeName=id,KeyType=HASH \\"
echo "     --billing-mode PAY_PER_REQUEST"
echo ""
echo "3. Create Worker Lambda:"
echo "   aws lambda create-function \\"
echo "     --function-name valro-worker \\"
echo "     --runtime python3.11 \\"
echo "     --role arn:aws:iam::YOUR_ACCOUNT:role/valro-worker-role \\"
echo "     --handler worker_lambda.lambda_handler \\"
echo "     --zip-file fileb://valro-worker-lambda.zip \\"
echo "     --timeout 600 \\"
echo "     --memory-size 1024 \\"
echo "     --environment Variables='{DYNAMODB_TABLE_NAME=valro-tasks,AGENT_RUNTIME_ARN=YOUR_ARN,AWS_REGION=us-east-1}'"
echo ""
echo "4. Create API Lambda:"
echo "   aws lambda create-function \\"
echo "     --function-name valro-backend \\"
echo "     --runtime python3.11 \\"
echo "     --role arn:aws:iam::YOUR_ACCOUNT:role/valro-lambda-role \\"
echo "     --handler lambda_function.lambda_handler \\"
echo "     --zip-file fileb://valro-api-lambda.zip \\"
echo "     --timeout 30 \\"
echo "     --memory-size 512 \\"
echo "     --environment Variables='{DYNAMODB_TABLE_NAME=valro-tasks,WORKER_LAMBDA_ARN=arn:aws:lambda:REGION:ACCOUNT:function:valro-worker,AWS_REGION=us-east-1}'"
echo ""
echo "5. Or update existing functions:"
echo "   aws lambda update-function-code --function-name valro-backend --zip-file fileb://valro-api-lambda.zip"
echo "   aws lambda update-function-code --function-name valro-worker --zip-file fileb://valro-worker-lambda.zip"
echo ""
echo "========================================="
