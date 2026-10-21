import pytest
from shared.avatars import avatar_file

BASE = "https://sleepercdn.com/uploads/"


@pytest.mark.parametrize("name", ["12345.jpg", "0a1b2c3d.jpeg"])
def test_avatar_file_returns_the_file_name(name):
    assert avatar_file(BASE + name) == name


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/uploads/12345.jpg",  # another host
        "https://sleepercdn.com.example.com/uploads/12345.jpg",  # lookalike host
        "http://sleepercdn.com/uploads/12345.jpg",  # not https
        "https://sleepercdn.com/avatars/12345.jpg",  # another path
        BASE + "../12345.jpg",  # path traversal
        BASE + "a/12345.jpg",  # subfolder
        BASE + "12345.jpg?size=1",  # query string
        BASE + "12345.svg",  # unexpected extension
        BASE + "12345.png",  # unexpected extension
        BASE + "12345.gif",  # unexpected extension
        BASE + "12345.webp",  # unexpected extension
        BASE + "12345.JPG",  # uppercase extension
        BASE + "12345",  # no extension
        BASE + "XYZ.jpg",  # not lowercase hex
        BASE + "12345.jpg\n",  # trailing newline
        BASE,  # nothing after the prefix
    ],
)
def test_avatar_file_rejects_other_urls(url):
    assert avatar_file(url) is None


@pytest.mark.parametrize("value", [None, "", 12345])
def test_avatar_file_rejects_non_urls(value):
    assert avatar_file(value) is None
