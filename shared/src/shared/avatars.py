import re

AVATAR_URL_PREFIX = "https://sleepercdn.com/uploads/"

# Where the copies live: the S3 key prefix and the site path. The CI publish
# step's --exclude and the batch role's IAM resource repeat it.
AVATARS_FOLDER = "avatars"

# A hex name with a .jpg or .jpeg extension. Anything else (subfolders, "..",
# query strings, other formats) is rejected, so an accepted name is always
# safe to use as an S3 key and a URL path.
AVATAR_FILE_PATTERN = re.compile(r"[0-9a-f]{1,64}\.jpe?g")


def avatar_file(url: object) -> str | None:
    """Return the file name of a Sleeper avatar upload URL.

    Args:
        url: A stored avatar value, normally a Sleeper upload URL.

    Returns:
        str | None: The file name, such as "1a2b3c.jpg", or None when the
            value isn't a Sleeper upload URL with a safe file name.
    """
    if not isinstance(url, str) or not url.startswith(AVATAR_URL_PREFIX):
        return None
    name = url.removeprefix(AVATAR_URL_PREFIX)
    return name if AVATAR_FILE_PATTERN.fullmatch(name) else None
