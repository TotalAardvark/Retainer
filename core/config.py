import json
import os
import subprocess
from pathlib import Path
from typing import Optional

# Standard macOS Application Support directory
CONFIG_DIR = Path.home() / "Library" / "Application Support" / "Retainer"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Legacy path for seamless automatic migration
LEGACY_CONFIG_FILE = Path.home() / ".config" / "youtube-retention" / "config.json"

KEYCHAIN_SERVICE = "com.retainer.app"
SECRET_KEYS = ("gemini_api_key", "jina_api_key")

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "jina_api_key": "",
    "save_to_obsidian": True,
    "obsidian_vault": "",
    "retainer_folder_name": "Retainer",
    "save_to_apple_notes": False,
    "apple_notes_folder": "Retainer",
    "anki_enabled": False,
    "anki_host": "127.0.0.1",
    "anki_port": 8765,
    "anki_deck": "YouTube Retention",
    "hide_dock_icon": False,
}


def get_keychain_secret(account: str) -> str:
    """Retrieve a secret from the macOS Login Keychain."""
    try:
        res = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                account,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def set_keychain_secret(account: str, secret: str) -> bool:
    """Store or update a secret in the macOS Login Keychain."""
    secret = secret.strip()
    if not secret:
        # Delete from keychain if cleared by user
        try:
            subprocess.run(
                [
                    "/usr/bin/security",
                    "delete-generic-password",
                    "-s",
                    KEYCHAIN_SERVICE,
                    "-a",
                    account,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            pass
        return True

    try:
        res = subprocess.run(
            [
                "/usr/bin/security",
                "add-generic-password",
                "-U",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                account,
                "-w",
                secret,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def _migrate_legacy_config_if_needed() -> None:
    """
    If the new macOS Application Support config does not exist yet
    but the legacy ~/.config/youtube-retention/config.json exists,
    migrate settings and move secrets into the macOS Keychain.
    """
    if CONFIG_FILE.exists() or not LEGACY_CONFIG_FILE.exists():
        return

    try:
        with open(LEGACY_CONFIG_FILE, "r", encoding="utf-8") as f:
            legacy_data = json.load(f)
    except Exception:
        return

    # Save to new location (which also moves secrets to Keychain and strips them from JSON)
    save_config(legacy_data)

    # Also scrub plaintext secrets from the legacy file so they aren't left exposed on disk
    try:
        scrubbed = False
        for k in SECRET_KEYS:
            if legacy_data.get(k):
                legacy_data[k] = ""
                scrubbed = True
        if scrubbed:
            with open(LEGACY_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(legacy_data, f, indent=2)
    except Exception:
        pass


def load_config() -> dict:
    _migrate_legacy_config_if_needed()

    config = DEFAULT_CONFIG.copy()
    file_had_plaintext_secrets = False

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config.update(data)
                for k in SECRET_KEYS:
                    if data.get(k):
                        file_had_plaintext_secrets = True
        except Exception:
            pass
    else:
        save_config(config)

    # Load secrets from macOS Keychain (or migrate any leftover plaintext secrets in JSON)
    for k in SECRET_KEYS:
        json_val = (config.get(k) or "").strip()
        kc_val = get_keychain_secret(k)
        if json_val and not kc_val:
            set_keychain_secret(k, json_val)
            config[k] = json_val
        elif kc_val:
            config[k] = kc_val

    if file_had_plaintext_secrets:
        # Re-save to strip plaintext secrets from config.json
        save_config(config)

    return config


def save_config(config_data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Store secrets securely in macOS Keychain
    for k in SECRET_KEYS:
        if k in config_data:
            set_keychain_secret(k, config_data.get(k) or "")

    # Never write plaintext secrets to disk in config.json
    disk_data = {
        k: v for k, v in config_data.items() if k not in SECRET_KEYS
    }

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(disk_data, f, indent=2)

    try:
        os.chmod(CONFIG_FILE, 0o600)
    except Exception:
        pass


def get_retainer_path(config: dict) -> Optional[Path]:
    vault = config.get("obsidian_vault", "").strip()
    if not vault:
        return None
    vault_path = Path(vault).expanduser().resolve()
    retainer_folder_name = config.get("retainer_folder_name", "Retainer").strip() or "Retainer"
    retainer_path = vault_path / retainer_folder_name
    return retainer_path
