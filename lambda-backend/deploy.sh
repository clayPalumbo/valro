#!/bin/bash

# Valro Lambda Deployment Script
# This script packages and prepares the Lambda function for deployment

set -e

echo "========================================="
echo "Valro Lambda Deployment Package Creator"
echo "========================================="

# Create deployment package
PACKAGE_DIR="package"
ZIP_FILE="valro-lambda.zip"

echo ""
echo "Step 1: Cleaning previous builds..."
rm -rf $PACKAGE_DIR
rm -f $ZIP_FILE

echo ""
echo "Step 2: Installing dependencies..."
mkdir -p $PACKAGE_DIR
pip install -r requirements.txt -t $PACKAGE_DIR/ --quiet

echo ""
echo "Step 3: Adding Lambda function code..."
cp lambda_function.py $PACKAGE_DIR/

echo ""
echo "Step 4: Creating deployment package..."
cd $PACKAGE_DIR
zip -r ../$ZIP_FILE . -q
cd ..

echo ""
echo "✓ Deployment package created: $ZIP_FILE"
echo ""
echo "Next steps:"
echo "1. Create Lambda function in AWS Console or use AWS CLI:"
echo ""
echo "   aws lambda create-function \\"
echo "     --function-name valro-backend \\"
echo "     --runtime python3.11 \\"
echo "     --role arn:aws:iam::YOUR_ACCOUNT:role/valro-lambda-role \\"
echo "     --handler lambda_function.lambda_handler \\"
echo "     --zip-file fileb://valro-lambda.zip \\"
echo "     --timeout 60 \\"
echo "     --memory-size 512 \\"
echo "     --environment Variables='{AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:975150127262:runtime/home_owner_concierge-tBcmf45NFO,AWS_REGION=us-east-1}'"
echo ""
echo "2. Or update existing function:"
echo ""
echo "   aws lambda update-function-code \\"
echo "     --function-name valro-backend \\"
echo "     --zip-file fileb://valro-lambda.zip"
echo ""
echo "3. Create API Gateway HTTP API and integrate with Lambda"
echo "4. Enable CORS in API Gateway"
echo ""
echo "========================================="
