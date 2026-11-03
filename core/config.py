import json
import os
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".config" / "youtube-retention"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "obsidian_vault": "",
    "retainer_folder_name": "Retainer",
    "jina_api_key": "",
    "anki_enabled": False,
    "anki_host": "127.0.0.1",
    "anki_port": 8765,
    "anki_deck": "YouTube Retention",
}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Merge with defaults in case keys were added
            config = DEFAULT_CONFIG.copy()
            config.update(data)
            return config
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config_data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)


def get_retainer_path(config: dict) -> Optional[Path]:
    vault = config.get("obsidian_vault", "").strip()
    if not vault:
        return None
    vault_path = Path(vault).expanduser().resolve()
    retainer_folder_name = config.get("retainer_folder_name", "Retainer").strip() or "Retainer"
    retainer_path = vault_path / retainer_folder_name
    return retainer_path
