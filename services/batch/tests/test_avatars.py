from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

import httpx
from app.main import AVATAR_CACHE_CONTROL, AVATAR_MAX_BYTES, copy_avatars
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

BUCKET = "test-bucket"
BASE = "https://sleepercdn.com/uploads/"
JPEG = b"\xff\xd8\xff fake jpeg"
NOTHING = {"copied": 0, "existing": 0, "failed": 0}


class FakeS3:
    """Stand-in for the two S3 calls copy_avatars makes.

    head_object finds only stored keys, or raises the given error code for
    every key; put_object records each upload and stores it.
    """

    def __init__(
        self, existing: tuple[str, ...] = (), head_error_code: str | None = None
    ) -> None:
        self.objects: dict[str, bytes] = dict.fromkeys(existing, b"")
        self.puts: list[dict[str, Any]] = []
        self.head_error_code = head_error_code

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        if self.head_error_code is not None:
            raise ClientError({"Error": {"Code": self.head_error_code}}, "HeadObject")
        if kwargs["Key"] not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.puts.append(kwargs)
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {}


def jpeg(body: bytes = JPEG) -> httpx.Response:
    return httpx.Response(200, content=body, headers={"content-type": "image/jpeg"})


def run(
    s3: FakeS3, responses: dict[str, httpx.Response], urls: Iterable[object]
) -> tuple[dict[str, int], list[httpx.Request]]:
    """Run copy_avatars against the fake S3 and a fake Sleeper CDN.

    The CDN answers each request from `responses`, looked up by file name.

    Returns:
        The counts from copy_avatars and the requests the CDN received.
    """
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return responses[request.url.path.rsplit("/", 1)[-1]]

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        counts = copy_avatars(cast("S3Client", s3), client, BUCKET, urls)
    return counts, requests


def test_copy_avatars_uploads_a_new_avatar():
    s3 = FakeS3()

    counts, requests = run(s3, {"12345.jpg": jpeg()}, [BASE + "12345.jpg"])

    assert counts == {"copied": 1, "existing": 0, "failed": 0}
    assert [str(request.url) for request in requests] == [BASE + "12345.jpg"]
    assert s3.puts == [
        {
            "Bucket": BUCKET,
            "Key": "avatars/12345.jpg",
            "Body": JPEG,
            "ContentType": "image/jpeg",
            "CacheControl": AVATAR_CACHE_CONTROL,
        }
    ]


def test_copy_avatars_skips_stored_avatars():
    s3 = FakeS3(existing=("avatars/12345.jpg",))

    counts, requests = run(s3, {}, [BASE + "12345.jpg"])

    assert counts == {"copied": 0, "existing": 1, "failed": 0}
    assert requests == []
    assert s3.puts == []


def test_copy_avatars_copies_a_shared_avatar_once():
    s3 = FakeS3()

    counts, requests = run(s3, {"12345.jpg": jpeg()}, [BASE + "12345.jpg"] * 2)

    assert counts == {"copied": 1, "existing": 0, "failed": 0}
    assert len(requests) == 1
    assert len(s3.puts) == 1


def test_copy_avatars_ignores_values_that_are_not_sleeper_uploads():
    s3 = FakeS3()

    counts, requests = run(s3, {}, [None, "https://example.com/uploads/12345.jpg"])

    assert counts == NOTHING
    assert requests == []
    assert s3.puts == []


def test_copy_avatars_carries_on_after_a_failed_download():
    s3 = FakeS3()
    responses = {"aaaa.jpg": httpx.Response(404), "bbbb.jpg": jpeg()}

    counts, _ = run(s3, responses, [BASE + "aaaa.jpg", BASE + "bbbb.jpg"])

    assert counts == {"copied": 1, "existing": 0, "failed": 1}
    assert [put["Key"] for put in s3.puts] == ["avatars/bbbb.jpg"]


def test_copy_avatars_rejects_a_non_jpeg():
    s3 = FakeS3()
    html = httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"})

    counts, _ = run(s3, {"12345.jpg": html}, [BASE + "12345.jpg"])

    assert counts == {"copied": 0, "existing": 0, "failed": 1}
    assert s3.puts == []


def test_copy_avatars_rejects_an_oversized_file():
    s3 = FakeS3()
    too_big = jpeg(b"\xff" * (AVATAR_MAX_BYTES + 1))

    counts, _ = run(s3, {"12345.jpg": too_big}, [BASE + "12345.jpg"])

    assert counts == {"copied": 0, "existing": 0, "failed": 1}
    assert s3.puts == []


def test_copy_avatars_treats_access_denied_as_a_failure():
    s3 = FakeS3(head_error_code="403")

    counts, requests = run(s3, {"12345.jpg": jpeg()}, [BASE + "12345.jpg"])

    assert counts == {"copied": 0, "existing": 0, "failed": 1}
    assert requests == []
    assert s3.puts == []
