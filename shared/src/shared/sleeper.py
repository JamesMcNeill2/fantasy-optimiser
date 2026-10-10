import logging
import time

import httpx

BASE_URL = "https://api.sleeper.app/v1"

logger = logging.getLogger(__name__)

def fetch_json[T](client: httpx.Client, path: str, expected_type: type[T]) -> T:
    """
    Fetch JSON from the API and verify that it has the expected type.

    Args:
        client: HTTP client to use for the request.
        path: Relative API path to request.
        expected_type: Python type expected for the decoded JSON payload.

    Returns:
        T: The decoded JSON payload, an instance of expected_type.

    Raises:
        httpx.HTTPStatusError: If the API request fails with a non-2xx status code.
        TypeError: If the decoded JSON payload is not an instance of expected_type.
    """

    # Query the url for a response and store it
    response = client.get(path)
    response.raise_for_status()

    # Parse returned data and determine the amount of time this took
    start = time.perf_counter()
    data = response.json()
    parse_seconds = time.perf_counter() - start

    logger.info(
        "Fetched %s: status=%s bytes=%s download=%.2fs, parse=%.2fs",
        path,
        response.status_code,
        len(response.content),
        response.elapsed.total_seconds(),
        parse_seconds,
    )

    # Check the response is of the expected data type
    if not isinstance(data, expected_type):
        raise TypeError(
            f"Expected {expected_type.__name__} from {path}, got {type(data).__name__}"
        )

    return data
