import re
import urllib.request
import urllib.error
from urllib.parse import urlparse
from typing import Dict, Any, Optional


def is_youtube_url(url: str) -> bool:
    """Return True if the URL points to YouTube or YouTube Shorts."""
    if not url:
        return False
    clean = url.strip().lower()
    return bool(
        re.search(r"(youtube\.com|youtu\.be)", clean)
    )


def is_valid_url(url: str) -> bool:
    """Check if string is a valid web URL, permitting URLs pasted without scheme (e.g. paulgraham.com/foundermode.html)."""
    if not url:
        return False
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        clean = f"https://{clean}"
    try:
        parsed = urlparse(clean)
        return bool(parsed.netloc) and "." in parsed.netloc
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """Ensure URL has http or https prefix."""
    clean = url.strip()
    if clean and not clean.startswith(("http://", "https://")):
        return f"https://{clean}"
    return clean


def fetch_article_jina(url: str, jina_api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch article content and metadata via Jina Reader (https://r.jina.ai/<url>).
    Returns dict with title, author/domain, url, markdown_content, and clean text.
    """
    url = normalize_url(url.strip())
    if not is_valid_url(url):
        raise ValueError(f"Invalid article URL: '{url}'")

    jina_endpoint = f"https://r.jina.ai/{url}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Retainer/1.0",
        "X-Return-Format": "markdown",
    }
    if jina_api_key:
        headers["Authorization"] = f"Bearer {jina_api_key.strip()}"

    req = urllib.request.Request(jina_endpoint, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Jina Reader HTTP error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error connecting to Jina Reader: {e.reason}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch article via Jina Reader: {str(e)}")

    if not raw_text.strip():
        raise RuntimeError("Jina Reader returned empty content for this URL.")

    # Parse metadata from Jina output headers
    # Format typically begins with:
    # Title: ...
    # URL Source: ...
    # Markdown Content: ...
    title = ""
    author_or_domain = ""
    markdown_content = raw_text

    title_match = re.search(r"^Title:\s*(.+)$", raw_text, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()

    # Domain / source from parsed URL
    parsed_source = urlparse(url)
    domain = parsed_source.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    author_or_domain = domain

    # Split markdown content after 'Markdown Content:' header if present
    content_split = re.split(r"^Markdown Content:\s*", raw_text, maxsplit=1, flags=re.MULTILINE)
    if len(content_split) > 1:
        markdown_content = content_split[1].strip()
    else:
        # Fallback if header not present
        markdown_content = raw_text.strip()

    if not title:
        # Fallback to first H1 in markdown
        h1_match = re.search(r"^#\s+(.+)$", markdown_content, re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()
        else:
            title = f"Article from {domain}"

    return {
        "title": title,
        "channel": author_or_domain,  # mapped for unified downstream pipeline
        "domain": domain,
        "url": url,
        "content_type": "article",
        "raw_text": markdown_content,
        "annotated_content": markdown_content,
    }
