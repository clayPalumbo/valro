# Valro - AI-Powered Home Services Concierge

**An autonomous, agentic POC for connecting homeowners with local service providers**

Valro is an end-to-end proof-of-concept demonstrating how AI agents can autonomously handle home service requests. When a user describes what they need (e.g., "Find me a landscaper in Charlotte under $300"), Valro's AI agent:

1. Extracts service type, location, and budget
2. Finds matching vendors
3. Sends outreach emails on behalf of the user
4. Manages the entire workflow without human intervention

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   React UI  │─────▶│ API Gateway  │─────▶│ Lambda Backend  │─────▶│ AgentCore       │
│  (Amplify)  │      │  (HTTP API)  │      │   (Python)      │      │ Agent (Strands) │
└─────────────┘      └──────────────┘      └─────────────────┘      └─────────────────┘
                                                                              │
                                                                              ▼
                                                                     ┌─────────────────┐
                                                                     │ Tools:          │
                                                                     │ - getVendors    │
                                                                     │ - sendEmail     │
                                                                     └─────────────────┘
```

## Features

### 🤖 Autonomous Agent
- Powered by AWS Bedrock AgentCore with Claude Sonnet 4.5
- Natural language understanding
- Automatic task decomposition
- Tool-based execution (vendor search, email outreach)
- Memory integration for context retention

### 🎯 Smart Vendor Matching
- Extracts service type, location, and budget from natural language
- Returns relevant local service providers
- Supports landscaping, painting, cleaning, handyman services
- Extensible to real vendor databases

### 📧 Automated Outreach
- Drafts and sends personalized emails to vendors
- Logs all communications
- Ready for integration with AWS SES

### 💻 Modern Frontend
- Real-time task status updates
- Clean, responsive UI
- Task history and timeline
- Mobile-friendly design

### 🚀 Serverless Infrastructure
- Fully serverless (no servers to manage)
- Auto-scaling with Lambda and AgentCore
- Pay-per-use pricing model
- Built on AWS best practices

## Project Structure

```
valro/
├── agentcore-basic-demo/
│   └── agent-code/
│       ├── basic_agent.py        # AgentCore Strands agent with tools
│       ├── requirements.txt       # Python dependencies
│       └── Dockerfile            # Container for AgentCore
│
├── lambda-backend/
│   ├── lambda_function.py        # API handler for tasks
│   ├── requirements.txt          # Lambda dependencies
│   ├── iam-policy.json          # IAM permissions
│   ├── deploy.sh                # Deployment script
│   └── README.md                # Backend documentation
│
├── valro-ui/
│   ├── src/
│   │   ├── App.jsx              # Main React component
│   │   ├── App.css              # Styles
│   │   └── main.jsx             # Entry point
│   ├── package.json             # NPM dependencies
│   ├── vite.config.js           # Vite configuration
│   └── README.md                # Frontend documentation
│
├── DEPLOYMENT.md                 # Complete deployment guide
├── TESTING.md                    # Testing guide and scenarios
└── README.md                     # This file
```

## Quick Start

### Prerequisites

- AWS Account with CLI configured
- Node.js 18+
- Python 3.11+
- Git

### 1. Deploy the Agent

```bash
cd agentcore-basic-demo/agent-code

# Install AgentCore CLI (if not already installed)
pip install bedrock-agentcore-starter-toolkit

# Configure and deploy
agentcore configure --entrypoint basic_agent.py --name home_owner_concierge
agentcore launch

# Save the agent runtime ARN from the output
agentcore status --verbose
```

### 2. Deploy the Backend

```bash
cd lambda-backend

# Package Lambda
./deploy.sh

# Deploy (replace ACCOUNT_ID and AGENT_ARN)
aws lambda create-function \
  --function-name valro-backend \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/valro-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://valro-lambda.zip \
  --timeout 60 \
  --environment Variables="{AGENT_RUNTIME_ARN=YOUR_AGENT_ARN,AWS_REGION=us-east-1}"

# Create API Gateway (see DEPLOYMENT.md for detailed steps)
```

### 3. Deploy the Frontend

```bash
cd valro-ui

# Install dependencies
npm install

# Create .env file with your API Gateway URL
echo "VITE_API_BASE=https://your-api-id.execute-api.us-east-1.amazonaws.com" > .env

# Run locally
npm run dev

# Or deploy to Amplify (see DEPLOYMENT.md)
```

### 4. Test End-to-End

1. Open the frontend URL in your browser
2. Enter a task: "Find me a landscaper in Charlotte under $300"
3. Click "Create Task"
4. Watch the agent process the request and contact vendors!

## Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide with step-by-step instructions
- **[TESTING.md](TESTING.md)** - Testing guide with scenarios and debugging tips
- **[lambda-backend/README.md](lambda-backend/README.md)** - Backend API documentation
- **[valro-ui/README.md](valro-ui/README.md)** - Frontend setup and deployment options

## Technology Stack

### Backend
- **AWS Bedrock AgentCore** - Agent runtime with built-in memory
- **Strands** - Agent framework for tool integration
- **Claude Sonnet 4.5** - LLM for natural language understanding
- **AWS Lambda** - Serverless compute
- **API Gateway** - HTTP API for frontend communication

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool and dev server
- **Native CSS** - No external CSS frameworks

### Infrastructure
- **AWS IAM** - Security and permissions
- **CloudWatch** - Logging and monitoring
- **Amplify or S3+CloudFront** - Frontend hosting

## Key Components

### 1. AgentCore Agent ([basic_agent.py](agentcore-basic-demo/agent-code/basic_agent.py))

The heart of Valro - an autonomous agent with:
- **Valro Persona**: Concierge mindset, action-oriented
- **getVendors Tool**: Searches mock vendor database
- **sendEmail Tool**: Sends outreach emails
- **Memory Integration**: Remembers user preferences and history

### 2. Lambda Backend ([lambda_function.py](lambda-backend/lambda_function.py))

RESTful API with three endpoints:
- `POST /tasks` - Create new task and invoke agent
- `GET /tasks` - List all tasks
- `GET /tasks/{id}` - Get task details (polled by frontend)

In-memory task storage (ready for DynamoDB migration).

### 3. React Frontend ([App.jsx](valro-ui/src/App.jsx))

Modern, single-page application with:
- Task creation form
- Task list with status badges
- Real-time polling (3-second updates)
- Activity timeline
- Responsive design

## Example Workflows

### Workflow 1: Landscaping Request

**User Input:** "Find me a landscaper in Charlotte under $300"

**Agent Processing:**
1. Extracts: service=landscaping, city=Charlotte, budget=300
2. Calls `getVendors("landscaping", "Charlotte", 300)`
3. Receives 3 vendors: Greenline Lawn, Queen City Turf, Uptown Yard
4. Calls `sendEmail` 3 times (one per vendor)
5. Responds: "I've contacted 3 landscaping vendors in Charlotte. They should respond within 24-48 hours."

**User Experience:**
- Task shows "processing" → "completed"
- Agent response visible in UI
- 3 email logs in CloudWatch

### Workflow 2: Painting Request

**User Input:** "I need my house painted, I'm in Raleigh"

**Agent Processing:**
1. Extracts: service=painting, city=Raleigh
2. Calls `getVendors("painting", "Raleigh")`
3. Fallback: Returns Charlotte painters (Raleigh not in mock DB)
4. Sends 2 emails
5. Responds with vendor information

## Current Limitations (POC)

This is a proof-of-concept with intentional simplifications:

- ✅ **Mock vendor database** - Hardcoded vendors in agent code
- ✅ **Email logging only** - Emails printed to logs, not actually sent
- ✅ **In-memory storage** - Tasks lost on Lambda cold start
- ✅ **No authentication** - Open API (add Cognito for production)
- ✅ **Basic error handling** - Minimal retry logic
- ✅ **Polling for updates** - Frontend polls every 3s (use WebSockets for production)

## Production Roadiness

To make this production-ready:

### Required Changes
1. **Vendor Database** - Replace mock data with real database (DynamoDB, RDS)
2. **Email Integration** - Use AWS SES to actually send emails
3. **Persistence** - Migrate from in-memory to DynamoDB
4. **Authentication** - Add Cognito user pools
5. **Authorization** - Implement fine-grained access control

### Recommended Enhancements
1. **WebSockets** - Replace polling with real-time updates (API Gateway WebSocket)
2. **Quote Collection** - Workflow for vendors to submit quotes
3. **Payment Integration** - Stripe/Dwolla for deposits
4. **Scheduling** - Calendar integration for appointments
5. **Notifications** - Email/SMS updates (SNS)
6. **Reviews** - Vendor rating system
7. **Analytics** - Track conversion rates, response times
8. **Multi-tenancy** - Support for multiple homeowners

## Cost Estimate

For **POC/Development** usage (~100 tasks/month):

| Service | Monthly Cost |
|---------|-------------|
| AgentCore Runtime | $0 (free tier during preview) |
| Lambda (100 invocations) | ~$0.20 |
| API Gateway (1K requests) | ~$1.00 |
| Amplify Hosting | ~$12.00 |
| **Total** | **~$13/month** |

For **Production** usage (10K tasks/month):
- Estimate ~$150-300/month depending on agent complexity and data storage

## Security Considerations

### Current Implementation
- ✅ CORS enabled for frontend domain
- ✅ IAM least-privilege policies
- ✅ No secrets in code (environment variables)
- ✅ CloudWatch logging enabled

### Production Requirements
- 🔒 Add WAF rules for API Gateway
- 🔒 Implement rate limiting
- 🔒 Enable CloudTrail for audit logs
- 🔒 Add DDoS protection (Shield)
- 🔒 Encrypt data at rest (DynamoDB encryption)
- 🔒 Regular security audits
- 🔒 Secrets Manager for API keys

## Monitoring

View logs in real-time:

```bash
# Lambda logs
aws logs tail /aws/lambda/valro-backend --follow

# AgentCore logs
aws logs tail /aws/bedrock-agentcore/home_owner_concierge --follow

# Filter for errors
aws logs tail /aws/lambda/valro-backend --filter-pattern "ERROR" --follow
```

## Troubleshooting

See [TESTING.md](TESTING.md) for comprehensive debugging guide.

**Common Issues:**
- **Agent not responding** → Check AGENT_RUNTIME_ARN and IAM permissions
- **CORS errors** → Verify API Gateway CORS configuration
- **Empty task list** → Expected with in-memory storage (tasks ephemeral)
- **504 timeout** → Increase Lambda timeout to 60+ seconds

## Contributing

This is a POC project. For enhancements:

1. Test thoroughly (see [TESTING.md](TESTING.md))
2. Update documentation
3. Follow AWS best practices
4. Consider security implications

## Cleanup

To remove all resources:

```bash
# Delete AgentCore agent
agentcore destroy --agent home_owner_concierge --force

# Delete Lambda
aws lambda delete-function --function-name valro-backend

# Delete API Gateway
aws apigatewayv2 delete-api --api-id YOUR_API_ID

# Delete frontend (Amplify)
aws amplify delete-app --app-id YOUR_APP_ID

# Delete IAM resources
aws iam delete-role-policy --role-name valro-lambda-role --policy-name ValroLambdaPolicy
aws iam delete-role --role-name valro-lambda-role
```

## License

Proof-of-concept project for demonstration purposes.

## Acknowledgments

Built with:
- AWS Bedrock AgentCore
- Anthropic Claude
- Strands Agent Framework
- React & Vite

---

**🏡 Valro - Making home services simple, one task at a time.**

For questions or issues, see [TESTING.md](TESTING.md) for debugging tips.
