import json

import httpx
import pytest
from shared.sleeper import fetch_json


def make_client(status, payload):
    body = json.dumps(payload).encode()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status, stream=httpx.ByteStream(body))
    )
    return httpx.Client(transport=transport, base_url="https://sleeper.test")


# Fetch_json() tests
def test_fetch_json_returns_data_when_type_matches():
    payload = {"4046": {"position": "QB"}}

    with make_client(200, payload) as client:
        result = fetch_json(client, "/players/nfl", dict)

    assert result == payload


def test_fetch_json_raises_type_error_on_type_mismatch():
    payload = {"4046": {"position": "QB"}}

    with (
        make_client(200, payload) as client,
        pytest.raises(TypeError, match="got dict"),
    ):
        fetch_json(client, "/players/nfl", list)


def test_fetch_json_raises_status_error_on_404_response():
    with (
        make_client(404, {}) as client,
        pytest.raises(httpx.HTTPStatusError) as exc_info,
    ):
        fetch_json(client, "/players/nfl", dict)

    assert exc_info.value.response.status_code == 404
