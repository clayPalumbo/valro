"""
Valro Lambda Backend - API Handler
Serverless API for managing home service tasks with AgentCore integration
Now with asynchronous processing and DynamoDB persistence
"""
import json
import os
import uuid
from datetime import datetime, timezone
import boto3
from dynamodb_helpers import (
    create_task,
    get_task,
    list_tasks,
    add_task_event
)

# AWS clients
lambda_client = boto3.client('lambda', region_name=os.environ.get("AWS_REGION", "us-east-1"))

# Environment variables
WORKER_LAMBDA_ARN = os.environ.get("WORKER_LAMBDA_ARN")
if not WORKER_LAMBDA_ARN:
    print("WARNING: WORKER_LAMBDA_ARN not set")


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
    """Create a new task and invoke Worker Lambda asynchronously"""
    try:
        body = json.loads(event.get("body") or "{}")
        description = body.get("description", "")

        if not description:
            return _cors_response(400, {"error": "Description is required"})

        # Create task with pending status
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "description": description,
            "status": "pending",
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

        # Save task to DynamoDB
        create_task(task)
        print(f"Task {task_id} created in DynamoDB")

        # Invoke Worker Lambda asynchronously
        try:
            worker_payload = {
                "task_id": task_id,
                "description": description
            }

            response = lambda_client.invoke(
                FunctionName=WORKER_LAMBDA_ARN,
                InvocationType='Event',  # Asynchronous invocation
                Payload=json.dumps(worker_payload)
            )

            print(f"Worker Lambda invoked: StatusCode={response.get('StatusCode')}")

            # Add event for successful worker invocation
            add_task_event(task_id, "Worker Lambda invoked - processing started", "info")

        except Exception as e:
            print(f"Error invoking Worker Lambda: {e}")
            # Update task status to error in DynamoDB
            from dynamodb_helpers import update_task_status
            update_task_status(task_id, "error", error_message=f"Failed to invoke worker: {str(e)}")
            add_task_event(task_id, f"Error invoking worker: {str(e)}", "error")

            return _cors_response(500, {
                "id": task_id,
                "status": "error",
                "error": f"Failed to start processing: {str(e)}"
            })

        # Return 202 Accepted - processing has started
        return _cors_response(202, {
            "id": task_id,
            "status": "pending",
            "message": "Task created and processing started"
        })

    except Exception as e:
        print(f"Error creating task: {e}")
        return _cors_response(500, {"error": f"Internal server error: {str(e)}"})


def handle_list_tasks():
    """Return all tasks from DynamoDB"""
    try:
        result = list_tasks(limit=50)
        tasks_list = result.get('tasks', [])

        print(f"Retrieved {len(tasks_list)} tasks from DynamoDB")

        return _cors_response(200, tasks_list)
    except Exception as e:
        print(f"Error listing tasks: {e}")
        return _cors_response(500, {"error": f"Internal server error: {str(e)}"})


def handle_get_task(task_id):
    """Get a specific task by ID from DynamoDB"""
    try:
        task = get_task(task_id)
        if not task:
            return _cors_response(404, {"error": "Task not found", "task_id": task_id})

        print(f"Retrieved task {task_id} with status: {task.get('status')}")
        return _cors_response(200, task)
    except Exception as e:
        print(f"Error getting task: {e}")
        return _cors_response(500, {"error": f"Internal server error: {str(e)}"})


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
    print("=== Valro API Lambda Local Test ===")
    print("Note: This requires AWS credentials and DynamoDB table to be set up")
    print()

    # Test event for creating a task
    test_event = {
        "httpMethod": "POST",
        "path": "/tasks",
        "body": json.dumps({"description": "Find me a landscaper in Charlotte under $300"})
    }

    print("Test: Creating a new task")
    result = lambda_handler(test_event, None)
    print("\nResult:")
    print(json.dumps(result, indent=2))
