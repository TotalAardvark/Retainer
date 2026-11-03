# YouTube Retention & Spaced-Repetition Engine

A native macOS menu bar app that transforms YouTube videos into structured Obsidian notes and spaced-repetition flashcards in Anki.

## Features

- **macOS Menu Bar Resident**: Vector monochrome brain icon living in your menu bar (`LSUIElement` - no Dock clutter).
- **Paste & Go**: Click **Paste**, and if your clipboard has a YouTube URL, it automatically triggers generation in a single click.
- **Fail-Fast Transcript Extraction**: Pulls captions via `youtube-transcript-api`. If the video has no transcript, it immediately alerts you (*"Transcript unavailable for this video"*).
- **Gemini 2.5 Flash Synthesis**: Extracts an executive summary, key technical concepts, and high-yield atomic flashcards.
- **Obsidian Vault First**: Saves Markdown files directly into the `Retainer` subfolder inside your selected Obsidian Vault (auto-creates `Retainer` if missing).
- **Optional Anki Integration**: Checks if AnkiConnect is running. If not installed or running, cards are gracefully skipped without failing your Obsidian note.

---

## Deliverables

1. **Standalone App Bundle**:
   - `dist/YouTubeRetention.app` (Can be copied directly into `/Applications`)
   - `dist/YouTubeRetention.zip` (Portable single-archive deliverable)
2. **Source Code**:
   - `main.py` - Application entrypoint.
   - `core/youtube.py` - Metadata & caption extractor.
   - `core/ai.py` - Google Gemini 2.5 Flash structured JSON schema client.
   - `core/obsidian.py` - Vault & `Retainer/` subfolder writer.
   - `core/anki.py` - AnkiConnect HTTP REST client.
   - `ui/tray_app.py` - Frameless popover, paste & go, system notifications.
   - `ui/settings_dialog.py` - Settings panel for API key and Obsidian Vault picker.
   - `ui/assets.py` - Dynamic vector SVG Brain template icon.

---

## Running from Source

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the app
python main.py
```

## Running the App Bundle

```bash
open dist/YouTubeRetention.app
```
