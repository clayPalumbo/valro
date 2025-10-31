"""
Valro Worker Lambda
Handles asynchronous agent processing for home service tasks
"""
import json
import os
from datetime import datetime, timezone
import boto3
from dynamodb_helpers import (
    get_task,
    update_task_status,
    add_task_event,
    update_task_with_agent_response
)

# AWS clients
bedrock_agentcore_client = boto3.client(
    "bedrock-agentcore",
    region_name=os.environ.get("AWS_REGION", "us-east-1")
)

# AgentCore configuration from environment variables
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN")
if not AGENT_RUNTIME_ARN:
    print("WARNING: AGENT_RUNTIME_ARN not set")


def lambda_handler(event, context):
    """
    Worker Lambda handler - invoked asynchronously by API Lambda

    Expected event format:
    {
        "task_id": "uuid",
        "description": "user's task description"
    }
    """
    print(f"Worker Lambda invoked with event: {json.dumps(event)}")

    task_id = event.get('task_id')
    description = event.get('description')

    if not task_id or not description:
        print(f"ERROR: Missing required fields. task_id={task_id}, description={description}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing task_id or description'})
        }

    try:
        # Verify task exists
        task = get_task(task_id)
        if not task:
            print(f"ERROR: Task {task_id} not found in DynamoDB")
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Task not found'})
            }

        # Update status to processing
        print(f"Starting agent processing for task {task_id}")
        update_task_status(task_id, "processing")
        add_task_event(task_id, "Agent processing started", "info")

        # Invoke the agent
        agent_response = invoke_agent(task_id, description)

        # Update task with successful response
        update_task_with_agent_response(
            task_id,
            agent_response.get('response', ''),
            vendors=agent_response.get('vendors', []),
            emails_sent=agent_response.get('emails_sent', 0)
        )

        # Mark as completed
        update_task_status(task_id, "completed")
        add_task_event(task_id, "Agent completed task successfully", "success")

        print(f"Task {task_id} completed successfully")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'task_id': task_id,
                'status': 'completed',
                'message': 'Agent processing completed'
            })
        }

    except Exception as e:
        print(f"ERROR processing task {task_id}: {str(e)}")

        # Update task with error status
        try:
            update_task_status(task_id, "error", error_message=str(e))
            add_task_event(task_id, f"Agent error: {str(e)}", "error")
        except Exception as update_error:
            print(f"ERROR updating task status: {str(update_error)}")

        return {
            'statusCode': 500,
            'body': json.dumps({
                'task_id': task_id,
                'status': 'error',
                'error': str(e)
            })
        }


def invoke_agent(task_id, user_input):
    """
    Invoke the AWS Bedrock AgentCore agent

    Args:
        task_id (str): Task ID for logging
        user_input (str): User's task description

    Returns:
        dict: {
            'response': agent response text,
            'vendors': list of vendors contacted,
            'emails_sent': number of emails sent
        }
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

        # Parse response
        status_code = response.get('statusCode', response.get('ResponseMetadata', {}).get('HTTPStatusCode'))
        print(f"Agent response status: {status_code}")

        # Read the streaming response body
        response_stream = response.get('response')
        if response_stream:
            response_bytes = response_stream.read()
            response_text = response_bytes.decode('utf-8')
            print(f"Agent response body: {response_text}")
            response_body = json.loads(response_text)
        else:
            print("No response body found")
            response_body = {}

        # Check if successful
        if status_code != 200:
            raise Exception(f"Agent returned status {status_code}")

        # Extract information from response
        agent_text = response_body.get("response", "")
        vendors = response_body.get("vendors", [])
        emails = response_body.get("emails", [])
        emails_sent = response_body.get("emails_sent", 0)

        print(f"Agent processing complete:")
        print(f"  - Response: {agent_text[:200]}...")
        print(f"  - Vendors: {len(vendors)}")
        print(f"  - Emails sent: {emails_sent}")

        # Store email details in vendors list for display
        # Match emails to vendors by email address
        for vendor in vendors:
            vendor_email = vendor.get('email', '')
            # Find matching emails sent to this vendor
            vendor['emails'] = [e for e in emails if e.get('recipient') == vendor_email]

        return {
            'response': agent_text,
            'vendors': vendors,
            'emails_sent': emails_sent
        }

    except Exception as e:
        print(f"Error invoking agent: {e}")
        raise


# For local testing
if __name__ == "__main__":
    # Test event
    test_event = {
        "task_id": "test-uuid-12345",
        "description": "Find me a landscaper in Charlotte under $300"
    }

    # Note: This will fail locally without proper AWS credentials and DynamoDB setup
    result = lambda_handler(test_event, None)
    print("\nTest result:")
    print(json.dumps(result, indent=2))
