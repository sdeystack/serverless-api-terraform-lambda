"""Unit tests for lambda/handler.py.

Tests use a mocked DynamoDB table, so no AWS credentials or network access
are needed. Run from the repo root:

    pip install -r requirements-dev.txt
    python -m pytest -q
"""

import json
import os
import pathlib
import sys

import pytest
from botocore.exceptions import ClientError
from unittest.mock import MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lambda"))

import handler  # noqa: E402


@pytest.fixture(autouse=True)
def mock_table(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-items")
    table = MagicMock()
    handler._table = table
    yield table
    handler._table = None


def _event(method, path, body=None, item_id=None):
    event = {
        "version": "2.0",
        "requestContext": {"http": {"method": method, "path": path}},
        "pathParameters": {"id": item_id} if item_id else None,
        "body": body,
        "isBase64Encoded": False,
    }
    return event


def _body(response):
    return json.loads(response["body"])


def test_create_item_success(mock_table):
    event = _event("POST", "/items", json.dumps({"name": "Widget", "description": "Test item"}))
    response = handler.lambda_handler(event, None)

    assert response["statusCode"] == 201
    item = _body(response)["item"]
    assert item["name"] == "Widget"
    assert item["description"] == "Test item"
    assert item["id"]
    assert item["created_at"]
    mock_table.put_item.assert_called_once()
    saved = mock_table.put_item.call_args.kwargs["Item"]
    assert saved["id"] == item["id"]


def test_create_item_requires_name(mock_table):
    event = _event("POST", "/items", json.dumps({"description": "No name"}))
    response = handler.lambda_handler(event, None)

    assert response["statusCode"] == 400
    assert "name" in _body(response)["error"]
    mock_table.put_item.assert_not_called()


def test_create_item_rejects_invalid_json(mock_table):
    event = _event("POST", "/items", "{not json")
    response = handler.lambda_handler(event, None)

    assert response["statusCode"] == 400
    mock_table.put_item.assert_not_called()


def test_create_item_rejects_non_object_body(mock_table):
    event = _event("POST", "/items", json.dumps(["a list, not an object"]))
    response = handler.lambda_handler(event, None)

    assert response["statusCode"] == 400
    mock_table.put_item.assert_not_called()


def test_list_items_sorted_by_created_at(mock_table):
    mock_table.scan.return_value = {
        "Items": [
            {"id": "2", "name": "B", "created_at": "2026-01-02T00:00:00Z"},
            {"id": "1", "name": "A", "created_at": "2026-01-01T00:00:00Z"},
        ]
    }
    response = handler.lambda_handler(_event("GET", "/items"), None)

    assert response["statusCode"] == 200
    body = _body(response)
    assert body["count"] == 2
    assert [item["id"] for item in body["items"]] == ["1", "2"]


def test_get_item_found(mock_table):
    mock_table.get_item.return_value = {"Item": {"id": "abc", "name": "Widget"}}
    response = handler.lambda_handler(_event("GET", "/items/abc", item_id="abc"), None)

    assert response["statusCode"] == 200
    assert _body(response)["item"]["id"] == "abc"
    mock_table.get_item.assert_called_once_with(Key={"id": "abc"})


def test_get_item_not_found(mock_table):
    mock_table.get_item.return_value = {}
    response = handler.lambda_handler(_event("GET", "/items/missing", item_id="missing"), None)

    assert response["statusCode"] == 404


def test_delete_item_success(mock_table):
    response = handler.lambda_handler(_event("DELETE", "/items/abc", item_id="abc"), None)

    assert response["statusCode"] == 200
    assert _body(response) == {"deleted": True, "id": "abc"}
    mock_table.delete_item.assert_called_once()


def test_delete_item_not_found(mock_table):
    mock_table.delete_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "No such item"}},
        "DeleteItem",
    )
    response = handler.lambda_handler(_event("DELETE", "/items/missing", item_id="missing"), None)

    assert response["statusCode"] == 404


def test_dynamodb_error_returns_500_without_details(mock_table):
    mock_table.scan.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "Boom, internal detail"}},
        "Scan",
    )
    response = handler.lambda_handler(_event("GET", "/items"), None)

    assert response["statusCode"] == 500
    assert "Boom" not in _body(response)["error"]


def test_unknown_route_returns_404(mock_table):
    response = handler.lambda_handler(_event("PATCH", "/items/abc", item_id="abc"), None)

    assert response["statusCode"] == 404
    mock_table.get_item.assert_not_called()
