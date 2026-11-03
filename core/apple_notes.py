import html
import re
import subprocess
from typing import Any, Dict, List, Optional


def to_html_paragraphs(text: str) -> str:
    """Convert line-separated text to HTML paragraphs and line breaks."""
    if not text:
        return ""
    paras = text.split("\n\n")
    html_paras = []
    for p in paras:
        p_clean = p.strip()
        if not p_clean:
            continue
        p_escaped = html.escape(p_clean).replace("\n", "<br>")
        html_paras.append(f"<p>{p_escaped}</p>")
    return "\n".join(html_paras)


def build_apple_notes_html(
    metadata: Dict[str, Any],
    analysis: Dict[str, Any],
    raw_transcript: str = "",
) -> str:
    """
    Constructs clean, styled HTML content optimized for Apple Notes.
    Apple Notes rich text rendering supports standard HTML tags:
    <h1>, <h2>, <h3>, <p>, <blockquote>, <ul>, <li>, <b>, <i>, <a>, <hr>.
    """
    original_title = metadata.get("title", "Untitled Video")
    channel = metadata.get("channel", "Unknown Source")
    url = metadata.get("url", "")
    content_type = metadata.get("content_type", "video")

    # Header / Meta
    out = []
    out.append(f"<h1>{html.escape(original_title)}</h1>")
    
    meta_p = f"<b>Source:</b> {html.escape(channel)}"
    if url:
        meta_p += f' | <a href="{html.escape(url)}">{html.escape(url)}</a>'
    out.append(f"<p>{meta_p}</p>")

    tags = analysis.get("tags") or []
    if tags:
        tag_str = ", ".join([f"#{t.strip()}" for t in tags if t.strip()])
        out.append(f"<p><i>Tags: {html.escape(tag_str)}</i></p>")

    out.append("<hr>")

    # Executive Summary
    exec_summary = (analysis.get("executive_summary") or "").strip()
    if exec_summary:
        out.append("<h2>Executive Summary</h2>")
        out.append(f"<blockquote><p>{html.escape(exec_summary)}</p></blockquote>")

    # Flashcards
    flashcards = analysis.get("flashcards") or []
    if flashcards:
        out.append("<h2>Flashcards</h2>")
        core_cards = [c for c in flashcards if c.get("tier") == "Core Concept"]
        deep_cards = [c for c in flashcards if c.get("tier") != "Core Concept"]

        card_idx = 1
        if core_cards:
            out.append("<h3>Core Concepts (Foundations & Vocabulary)</h3>")
            for c in core_cards:
                q = html.escape(c.get("front", "").strip())
                a = html.escape(c.get("back", "").strip())
                out.append(f"<p><b>Q{card_idx}: {q}</b><br><i>A:</i> {a}</p>")
                card_idx += 1

        if deep_cards:
            out.append("<h3>Deep Dives (Mechanisms, Evidence & Nuance)</h3>")
            for c in deep_cards:
                q = html.escape(c.get("front", "").strip())
                a = html.escape(c.get("back", "").strip())
                out.append(f"<p><b>Q{card_idx}: {q}</b><br><i>A:</i> {a}</p>")
                card_idx += 1

    # Abstracts
    short_abstract = (analysis.get("short_abstract") or "").strip()
    detailed_abstract = (analysis.get("detailed_abstract") or "").strip()
    if short_abstract or detailed_abstract:
        out.append("<h2>Abstract</h2>")
        if short_abstract:
            out.append("<p><b>Quick Summary:</b></p>")
            out.append(f"<blockquote><p>{html.escape(short_abstract)}</p></blockquote>")
        if detailed_abstract:
            out.append("<p><b>Detailed Overview:</b></p>")
            out.append(f"<blockquote><p>{html.escape(detailed_abstract)}</p></blockquote>")

    # Key Concepts & Takeaways
    takeaways = analysis.get("key_takeaways") or []
    if takeaways:
        out.append("<h2>Key Concepts and Takeaways</h2>")
        out.append("<ul>")
        for pt in takeaways:
            out.append(f"<li>{html.escape(str(pt).strip())}</li>")
        out.append("</ul>")

    # Outline
    outline_items = analysis.get("outline") or []
    if outline_items:
        outline_heading = "Article Outline" if content_type == "article" else "Video Outline"
        out.append(f"<h2>{outline_heading}</h2>")
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

            out.append(f"<h3>{ts_link}{c_title}</h3>")
            if c_summary:
                # Format bullets or paragraphs in section summary
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

    # Full Content / Transcript
    if raw_transcript:
        content_heading = "Detailed Content" if content_type == "article" else "Full Transcript"
        out.append("<hr>")
        out.append(f"<h2>{content_heading}</h2>")
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
