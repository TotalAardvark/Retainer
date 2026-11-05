import html
import re
import subprocess
from typing import Any, Dict, List, Optional


def to_html_paragraphs(text: str, words_per_paragraph: int = 75) -> str:
    """Format raw transcript or article content into well-spaced, readable HTML paragraphs."""
    if not text:
        return ""
    
    # If text already has double-newlines, respect them; otherwise chunk by words
    raw_paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(raw_paras) > 1:
        html_paras = []
        for p in raw_paras:
            p_escaped = html.escape(p).replace("\n", "<br>")
            html_paras.append(f"<p>{p_escaped}</p>\n<div><br></div>")
        return "\n".join(html_paras)

    # Single wall of text: chunk by word count
    words = text.split()
    html_paras = []
    for i in range(0, len(words), words_per_paragraph):
        chunk = " ".join(words[i : i + words_per_paragraph])
        html_paras.append(f"<p>{html.escape(chunk)}</p>\n<div><br></div>")
    return "\n".join(html_paras)


def build_apple_notes_html(
    metadata: Dict[str, Any],
    analysis: Dict[str, Any],
    raw_transcript: str = "",
) -> str:
    """
    Constructs clean, styled HTML content optimized for Apple Notes.
    - Uses suggested/generated recall title (no clickbait).
    - Centered and underlined main section headers.
    - Centered bold-italic subheaders.
    - Structured property card for metadata.
    - Single empty line spacer (<div><br></div>) between sections.
    - Indented blockquote styling for flashcard answers.
    - Formatted, well-spaced paragraphs for transcripts.
    """
    original_title = metadata.get("title", "Untitled Video")
    agent_title = (analysis.get("suggested_title") or original_title).strip()
    channel = metadata.get("channel", "Unknown Source")
    url = metadata.get("url", "")
    content_type = metadata.get("content_type", "video")

    out = []

    # Title & spacer
    out.append(f"<h1>{html.escape(agent_title)}</h1>")
    out.append("<div><br></div>")

    # Structured metadata list
    meta_items = []
    if channel:
        meta_items.append(f"<li><b>Source:</b> {html.escape(channel)}</li>")
    if original_title and original_title != agent_title:
        meta_items.append(f"<li><b>Original Title:</b> {html.escape(original_title)}</li>")
    if url:
        link_label = "Watch on YouTube" if content_type == "video" else "Source Link"
        meta_items.append(f'<li><b>Link:</b> <a href="{html.escape(url)}">{link_label}</a></li>')

    tags = analysis.get("tags") or []
    if tags:
        tag_str = ", ".join([f"#{t.strip()}" for t in tags if t.strip()])
        meta_items.append(f"<li><b>Tags:</b> {html.escape(tag_str)}</li>")

    out.append("<ul>" + "".join(meta_items) + "</ul>")
    out.append("<hr>")

    def section_header(title: str) -> str:
        return f'<center><h2><u>{html.escape(title)}</u></h2></center>\n<div><br></div>'

    def sub_header(title: str) -> str:
        return f'<center><p><b><i>{html.escape(title)}</i></b></p></center>\n<div><br></div>'

    # Executive Summary
    exec_summary = (analysis.get("executive_summary") or "").strip()
    if exec_summary:
        out.append(section_header("Executive Summary"))
        out.append(f"<blockquote><p>{html.escape(exec_summary)}</p></blockquote>")
        out.append("<div><br></div>")

    # Flashcards
    flashcards = analysis.get("flashcards") or []
    if flashcards:
        out.append(section_header("Flash Cards"))
        core_cards = [c for c in flashcards if c.get("tier") == "Core Concept"]
        deep_cards = [c for c in flashcards if c.get("tier") != "Core Concept"]

        card_idx = 1
        if core_cards:
            out.append(sub_header("Core Concepts (Foundations & Vocabulary)"))
            for c in core_cards:
                q = html.escape(c.get("front", "").strip())
                a = html.escape(c.get("back", "").strip())
                out.append(f"<p><b>Q{card_idx}: {q}</b></p>")
                out.append(f"<blockquote><p><i>A: {a}</i></p></blockquote>")
                out.append("<div><br></div>")
                card_idx += 1

        if deep_cards:
            out.append(sub_header("Deep Dives (Mechanisms, Evidence & Nuance)"))
            for c in deep_cards:
                q = html.escape(c.get("front", "").strip())
                a = html.escape(c.get("back", "").strip())
                out.append(f"<p><b>Q{card_idx}: {q}</b></p>")
                out.append(f"<blockquote><p><i>A: {a}</i></p></blockquote>")
                out.append("<div><br></div>")
                card_idx += 1

    # Abstracts
    short_abstract = (analysis.get("short_abstract") or "").strip()
    detailed_abstract = (analysis.get("detailed_abstract") or "").strip()
    if short_abstract or detailed_abstract:
        out.append(section_header("Abstract"))
        if short_abstract:
            out.append(sub_header("Quick Summary"))
            out.append(f"<blockquote><p>{html.escape(short_abstract)}</p></blockquote>")
            out.append("<div><br></div>")
        if detailed_abstract:
            out.append(sub_header("Detailed Overview"))
            out.append(f"<blockquote><p>{html.escape(detailed_abstract)}</p></blockquote>")
            out.append("<div><br></div>")

    # Key Concepts & Takeaways
    takeaways = analysis.get("key_takeaways") or []
    if takeaways:
        out.append(section_header("Key Concepts and Takeaways"))
        out.append("<ul>")
        for pt in takeaways:
            out.append(f"<li>{html.escape(str(pt).strip())}</li>")
        out.append("</ul>")
        out.append("<div><br></div>")

    # Outline
    outline_items = analysis.get("outline") or []
    if outline_items:
        outline_heading = "Article Outline" if content_type == "article" else "Video Outline"
        out.append(section_header(outline_heading))
        for item in outline_items:
            c_title = html.escape(item.get("title", "Section").strip())
            ts_display = item.get("timestamp_display", "").strip()
            start_sec = item.get("start_seconds")
            c_summary = (item.get("summary") or "").strip()

            if start_sec is not None and content_type == "video" and url:
                ts_link = f'<a href="{html.escape(url)}&t={start_sec}s">[{html.escape(ts_display)}]</a> '
            elif ts_display:
                ts_link = f"[{html.escape(ts_display)}] "
            else:
                ts_link = ""

            out.append(f"<p><b>{ts_link}{c_title}</b></p>")
            if c_summary:
                lines = c_summary.split("\n")
                in_list = False
                for line in lines:
                    line_s = line.strip()
                    if not line_s:
                        if in_list:
                            out.append("</ul>")
                            in_list = False
                        continue
                    if line_s.startswith("- ") or line_s.startswith("* "):
                        if not in_list:
                            out.append("<ul>")
                            in_list = True
                        bullet_txt = html.escape(line_s[2:].strip())
                        out.append(f"<li>{bullet_txt}</li>")
                    else:
                        if in_list:
                            out.append("</ul>")
                            in_list = False
                        out.append(f"<p>{html.escape(line_s)}</p>")
                if in_list:
                    out.append("</ul>")
            out.append("<div><br></div>")

    # Full Content / Transcript
    if raw_transcript:
        content_heading = "Detailed Content" if content_type == "article" else "Full Transcript"
        out.append(section_header(content_heading))
        out.append(to_html_paragraphs(raw_transcript))

    return "\n".join(out)


def create_apple_note(
    title: str,
    html_body: str,
    folder_name: str = "Retainer",
) -> bool:
    """
    Creates a rich HTML note in Apple Notes using osascript (AppleScript).
    Creates target folder under the user's default/first account if it does not exist.
    """
    target_folder = folder_name.strip() or "Retainer"

    # AppleScript template using AppleScript string literals or variables
    # We pass the body and folder through osascript arguments to prevent escaping/injection issues
    script = """
    on run argv
        set noteFolder to item 1 of argv
        set noteBody to item 2 of argv

        tell application "Notes"
            -- Find or create folder in the default account
            set targetAccount to default account
            set destFolder to missing value

            repeat with aFolder in (folders of targetAccount)
                if (name of aFolder) is equal to noteFolder then
                    set destFolder to aFolder
                    exit repeat
                end if
            end repeat

            if destFolder is missing value then
                tell targetAccount
                    set destFolder to make new folder with properties {name:noteFolder}
                end tell
            end if

            -- Create note inside destFolder
            tell destFolder
                make new note with properties {body:noteBody}
            end tell
        end tell
    end run
    """

    res = subprocess.run(
        ["osascript", "-e", script, target_folder, html_body],
        capture_output=True,
        text=True,
    )

    if res.returncode != 0:
        raise RuntimeError(f"Apple Notes AppleScript error: {res.stderr.strip()}")

    return True


def save_apple_note(
    metadata: Dict[str, Any],
    analysis: Dict[str, Any],
    raw_transcript: str = "",
    folder_name: str = "Retainer",
) -> str:
    """
    End-to-end function to build and save a note to Apple Notes.
    Returns the target folder name on success.
    """
    title = (analysis.get("suggested_title") or metadata.get("title") or "Untitled Note").strip()
    html_content = build_apple_notes_html(metadata, analysis, raw_transcript)
    create_apple_note(title=title, html_body=html_content, folder_name=folder_name)
    return folder_name
