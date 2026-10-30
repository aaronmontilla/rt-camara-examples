"""
API errors are translated into one readable sentence for the model.

CAMARA error bodies carry a "message" that usually ends with a period; the
translated message must not end up with two of them ("found.. Verify").
"""

import httpx
import pytest

from camara.client import handle_error


def _status_error(status: int, body=None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.example.com/dedicated-network/networks/x")
    if body is None:
        response = httpx.Response(status, request=request)
    else:
        response = httpx.Response(status, json=body, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_message_ending_with_a_period_is_not_doubled():
    error = _status_error(404, {"code": "NOT_FOUND", "message": "The specified resource is not found."})
    assert handle_error(error) == (
        "Error 404 Not Found — The specified resource is not found. Verify the ID is correct."
    )


@pytest.mark.parametrize("message", ["Invalid input", "Invalid input.", "Invalid input. ", "Invalid input.."])
def test_detail_is_followed_by_exactly_one_period(message):
    text = handle_error(_status_error(400, {"code": "INVALID_ARGUMENT", "message": message}))
    assert text == "Error 400 Bad Request — Invalid input. Check all required fields are correct."


def test_code_is_used_when_there_is_no_message():
    text = handle_error(_status_error(409, {"code": "CONFLICT"}))
    assert text.startswith("Error 409 Conflict — CONFLICT. ")
    assert ".." not in text


def test_body_without_json_gives_the_generic_message():
    assert handle_error(_status_error(404)) == "Error 404 Not Found. Verify the ID is correct."
