from __future__ import annotations

import ctypes
import sys

from ctypes import wintypes
from dataclasses import dataclass

from PySide6.QtGui import QGuiApplication


# =========================================================
# Win32
# =========================================================

if sys.platform == "win32":

    user32 = ctypes.WinDLL(
        "user32",
        use_last_error=True,
    )

    EnumWindowsProc = (
        ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )
    )

    user32.EnumWindows.argtypes = [
        EnumWindowsProc,
        wintypes.LPARAM,
    ]

    user32.EnumWindows.restype = (
        wintypes.BOOL
    )

    user32.IsWindowVisible.argtypes = [
        wintypes.HWND
    ]

    user32.IsWindowVisible.restype = (
        wintypes.BOOL
    )

    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(
            wintypes.DWORD
        ),
    ]

    user32.GetWindowThreadProcessId.restype = (
        wintypes.DWORD
    )

    user32.GetWindowRect.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(
            wintypes.RECT
        ),
    ]

    user32.GetWindowRect.restype = (
        wintypes.BOOL
    )

    user32.GetWindowTextLengthW.argtypes = [
        wintypes.HWND
    ]

    user32.GetWindowTextLengthW.restype = (
        ctypes.c_int
    )

    user32.ShowWindow.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
    ]

    user32.ShowWindow.restype = (
        wintypes.BOOL
    )

    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]

    user32.SetWindowPos.restype = (
        wintypes.BOOL
    )


    if ctypes.sizeof(
        ctypes.c_void_p
    ) == 8:

        GetWindowLongPtr = (
            user32.GetWindowLongPtrW
        )

        SetWindowLongPtr = (
            user32.SetWindowLongPtrW
        )

    else:

        GetWindowLongPtr = (
            user32.GetWindowLongW
        )

        SetWindowLongPtr = (
            user32.SetWindowLongW
        )


    GetWindowLongPtr.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
    ]

    GetWindowLongPtr.restype = (
        ctypes.c_ssize_t
    )

    SetWindowLongPtr.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_ssize_t,
    ]

    SetWindowLongPtr.restype = (
        ctypes.c_ssize_t
    )


GWL_STYLE = -16

WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000

SW_RESTORE = 9
SW_MAXIMIZE = 3

SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


@dataclass
class LayoutResult:

    success: bool
    message: str
    mode: str | None = None


# =========================================================
# Window discovery
# =========================================================

def find_main_window(
    pid: int,
) -> int | None:

    if sys.platform != "win32":
        return None


    candidates = []


    @EnumWindowsProc
    def callback(
        hwnd,
        lparam,
    ):

        if not user32.IsWindowVisible(
            hwnd
        ):
            return True


        window_pid = (
            wintypes.DWORD()
        )


        user32.GetWindowThreadProcessId(
            hwnd,
            ctypes.byref(
                window_pid
            ),
        )


        if window_pid.value != pid:
            return True


        rect = wintypes.RECT()


        if not user32.GetWindowRect(
            hwnd,
            ctypes.byref(
                rect
            ),
        ):
            return True


        width = (
            rect.right
            - rect.left
        )

        height = (
            rect.bottom
            - rect.top
        )


        if (
            width < 400
            or height < 300
        ):
            return True


        title_length = (
            user32
            .GetWindowTextLengthW(
                hwnd
            )
        )


        # Prefer the large, titled game window.
        score = (
            width * height
            + max(
                title_length,
                0,
            ) * 1000
        )


        candidates.append(
            (
                score,
                hwnd,
            )
        )


        return True


    user32.EnumWindows(
        callback,
        0,
    )


    if not candidates:
        return None


    candidates.sort(
        reverse=True,
    )


    return candidates[0][1]


# =========================================================
# Borderless handling
# =========================================================

def make_borderless(
    hwnd: int,
) -> None:

    style = (
        GetWindowLongPtr(
            hwnd,
            GWL_STYLE,
        )
    )


    remove = (
        WS_CAPTION
        | WS_THICKFRAME
        | WS_MINIMIZEBOX
        | WS_MAXIMIZEBOX
        | WS_SYSMENU
    )


    style &= ~remove


    SetWindowLongPtr(
        hwnd,
        GWL_STYLE,
        style,
    )


def move_window(
    hwnd: int,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:

    user32.ShowWindow(
        hwnd,
        SW_RESTORE,
    )


    user32.SetWindowPos(
        hwnd,
        None,
        int(x),
        int(y),
        int(width),
        int(height),
        (
            SWP_NOZORDER
            | SWP_NOACTIVATE
            | SWP_FRAMECHANGED
        ),
    )


# =========================================================
# Layout decision
# =========================================================

def arrange_eu5_window(
    pid: int,
    companion_window,
) -> LayoutResult:

    if sys.platform != "win32":

        return LayoutResult(
            False,
            "Window arrangement is only "
            "implemented for Windows.",
        )


    hwnd = find_main_window(
        pid
    )


    if hwnd is None:

        return LayoutResult(
            False,
            "EU5 window is not ready yet.",
        )


    screens = (
        QGuiApplication.screens()
    )


    if not screens:

        return LayoutResult(
            False,
            "No displays detected.",
        )


    companion_screen = (
        companion_window.screen()
        or QGuiApplication.primaryScreen()
    )


    # =====================================================
    # Multiple monitors
    # =====================================================

    if len(screens) >= 2:

        alternatives = [
            screen
            for screen in screens
            if screen is not companion_screen
        ]


        # Largest alternative display wins.
        target = max(
            alternatives,
            key=lambda screen: (
                screen.geometry().width()
                * screen.geometry().height()
            ),
        )


        rect = (
            target.geometry()
        )


        make_borderless(
            hwnd
        )


        move_window(
            hwnd,
            rect.x(),
            rect.y(),
            rect.width(),
            rect.height(),
        )


        return LayoutResult(
            True,
            (
                "EU5 arranged on "
                f"{target.name()} "
                f"({rect.width()}x"
                f"{rect.height()})"
            ),
            "multi-monitor",
        )


    # =====================================================
    # One monitor
    # =====================================================

    screen = screens[0]

    available = (
        screen.availableGeometry()
    )


    aspect = (
        available.width()
        / max(
            available.height(),
            1,
        )
    )


    # Treat ~21:9 and wider / very wide resolutions
    # as an ultrawide companion layout.
    ultrawide = (
        aspect >= 2.15
        or available.width() >= 3000
    )


    if ultrawide:

        companion_width = int(
            available.width()
            * 0.27
        )


        # Don't make the companion unusably narrow.
        companion_width = max(
            430,
            companion_width,
        )


        game_width = (
            available.width()
            - companion_width
        )


        make_borderless(
            hwnd
        )


        move_window(
            hwnd,
            available.x(),
            available.y(),
            game_width,
            available.height(),
        )


        companion_window.setGeometry(
            available.x()
            + game_width,
            available.y(),
            companion_width,
            available.height(),
        )


        return LayoutResult(
            True,
            (
                "Ultrawide layout: "
                f"EU5 {game_width}px / "
                f"Companion "
                f"{companion_width}px"
            ),
            "ultrawide",
        )


    # =====================================================
    # Normal single monitor
    # =====================================================

    # Don't force the Companion into a tiny overlay.
    # Just maximize EU5 normally.
    user32.ShowWindow(
        hwnd,
        SW_MAXIMIZE,
    )


    return LayoutResult(
        True,
        (
            "Single-display layout: "
            "EU5 maximized."
        ),
        "single-monitor",
    )


if __name__ == "__main__":

    print(
        "window_layout.py loaded."
    )
