from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from save_metadata import list_saves


MONTHS = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def human_date(
    raw: str | None,
) -> str:

    if not raw:
        return "Unknown"

    try:
        parts = raw.split(".")

        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])

        return (
            f"{day} "
            f"{MONTHS[month]} "
            f"{year}"
        )

    except Exception:
        return raw


class SaveBrowserDialog(
    QDialog,
):

    def __init__(
        self,
        rakaly: Path,
        save_dir: Path,
        parent=None,
    ):
        super().__init__(
            parent
        )

        self.rakaly = rakaly
        self.save_dir = save_dir
        self.selected_save = None
        self.rows = []

        self.setWindowTitle(
            "Load Game"
        )

        self.resize(
            850,
            580,
        )

        self.setStyleSheet(
            """
            QDialog {
                background: #16181d;
                color: #e7e9ee;
            }

            QLabel {
                color: #d6d9df;
            }

            QLineEdit {
                background: #20242b;
                border: 1px solid #343943;
                border-radius: 6px;
                padding: 8px;
                color: #f0f2f5;
            }

            QTableWidget {
                background: #1b1e24;
                alternate-background-color: #20242b;
                border: 1px solid #30353e;
                gridline-color: #30353e;
                color: #e7e9ee;
                selection-background-color: #34465f;
            }

            QHeaderView::section {
                background: #242831;
                color: #dfe3e8;
                border: none;
                padding: 7px;
            }

            QPushButton {
                background: #292e37;
                border: 1px solid #3a404b;
                border-radius: 6px;
                padding: 8px 14px;
                color: #eeeeee;
            }

            QPushButton:hover {
                background: #343b47;
            }

            QPushButton:disabled {
                color: #777;
            }

            QPushButton#loadButton {
                background: #315a84;
            }

            QPushButton#loadButton:hover {
                background: #3a6a9c;
            }
            """
        )


        root = QVBoxLayout(
            self
        )


        title = QLabel(
            "Load Europa Universalis V save"
        )

        title.setStyleSheet(
            "font-size: 18px; "
            "font-weight: 600;"
        )

        root.addWidget(
            title
        )


        subtitle = QLabel(
            "Ironman saves are hidden because "
            "Advisor Mode does not support them."
        )

        subtitle.setStyleSheet(
            "color: #8f96a3;"
        )

        root.addWidget(
            subtitle
        )


        self.search = QLineEdit()

        self.search.setPlaceholderText(
            "Search country, date, version "
            "or filename…"
        )

        self.search.textChanged.connect(
            self.apply_filter
        )

        root.addWidget(
            self.search
        )


        self.table = QTableWidget(
            0,
            4,
        )

        self.table.setHorizontalHeaderLabels(
            [
                "Country",
                "Game date",
                "Version",
                "Modified",
            ]
        )

        self.table.setAlternatingRowColors(
            True
        )

        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.table.verticalHeader().setVisible(
            False
        )

        header = (
            self.table.horizontalHeader()
        )

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        self.table.itemSelectionChanged.connect(
            self.selection_changed
        )

        self.table.itemDoubleClicked.connect(
            lambda *_:
                self.accept_selected()
        )

        root.addWidget(
            self.table,
            1,
        )


        footer = QHBoxLayout()

        self.count_label = QLabel()

        self.count_label.setStyleSheet(
            "color: #8f96a3;"
        )

        footer.addWidget(
            self.count_label
        )

        footer.addStretch()


        cancel = QPushButton(
            "Cancel"
        )

        cancel.clicked.connect(
            self.reject
        )

        footer.addWidget(
            cancel
        )


        self.load_button = QPushButton(
            "Load selected"
        )

        self.load_button.setObjectName(
            "loadButton"
        )

        self.load_button.setEnabled(
            False
        )

        self.load_button.clicked.connect(
            self.accept_selected
        )

        footer.addWidget(
            self.load_button
        )


        root.addLayout(
            footer
        )


        self.load_rows()


    def load_rows(
        self,
    ):

        saves = list_saves(
            self.rakaly,
            self.save_dir,
        )

        self.rows = [
            save
            for save in saves
            if not save.ironman
        ]

        self.populate(
            self.rows
        )


    def populate(
        self,
        saves,
    ):

        self.table.setRowCount(
            0
        )


        for save in saves:

            row = (
                self.table.rowCount()
            )

            self.table.insertRow(
                row
            )


            country = QTableWidgetItem(
                save.country_name
                or "Unknown country"
            )

            country.setData(
                Qt.ItemDataRole.UserRole,
                str(save.path),
            )

            country.setToolTip(
                save.path.name
            )


            game_date = QTableWidgetItem(
                human_date(
                    save.date
                )
            )


            version = QTableWidgetItem(
                save.version
                or "?"
            )


            modified = QTableWidgetItem(
                datetime.fromtimestamp(
                    save.modified
                ).strftime(
                    "%d %b %Y  %H:%M"
                )
            )


            self.table.setItem(
                row,
                0,
                country,
            )

            self.table.setItem(
                row,
                1,
                game_date,
            )

            self.table.setItem(
                row,
                2,
                version,
            )

            self.table.setItem(
                row,
                3,
                modified,
            )


        self.count_label.setText(
            f"{len(saves)} saves"
        )


    def apply_filter(
        self,
        text,
    ):

        query = (
            text.strip().lower()
        )

        if not query:
            self.populate(
                self.rows
            )
            return


        filtered = []


        for save in self.rows:

            haystack = " ".join(
                [
                    save.country_name
                    or "",
                    save.date
                    or "",
                    save.version
                    or "",
                    save.path.name,
                    save.playthrough_name
                    or "",
                ]
            ).lower()


            if query in haystack:
                filtered.append(
                    save
                )


        self.populate(
            filtered
        )


    def selection_changed(
        self,
    ):

        self.load_button.setEnabled(
            bool(
                self.table.selectedItems()
            )
        )


    def accept_selected(
        self,
    ):

        row = (
            self.table.currentRow()
        )

        if row < 0:
            return


        item = self.table.item(
            row,
            0,
        )

        if item is None:
            return


        self.selected_save = Path(
            item.data(
                Qt.ItemDataRole.UserRole
            )
        )


        self.accept()


def main():

    if len(sys.argv) != 3:

        raise SystemExit(
            "Usage: save_browser_dialog.py "
            "RAKALY SAVE_DIR"
        )


    app = QApplication(
        sys.argv
    )


    dialog = SaveBrowserDialog(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
    )


    if (
        dialog.exec()
        == QDialog.DialogCode.Accepted
        and dialog.selected_save
    ):

        print(
            dialog.selected_save
        )


if __name__ == "__main__":
    main()
