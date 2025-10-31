# Valro Testing Guide

Comprehensive testing guide for the Valro POC, covering unit tests, integration tests, and end-to-end scenarios.

## Testing Strategy

```
┌────────────────────────────────────────┐
│         End-to-End Tests               │
│  (Full user workflow through UI)       │
├────────────────────────────────────────┤
│         Integration Tests              │
│  (Lambda ↔ AgentCore)                  │
├────────────────────────────────────────┤
│         Component Tests                │
│  (Agent tools, Lambda handlers)        │
└────────────────────────────────────────┘
```

## Pre-Deployment Testing

### 1. Test Agent Locally

#### Test Agent Tools in Isolation

```bash
cd agentcore-basic-demo/agent-code

# Create test script
cat > test_agent.py << 'EOF'
from basic_agent import getVendors, sendEmail
import json

# Test getVendors
print("Testing getVendors...")
result = getVendors("landscaping", "Charlotte", 300)
vendors = json.loads(result)
print(f"✓ Found {vendors['count']} vendors")
print(json.dumps(vendors, indent=2))

# Test sendEmail
print("\nTesting sendEmail...")
result = sendEmail(
    to="test@example.com",
    subject="Test Quote Request",
    body="Hello, can you provide a quote?",
    taskId="test-123"
)
print(json.dumps(json.loads(result), indent=2))
print("✓ Email function works")
EOF

# Run test
python test_agent.py
```

**Expected Output:**
```
Testing getVendors...
✓ Found 3 vendors
{
  "vendors": [
    {
      "id": "vendor_1",
      "name": "Greenline Lawn",
      ...
    }
  ],
  ...
}

Testing sendEmail...
{
  "status": "sent",
  "timestamp": "2025-10-31T...",
  ...
}
✓ Email function works
```

#### Test Agent with Strands

```bash
# Create integration test
cat > test_agent_integration.py << 'EOF'
import os
os.environ['BEDROCK_AGENTCORE_MEMORY_ID'] = 'test-memory'
os.environ['AWS_REGION'] = 'us-east-1'

from basic_agent import invoke

# Mock context
class MockContext:
    session_id = "test-session"
    headers = {}

# Test payload
payload = {
    "prompt": "Find me a landscaper in Charlotte under $300"
}

print("Testing agent with full prompt...")
try:
    result = invoke(payload, MockContext())
    print("✓ Agent responded")
    print(f"Response: {result['response'][:200]}...")
except Exception as e:
    print(f"✗ Error: {e}")
EOF

python test_agent_integration.py
```

### 2. Test Lambda Function Locally

#### Test Lambda Handler

```bash
cd lambda-backend

# Create test script
cat > test_lambda.py << 'EOF'
import json
from lambda_function import lambda_handler

# Test GET /tasks
print("Testing GET /tasks...")
event = {
    "httpMethod": "GET",
    "path": "/tasks",
    "body": None
}
result = lambda_handler(event, None)
print(f"Status: {result['statusCode']}")
print(f"Response: {json.loads(result['body'])}")

# Test POST /tasks
print("\nTesting POST /tasks...")
event = {
    "httpMethod": "POST",
    "path": "/tasks",
    "body": json.dumps({
        "description": "Find me a painter in Charlotte under $500"
    })
}
result = lambda_handler(event, None)
print(f"Status: {result['statusCode']}")
response = json.loads(result['body'])
print(f"Task ID: {response.get('id')}")

# Test GET /tasks/{id}
print("\nTesting GET /tasks/{id}...")
task_id = response.get('id')
event = {
    "httpMethod": "GET",
    "path": f"/tasks/{task_id}",
    "body": None
}
result = lambda_handler(event, None)
print(f"Status: {result['statusCode']}")
task = json.loads(result['body'])
print(f"Task status: {task.get('status')}")
EOF

python test_lambda.py
```

**Expected Output:**
```
Testing GET /tasks...
Status: 200
Response: []

Testing POST /tasks...
Status: 200
Task ID: <uuid>

Testing GET /tasks/{id}...
Status: 200
Task status: processing
```

#### Test with Sample Events

```bash
# Create API Gateway test event
cat > events/post-task.json << EOF
{
  "httpMethod": "POST",
  "path": "/tasks",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": "{\"description\": \"Find me a landscaper in Charlotte under $300\"}"
}
EOF

cat > events/get-tasks.json << EOF
{
  "httpMethod": "GET",
  "path": "/tasks",
  "headers": {}
}
EOF

# Run tests
python -c "
import json
from lambda_function import lambda_handler

with open('events/post-task.json') as f:
    event = json.load(f)
    result = lambda_handler(event, None)
    print(json.dumps(result, indent=2))
"
```

### 3. Test Frontend Components

```bash
cd valro-ui

# Install dependencies
npm install

# Run dev server
npm run dev
```

**Manual UI Tests:**

1. **Create Task Test:**
   - Enter description: "Find me a landscaper in Charlotte under $300"
   - Click "Create Task"
   - ✓ Task appears in sidebar
   - ✓ Status shows "processing"

2. **Task List Test:**
   - ✓ Tasks display in sidebar
   - ✓ Click on task to select
   - ✓ Selected task highlighted

3. **Task Detail Test:**
   - ✓ Description displays correctly
   - ✓ Status badge shows correct color
   - ✓ Timestamps formatted properly
   - ✓ Events timeline displays

4. **Polling Test:**
   - Select a task
   - ✓ Check network tab shows requests every 3 seconds
   - ✓ Task updates automatically when status changes

5. **Error Handling Test:**
   - Stop backend
   - Try to create task
   - ✓ Error message displays
   - ✓ UI doesn't crash

## Post-Deployment Testing

### 1. API Gateway Tests

```bash
# Set your API endpoint
export API_ENDPOINT="https://your-api-id.execute-api.us-east-1.amazonaws.com"

# Test CORS preflight
curl -X OPTIONS $API_ENDPOINT/tasks \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -v

# Expected: 200 OK with CORS headers

# Test GET /tasks
curl $API_ENDPOINT/tasks | jq

# Expected: []

# Test POST /tasks
TASK_ID=$(curl -X POST $API_ENDPOINT/tasks \
  -H "Content-Type: application/json" \
  -d '{"description": "Find me a landscaper in Charlotte under $300"}' \
  | jq -r '.id')

echo "Created task: $TASK_ID"

# Test GET /tasks/{id}
curl $API_ENDPOINT/tasks/$TASK_ID | jq

# Wait a few seconds for agent processing
sleep 10

# Check task status again
curl $API_ENDPOINT/tasks/$TASK_ID | jq '.status'

# Expected: "completed"
```

### 2. AgentCore Integration Tests

```bash
# Test agent invocation directly
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/home_owner_concierge-XXXXX" \
  --payload $(echo -n '{"prompt": "Find me a landscaper in Charlotte under $300"}' | base64) \
  /tmp/agent-output.json

# Check response
cat /tmp/agent-output.json | jq
```

### 3. End-to-End Test Scenarios

#### Scenario 1: Basic Landscaping Request

**Input:** "Find me a landscaper in Charlotte under $300"

**Expected Behavior:**
1. Task created with "processing" status
2. Agent invoked automatically
3. `getVendors` tool called with:
   - service: "landscaping"
   - city: "Charlotte"
   - budget: 300
4. Returns 3 vendors (Greenline Lawn, Queen City Turf, Uptown Yard)
5. `sendEmail` called 3 times (one per vendor)
6. Agent response includes:
   - "I've contacted 3 landscaping vendors"
   - "waiting for vendor replies"
7. Task status changes to "completed"

**Verification:**
```bash
# Check Lambda logs
aws logs tail /aws/lambda/valro-backend --follow | grep -A 5 "EMAIL SENT"

# Should see 3 email logs
```

#### Scenario 2: Painting Request Different City

**Input:** "I need a painter in Raleigh"

**Expected Behavior:**
1. Agent extracts: service=painting, city=Raleigh
2. Fallback to default vendors (no Raleigh painters in mock DB)
3. Returns Charlotte painters instead
4. Sends emails to 2 vendors

#### Scenario 3: Multiple Tasks

**Test:**
```bash
# Create 5 tasks rapidly
for i in {1..5}; do
  curl -X POST $API_ENDPOINT/tasks \
    -H "Content-Type: application/json" \
    -d "{\"description\": \"Task $i: Find a cleaner in Charlotte\"}"
  sleep 1
done

# Check all tasks
curl $API_ENDPOINT/tasks | jq 'length'
# Expected: 5

# Check each task status
curl $API_ENDPOINT/tasks | jq '.[] | {id, status}'
```

#### Scenario 4: Invalid Input Handling

```bash
# Empty description
curl -X POST $API_ENDPOINT/tasks \
  -H "Content-Type: application/json" \
  -d '{"description": ""}'
# Expected: 400 Bad Request

# Missing body
curl -X POST $API_ENDPOINT/tasks \
  -H "Content-Type: application/json"
# Expected: 400 Bad Request

# Invalid task ID
curl $API_ENDPOINT/tasks/invalid-id
# Expected: 404 Not Found
```

#### Scenario 5: Frontend Polling

1. Create a task via UI
2. Open browser DevTools → Network tab
3. Select the task
4. Observe requests to `/tasks/{id}` every 3 seconds
5. Status should update from "processing" to "completed"

### 4. Load Testing (Optional)

```bash
# Install Apache Bench
# macOS: brew install httpd
# Linux: apt-get install apache2-utils

# Test POST /tasks (100 requests, 10 concurrent)
ab -n 100 -c 10 \
  -p test-payload.json \
  -T application/json \
  $API_ENDPOINT/tasks

# Test GET /tasks
ab -n 1000 -c 50 $API_ENDPOINT/tasks
```

## Monitoring & Debugging

### CloudWatch Logs

```bash
# Lambda logs (real-time)
aws logs tail /aws/lambda/valro-backend --follow

# Filter for errors
aws logs tail /aws/lambda/valro-backend --follow --filter-pattern "ERROR"

# AgentCore logs
aws logs tail /aws/bedrock-agentcore/home_owner_concierge --follow
```

### Check Agent Status

```bash
# Get agent status
agentcore status --agent home_owner_concierge --verbose

# Check memory status
aws bedrock-agentcore-control list-memories | jq
```

### API Gateway Metrics

```bash
# Get request count (last hour)
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiId,Value=YOUR_API_ID \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Get error rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name 4XXError \
  --dimensions Name=ApiId,Value=YOUR_API_ID \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

## Common Issues & Solutions

### Issue: Agent not responding

**Symptoms:** Task stays in "processing" forever

**Debug:**
```bash
# Check agent status
agentcore status --agent home_owner_concierge

# Check Lambda can invoke agent
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn YOUR_ARN \
  --payload $(echo -n '{"prompt": "test"}' | base64) \
  /tmp/test.json

# Check IAM permissions
aws iam get-role-policy \
  --role-name valro-lambda-role \
  --policy-name ValroLambdaPolicy
```

**Solution:** Verify AGENT_RUNTIME_ARN and IAM permissions

### Issue: CORS errors in browser

**Symptoms:** Preflight request fails, red errors in console

**Debug:**
```bash
# Test CORS manually
curl -X OPTIONS $API_ENDPOINT/tasks \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -v
```

**Solution:**
- Verify API Gateway CORS configuration
- Check Lambda response includes CORS headers
- Ensure `Access-Control-Allow-Origin` matches frontend domain

### Issue: Lambda timeout

**Symptoms:** 504 Gateway Timeout from API Gateway

**Debug:**
```bash
# Check Lambda timeout setting
aws lambda get-function-configuration \
  --function-name valro-backend | jq '.Timeout'

# Check recent invocations
aws lambda get-function \
  --function-name valro-backend
```

**Solution:** Increase Lambda timeout to 60+ seconds

### Issue: Empty task list

**Symptoms:** GET /tasks returns empty array

**Debug:** This is expected behavior with in-memory storage (tasks lost on Lambda cold start)

**Solution:** Tasks are ephemeral in POC. For persistence, migrate to DynamoDB.

## Test Checklist

### Pre-Deployment
- [ ] Agent tools (getVendors, sendEmail) work in isolation
- [ ] Agent responds to prompts with correct tool calls
- [ ] Lambda handler routes requests correctly
- [ ] Lambda creates and retrieves tasks
- [ ] Frontend displays task list
- [ ] Frontend creates new tasks
- [ ] Frontend polls and updates task details

### Post-Deployment
- [ ] API Gateway responds to all routes
- [ ] CORS works from frontend domain
- [ ] Lambda successfully invokes AgentCore
- [ ] Agent processes requests and returns responses
- [ ] Emails are logged (check CloudWatch)
- [ ] Frontend connects to API successfully
- [ ] End-to-end task creation flow works
- [ ] Multiple concurrent tasks work
- [ ] Error handling works (invalid input, not found, etc.)

### Performance
- [ ] Task creation < 2 seconds
- [ ] Agent processing < 30 seconds
- [ ] API responses < 1 second
- [ ] Frontend loads < 3 seconds
- [ ] No memory leaks in extended use

### Security
- [ ] API requires valid requests
- [ ] No sensitive data in logs
- [ ] CORS restricted to known domains (production)
- [ ] IAM follows least-privilege
- [ ] Environment variables not exposed

## Automated Testing (Future Enhancement)

For production, consider adding:

```python
# pytest tests for Lambda
# tests/test_lambda_function.py

def test_create_task():
    event = {
        "httpMethod": "POST",
        "path": "/tasks",
        "body": json.dumps({"description": "test"})
    }
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200

def test_list_tasks():
    event = {"httpMethod": "GET", "path": "/tasks"}
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
```

```javascript
// Jest tests for React
// src/App.test.jsx

test('renders task list', () => {
  render(<App />);
  expect(screen.getByText(/Valro/i)).toBeInTheDocument();
});

test('creates new task', async () => {
  render(<App />);
  // ... test implementation
});
```

## Conclusion

Run through all test scenarios before considering the POC complete. Focus on the end-to-end scenarios to ensure the full workflow works as expected.

For production deployment, implement automated testing with CI/CD pipelines.
