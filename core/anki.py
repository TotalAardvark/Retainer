from typing import Dict, Any, List, Optional
import requests


class AnkiConnectClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.url = f"http://{host}:{port}"

    def is_available(self) -> bool:
        """Check if AnkiConnect is running and responsive."""
        try:
            resp = requests.post(
                self.url,
                json={"action": "version", "version": 6},
                timeout=1.5,
            )
            return resp.status_code == 200 and resp.json().get("error") is None
        except Exception:
            return False

    def invoke(self, action: str, **params) -> Any:
        try:
            payload = {"action": action, "version": 6}
            if params:
                payload["params"] = params
            resp = requests.post(self.url, json=payload, timeout=5.0)
            data = resp.json()
            if data.get("error"):
                raise RuntimeError(f"AnkiConnect error on {action}: {data['error']}")
            return data.get("result")
        except Exception as e:
            raise RuntimeError(f"Failed to communicate with AnkiConnect: {e}") from e

    def ensure_deck(self, deck_name: str) -> None:
        """Create deck if it doesn't already exist."""
        self.invoke("createDeck", deck=deck_name)

    def add_cards(
        self,
        deck_name: str,
        cards: List[Dict[str, str]],
        video_url: str,
        video_title: str,
    ) -> int:
        """
        Push flashcards to Anki deck using standard 'Basic' note type.
        Returns count of successfully added cards.
        """
        if not cards:
            return 0

        self.ensure_deck(deck_name)

        notes = []
        for card in cards:
            front = card.get("front", "").strip()
            back = card.get("back", "").strip()
            tier = card.get("tier", "").strip().lower().replace(" ", "-")
            tier_tag = f"tier::{tier}" if tier else "tier::deep-dive"

            # Append video reference to back
            back_with_source = f"{back}<br><br><small><i>Source: <a href='{video_url}'>{video_title}</a></i></small>"

            notes.append(
                {
                    "deckName": deck_name,
                    "modelName": "Basic",
                    "fields": {
                        "Front": front,
                        "Back": back_with_source,
                    },
                    "options": {
                        "allowDuplicate": False,
                        "duplicateScope": "deck",
                    },
                    "tags": ["youtube-retention", tier_tag],
                }
            )

        results = self.invoke("addNotes", notes=notes)
        added_count = sum(1 for r in results if r is not None)

        # Trigger cloud sync
        try:
            self.invoke("sync")
        except Exception:
            pass  # Sync non-fatal

        return added_count
