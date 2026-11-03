import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple


def sanitize_filename(name: str) -> str:
    """Sanitize string to create safe filename across OSes."""
    # Replace invalid chars with space or dash
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:100] or "youtube_note"


def to_blockquote(text: str) -> str:
    """Format multiline text into Markdown blockquotes with '> '."""
    if not text:
        return ""
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    quoted_paragraphs = []
    for p in paragraphs:
        lines = p.split("\n")
        quoted_lines = [f"> {line}" for line in lines]
        quoted_paragraphs.append("\n".join(quoted_lines))
    return "\n>\n".join(quoted_paragraphs)


def format_transcript_paragraphs(raw_text: str, words_per_paragraph: int = 75) -> str:
    """Format raw transcript text into well-spaced, readable paragraphs."""
    words = raw_text.split()
    if not words:
        return ""
    paragraphs = []
    for i in range(0, len(words), words_per_paragraph):
        paragraphs.append(" ".join(words[i : i + words_per_paragraph]))
    return "\n\n".join(paragraphs)


def ensure_list_spacing(text: str) -> str:
    """
    Ensure an empty line precedes the first list item in a list,
    and an empty line separates list items for maximum readability.
    """
    if not text:
        return ""
    lines = [l.rstrip() for l in text.split("\n")]
    out = []

    def is_list_item(s: str) -> bool:
        return bool(re.match(r"^\s*([-*+]|\d+[\.\)])\s+", s))

    for i, line in enumerate(lines):
        if not line.strip():
            if out and out[-1] != "":
                out.append("")
            continue

        if is_list_item(line):
            # If preceding line is non-empty and not a list item, add blank line before list starts
            if out and out[-1] != "" and not is_list_item(out[-1]):
                out.append("")

        out.append(line)

        # If current line is a list item, ensure empty line after it if there is further content
        if is_list_item(line) and i + 1 < len(lines):
            next_non_empty = None
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    next_non_empty = lines[j]
                    break
            if next_non_empty:
                out.append("")

    return "\n".join(out)


def save_obsidian_note(
    vault_path_str: str,
    metadata: Dict[str, Any],
    analysis: Dict[str, Any],
    raw_transcript: str,
    retainer_folder_name: str = "Retainer",
) -> Tuple[Path, bool]:
    """
    Save structured note directly into the Obsidian Vault's 'Retainer' subfolder.
    Creates the Retainer subfolder if it does not exist.
    Returns (saved_file_path, was_already_present).
    """
    if not vault_path_str:
        raise ValueError("Obsidian Vault directory is not configured. Please set it in Settings.")

    vault = Path(vault_path_str).expanduser().resolve()
    if not vault.exists():
        vault.mkdir(parents=True, exist_ok=True)

    retainer_dir = vault / (retainer_folder_name.strip() or "Retainer")
    retainer_dir.mkdir(parents=True, exist_ok=True)

    video_id = metadata.get("video_id", "unknown")
    original_title = metadata.get("title", "Untitled Video")
    channel = metadata.get("channel", "Unknown Channel")
    url = metadata.get("url", f"https://www.youtube.com/watch?v={video_id}")
    content_type = metadata.get("content_type", "video")

    # Note Title & Filename convention: (Channel/Author) - (4-10 word recall title).md
    agent_title = (analysis.get("suggested_title") or original_title).strip()
    safe_channel = sanitize_filename(channel)
    safe_file_title = sanitize_filename(agent_title)
    file_path = retainer_dir / f"{safe_channel} - {safe_file_title}.md"

    # Remove any legacy-named file for the same video ID to avoid duplicates (if video)
    target_path = file_path
    if content_type == "video" and video_id != "unknown":
        for existing_file in retainer_dir.glob("*.md"):
            if existing_file != file_path and (f"[{video_id}]" in existing_file.name or existing_file.name == f"{video_id}.md"):
                try:
                    existing_file.unlink()
                except Exception:
                    pass
                break

    # Merge tags: base tags + all generated subject matter tags
    base_tags = [content_type, "retention"]
    generated_tags = analysis.get("tags") or []
    seen_tags = set(base_tags)
    merged_tags = list(base_tags)
    for t in generated_tags:
        cleaned_tag = re.sub(r"[^a-zA-Z0-9_-]", "-", t.strip().lower()).strip("-")
        if cleaned_tag and cleaned_tag not in seen_tags:
            seen_tags.add(cleaned_tag)
            merged_tags.append(cleaned_tag)
    tags_yaml = ", ".join(merged_tags)

    # Format Executive Summary (30-40 word concise summary)
    exec_summary = (analysis.get("executive_summary") or "").strip()
    exec_summary_section = ""
    if exec_summary:
        exec_summary_section = f"## Executive Summary\n\n{to_blockquote(exec_summary)}\n\n"

    # Format Abstracts
    short_abstract = analysis.get("short_abstract", "").strip()
    detailed_abstract = analysis.get("detailed_abstract", "").strip()

    # Format Key Concepts & Takeaways (with empty lines between bullets)
    takeaways = analysis.get("key_takeaways", [])
    raw_takeaways_md = "\n".join([f"- {pt}" for pt in takeaways])
    takeaways_md = ensure_list_spacing(raw_takeaways_md)

    # Format Outline (Rich & Chapter-based with YouTube timestamp links)
    outline_items = analysis.get("outline", [])
    outline_blocks = []
    for item in outline_items:
        c_title = item.get("title", "Section").strip()
        ts_display = item.get("timestamp_display", "").strip()
        start_sec = item.get("start_seconds")
        c_summary = item.get("summary", "").strip()
        c_summary_spaced = ensure_list_spacing(c_summary)

        # Build clickable timestamp link if start_seconds is available and content is video
        if start_sec is not None and content_type == "video":
            ts_link = f"[{ts_display}]({url}&t={start_sec}s)"
        elif ts_display:
            ts_link = f"[{ts_display}]"
        else:
            ts_link = ""

        # Heading format
        heading_prefix = f"### {ts_link} {c_title}".strip() if ts_link else f"### {c_title}"
        outline_blocks.append(f"{heading_prefix}\n\n{c_summary_spaced}")
    outline_md = "\n\n".join(outline_blocks)

    # Format Flashcards partitioned into Core Concepts and Deep Dives
    flashcards = analysis.get("flashcards", [])
    flashcards_md = ""
    if flashcards:
        core_cards = [c for c in flashcards if c.get("tier") == "Core Concept"]
        deep_cards = [c for c in flashcards if c.get("tier") != "Core Concept"]

        sections = []
        card_counter = 1

        if core_cards:
            sections.append("### Core Concepts (Foundations & Vocabulary)")
            for card in core_cards:
                q = card.get("front", "").strip()
                a = card.get("back", "").strip()
                sections.append(f"**Q{card_counter}: {q}**\n\n- *A:* {a}")
                card_counter += 1

        if deep_cards:
            if core_cards:
                sections.append("\n### Deep Dives (Mechanisms, Evidence & Nuance)")
            else:
                sections.append("### Deep Dives (Mechanisms, Evidence & Nuance)")
            for card in deep_cards:
                q = card.get("front", "").strip()
                a = card.get("back", "").strip()
                sections.append(f"**Q{card_counter}: {q}**\n\n- *A:* {a}")
                card_counter += 1

        flashcards_md = "\n\n".join(sections)

    # Formatted readable text/transcript in collapsible section
    content_heading = "Detailed Content" if content_type == "article" else "Full Transcript"
    outline_heading = "Article Outline" if content_type == "article" else "Video Outline"
    readable_content = format_transcript_paragraphs(raw_transcript)

    # Enclose abstracts inside quote blocks
    quoted_short_abstract = to_blockquote(short_abstract)
    quoted_detailed_abstract = to_blockquote(detailed_abstract)

    markdown_content = f"""---
title: "{original_title.replace('"', '')}"
channel: "{channel.replace('"', '')}"
url: "{url}"
tags: [{tags_yaml}]
---

{exec_summary_section}## Flashcards

{flashcards_md}

## Abstract

**Quick Summary:**

{quoted_short_abstract}

**Detailed Overview:**

{quoted_detailed_abstract}

## Key Concepts and Takeaways

{takeaways_md}

## {outline_heading}

{outline_md}

---
<details>
<summary><b>{content_heading}</b> (Click to expand)</summary>

{readable_content}

</details>
"""

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return target_path, target_path.exists()
