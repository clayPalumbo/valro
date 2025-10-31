"""
Valro - Autonomous Home Services Concierge Agent
Built on AWS Bedrock AgentCore with Strands
"""
import os
import json
from datetime import datetime, timezone
from strands import Agent, tool
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

MEMORY_ID = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
REGION = os.getenv("AWS_REGION")
MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

ci_sessions = {}
current_session = None

# Track tool executions for response
tool_executions = {
    'vendors': [],
    'emails': []
}

# Mock vendor database for POC
VENDOR_DATABASE = {
    "landscaping": {
        "charlotte": [
            {"id": "vendor_1", "name": "Greenline Lawn", "email": "quotes+greenline@example.com", "service": "landscaping", "city": "Charlotte"},
            {"id": "vendor_2", "name": "Queen City Turf", "email": "quotes+qcturf@example.com", "service": "landscaping", "city": "Charlotte"},
            {"id": "vendor_3", "name": "Uptown Yard", "email": "quotes+uptown@example.com", "service": "landscaping", "city": "Charlotte"}
        ],
        "raleigh": [
            {"id": "vendor_4", "name": "Capital Landscapes", "email": "quotes+capital@example.com", "service": "landscaping", "city": "Raleigh"},
            {"id": "vendor_5", "name": "Triangle Green", "email": "quotes+triangle@example.com", "service": "landscaping", "city": "Raleigh"}
        ]
    },
    "painting": {
        "charlotte": [
            {"id": "vendor_6", "name": "Perfect Paint Co", "email": "quotes+perfectpaint@example.com", "service": "painting", "city": "Charlotte"},
            {"id": "vendor_7", "name": "Charlotte Painters", "email": "quotes+cltpainters@example.com", "service": "painting", "city": "Charlotte"}
        ]
    },
    "cleaning": {
        "charlotte": [
            {"id": "vendor_8", "name": "Sparkle Clean", "email": "quotes+sparkle@example.com", "service": "cleaning", "city": "Charlotte"},
            {"id": "vendor_9", "name": "Fresh Home Services", "email": "quotes+fresh@example.com", "service": "cleaning", "city": "Charlotte"}
        ]
    },
    "handyman": {
        "charlotte": [
            {"id": "vendor_10", "name": "Fix It Fast", "email": "quotes+fixit@example.com", "service": "handyman", "city": "Charlotte"},
            {"id": "vendor_11", "name": "Home Repair Pro", "email": "quotes+homerepair@example.com", "service": "handyman", "city": "Charlotte"}
        ]
    }
}

@tool
def getVendors(service: str, city: str, budget: float = None) -> str:
    """
    Return a list of vendors for a given home-service request.

    Args:
        service: Type of service (e.g., landscaping, painting, cleaning, handyman)
        city: City or area to search in
        budget: Optional maximum budget if provided by user

    Returns:
        JSON string with list of matching vendors
    """
    service_lower = service.lower()
    city_lower = city.lower()

    # Try to find matching vendors
    vendors = []
    if service_lower in VENDOR_DATABASE:
        if city_lower in VENDOR_DATABASE[service_lower]:
            vendors = VENDOR_DATABASE[service_lower][city_lower]
        else:
            # If specific city not found, return first available city's vendors
            first_city = list(VENDOR_DATABASE[service_lower].keys())[0]
            vendors = VENDOR_DATABASE[service_lower][first_city]
    else:
        # Default fallback - return Charlotte landscaping vendors
        vendors = VENDOR_DATABASE["landscaping"]["charlotte"]

    # Track vendors for response
    tool_executions['vendors'] = vendors

    result = {
        "vendors": vendors,
        "matched_service": service,
        "matched_city": city,
        "budget_filter": budget,
        "count": len(vendors)
    }

    return json.dumps(result, indent=2)

@tool
def sendEmail(to: str, subject: str, body: str, taskId: str = None) -> str:
    """
    Send an outreach email to a vendor about a homeowner's request.

    Args:
        to: Vendor email address
        subject: Email subject line
        body: Email content/body
        taskId: Optional task ID to correlate in the app

    Returns:
        JSON string with send status
    """
    # Log the email (for POC, we don't actually send)
    timestamp = datetime.now(timezone.utc).isoformat()

    print(f"[EMAIL SENT] {timestamp}")
    print(f"To: {to}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")
    print(f"Task ID: {taskId}")
    print("-" * 80)

    # Track email for response
    email_record = {
        "recipient": to,
        "subject": subject,
        "body": body,
        "timestamp": timestamp
    }
    tool_executions['emails'].append(email_record)

    return json.dumps({
        "status": "sent",
        "timestamp": timestamp,
        "recipient": to,
        "message": "Email sent successfully"
    })

@tool
def calculate(code: str) -> str:
    """Execute Python code for calculations or analysis."""
    session_id = current_session or 'default'

    if session_id not in ci_sessions:
        ci_sessions[session_id] = {
            'client': CodeInterpreter(REGION),
            'session_id': None
        }

    ci = ci_sessions[session_id]
    if not ci['session_id']:
        ci['session_id'] = ci['client'].start(
            name=f"session_{session_id[:30]}",
            session_timeout_seconds=1800
        )

    result = ci['client'].invoke("executeCode", {
        "code": code,
        "language": "python"
    })

    for event in result.get("stream", []):
        if stdout := event.get("result", {}).get("structuredContent", {}).get("stdout"):
            return stdout
    return "Executed"

@app.entrypoint
def invoke(payload, context):
    global current_session, tool_executions

    # Reset tool execution tracking for this invocation
    tool_executions = {
        'vendors': [],
        'emails': []
    }

    if not MEMORY_ID:
        return {"error": "Memory not configured"}

    actor_id = context.headers.get('X-Amzn-Bedrock-AgentCore-Runtime-Custom-Actor-Id', 'user') if hasattr(context, 'headers') else 'user'

    session_id = getattr(context, 'session_id', 'default')
    current_session = session_id

    memory_config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        session_id=session_id,
        actor_id=actor_id,
        retrieval_config={
            f"/users/{actor_id}/facts": RetrievalConfig(top_k=3, relevance_score=0.5),
            f"/users/{actor_id}/preferences": RetrievalConfig(top_k=3, relevance_score=0.5)
        }
    )

    # Valro system prompt
    valro_system_prompt = """You are Valro, an autonomous home-services concierge. Your purpose is to help homeowners get real work done with local service providers (landscaping, lawn care, cleaning, handyman, painting, small renovations, seasonal services).

When a user describes what they need, you must:

1. Understand the request and extract: service type, location/city, budget (if present), and timing.

2. Call the getVendors tool to retrieve matching vendors.

3. For each returned vendor, call the sendEmail tool to initiate outreach on behalf of the user.

4. Then tell the user that outreach has been sent and that you are waiting for vendor replies.

Assume this is a long-running task: the user SHOULD NOT have to call, text, or email vendors themselves unless all automated attempts fail. Prefer taking action over asking follow-up questions. Keep responses clear and brief."""

    agent = Agent(
        model=MODEL_ID,
        session_manager=AgentCoreMemorySessionManager(memory_config, REGION),
        system_prompt=valro_system_prompt,
        tools=[getVendors, sendEmail]
    )

    result = agent(payload.get("prompt", ""))

    # Extract text response
    text_response = result.message.get('content', [{}])[0].get('text', str(result))

    # Return tracked tool execution data
    return {
        "response": text_response,
        "vendors": tool_executions.get('vendors', []),
        "emails": tool_executions.get('emails', []),
        "emails_sent": len(tool_executions.get('emails', []))
    }

if __name__ == "__main__":
    app.run()