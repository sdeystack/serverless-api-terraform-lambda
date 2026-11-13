"""Serverless items API handler (API Gateway HTTP API, payload format 2.0).

Routes:
    POST   /items       Create an item
    GET    /items       List items
    GET    /items/{id}  Get one item
    DELETE /items/{id}  Delete one item

The handler is deliberately small so it can be explained end to end in an
interview: parse and validate input, call DynamoDB with the least-privilege
role attached to the function, return a structured JSON response, and log
failures without leaking internal details to the caller.

Environment variables:
    TABLE_NAME: DynamoDB table name, set by Terraform.
"""

import base64
import datetime
import json
import logging
import os
import uuid

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_table = None


def _get_table():
    """Return the DynamoDB table, creating the resource lazily.

    Lazy creation keeps unit tests fast and avoids touching AWS at import
    time. Tests replace ``_table`` with a mock.
    """
    global _table
    if _table is None:
        dynamodb = boto3.resource("dynamodb")
        _table = dynamodb.Table(os.environ["TABLE_NAME"])
    return _table


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _response(status_code, body=None):
    payload = body if body is not None else {}
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(payload),
    }


def _error(status_code, message):
    return _response(status_code, {"error": message})


def _parse_body(event):
    raw_body = event.get("body")
    if raw_body is None:
        return None, "Request body is required."
    if event.get("isBase64Encoded"):
        try:
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None, "Request body must be valid base64-encoded UTF-8 JSON."
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return None, "Request body must be valid JSON."
    if not isinstance(parsed, dict):
        return None, "Request body must be a JSON object."
    return parsed, None


def _validate_item_payload(payload):
    """Return (name, description, error_message)."""
    name = payload.get("name")
    description = payload.get("description", "")
    if not isinstance(name, str) or not name.strip():
        return None, None, "Field 'name' is required and must be a non-empty string."
    if len(name.strip()) > 200:
        return None, None, "Field 'name' must be 200 characters or fewer."
    if description is None:
        description = ""
    if not isinstance(description, str):
        return None, None, "Field 'description' must be a string."
    if len(description) > 2000:
        return None, None, "Field 'description' must be 2000 characters or fewer."
    return name.strip(), description, None


def _create_item(event):
    payload, parse_error = _parse_body(event)
    if parse_error:
        return _error(400, parse_error)
    name, description, validation_error = _validate_item_payload(payload)
    if validation_error:
        return _error(400, validation_error)

    item = {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "created_at": _now_iso(),
    }
    try:
        _get_table().put_item(Item=item)
    except ClientError:
        logger.exception("DynamoDB put_item failed")
        return _error(500, "Could not save the item. Please try again.")
    return _response(201, {"item": item})


def _list_items():
    try:
        result = _get_table().scan()
    except ClientError:
        logger.exception("DynamoDB scan failed")
        return _error(500, "Could not list items. Please try again.")
    items = result.get("Items", [])
    items.sort(key=lambda x: x.get("created_at", ""))
    return _response(200, {"items": items, "count": len(items)})


def _get_item(item_id):
    if not item_id:
        return _error(400, "Path parameter 'id' is required.")
    try:
        result = _get_table().get_item(Key={"id": item_id})
    except ClientError:
        logger.exception("DynamoDB get_item failed")
        return _error(500, "Could not fetch the item. Please try again.")
    item = result.get("Item")
    if not item:
        return _error(404, "Item not found.")
    return _response(200, {"item": item})


def _delete_item(item_id):
    if not item_id:
        return _error(400, "Path parameter 'id' is required.")
    try:
        _get_table().delete_item(
            Key={"id": item_id},
            ConditionExpression="attribute_exists(id)",
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            return _error(404, "Item not found.")
        logger.exception("DynamoDB delete_item failed")
        return _error(500, "Could not delete the item. Please try again.")
    return _response(200, {"deleted": True, "id": item_id})


def lambda_handler(event, context):
    """Entry point for API Gateway HTTP API (payload format 2.0)."""
    try:
        http = event.get("requestContext", {}).get("http", {})
        method = http.get("method", "")
        path = http.get("path", "")
        path_parameters = event.get("pathParameters") or {}
        item_id = path_parameters.get("id")
    except AttributeError:
        logger.exception("Malformed API Gateway event")
        return _error(400, "Malformed request.")

    logger.info("Request: %s %s", method, path)

    try:
        if method == "POST" and path == "/items":
            return _create_item(event)
        if method == "GET" and path == "/items":
            return _list_items()
        if method == "GET" and item_id:
            return _get_item(item_id)
        if method == "DELETE" and item_id:
            return _delete_item(item_id)
    except Exception:  # Last-resort guard: never leak a stack trace to the caller.
        logger.exception("Unhandled error in lambda_handler")
        return _error(500, "Internal error. Please try again.")

    return _error(404, "Route not found.")
