from __future__ import annotations

# ============================================================
# Frozen child-script dispatcher
#
# Development:
#   python child.py args...
#
# Packaged:
#   EU5 AI Companion.exe child.py args...
#
# Existing subprocess code can therefore keep using
# sys.executable.
# ============================================================

import runpy
import sys
from pathlib import Path as _BootstrapPath


import os as _bootstrap_os

# Force UTF-8 for this process and every Companion worker
# spawned from it. Windows otherwise defaults some frozen
# console/pipe streams to cp1252.
_bootstrap_os.environ["PYTHONUTF8"] = "1"
_bootstrap_os.environ["PYTHONIOENCODING"] = "utf-8"

for _stream in (
    sys.stdout,
    sys.stderr,
):
    if (
        _stream is not None
        and hasattr(
            _stream,
            "reconfigure",
        )
    ):
        try:
            _stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            pass


if (
    getattr(sys, "frozen", False)
    and len(sys.argv) >= 2
):

    _candidate = _BootstrapPath(
        sys.argv[1]
    )

    if (
        _candidate.suffix.lower() == ".py"
        and _candidate.exists()
    ):

        _script = (
            _candidate.resolve()
        )

        _script_dir = str(
            _script.parent
        )

        if _script_dir not in sys.path:
            sys.path.insert(
                0,
                _script_dir,
            )

        sys.argv = [
            str(_script),
            *sys.argv[2:],
        ]

        runpy.run_path(
            str(_script),
            run_name="__main__",
        )

        raise SystemExit(0)



from runtime_paths import CAMPAIGN_DB, STATIC_DB, initialize_runtime

import csv
import html
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from runtime_paths import APP_ROOT
from version import get_app_version

from companion_playset import ensure_companion_playset_enabled

import markdown

from PySide6.QtCore import (
    QProcess,
    QProcessEnvironment,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QFont,
    QKeyEvent,
)
from app_settings import (
    PROVIDERS,
    get_api_key,
    get_model,
    get_provider,
)

from settings_dialog import (
    SettingsDialog,
)

from save_browser_dialog import SaveBrowserDialog

from game_paths import (
    find_eu5_executable,
    find_eu5_save_directory,
    save_manual_eu5_executable,
)


from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QMenu,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)



# ============================================================
# Companion helper mod provisioning
# ============================================================

COMPANION_INTEGRATION_RESULT = None
COMPANION_INTEGRATION_ERROR = None

try:
    COMPANION_INTEGRATION_RESULT = (
        ensure_companion_playset_enabled()
    )

except Exception as exc:
    COMPANION_INTEGRATION_ERROR = str(
        exc
    )


PROJECT_ROOT = APP_ROOT
APP_DISPLAY_VERSION = get_app_version()

ASK_SCRIPT = (
    PROJECT_ROOT
    / "src"
    / "ask_eu5.py"
)


def localize_static_key(
    key: str,
) -> str:

    if not STATIC_DB.exists():
        return key

    try:
        with sqlite3.connect(
            STATIC_DB
        ) as conn:

            row = conn.execute(
                """
                SELECT value
                FROM localization
                WHERE key = ?
                """,
                (
                    key,
                ),
            ).fetchone()

        if row and row[0]:
            return str(
                row[0]
            )

    except sqlite3.Error:
        pass

    return key


def pretty_game_date(
    raw_date: str,
) -> str:

    try:
        value = datetime.strptime(
            raw_date,
            "%Y-%m-%d",
        )

        return (
            f"{value.day} "
            f"{value.strftime('%B')} "
            f"{value.year}"
        )

    except ValueError:
        return raw_date

def find_rakaly() -> Path | None:

    rakaly_root = (
        PROJECT_ROOT
        / "tools"
        / "rakaly"
    )

    if not rakaly_root.exists():
        return None

    candidates = sorted(
        rakaly_root.rglob(
            "rakaly.exe"
        )
    )

    if not candidates:
        return None

    return candidates[-1]


def find_eu5_pid() -> int | None:

    creation_flags = 0

    if sys.platform == "win32":
        creation_flags = (
            subprocess.CREATE_NO_WINDOW
        )

    try:

        result = subprocess.run(
            [
                "tasklist",
                "/FI",
                "IMAGENAME eq eu5.exe",
                "/FO",
                "CSV",
                "/NH",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creation_flags,
            timeout=5,
        )

    except Exception:
        return None


    if result.returncode != 0:
        return None


    for row in csv.reader(
        result.stdout.splitlines()
    ):

        if len(row) < 2:
            continue

        if row[0].lower() != "eu5.exe":
            continue

        try:
            return int(
                row[1].replace(
                    ",",
                    "",
                )
            )

        except ValueError:
            continue


    return None


class MessageInput(
    QPlainTextEdit
):

    send_requested = Signal()


    def keyPressEvent(
        self,
        event: QKeyEvent,
    ):

        if (
            event.key()
            in (
                Qt.Key_Return,
                Qt.Key_Enter,
            )
            and not (
                event.modifiers()
                & Qt.ShiftModifier
            )
        ):

            self.send_requested.emit()
            return


        super().keyPressEvent(
            event
        )


initialize_runtime()


class CompanionWindow(
    QMainWindow
):

    def __init__(self):

        super().__init__()

        self.process: (
            QProcess | None
        ) = None

        self.output_buffer = ""

        self.current_question = ""

        self._startup_health_checked = False

        self.rakaly = (
            find_rakaly()
        )


        self.setWindowTitle(
            f"EU5 AI Companion v{APP_DISPLAY_VERSION}"
        )

        self.resize(
            900,
            780,
        )


        self.build_ui()

        self.setStyleSheet("""
            QMainWindow,
            QWidget {
                background: #16191d;
                color: #e8e8e8;
            }

            QTextBrowser,
            QPlainTextEdit {
                background: #101215;
                color: #ececec;
                border: 1px solid #343941;
                border-radius: 6px;
                padding: 8px;
                selection-background-color: #4b5d70;
            }

            QPushButton {
                background: #303842;
                color: white;
                border: 1px solid #47515e;
                border-radius: 6px;
                padding: 8px 14px;
            }

            QPushButton:hover {
                background: #3b4551;
            }

            QPushButton:disabled {
                color: #7d8288;
                background: #23272c;
            }

            QLabel#Header {
                font-size: 18px;
                font-weight: bold;
            }

            QLabel#Status {
                color: #b9c0c8;
            }

            QLabel#Footer {
                color: #8d959e;
                font-size: 11px;
            }

            QProgressBar {
                border: 1px solid #343941;
                border-radius: 4px;
                background: #101215;
                max-height: 8px;
            }

            QProgressBar::chunk {
                background: #65788d;
            }
        """)


    def build_ui(
        self,
    ):

        root = QWidget()

        self.setCentralWidget(
            root
        )


        layout = QVBoxLayout(
            root
        )

        layout.setContentsMargins(
            16,
            16,
            16,
            16,
        )

        layout.setSpacing(
            10
        )


        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        top_row = QHBoxLayout()


        self.header = QLabel(
            '<span style="color:#8d969f; '
            'font-weight:700;">'
            'WAITING'
            '</span>'
            '<span style="color:#626b74;">'
            '&nbsp;&nbsp;|&nbsp;&nbsp;'
            '</span>'
            '<span style="color:#cfd4d9;">'
            'No live snapshot yet'
            '</span>'
        )


        self.header.setObjectName(
            "Header"
        )


        self.ai_badge = QLabel()

        self.ai_badge.setStyleSheet(
            """
            QLabel {
                color: #b9c8d6;
                background: #202832;
                border: 1px solid #3b4754;
                border-radius: 5px;
                padding: 6px 10px;
                font-size: 11px;
            }
            """
        )

        self.refresh_ai_badge()


        self.game_button = QPushButton(
            "Game"
        )

        self.game_menu = QMenu(
            self.game_button
        )

        self.game_menu.setStyleSheet(
            '''
            QMenu {
                background: #20242b;
                color: #e7e9ee;
                border: 1px solid #3a404b;
                padding: 5px;
            }

            QMenu::item {
                padding: 7px 24px 7px 12px;
            }

            QMenu::item:selected {
                background: #34465f;
            }

            QMenu::item:disabled {
                color: #707780;
            }

            QMenu::separator {
                height: 1px;
                background: #3a404b;
                margin: 5px 8px;
            }
            '''
        )

        self.start_game_action = (
            self.game_menu.addAction(
                "Start Game"
            )
        )

        self.continue_game_action = (
            self.game_menu.addAction(
                "Continue"
            )
        )

        self.load_game_action = (
            self.game_menu.addAction(
                "Load Game..."
            )
        )

        self.arrange_windows_action = (
            self.game_menu.addAction(
                "Arrange Windows"
            )
        )

        self.arrange_windows_action.triggered.connect(
            self.arrange_windows
        )

        self.game_menu.addSeparator()

        self.log_action = (
            self.game_menu.addAction(
                "Show Debug Log"
            )
        )

        self.log_action.setCheckable(
            True
        )

        self.start_game_action.setEnabled(
            True
        )

        self.start_game_action.triggered.connect(
            self.start_game
        )

        self.continue_game_action.setEnabled(
            False
        )

        # Runtime console loading is unreliable
        # in the current EU5 build, so keep the
        # save browser without pretending it loads.
        self.load_game_action.setText(
            "Browse Saves..."
        )

        self.load_game_action.triggered.connect(
            self.open_load_game
        )
        self.load_game_action.triggered.connect(
            self.open_load_game
        )

        self.log_action.toggled.connect(
            self.toggle_log
        )

        self.game_button.setMenu(
            self.game_menu
        )


        self.settings_button = QPushButton(
            "Settings"
        )

        self.settings_button.clicked.connect(
            self.open_settings
        )


        top_row.addWidget(
            self.header
        )

        top_row.addStretch()

        top_row.addWidget(
            self.game_button
        )

        top_row.addWidget(
            self.ai_badge
        )

        top_row.addWidget(
            self.settings_button
        )


        layout.addLayout(
            top_row
        )


        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        self.status = QLabel(
            "Ready"
        )

        self.status.setObjectName(
            "Status"
        )


        self.progress = QProgressBar()

        self.progress.setRange(
            0,
            1,
        )

        self.progress.setValue(
            0
        )

        self.progress.setTextVisible(
            False
        )


        layout.addWidget(
            self.status
        )

        layout.addWidget(
            self.progress
        )


        # ----------------------------------------------------
        # Chat
        # ----------------------------------------------------

        self.chat = QTextBrowser()

        self.chat.setOpenExternalLinks(
            True
        )

        self.chat.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )


        self.chat.setHtml("""
            <div style="color:#9aa3ad;">
                EU5 AI Companion ready.<br><br>
                Start Europa Universalis V, then ask something about
                the current campaign.
            </div>
        """)


        layout.addWidget(
            self.chat,
            1,
        )


        # ----------------------------------------------------
        # Debug log
        # ----------------------------------------------------

        self.debug_log = (
            QPlainTextEdit()
        )

        self.debug_log.setReadOnly(
            True
        )

        self.debug_log.setVisible(
            False
        )

        self.debug_log.setMaximumHeight(
            240
        )


        font = QFont(
            "Consolas"
        )

        font.setPointSize(
            9
        )

        self.debug_log.setFont(
            font
        )


        layout.addWidget(
            self.debug_log
        )


        # ----------------------------------------------------
        # Input
        # ----------------------------------------------------

        input_row = QHBoxLayout()


        self.input = MessageInput()

        self.input.setPlaceholderText(
            "Ask about the current EU5 campaign…"
        )

        self.input.setMaximumHeight(
            110
        )

        self.input.send_requested.connect(
            self.send_question
        )


        self.send_button = QPushButton(
            "Send"
        )

        self.send_button.setMinimumWidth(
            90
        )

        self.send_button.clicked.connect(
            self.send_question
        )


        input_row.addWidget(
            self.input,
            1,
        )

        input_row.addWidget(
            self.send_button
        )


        layout.addLayout(
            input_row
        )


        # ----------------------------------------------------
        # Footer
        # ----------------------------------------------------

        self.footer = QLabel(
            f"v{APP_DISPLAY_VERSION} • "
            "Enter = send • Shift+Enter = newline"
        )

        self.footer.setObjectName(
            "Footer"
        )


        layout.addWidget(
            self.footer
        )


    def update_live_header_from_db(
        self,
    ):

        if not CAMPAIGN_DB.exists():
            return

        try:

            with sqlite3.connect(
                CAMPAIGN_DB
            ) as conn:

                row = conn.execute(
                    """
                    SELECT
                        player_tag,
                        game_date
                    FROM current_meta
                    WHERE singleton = 1
                    """
                ).fetchone()

        except sqlite3.Error:
            return


        if not row:
            return


        tag = str(
            row[0]
        )

        raw_date = str(
            row[1]
        )


        country_name = (
            localize_static_key(
                tag
            )
        )

        date_text = (
            pretty_game_date(
                raw_date
            )
        )


        self.header.setText(
            '<span style="color:#72c487; '
            'font-weight:700;">'
            'LIVE'
            '</span>'
            '<span style="color:#6f7882;">'
            '&nbsp;&nbsp;|&nbsp;&nbsp;'
            '</span>'
            '<span style="color:#e5e8eb; '
            'font-weight:600;">'
            + html.escape(
                country_name
            )
            + '</span>'
            '<span style="color:#6f7882;">'
            '&nbsp;&nbsp;|&nbsp;&nbsp;'
            '</span>'
            '<span style="color:#c7cdd3;">'
            + html.escape(
                date_text
            )
            + '</span>'
        )


    def collect_health_status(
        self,
    ) -> list[tuple[str, bool, str]]:

        results = []


        # -------------------------------------------------
        # Europa Universalis V
        # -------------------------------------------------

        try:

            eu5_exe = (
                find_eu5_executable()
            )

        except Exception as exc:

            eu5_exe = None

            eu5_detail = (
                f"Detection failed: {exc}"
            )

        else:

            if eu5_exe:

                eu5_detail = str(
                    eu5_exe
                )

            else:

                eu5_detail = (
                    "Europa Universalis V "
                    "installation not found"
                )


        results.append(
            (
                "Europa Universalis V",
                eu5_exe is not None,
                eu5_detail,
            )
        )


        # -------------------------------------------------
        # Save directory
        # -------------------------------------------------

        try:

            save_dir = (
                find_eu5_save_directory()
            )

        except Exception as exc:

            save_dir = None

            save_detail = (
                f"Detection failed: {exc}"
            )

        else:

            if save_dir:

                save_detail = str(
                    save_dir
                )

            else:

                save_detail = (
                    "EU5 save directory "
                    "not found"
                )


        results.append(
            (
                "Save directory",
                save_dir is not None,
                save_detail,
            )
        )


        # -------------------------------------------------
        # Rakaly
        # -------------------------------------------------

        rakaly_ok = (
            self.rakaly is not None
            and Path(
                self.rakaly
            ).is_file()
        )


        results.append(
            (
                "Rakaly",
                rakaly_ok,
                (
                    str(self.rakaly)
                    if rakaly_ok
                    else "rakaly.exe not found"
                ),
            )
        )


        # -------------------------------------------------
        # Static game data
        # -------------------------------------------------

        static_ok = (
            STATIC_DB.is_file()
            and STATIC_DB.stat().st_size > 0
        )


        results.append(
            (
                "Static game data",
                static_ok,
                (
                    str(STATIC_DB)
                    if static_ok
                    else (
                        "static_data.db "
                        "not found"
                    )
                ),
            )
        )


        # -------------------------------------------------
        # Backend
        # -------------------------------------------------

        backend_ok = (
            ASK_SCRIPT.is_file()
        )


        results.append(
            (
                "Companion backend",
                backend_ok,
                (
                    str(ASK_SCRIPT)
                    if backend_ok
                    else (
                        "ask_eu5.py "
                        "not found"
                    )
                ),
            )
        )


        # -------------------------------------------------
        # AI provider / key
        # -------------------------------------------------

        try:

            provider = (
                get_provider()
            )

        except Exception:

            provider = None


        provider_ok = bool(
            provider
        )


        results.append(
            (
                "AI provider",
                provider_ok,
                (
                    provider
                    if provider_ok
                    else (
                        "No AI provider "
                        "selected"
                    )
                ),
            )
        )


        api_key = None


        if provider_ok:

            try:

                api_key = (
                    get_api_key(
                        provider
                    )
                )

            except Exception:
                api_key = None


        provider_names = {
            "openai": "OpenAI",
            "groq": "Groq",
        }


        pretty_provider = (
            provider_names.get(
                provider,
                (
                    str(provider)
                    if provider
                    else "AI"
                ),
            )
        )


        results.append(
            (
                f"{pretty_provider} API key",
                bool(api_key),
                (
                    "Configured"
                    if api_key
                    else "Not configured"
                ),
            )
        )


        return results


    def run_startup_health_check(
        self,
    ) -> None:

        results = (
            self.collect_health_status()
        )


        missing = [
            item
            for item in results
            if not item[1]
        ]


        # Everything required is present.
        # Stay quiet.
        if not missing:
            return


        lines = []


        for name, ok, detail in results:

            symbol = (
                "OK"
                if ok
                else "MISSING"
            )

            lines.append(
                f"{symbol}  {name}"
            )


        lines.append("")
        lines.append(
            "Some required components "
            "need attention."
        )


        # If the only missing item is an API key,
        # Settings is the most useful next step.
        api_problem = any(
            (
                "API key"
                in name
            )
            and not ok
            for name, ok, detail
            in results
        )


        box = QMessageBox(
            self
        )

        box.setWindowTitle(
            "EU5 AI Companion setup"
        )

        box.setIcon(
            QMessageBox.Icon.Warning
        )

        box.setText(
            "Setup check found "
            "something that needs attention."
        )

        box.setDetailedText(
            "\n".join(
                (
                    f"{name}: {detail}"
                    for name, ok, detail
                    in missing
                )
            )
        )

        box.setInformativeText(
            "\n".join(lines)
        )


        if api_problem:

            settings_button = (
                box.addButton(
                    "Open Settings",
                    (
                        QMessageBox
                        .ButtonRole
                        .ActionRole
                    ),
                )
            )

        else:

            settings_button = None


        box.addButton(
            "Continue",
            (
                QMessageBox
                .ButtonRole
                .RejectRole
            ),
        )


        box.exec()


        if (
            settings_button is not None
            and box.clickedButton()
            is settings_button
        ):

            self.open_settings()


    def showEvent(
        self,
        event,
    ):

        super().showEvent(
            event
        )


        if self._startup_health_checked:
            return


        self._startup_health_checked = True

        self.run_startup_health_check()


    def refresh_ai_badge(
        self,
    ):

        provider = get_provider()
        model_id = get_model(
            provider
        )

        provider_names = {
            "openai": "OpenAI",
            "groq": "Groq",
        }

        model_names = {
            "gpt-5.6-luna": "GPT-5.6 Luna",
            "gpt-5.6-terra": "GPT-5.6 Terra",
            "gpt-5.6-sol": "GPT-5.6 Sol",
            "openai/gpt-oss-20b": "GPT-OSS 20B",
            "openai/gpt-oss-120b": "GPT-OSS 120B",
        }

        provider_name = (
            provider_names.get(
                provider,
                provider.title(),
            )
        )

        model_name = (
            model_names.get(
                model_id,
                model_id,
            )
        )

        self.ai_badge.setText(
            f"{provider_name} / "
            f"{model_name}"
        )


    def resolve_eu5_executable(
        self,
    ):

        exe = (
            find_eu5_executable()
        )

        if exe:
            return exe


        selected, _ = (
            QFileDialog.getOpenFileName(
                self,
                "Locate Europa Universalis V",
                str(
                    Path.home()
                ),
                (
                    "Europa Universalis V "
                    "(eu5.exe);;"
                    "Executable files (*.exe)"
                ),
            )
        )


        if not selected:
            return None


        candidate = Path(
            selected
        )


        if (
            candidate.name.lower()
            != "eu5.exe"
        ):

            QMessageBox.warning(
                self,
                "Wrong executable",
                (
                    "Please select "
                    "Europa Universalis V's "
                    "eu5.exe."
                ),
            )

            return None


        try:

            save_manual_eu5_executable(
                candidate
            )

        except Exception as exc:

            QMessageBox.warning(
                self,
                "Could not save game path",
                str(exc),
            )

            return None


        return candidate


    def start_game(
        self,
    ):

        existing_pid = (
            find_eu5_pid()
        )


        if existing_pid is not None:

            if sys.platform == "win32":

                try:

                    import ctypes
                    from ctypes import wintypes

                    user32 = (
                        ctypes.windll.user32
                    )

                    windows = []


                    @ctypes.WINFUNCTYPE(
                        ctypes.c_bool,
                        wintypes.HWND,
                        wintypes.LPARAM,
                    )
                    def enum_windows(
                        hwnd,
                        lparam,
                    ):

                        if not (
                            user32
                            .IsWindowVisible(
                                hwnd
                            )
                        ):
                            return True


                        pid = (
                            wintypes.DWORD()
                        )


                        user32.GetWindowThreadProcessId(
                            hwnd,
                            ctypes.byref(
                                pid
                            ),
                        )


                        if (
                            pid.value
                            != existing_pid
                        ):
                            return True


                        if (
                            user32
                            .GetWindowTextLengthW(
                                hwnd
                            )
                            <= 0
                        ):
                            return True


                        windows.append(
                            hwnd
                        )

                        return False


                    user32.EnumWindows(
                        enum_windows,
                        0,
                    )


                    if windows:

                        user32.ShowWindow(
                            windows[0],
                            9,
                        )

                        user32.SetForegroundWindow(
                            windows[0]
                        )


                except Exception:
                    pass


            self.status.setText(
                "Europa Universalis V "
                "is already running"
            )

            return


        eu5_exe = (
            self.resolve_eu5_executable()
        )


        if eu5_exe is None:

            self.status.setText(
                "EU5 installation not selected"
            )

            return


        try:

            game_process = subprocess.Popen(
                [
                    str(eu5_exe),
                    "-console",
                ],
                cwd=str(
                    eu5_exe.parent
                ),
            )


        except Exception as exc:

            QMessageBox.warning(
                self,
                "Could not start EU5",
                str(exc),
            )

            return


        self.status.setText(
            "Starting Europa Universalis V "
            "with console enabled..."
        )

        self._arrange_after_launch(
            game_process.pid,
            0,
        )


    def _arrange_after_launch(
        self,
        pid: int,
        attempt: int,
    ):

        from PySide6.QtCore import QTimer

        from window_layout import (
            arrange_eu5_window,
        )


        result = arrange_eu5_window(
            pid,
            self,
        )


        if result.success:

            self.status.setText(
                result.message
            )

            return


        # EU5 takes a while before its actual
        # game window exists.
        if attempt < 40:

            QTimer.singleShot(
                500,
                lambda: (
                    self._arrange_after_launch(
                        pid,
                        attempt + 1,
                    )
                ),
            )

            return


        self.status.setText(
            "EU5 started, but its window "
            "could not be arranged automatically."
        )


    def arrange_windows(
        self,
    ):

        from window_layout import (
            arrange_eu5_window,
        )


        pid = find_eu5_pid()


        if pid is None:

            QMessageBox.information(
                self,
                "Europa Universalis V",
                (
                    "Europa Universalis V "
                    "is not currently running."
                ),
            )

            return


        result = arrange_eu5_window(
            pid,
            self,
        )


        self.status.setText(
            result.message
        )


        if not result.success:

            QMessageBox.information(
                self,
                "Arrange Windows",
                result.message,
            )


    def open_load_game(
        self,
    ):

        project_root = (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )


        rakaly_candidates = sorted(
            (
                project_root
                / "tools"
                / "rakaly"
            ).glob(
                "**/rakaly.exe"
            )
        )


        if not rakaly_candidates:

            QMessageBox.warning(
                self,
                "Rakaly not found",
                (
                    "Could not find Rakaly "
                    "inside the companion "
                    "tools directory."
                ),
            )

            return


        save_dir = (
            find_eu5_save_directory()
        )


        if save_dir is None:

            QMessageBox.warning(
                self,
                "Save directory not found",
                (
                    "The companion could not "
                    "find Europa Universalis V's "
                    "save-game directory."
                ),
            )

            return


        dialog = SaveBrowserDialog(
            rakaly_candidates[-1],
            save_dir,
            self,
        )


        if not dialog.exec():
            return


        selected = (
            dialog.selected_save
        )


        if not selected:
            return


        self.status.setText(
            "Selected save: "
            + selected.name
        )


        QMessageBox.information(
            self,
            "Save selected",
            (
                selected.name
                + "\n\n"
                + "Direct runtime loading is "
                  "temporarily disabled because "
                  "EU5's console load command "
                  "is not resolving save files "
                  "correctly in the current build."
            ),
        )


    def open_settings(
        self,
    ):

        dialog = SettingsDialog(
            self
        )


        if dialog.exec():

            self.refresh_ai_badge()

            provider = (
                get_provider()
            )

            model = get_model(
                provider
            )


            self.status.setText(
                "Settings saved - "
                f"{provider} / {model}"
            )


    # ========================================================
    # UI helpers
    # ========================================================

    def toggle_log(
        self,
        checked: bool,
    ):

        self.debug_log.setVisible(
            checked
        )

        self.log_action.setText(
            "Hide Debug Log"
            if checked
            else "Show Debug Log"
        )


    def append_user(
        self,
        text: str,
    ):

        safe = html.escape(
            text
        )

        self.chat.append(
            f"""
            <div style="
                margin-top:16px;
                margin-bottom:14px;
            ">
                <span style="
                    color:#d1b477;
                    font-size:12px;
                    font-weight:600;
                ">
                    YOU
                </span>
                <br>
                <span style="
                    color:#eeeeee;
                    font-size:14px;
                ">
                    {safe}
                </span>
            </div>
            """
        )


    def append_assistant(
        self,
        text: str,
    ):

        rendered = markdown.markdown(
            text,
            extensions=[
                "sane_lists",
                "tables",
            ],
        )

        self.chat.append(
            f"""
            <table
                width="100%"
                cellspacing="0"
                cellpadding="12"
                bgcolor="#18232d"
            >
                <tr>
                    <td>
                        <span style="
                            color:#8fbadd;
                            font-size:12px;
                            font-weight:600;
                        ">
                            COMPANION
                        </span>
                        <br><br>
                        <span style="
                            color:#dce7ef;
                            font-size:14px;
                        ">
                            {rendered}
                        </span>
                    </td>
                </tr>
            </table>
            """
        )

        scrollbar = (
            self.chat
            .verticalScrollBar()
        )

        scrollbar.setValue(
            scrollbar.maximum()
        )


    def set_busy(
        self,
        busy: bool,
    ):

        self.input.setEnabled(
            not busy
        )

        self.send_button.setEnabled(
            not busy
        )


        if busy:

            self.progress.setRange(
                0,
                0,
            )

        else:

            self.progress.setRange(
                0,
                1,
            )

            self.progress.setValue(
                1
            )


    # ========================================================
    # Ask
    # ========================================================

    def send_question(
        self,
    ):

        if (
            self.process is not None
            and self.process.state()
            != QProcess.NotRunning
        ):
            return


        raw_question = (
            self.input
            .toPlainText()
            .strip()
        )


        if not raw_question:
            return


        # Keep the first GUI version simple:
        # normalize accidental multiline input into a single
        # CLI argument.
        question = " ".join(
            raw_question.split()
        )


        if self.rakaly is None:

            QMessageBox.critical(
                self,
                "Rakaly not found",
                (
                    "Could not locate rakaly.exe "
                    "under tools\\rakaly."
                ),
            )

            return


        if not ASK_SCRIPT.exists():

            QMessageBox.critical(
                self,
                "Backend not found",
                str(
                    ASK_SCRIPT
                ),
            )

            return


        provider = (
            get_provider()
        )

        api_key = get_api_key(
            provider
        )

        model = get_model(
            provider
        )


        if not api_key:

            QMessageBox.information(
                self,
                "AI provider not configured",
                (
                    "Add an API key in "
                    "Settings before asking "
                    "the companion."
                ),
            )


            self.open_settings()


            provider = (
                get_provider()
            )

            api_key = get_api_key(
                provider
            )

            model = get_model(
                provider
            )


            if not api_key:
                return


        eu5_pid = (
            find_eu5_pid()
        )


        if eu5_pid is None:

            # Web/general questions can run without EU5.
            # If the model later requests campaign data,
            # ask_eu5.py will report that EU5 is required.
            eu5_pid = 0


        self.current_question = (
            question
        )

        self.output_buffer = ""

        self.debug_log.clear()

        self.input.clear()


        self.append_user(
            question
        )


        self.status.setText(
            "Fetching current game state…"
        )

        self.footer.setText(
            f"v{APP_DISPLAY_VERSION} • Working…"
        )

        self.set_busy(
            True
        )


        # ----------------------------------------------------
        # QProcess keeps the UI responsive while the existing
        # backend does its work.
        # ----------------------------------------------------

        process = QProcess(
            self
        )

        self.process = process


        process.setWorkingDirectory(
            str(
                PROJECT_ROOT
            )
        )


        environment = (
            QProcessEnvironment.systemEnvironment()
        )

        environment.insert(
            "PYTHONUTF8",
            "1",
        )

        environment.insert(
            "PYTHONIOENCODING",
            "utf-8",
        )

        environment.insert(
            "AI_PROVIDER",
            provider,
        )

        environment.insert(
            "AI_MODEL",
            model,
        )


        if provider == "groq":

            environment.insert(
                "GROQ_API_KEY",
                api_key,
            )

        else:

            environment.insert(
                "OPENAI_API_KEY",
                api_key,
            )

        process.setProcessEnvironment(
            environment
        )


        process.setProcessChannelMode(
            QProcess.MergedChannels
        )


        process.readyReadStandardOutput.connect(
            self.read_process_output
        )

        process.finished.connect(
            self.process_finished
        )

        process.errorOccurred.connect(
            self.process_error
        )


        args = [
            str(
                ASK_SCRIPT
            ),
            str(
                eu5_pid
            ),
            str(
                self.rakaly
            ),
            str(
                PROJECT_ROOT
            ),
            question,
        ]


        process.start(
            sys.executable,
            args,
        )


    # ========================================================
    # Live process output
    # ========================================================

    def read_process_output(
        self,
    ):

        if self.process is None:
            return


        chunk = bytes(
            self.process
            .readAllStandardOutput()
        ).decode(
            "utf-8",
            errors="replace",
        )


        if not chunk:
            return


        self.output_buffer += (
            chunk
        )


        self.debug_log.insertPlainText(
            chunk
        )

        scrollbar = (
            self.debug_log
            .verticalScrollBar()
        )

        scrollbar.setValue(
            scrollbar.maximum()
        )


        self.update_status_from_output()


    def update_status_from_output(
        self,
    ):

        output = self.output_buffer

        if (
            "Requesting exact-date save"
            in output
        ):

            self.status.setText(
                "Saving exact current game state…"
            )


        if (
            "Waiting for EU5 to write"
            in output
        ):

            self.status.setText(
                "Waiting for EU5 save…"
            )


        if (
            "Decoding EU5 save"
            in output
            or "Decoding:"
            in output
        ):

            self.status.setText(
                "Decoding save…"
            )


        if (
            "Updating visible-world database"
            in output
            or "DIRECT VISIBLE-WORLD IMPORT"
            in output
        ):

            self.status.setText(
                "Reading visible world…"
            )


        if "Reading: " in output:

            self.status.setText(
                "Thinking with live game data…"
            )


        live_match = re.search(
            r"LIVE ? ([A-Za-z0-9_]+) "
            r"(\d{4}-\d{2}-\d{2})",
            output,
        )

        if live_match:

            country_key = (
                live_match.group(1)
            )

            raw_date = (
                live_match.group(2)
            )

            country_name = (
                localize_static_key(
                    country_key
                )
            )

            date_text = (
                pretty_game_date(
                    raw_date
                )
            )

            self.header.setText(
                '<span style="color:#72c487;">'
                '? LIVE'
                '</span>'
                '<span style="color:#dce2e8;">'
                '&nbsp;&nbsp;|&nbsp;&nbsp;'
                + html.escape(
                    country_name
                )
                + '&nbsp;&nbsp;|&nbsp;&nbsp;'
                + html.escape(
                    date_text
                )
                + '</span>'
            )


    # ========================================================
    # Completion
    # ========================================================

    def process_finished(
        self,
        exit_code: int,
        exit_status,
    ):

        # Grab anything left in the pipe.
        self.read_process_output()


        output = (
            self.output_buffer
        )


        self.set_busy(
            False
        )


        if exit_code != 0:

            self.status.setText(
                "Request failed"
            )

            self.footer.setText(
                f"v{APP_DISPLAY_VERSION} • "
                f"Backend exited with code {exit_code}"
            )


            tail = "\n".join(
                output
                .strip()
                .splitlines()[-12:]
            )


            self.append_assistant(
                "The backend request failed.\n\n"
                + tail
            )

            return


        if (
            "Campaign state:          used"
            in output
        ):

            self.update_live_header_from_db()


        answer = (
            self.extract_answer(
                output
            )
        )


        if answer:

            self.append_assistant(
                answer
            )

        else:

            self.append_assistant(
                (
                    "The request completed, "
                    "but I could not extract "
                    "the answer from the backend output."
                )
            )


        cost = self.extract_value(
            output,
            r"Estimated API cost:\s+([^\r\n]+)",
        )


        provider = self.extract_value(
            output,
            r"Provider:\s+([^\r\n]+)",
        )


        model = self.extract_value(
            output,
            r"Model:\s+([^\r\n]+)",
        )


        acquisition = self.extract_value(
            output,
            r"Fresh-state acquisition:\s+([^\r\n]+)",
        )


        reasoning = self.extract_value(
            output,
            r"OpenAI reasoning:\s+([^\r\n]+)",
        )


        footer_parts = [
            f"v{APP_DISPLAY_VERSION}"
        ]


        if provider:
            footer_parts.append(
                provider.title()
            )

        if model:
            footer_parts.append(
                model
            )

        if cost:
            footer_parts.append(
                f"cost {cost}"
            )

        if acquisition:
            footer_parts.append(
                f"state {acquisition}"
            )

        if reasoning:
            footer_parts.append(
                f"AI {reasoning}"
            )


        self.footer.setText(
            " • ".join(
                footer_parts
            )
            if footer_parts
            else "Ready"
        )


        self.status.setText(
            "Ready"
        )


        self.input.setFocus()


    def process_error(
        self,
        error,
    ):

        self.set_busy(
            False
        )

        self.status.setText(
            "Process error"
        )


    # ========================================================
    # Output parser
    # ========================================================

    @staticmethod
    def extract_value(
        output: str,
        pattern: str,
    ) -> str | None:

        match = re.search(
            pattern,
            output,
        )

        if not match:
            return None

        return (
            match.group(1)
            .strip()
        )


    @staticmethod
    def extract_answer(
        output: str,
    ) -> str:

        # Normalize Windows line endings first.
        text = output.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )


        # Backend output contains:
        #
        # You: question
        #
        # answer...
        #
        # ======================================================================
        # Fresh-state acquisition: ...
        #
        # Use the LAST You: block in case other child output
        # happens to contain similar text.

        marker = "\nYou: "

        you_position = text.rfind(
            marker
        )

        if you_position < 0:

            if text.startswith(
                "You: "
            ):
                you_position = 0

            else:
                return ""


        # Move to the end of the You: line.
        line_end = text.find(
            "\n",
            you_position + 1,
        )

        if line_end < 0:
            return ""


        answer_start = (
            line_end + 1
        )


        # Skip blank lines between question and answer.
        while (
            answer_start < len(text)
            and text[answer_start] == "\n"
        ):
            answer_start += 1


        stats_marker = (
            "\n"
            + "=" * 70
            + "\nFresh-state acquisition:"
        )


        answer_end = text.find(
            stats_marker,
            answer_start,
        )


        if answer_end < 0:

            # Fallback: first 70-character divider after answer.
            divider = (
                "\n"
                + "=" * 70
            )

            answer_end = text.find(
                divider,
                answer_start,
            )


        if answer_end < 0:
            answer_end = len(
                text
            )


        return (
            text[
                answer_start:
                answer_end
            ]
            .strip()
        )



def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "EU5 AI Companion"
    )


    window = CompanionWindow()

    window.show()


    raise SystemExit(
        app.exec()
    )


if __name__ == "__main__":
    main()
