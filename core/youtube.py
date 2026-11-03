import json
import re
import urllib.request
from typing import Dict, Any, Optional
import yt_dlp
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)


def extract_video_id(url_or_id: str) -> Optional[str]:
    """Extract YouTube 11-character video ID from varied URL formats."""
    url_or_id = url_or_id.strip()
    if len(url_or_id) == 11 and re.match(r"^[A-Za-z0-9_-]{11}$", url_or_id):
        return url_or_id

    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:&|\?|$)",
        r"youtu\.be\/([0-9A-Za-z_-]{11})(?:\?|$)",
        r"youtube\.com\/embed\/([0-9A-Za-z_-]{11})",
        r"youtube\.com\/shorts\/([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return None


def extract_chapters_from_html(html: str) -> list:
    """Extract official video chapters if present in YouTube initial data."""
    try:
        match = re.search(r'var ytInitialData = ({.*?});</script>', html)
        if not match:
            return []
        data = json.loads(match.group(1))
        seen = set()
        chapters = []

        def walk(obj):
            if isinstance(obj, dict):
                if 'chapterRenderer' in obj:
                    cr = obj['chapterRenderer']
                    title = (
                        cr.get('title', {}).get('simpleText')
                        or (cr.get('title', {}).get('runs', [{}])[0].get('text') if cr.get('title', {}).get('runs') else 'Chapter')
                    )
                    start_sec = int(cr.get('timeRangeStartMillis', 0) / 1000)
                    if start_sec not in seen:
                        seen.add(start_sec)
                        chapters.append({'title': title.strip(), 'start_seconds': start_sec})
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)
        chapters.sort(key=lambda x: x['start_seconds'])
        return chapters
    except Exception:
        return []


def _fetch_metadata_oembed(video_id: str) -> Dict[str, Any]:
    """Fallback metadata fetch via YouTube's public oEmbed API and page HTML."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    oembed_url = f"https://www.youtube.com/oembed?url={video_url}&format=json"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    chapters = []
    # Try fetching watch page HTML to extract chapters
    try:
        page_req = urllib.request.Request(video_url, headers=headers)
        with urllib.request.urlopen(page_req, timeout=10) as page_resp:
            page_html = page_resp.read().decode("utf-8", errors="ignore")
            chapters = extract_chapters_from_html(page_html)
    except Exception:
        chapters = []

    req = urllib.request.Request(oembed_url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return {
            "video_id": video_id,
            "title": data.get("title", "Untitled Video"),
            "channel": data.get("author_name", "Unknown Channel"),
            "upload_date": "",
            "url": video_url,
            "duration": 0,
            "chapters": chapters,
        }


def fetch_video_metadata(video_id: str) -> Dict[str, Any]:
    """Fetch video metadata using yt-dlp, falling back to oEmbed if blocked."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            chapters_raw = info.get("chapters") or []
            chapters = [
                {"title": c.get("title", "").strip(), "start_seconds": int(c.get("start_time", 0))}
                for c in chapters_raw
                if c.get("title")
            ]
            return {
                "video_id": video_id,
                "title": info.get("title", "Untitled Video"),
                "channel": info.get("uploader") or info.get("channel", "Unknown Channel"),
                "upload_date": info.get("upload_date", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "duration": info.get("duration", 0),
                "chapters": chapters,
            }
    except Exception:
        # Fall back to lightweight oEmbed API if yt-dlp fails due to YouTube bot restrictions
        try:
            return _fetch_metadata_oembed(video_id)
        except Exception as oembed_err:
            raise RuntimeError(f"Failed to fetch video metadata: {oembed_err}")


def fetch_transcript(video_id: str) -> Dict[str, Any]:
    """
    Fetch transcript using youtube-transcript-api.
    Returns a dict with:
      - 'raw_text': clean continuous text for reading/full display
      - 'timestamped_text': sampled timestamp-annotated transcript for Gemini outline referencing
    Raises RuntimeError if transcript is disabled/unavailable.
    """
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)

        # Prioritize English manual, then English auto, then any available
        try:
            transcript = transcript_list.find_manually_created_transcript(["en", "en-US", "en-GB"])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(["en", "en-US", "en-GB"])
            except Exception:
                try:
                    transcript = transcript_list.find_transcript(["en"])
                except Exception:
                    transcript = next(iter(transcript_list))

        items = transcript.fetch()
        
        # Build raw text and timestamped text
        raw_parts = []
        timestamped_parts = []
        last_marked_sec = -60  # Mark timestamp roughly every 30-45 seconds or on major gaps

        for item in items:
            t = getattr(item, "text", "") or ""
            t = t.replace("\n", " ").strip()
            if not t:
                continue
            raw_parts.append(t)
            
            start_sec = int(getattr(item, "start", 0))
            if start_sec - last_marked_sec >= 30:
                m, s = divmod(start_sec, 60)
                h, m = divmod(m, 60)
                ts_str = f"[{h}:{m:02d}:{s:02d}]" if h else f"[{m}:{s:02d}]"
                timestamped_parts.append(f"\n{ts_str} {t}")
                last_marked_sec = start_sec
            else:
                timestamped_parts.append(t)

        clean_text = " ".join(raw_parts)
        if not clean_text:
            raise RuntimeError("Transcript is empty.")

        annotated_transcript = " ".join(timestamped_parts).strip()

        return {
            "raw_text": clean_text,
            "timestamped_text": annotated_transcript,
        }

    except (TranscriptsDisabled, NoTranscriptFound) as e:
        raise RuntimeError("Transcript unavailable: This video has no captions or transcripts enabled.") from e
    except Exception as e:
        msg = str(e)
        if any(term in msg for term in ["Subtitles are disabled", "No transcript", "Could not retrieve a transcript", "TranscriptsDisabled"]):
            raise RuntimeError("Transcript unavailable: This video has no captions or transcripts enabled.") from e
        raise RuntimeError(f"Error fetching transcript: {msg}") from e
