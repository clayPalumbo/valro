"""
DynamoDB Helper Functions for Valro Task Management
Shared utilities for both API and Worker Lambdas
"""
import os
from datetime import datetime, timezone
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'valro-tasks')


def get_table():
    """Get DynamoDB table reference"""
    return dynamodb.Table(TABLE_NAME)


def create_task(task):
    """
    Create a new task in DynamoDB

    Args:
        task (dict): Task object with all required fields

    Returns:
        dict: The created task
    """
    table = get_table()

    # Convert datetime objects to ISO strings if needed
    task_copy = _prepare_item_for_dynamodb(task)

    table.put_item(Item=task_copy)
    return task


def get_task(task_id):
    """
    Get a task by ID

    Args:
        task_id (str): Task ID

    Returns:
        dict: Task object or None if not found
    """
    table = get_table()

    try:
        response = table.get_item(Key={'id': task_id})
        return response.get('Item')
    except Exception as e:
        print(f"Error getting task {task_id}: {e}")
        return None


def update_task_status(task_id, status, error_message=None):
    """
    Update task status

    Args:
        task_id (str): Task ID
        status (str): New status (pending, processing, completed, error)
        error_message (str, optional): Error message if status is 'error'

    Returns:
        dict: Updated task
    """
    table = get_table()

    update_expression = "SET #status = :status, updated_at = :updated_at"
    expression_values = {
        ':status': status,
        ':updated_at': datetime.now(timezone.utc).isoformat()
    }
    expression_names = {
        '#status': 'status'  # 'status' might be a reserved word
    }

    if error_message:
        update_expression += ", error_message = :error_message"
        expression_values[':error_message'] = error_message

    try:
        response = table.update_item(
            Key={'id': task_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_names,
            ReturnValues='ALL_NEW'
        )
        return response.get('Attributes')
    except Exception as e:
        print(f"Error updating task status for {task_id}: {e}")
        raise


def add_task_event(task_id, message, event_type="info"):
    """
    Add an event to the task's event timeline

    Args:
        task_id (str): Task ID
        message (str): Event message
        event_type (str): Event type (info, success, error)

    Returns:
        dict: Updated task
    """
    table = get_table()

    event = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'message': message,
        'type': event_type
    }

    try:
        response = table.update_item(
            Key={'id': task_id},
            UpdateExpression="SET events = list_append(if_not_exists(events, :empty_list), :event), updated_at = :updated_at",
            ExpressionAttributeValues={
                ':event': [event],
                ':empty_list': [],
                ':updated_at': datetime.now(timezone.utc).isoformat()
            },
            ReturnValues='ALL_NEW'
        )
        return response.get('Attributes')
    except Exception as e:
        print(f"Error adding event to task {task_id}: {e}")
        raise


def update_task_with_agent_response(task_id, agent_response, vendors=None, emails_sent=0):
    """
    Update task with agent response and results

    Args:
        task_id (str): Task ID
        agent_response (str): Agent's response text
        vendors (list, optional): List of vendors contacted
        emails_sent (int): Number of emails sent

    Returns:
        dict: Updated task
    """
    table = get_table()

    update_expression = "SET agent_response = :agent_response, emails_sent = :emails_sent, updated_at = :updated_at"
    expression_values = {
        ':agent_response': agent_response,
        ':emails_sent': emails_sent,
        ':updated_at': datetime.now(timezone.utc).isoformat()
    }

    if vendors:
        update_expression += ", vendors = :vendors"
        expression_values[':vendors'] = vendors

    try:
        response = table.update_item(
            Key={'id': task_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues='ALL_NEW'
        )
        return response.get('Attributes')
    except Exception as e:
        print(f"Error updating task with agent response for {task_id}: {e}")
        raise


def list_tasks(limit=50, last_evaluated_key=None):
    """
    List all tasks with pagination

    Args:
        limit (int): Maximum number of tasks to return
        last_evaluated_key (dict, optional): Pagination key from previous request

    Returns:
        dict: {
            'tasks': list of tasks,
            'last_evaluated_key': pagination key for next page (None if no more pages)
        }
    """
    table = get_table()

    scan_kwargs = {
        'Limit': limit
    }

    if last_evaluated_key:
        scan_kwargs['ExclusiveStartKey'] = last_evaluated_key

    try:
        response = table.scan(**scan_kwargs)

        tasks = response.get('Items', [])

        # Sort by created_at descending (newest first)
        tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return {
            'tasks': tasks,
            'last_evaluated_key': response.get('LastEvaluatedKey')
        }
    except Exception as e:
        print(f"Error listing tasks: {e}")
        raise


def _prepare_item_for_dynamodb(item):
    """
    Prepare an item for DynamoDB by converting incompatible types

    Args:
        item (dict): Item to prepare

    Returns:
        dict: Prepared item
    """
    if isinstance(item, dict):
        return {k: _prepare_item_for_dynamodb(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [_prepare_item_for_dynamodb(v) for v in item]
    elif isinstance(item, float):
        return Decimal(str(item))
    else:
        return item
