from __future__ import annotations

from openai import OpenAI

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app_settings import (
    PROVIDERS,
    clear_api_key,
    get_api_key,
    get_model,
    get_provider,
    save_api_key,
    save_model,
    save_provider,
)


class SettingsDialog(
    QDialog
):

    def __init__(
        self,
        parent=None,
    ):

        super().__init__(
            parent
        )

        self.setWindowTitle(
            "EU5 AI Companion — Settings"
        )

        self.setMinimumWidth(
            600
        )

        self.build_ui()
        self.load_values()


    # ========================================================
    # UI
    # ========================================================

    def build_ui(
        self,
    ):

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        layout.setSpacing(
            14
        )


        title = QLabel(
            "<b>AI Provider</b>"
        )

        title.setStyleSheet(
            "font-size:16px;"
        )

        layout.addWidget(
            title
        )


        form = QFormLayout()

        form.setSpacing(
            10
        )


        # ----------------------------------------------------
        # Provider
        # ----------------------------------------------------

        self.provider = QComboBox()


        for provider_id, info in (
            PROVIDERS.items()
        ):

            self.provider.addItem(
                info["label"],
                provider_id,
            )


        self.provider.currentIndexChanged.connect(
            self.provider_changed
        )


        # ----------------------------------------------------
        # API key
        # ----------------------------------------------------

        self.api_key = QLineEdit()

        self.api_key.setEchoMode(
            QLineEdit.Password
        )


        self.show_key = QPushButton(
            "Show"
        )

        self.show_key.setCheckable(
            True
        )

        self.show_key.toggled.connect(
            self.toggle_key_visibility
        )


        key_row = QHBoxLayout()

        key_row.addWidget(
            self.api_key,
            1,
        )

        key_row.addWidget(
            self.show_key
        )


        # ----------------------------------------------------
        # Model
        # ----------------------------------------------------

        self.model = QComboBox()


        form.addRow(
            "Provider:",
            self.provider,
        )

        form.addRow(
            "API key:",
            key_row,
        )

        form.addRow(
            "Model:",
            self.model,
        )


        layout.addLayout(
            form
        )


        # ----------------------------------------------------
        # Free tier explanation
        # ----------------------------------------------------

        self.free_note = QLabel()

        self.free_note.setWordWrap(
            True
        )

        self.free_note.setStyleSheet(
            """
            color:#aeb7c0;
            background:#141a20;
            border:1px solid #323a43;
            border-radius:5px;
            padding:8px;
            """
        )

        self.free_note.setVisible(
            False
        )

        layout.addWidget(
            self.free_note
        )


        # ----------------------------------------------------
        # Useful links
        # ----------------------------------------------------

        self.links = QLabel()

        self.links.setOpenExternalLinks(
            True
        )

        self.links.setTextInteractionFlags(
            Qt.TextBrowserInteraction
        )

        layout.addWidget(
            self.links
        )


        # ----------------------------------------------------
        # Security note
        # ----------------------------------------------------

        security_note = QLabel(
            "API keys are stored using the "
            "Windows credential store. "
            "They are not written to "
            "campaign.db or the Companion "
            "project files."
        )

        security_note.setWordWrap(
            True
        )

        security_note.setStyleSheet(
            "color:#89939d;"
        )

        layout.addWidget(
            security_note
        )


        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        self.status = QLabel()

        self.status.setWordWrap(
            True
        )

        layout.addWidget(
            self.status
        )


        layout.addStretch()


        # ----------------------------------------------------
        # Buttons
        # ----------------------------------------------------

        buttons = QHBoxLayout()


        self.test_button = QPushButton(
            "Test connection"
        )

        self.test_button.clicked.connect(
            self.test_connection
        )


        self.clear_button = QPushButton(
            "Clear key"
        )

        self.clear_button.clicked.connect(
            self.clear_key
        )


        cancel = QPushButton(
            "Cancel"
        )

        cancel.clicked.connect(
            self.reject
        )


        save = QPushButton(
            "Save"
        )

        save.clicked.connect(
            self.save
        )


        buttons.addWidget(
            self.test_button
        )

        buttons.addWidget(
            self.clear_button
        )

        buttons.addStretch()

        buttons.addWidget(
            cancel
        )

        buttons.addWidget(
            save
        )


        layout.addLayout(
            buttons
        )


    # ========================================================
    # Provider state
    # ========================================================

    def current_provider(
        self,
    ) -> str:

        return str(
            self.provider.currentData()
        )


    def load_values(
        self,
    ):

        provider = (
            get_provider()
        )


        for index in range(
            self.provider.count()
        ):

            if (
                self.provider.itemData(
                    index
                )
                == provider
            ):

                self.provider.setCurrentIndex(
                    index
                )

                break


        self.provider_changed()


    def provider_changed(
        self,
    ):

        provider = (
            self.current_provider()
        )

        info = PROVIDERS[
            provider
        ]


        # ----------------------------------------------------
        # Models
        # ----------------------------------------------------

        self.model.clear()


        for label, model_id in (
            info["models"]
        ):

            self.model.addItem(
                label,
                model_id,
            )


        selected_model = (
            get_model(
                provider
            )
        )


        for index in range(
            self.model.count()
        ):

            if (
                self.model.itemData(
                    index
                )
                == selected_model
            ):

                self.model.setCurrentIndex(
                    index
                )

                break


        # ----------------------------------------------------
        # Saved key
        # ----------------------------------------------------

        key = get_api_key(
            provider
        )

        self.api_key.setText(
            key or ""
        )


        self.api_key.setPlaceholderText(
            f"Paste your "
            f"{info['label']} "
            f"API key"
        )


        # ----------------------------------------------------
        # Free tier info
        # ----------------------------------------------------

        free_note = info.get(
            "free_note"
        )


        if free_note:

            self.free_note.setText(
                "FREE TIER\n\n"
                + free_note
            )

            self.free_note.setVisible(
                True
            )

        else:

            self.free_note.setVisible(
                False
            )


        # ----------------------------------------------------
        # Links
        # ----------------------------------------------------

        links = [
            (
                info["key_url"],
                "Get API key",
            ),
            (
                info["pricing_url"],
                "Pricing",
            ),
            (
                info["models_url"],
                "Models",
            ),
        ]


        if info.get(
            "limits_url"
        ):

            links.append(
                (
                    info[
                        "limits_url"
                    ],
                    "Free tier limits",
                )
            )


        self.links.setText(
            "&nbsp;&nbsp;·&nbsp;&nbsp;".join(
                (
                    f'<a href="{url}">'
                    f'{label}'
                    f'</a>'
                )
                for url, label
                in links
            )
        )


        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        if key:

            self.status.setText(
                "API key configured."
            )

        else:

            self.status.setText(
                "No API key configured yet."
            )


    # ========================================================
    # Key visibility
    # ========================================================

    def toggle_key_visibility(
        self,
        visible: bool,
    ):

        self.api_key.setEchoMode(
            QLineEdit.Normal
            if visible
            else QLineEdit.Password
        )


        self.show_key.setText(
            "Hide"
            if visible
            else "Show"
        )


    # ========================================================
    # Test connection
    # ========================================================

    def test_connection(
        self,
    ):

        provider = (
            self.current_provider()
        )

        info = PROVIDERS[
            provider
        ]


        key = (
            self.api_key
            .text()
            .strip()
        )


        if not key:

            self.status.setText(
                "Enter an API key first."
            )

            return


        model = (
            self.model.currentData()
        )


        self.status.setText(
            "Testing connection…"
        )

        self.test_button.setEnabled(
            False
        )


        try:

            kwargs = {
                "api_key": key,
            }


            if info[
                "base_url"
            ]:

                kwargs[
                    "base_url"
                ] = info[
                    "base_url"
                ]


            client = OpenAI(
                **kwargs
            )


            models = {
                item.id
                for item
                in client.models.list().data
            }


            if model in models:

                self.status.setText(
                    "✓ Connection successful. "
                    f"{model} is available."
                )

            else:

                self.status.setText(
                    "✓ API key works, but "
                    f"{model} was not returned "
                    "by the provider for this account."
                )


        except Exception as exc:

            self.status.setText(
                "Connection failed: "
                f"{type(exc).__name__}: "
                f"{exc}"
            )


        finally:

            self.test_button.setEnabled(
                True
            )


    # ========================================================
    # Clear key
    # ========================================================

    def clear_key(
        self,
    ):

        provider = (
            self.current_provider()
        )

        name = PROVIDERS[
            provider
        ]["label"]


        answer = QMessageBox.question(
            self,
            "Clear API key?",
            (
                f"Remove the saved "
                f"{name} API key from "
                "Windows Credential Manager?"
            ),
        )


        if answer != QMessageBox.Yes:
            return


        clear_api_key(
            provider
        )

        self.api_key.clear()

        self.status.setText(
            "Saved API key cleared."
        )


    # ========================================================
    # Save
    # ========================================================

    def save(
        self,
    ):

        provider = (
            self.current_provider()
        )


        key = (
            self.api_key
            .text()
            .strip()
        )


        model = str(
            self.model.currentData()
        )


        if not key:

            QMessageBox.warning(
                self,
                "API key required",
                (
                    "Add an API key before "
                    "saving these settings."
                ),
            )

            return


        try:

            save_api_key(
                provider,
                key,
            )

            save_provider(
                provider
            )

            save_model(
                provider,
                model,
            )


        except Exception as exc:

            QMessageBox.critical(
                self,
                "Could not save settings",
                str(exc),
            )

            return


        self.accept()
