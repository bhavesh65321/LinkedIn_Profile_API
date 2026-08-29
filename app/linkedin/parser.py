import re
from urllib.parse import unquote, urlparse

from app.linkedin.exceptions import InvalidProfileUrlError

_PROFILE_PATH_RE = re.compile(
    r"^/in/(?P<slug>[^/?#]+)/?",
    re.IGNORECASE,
)


def extract_public_identifier(profile_url: str) -> str:
    if not profile_url or not profile_url.strip():
        raise InvalidProfileUrlError("Profile URL is required")

    raw = profile_url.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]

    if host not in {"linkedin.com", "linkedin.cn"}:
        raise InvalidProfileUrlError("URL must be a linkedin.com profile link")

    match = _PROFILE_PATH_RE.match(parsed.path or "")
    if not match:
        raise InvalidProfileUrlError(
            "URL must look like https://www.linkedin.com/in/{public-identifier}/"
        )

    slug = unquote(match.group("slug")).strip().strip("/")
    if not slug or slug.lower() in {"pub", "dir"}:
        raise InvalidProfileUrlError("Could not parse a public profile identifier from URL")

    return slug
