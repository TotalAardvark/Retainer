from typing import Dict, Any, Callable, Optional
from pathlib import Path

from core.config import load_config
from core.youtube import extract_video_id, fetch_video_metadata, fetch_transcript
from core.reader import is_youtube_url, is_valid_url, normalize_url, fetch_article_jina
from core.ai import analyze_transcript
from core.obsidian import save_obsidian_note
from core.apple_notes import save_apple_note
from core.anki import AnkiConnectClient


def run_pipeline(
    url_input: str,
    status_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Executes the Retention pipeline for both YouTube videos and Web Articles:
    1. Detect content type (YouTube URL vs Web Article URL)
    2. Extract metadata & raw content (via yt-dlp/transcript API or Jina Reader)
    3. Query Gemini Flash with structured schema
    4. Save Obsidian Note in Vault/Retainer
    5. Optionally push cards to AnkiConnect if enabled and reachable
    """
    def log(msg: str):
        if status_callback:
            status_callback(msg)

    url_str = url_input.strip()
    if not url_str:
        raise ValueError("No URL provided.")

    config = load_config()

    # Validate destination configuration
    save_obsidian = config.get("save_to_obsidian", True)
    save_apple = config.get("save_to_apple_notes", False)

    if not save_obsidian and not save_apple:
        raise ValueError("No destination selected. Please enable Obsidian, Apple Notes, or both in Settings.")

    vault_dir = config.get("obsidian_vault", "").strip()
    if save_obsidian and not vault_dir:
        raise ValueError("Obsidian is enabled but Vault path is not configured. Please select your vault in Settings.")

    # Validate Gemini API Key
    api_key = config.get("gemini_api_key", "").strip()
    if not api_key:
        raise ValueError("Gemini API Key is not configured. Please open Settings and enter your key.")

    # 1. Determine Content Type & Fetch
    is_yt = is_youtube_url(url_str) or bool(extract_video_id(url_str))

    if is_yt:
        video_id = extract_video_id(url_str)
        if not video_id:
            raise ValueError("Invalid YouTube URL or ID.")

        log("Fetching video info...")
        metadata = fetch_video_metadata(video_id)
        metadata["content_type"] = "video"

        log("Retrieving transcript...")
        transcript_data = fetch_transcript(video_id)
        raw_content = transcript_data.get("raw_text", "")
        annotated_content = transcript_data.get("timestamped_text", raw_content)
        chapters = metadata.get("chapters")
        content_type = "video"
    else:
        # Web Article via Jina Reader
        normalized_article_url = normalize_url(url_str)
        if not is_valid_url(normalized_article_url):
            raise ValueError(f"Invalid URL: '{url_str}'. Please provide a valid web link.")

        log("Fetching article via Jina Reader...")
        jina_api_key = config.get("jina_api_key", "").strip() or None
        article_data = fetch_article_jina(normalized_article_url, jina_api_key=jina_api_key)

        metadata = {
            "title": article_data["title"],
            "channel": article_data["channel"],
            "url": article_data["url"],
            "domain": article_data["domain"],
            "content_type": "article",
            "video_id": "article",
        }
        raw_content = article_data["raw_text"]
        annotated_content = article_data["annotated_content"]
        chapters = None
        content_type = "article"

    # 2. Analyze with Gemini
    log("Synthesizing with Gemini...")
    analysis = analyze_transcript(
        api_key=api_key,
        title=metadata.get("title", ""),
        channel=metadata.get("channel", ""),
        transcript_annotated=annotated_content,
        chapters=chapters,
        content_type=content_type,
    )

    # 3. Save Notes (Obsidian and/or Apple Notes)
    saved_destinations = []
    note_path = None

    if save_obsidian:
        log("Writing note to Obsidian Vault/Retainer...")
        retainer_name = config.get("retainer_folder_name", "Retainer")
        obsidian_file, _ = save_obsidian_note(
            vault_path_str=vault_dir,
            metadata=metadata,
            analysis=analysis,
            raw_transcript=raw_content,
            retainer_folder_name=retainer_name,
        )
        note_path = obsidian_file
        saved_destinations.append("Obsidian")

    if save_apple:
        log("Writing note to Apple Notes...")
        an_folder = config.get("apple_notes_folder", "Retainer")
        save_apple_note(
            metadata=metadata,
            analysis=analysis,
            raw_transcript=raw_content,
            folder_name=an_folder,
        )
        saved_destinations.append("Apple Notes")

    # 4. Optional Anki step
    anki_status = "skipped"
    anki_added = 0
    if config.get("anki_enabled", False):
        log("Checking AnkiConnect...")
        anki_client = AnkiConnectClient(
            host=config.get("anki_host", "127.0.0.1"),
            port=int(config.get("anki_port", 8765)),
        )
        if anki_client.is_available():
            deck_name = config.get("anki_deck", "YouTube Retention")
            log(f"Pushing cards to Anki deck '{deck_name}'...")
            anki_added = anki_client.add_cards(
                deck_name=deck_name,
                cards=analysis.get("flashcards", []),
                video_url=metadata.get("url", ""),
                video_title=metadata.get("title", ""),
            )
            anki_status = f"pushed {anki_added} cards"
        else:
            anki_status = "unreachable (Anki not running)"

    return {
        "title": metadata.get("title"),
        "channel": metadata.get("channel"),
        "content_type": content_type,
        "note_path": str(note_path) if note_path else None,
        "destinations": saved_destinations,
        "card_count": len(analysis.get("flashcards", [])),
        "anki_status": anki_status,
        "anki_added": anki_added,
    }
