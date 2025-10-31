"""
Valro Lambda Backend
Serverless API for managing home service tasks with AgentCore integration
"""
import json
import os
import uuid
from datetime import datetime, timezone
import boto3

# In-memory task store for POC (replace with DynamoDB for production)
TASKS = {}

# AWS clients
bedrock_agentcore_client = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1"))
# Lambda client to invoke a worker asynchronously (defaults to this function)
lambda_client = boto3.client("lambda", region_name=os.environ.get("AWS_REGION", "us-east-1"))

# Worker function name/ARN to invoke for processing heavy/long-running tasks.
# By default, use the current function name so the same Lambda can act as a worker.
WORKER_LAMBDA_NAME = os.environ.get("WORKER_LAMBDA_NAME") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")

# AgentCore configuration from environment variables
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN")
if not AGENT_RUNTIME_ARN:
    print("WARNING: AGENT_RUNTIME_ARN not set. Using default.")
    AGENT_RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:975150127262:runtime/home_owner_concierge-tBcmf45NFO"


def lambda_handler(event, context):
    """
    API Gateway (HTTP API) compatible handler.
    Supports:
    - POST /tasks - Create a new task
    - GET /tasks - List all tasks
    - GET /tasks/{id} - Get specific task details
    """
    print(f"Received event: {json.dumps(event)}")

    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    raw_path = event.get("path") or event.get("rawPath", "")

    # Handle CORS preflight
    if method == "OPTIONS":
        return _cors_response(200, {"ok": True})

    # Internal async worker invocation payloads will set {"action": "process_task", ...}
    # This branch allows the same Lambda to be invoked asynchronously to do long-running work.
    if isinstance(event, dict) and event.get("action") == "process_task":
        task_id = event.get("task_id")
        description = event.get("description")
        if not task_id or not description:
            return _cors_response(400, {"error": "Missing task_id or description for process_task"})
        try:
            _invoke_agent(task_id, description)
            return _cors_response(200, {"ok": True, "task_id": task_id})
        except Exception as e:
            print(f"Worker error invoking agent for {task_id}: {e}")
            return _cors_response(500, {"error": str(e)})

    # Route handling
    if method == "POST" and raw_path == "/tasks":
        return handle_create_task(event)

    if method == "GET" and raw_path == "/tasks":
        return handle_list_tasks()

    if method == "GET" and raw_path.startswith("/tasks/"):
        task_id = raw_path.split("/")[-1]
        return handle_get_task(task_id)

    return _cors_response(404, {"error": "Not found", "path": raw_path, "method": method})


def handle_create_task(event):
    """Create a new task and invoke AgentCore agent"""
    try:
        body = json.loads(event.get("body") or "{}")
        description = body.get("description", "")

        if not description:
            return _cors_response(400, {"error": "Description is required"})

        # Create task
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "description": description,
            "status": "processing",
            "vendors": [],
            "quotes": [],
            "emails_sent": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "events": [
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "message": "Task created",
                    "type": "info"
                }
            ],
        }

        TASKS[task_id] = task

        # Queue work to a worker Lambda asynchronously so API returns quickly.
        invoke_payload = {
            "action": "process_task",
            "task_id": task_id,
            "description": description,
        }
        try:
            print(f"Invoking worker Lambda {WORKER_LAMBDA_NAME} for task {task_id}")
            lambda_client.invoke(
                FunctionName=WORKER_LAMBDA_NAME,
                InvocationType='Event',  # asynchronous
                Payload=json.dumps(invoke_payload).encode('utf-8')
            )
            task["events"].append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "message": "Agent queued for processing",
                "type": "info"
            })
            # Return 202 Accepted semantics to client
            task["status"] = "queued"
        except Exception as e:
            print(f"Error invoking worker Lambda: {e}")
            # Fallback: attempt synchronous invocation (best-effort)
            try:
                _invoke_agent(task_id, description)
                task["events"].append({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "message": "Agent invoked synchronously after async invoke failed",
                    "type": "warning"
                })
            except Exception as e2:
                print(f"Fallback sync invoke failed: {e2}")
                task["status"] = "error"
                task["events"].append({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "message": f"Error invoking agent: {str(e2)}",
                    "type": "error"
                })

        task["updated_at"] = datetime.now(timezone.utc).isoformat()

        # If we queued the work, return 202 Accepted to indicate processing
        if task["status"] == "queued":
            return _cors_response(202, {
                "id": task_id,
                "status": task["status"],
                "message": "Task queued for processing"
            })

        return _cors_response(200, {
            "id": task_id,
            "status": task["status"],
            "message": "Task created successfully"
        })

    except Exception as e:
        print(f"Error creating task: {e}")
        return _cors_response(500, {"error": f"Internal server error: {str(e)}"})


def handle_list_tasks():
    """Return all tasks"""
    try:
        tasks_list = list(TASKS.values())
        # Sort by created_at descending (newest first)
        tasks_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return _cors_response(200, tasks_list)
    except Exception as e:
        print(f"Error listing tasks: {e}")
        return _cors_response(500, {"error": f"Internal server error: {str(e)}"})


def handle_get_task(task_id):
    """Get a specific task by ID"""
    try:
        task = TASKS.get(task_id)
        if not task:
            return _cors_response(404, {"error": "Task not found", "task_id": task_id})
        return _cors_response(200, task)
    except Exception as e:
        print(f"Error getting task: {e}")
        return _cors_response(500, {"error": f"Internal server error: {str(e)}"})


def _invoke_agent(task_id: str, user_input: str):
    """
    Invoke the AWS Bedrock AgentCore agent.

    Note: For POC, we're making a simple invocation. In production, you would:
    1. Stream the response to parse tool calls in real-time
    2. Update the task state based on tool execution
    3. Handle errors and retries
    """
    try:
        print(f"Invoking AgentCore agent for task {task_id}")
        print(f"Agent Runtime ARN: {AGENT_RUNTIME_ARN}")
        print(f"User input: {user_input}")

        # Prepare the payload
        payload = json.dumps({"prompt": user_input})

        # Invoke agent runtime
        response = bedrock_agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            payload=payload.encode('utf-8')
        )

        # Parse response - AgentCore returns a streaming response
        status_code = response.get('statusCode', response.get('ResponseMetadata', {}).get('HTTPStatusCode'))
        print(f"Agent response status: {status_code}")

        # Read the streaming response body
        response_stream = response.get('response')
        if response_stream:
            # Read the entire stream
            response_bytes = response_stream.read()
            response_text = response_bytes.decode('utf-8')
            print(f"Agent response body: {response_text}")
            response_body = json.loads(response_text)
        else:
            print("No response body found")
            response_body = {}

        # Check if successful
        if status_code == 200:
            # Update task with response
            task = TASKS.get(task_id)
            if task:
                task["status"] = "completed"
                task["agent_response"] = response_body.get("response", "")
                task["updated_at"] = datetime.now(timezone.utc).isoformat()
                task["events"].append({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "message": "Agent completed task",
                    "type": "success"
                })

                # Try to parse vendors from response (basic extraction)
                # In production, you'd parse the actual tool calls from the agent
                if "vendor" in response_body.get("response", "").lower():
                    task["events"].append({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "message": "Vendors contacted - awaiting responses",
                        "type": "info"
                    })
        else:
            raise Exception(f"Agent returned status {status_code}")

    except Exception as e:
        print(f"Error invoking agent: {e}")
        task = TASKS.get(task_id)
        if task:
            task["status"] = "error"
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
            task["events"].append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "message": f"Agent error: {str(e)}",
                "type": "error"
            })
        raise


def _cors_response(status_code: int, body):
    """Generate CORS-enabled API Gateway response"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        },
        "body": json.dumps(body, default=str)
    }


# For local testing
if __name__ == "__main__":
    # Test event
    test_event = {
        "httpMethod": "POST",
        "path": "/tasks",
        "body": json.dumps({"description": "Find me a landscaper in Charlotte under $300"})
    }

    result = lambda_handler(test_event, None)
    print("\nTest result:")
    print(json.dumps(result, indent=2))
