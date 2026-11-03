from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QCheckBox,
    QMessageBox,
    QGroupBox,
)
from PyQt6.QtCore import Qt

from core.config import load_config, save_config, get_retainer_path


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Retainer - Settings")
        self.setMinimumWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.config = load_config()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # 1. Gemini API Key Section
        api_group = QGroupBox("Google Gemini API")
        api_layout = QVBoxLayout(api_group)
        api_layout.setSpacing(6)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Enter your Gemini API Key")
        self.api_key_input.setText(self.config.get("gemini_api_key", ""))

        toggle_api_btn = QPushButton("Show / Hide")
        toggle_api_btn.setFixedWidth(90)
        toggle_api_btn.clicked.connect(self.toggle_api_visibility)

        api_row = QHBoxLayout()
        api_row.addWidget(self.api_key_input)
        api_row.addWidget(toggle_api_btn)
        api_layout.addLayout(api_row)

        api_hint = QLabel("Used for transcript & article summarization with Gemini 3.8 Flash.")
        api_hint.setStyleSheet("color: #777; font-size: 11px;")
        api_layout.addWidget(api_hint)

        # Optional Jina API Key row
        jina_label = QLabel("Jina Reader API Key (Optional):")
        jina_label.setStyleSheet("font-size: 11px; margin-top: 4px;")
        api_layout.addWidget(jina_label)

        self.jina_key_input = QLineEdit()
        self.jina_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.jina_key_input.setPlaceholderText("Optional: Leave blank for standard free Jina access")
        self.jina_key_input.setText(self.config.get("jina_api_key", ""))
        api_layout.addWidget(self.jina_key_input)

        layout.addWidget(api_group)

        # 2. Obsidian Vault Section
        obs_group = QGroupBox("Obsidian Vault")
        obs_layout = QVBoxLayout(obs_group)
        obs_layout.setSpacing(6)

        obs_row = QHBoxLayout()
        self.vault_input = QLineEdit()
        self.vault_input.setPlaceholderText("/Users/.../MyObsidianVault")
        self.vault_input.setText(self.config.get("obsidian_vault", ""))

        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(85)
        browse_btn.clicked.connect(self.browse_vault)

        obs_row.addWidget(self.vault_input)
        obs_row.addWidget(browse_btn)
        obs_layout.addLayout(obs_row)

        obs_hint = QLabel("A folder named '<b>Retainer</b>' will be automatically created inside your vault.")
        obs_hint.setStyleSheet("color: #777; font-size: 11px;")
        obs_layout.addWidget(obs_hint)
        layout.addWidget(obs_group)

        # 3. Anki Connection (Optional)
        anki_group = QGroupBox("Anki Connection (Optional)")
        anki_layout = QVBoxLayout(anki_group)
        anki_layout.setSpacing(8)

        self.anki_enabled_chk = QCheckBox("Enable Anki Sync (requires desktop Anki + AnkiConnect)")
        self.anki_enabled_chk.setChecked(self.config.get("anki_enabled", False))
        anki_layout.addWidget(self.anki_enabled_chk)

        anki_row = QHBoxLayout()
        self.anki_host_input = QLineEdit(self.config.get("anki_host", "127.0.0.1"))
        self.anki_host_input.setPlaceholderText("Host (127.0.0.1)")

        self.anki_port_input = QLineEdit(str(self.config.get("anki_port", 8765)))
        self.anki_port_input.setPlaceholderText("Port (8765)")
        self.anki_port_input.setFixedWidth(70)

        self.anki_deck_input = QLineEdit(self.config.get("anki_deck", "YouTube Retention"))
        self.anki_deck_input.setPlaceholderText("Deck Name")

        anki_row.addWidget(QLabel("Host:"))
        anki_row.addWidget(self.anki_host_input)
        anki_row.addWidget(QLabel("Port:"))
        anki_row.addWidget(self.anki_port_input)
        anki_layout.addLayout(anki_row)

        deck_row = QHBoxLayout()
        deck_row.addWidget(QLabel("Target Deck:"))
        deck_row.addWidget(self.anki_deck_input)
        anki_layout.addLayout(deck_row)

        layout.addWidget(anki_group)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save Settings")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def toggle_api_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

    def browse_vault(self):
        current_dir = self.vault_input.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Your Obsidian Vault Folder",
            current_dir,
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            self.vault_input.setText(folder)
            # Create Retainer folder immediately as preview
            retainer_path = Path(folder) / "Retainer"
            retainer_path.mkdir(parents=True, exist_ok=True)

    def save(self):
        vault = self.vault_input.text().strip()
        api_key = self.api_key_input.text().strip()

        try:
            port = int(self.anki_port_input.text().strip())
        except ValueError:
            port = 8765

        # Check Retainer creation
        if vault:
            vault_p = Path(vault).expanduser().resolve()
            if not vault_p.exists():
                try:
                    vault_p.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    QMessageBox.warning(self, "Invalid Path", f"Could not create vault folder: {e}")
                    return
            retainer_p = vault_p / "Retainer"
            retainer_p.mkdir(parents=True, exist_ok=True)

        self.config["gemini_api_key"] = api_key
        self.config["jina_api_key"] = self.jina_key_input.text().strip()
        self.config["obsidian_vault"] = vault
        self.config["anki_enabled"] = self.anki_enabled_chk.isChecked()
        self.config["anki_host"] = self.anki_host_input.text().strip() or "127.0.0.1"
        self.config["anki_port"] = port
        self.config["anki_deck"] = self.anki_deck_input.text().strip() or "YouTube Retention"

        save_config(self.config)
        self.accept()
