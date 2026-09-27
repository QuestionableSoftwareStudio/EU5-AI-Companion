from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import time

from runtime_paths import CONSOLE_LOG, initialize_runtime


if len(sys.argv) < 4:
    raise SystemExit(
        "Usage: eu5_console_expect.py "
        "EU5_PID EXPECTED_TEXT COMMAND..."
    )

pid = int(sys.argv[1])
expected = sys.argv[2]
command = " ".join(sys.argv[3:])

TIMEOUT = 3.0
POLL_INTERVAL = 0.05
TAIL_ROWS = 120

initialize_runtime()


def log(message: str) -> None:
    with CONSOLE_LOG.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            "[console-expect] "
            + message
            + "\n"
        )


kernel32 = ctypes.WinDLL(
    "kernel32",
    use_last_error=True,
)
user32 = ctypes.WinDLL(
    "user32",
    use_last_error=True,
)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000

FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002

OPEN_EXISTING = 3
KEY_EVENT = 0x0001
VK_RETURN = 0x0D

INVALID_HANDLE_VALUE = (
    wintypes.HANDLE(-1).value
)


class COORD(ctypes.Structure):
    _fields_ = [
        ("X", ctypes.c_short),
        ("Y", ctypes.c_short),
    ]


class SMALL_RECT(ctypes.Structure):
    _fields_ = [
        ("Left", ctypes.c_short),
        ("Top", ctypes.c_short),
        ("Right", ctypes.c_short),
        ("Bottom", ctypes.c_short),
    ]


class CONSOLE_SCREEN_BUFFER_INFO(
    ctypes.Structure
):
    _fields_ = [
        ("dwSize", COORD),
        ("dwCursorPosition", COORD),
        ("wAttributes", wintypes.WORD),
        ("srWindow", SMALL_RECT),
        ("dwMaximumWindowSize", COORD),
    ]


class CHAR_UNION(ctypes.Union):
    _fields_ = [
        ("UnicodeChar", wintypes.WCHAR),
        ("AsciiChar", ctypes.c_char),
    ]


class KEY_EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", wintypes.BOOL),
        ("wRepeatCount", wintypes.WORD),
        ("wVirtualKeyCode", wintypes.WORD),
        ("wVirtualScanCode", wintypes.WORD),
        ("uChar", CHAR_UNION),
        ("dwControlKeyState", wintypes.DWORD),
    ]


class EVENT_UNION(ctypes.Union):
    _fields_ = [
        ("KeyEvent", KEY_EVENT_RECORD),
        ("raw", ctypes.c_byte * 16),
    ]


class INPUT_RECORD(ctypes.Structure):
    _fields_ = [
        ("EventType", wintypes.WORD),
        ("Event", EVENT_UNION),
    ]


kernel32.AttachConsole.argtypes = [
    wintypes.DWORD
]
kernel32.AttachConsole.restype = (
    wintypes.BOOL
)

kernel32.FreeConsole.restype = (
    wintypes.BOOL
)

kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
kernel32.CreateFileW.restype = (
    wintypes.HANDLE
)

kernel32.CloseHandle.argtypes = [
    wintypes.HANDLE
]
kernel32.CloseHandle.restype = (
    wintypes.BOOL
)

kernel32.GetConsoleScreenBufferInfo.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(
        CONSOLE_SCREEN_BUFFER_INFO
    ),
]
kernel32.GetConsoleScreenBufferInfo.restype = (
    wintypes.BOOL
)

kernel32.ReadConsoleOutputCharacterW.argtypes = [
    wintypes.HANDLE,
    wintypes.LPWSTR,
    wintypes.DWORD,
    COORD,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.ReadConsoleOutputCharacterW.restype = (
    wintypes.BOOL
)

kernel32.WriteConsoleInputW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(INPUT_RECORD),
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.WriteConsoleInputW.restype = (
    wintypes.BOOL
)

user32.VkKeyScanW.argtypes = [
    wintypes.WCHAR
]
user32.VkKeyScanW.restype = (
    ctypes.c_short
)

user32.MapVirtualKeyW.argtypes = [
    wintypes.UINT,
    wintypes.UINT,
]
user32.MapVirtualKeyW.restype = (
    wintypes.UINT
)


def fail(message: str, code: int) -> None:
    log(message)

    try:
        kernel32.FreeConsole()
    except Exception:
        pass

    raise SystemExit(code)


def read_tail(
    handle,
    rows: int = TAIL_ROWS,
) -> str:

    info = CONSOLE_SCREEN_BUFFER_INFO()

    if not kernel32.GetConsoleScreenBufferInfo(
        handle,
        ctypes.byref(info),
    ):
        fail(
            "GetConsoleScreenBufferInfo failed",
            31,
        )

    width = max(
        1,
        int(info.dwSize.X),
    )

    cursor_y = max(
        0,
        int(info.dwCursorPosition.Y),
    )

    start_y = max(
        0,
        cursor_y - rows + 1,
    )

    row_count = (
        cursor_y - start_y + 1
    )

    length = (
        width * row_count
    )

    buffer = ctypes.create_unicode_buffer(
        length + 1
    )

    chars_read = wintypes.DWORD(0)

    ok = kernel32.ReadConsoleOutputCharacterW(
        handle,
        buffer,
        length,
        COORD(0, start_y),
        ctypes.byref(chars_read),
    )

    if not ok:
        fail(
            "ReadConsoleOutputCharacterW failed",
            32,
        )

    raw = buffer[:chars_read.value]

    lines = []

    for offset in range(
        0,
        len(raw),
        width,
    ):
        lines.append(
            raw[
                offset:
                offset + width
            ].rstrip()
        )

    return "\n".join(lines)


def make_key(
    char: str,
    down: bool,
) -> INPUT_RECORD:

    record = INPUT_RECORD()
    record.EventType = KEY_EVENT

    key = record.Event.KeyEvent

    key.bKeyDown = bool(down)
    key.wRepeatCount = 1
    key.dwControlKeyState = 0

    if char == "\r":
        vk = VK_RETURN
    else:
        result = user32.VkKeyScanW(
            char
        )

        vk = (
            result & 0xFF
            if result != -1
            else 0
        )

    key.wVirtualKeyCode = vk

    key.wVirtualScanCode = (
        user32.MapVirtualKeyW(
            vk,
            0,
        )
        if vk
        else 0
    )

    key.uChar.UnicodeChar = char

    return record


# Leave PowerShell's console and attach
# to EU5's console.
kernel32.FreeConsole()

if not kernel32.AttachConsole(pid):
    error = ctypes.get_last_error()

    fail(
        f"AttachConsole failed: {error}",
        30,
    )


conin = kernel32.CreateFileW(
    "CONIN$",
    GENERIC_READ | GENERIC_WRITE,
    FILE_SHARE_READ | FILE_SHARE_WRITE,
    None,
    OPEN_EXISTING,
    0,
    None,
)

if conin == INVALID_HANDLE_VALUE:
    fail(
        "Could not open CONIN$",
        33,
    )


conout = kernel32.CreateFileW(
    "CONOUT$",
    GENERIC_READ | GENERIC_WRITE,
    FILE_SHARE_READ | FILE_SHARE_WRITE,
    None,
    OPEN_EXISTING,
    0,
    None,
)

if conout == INVALID_HANDLE_VALUE:
    kernel32.CloseHandle(conin)

    fail(
        "Could not open CONOUT$",
        34,
    )


before = read_tail(
    conout
)

before_count = (
    before.count(expected)
)

log(
    f"PID={pid} "
    f"command={command!r} "
    f"before_count={before_count}"
)


records = []

for char in command:
    records.append(
        make_key(char, True)
    )
    records.append(
        make_key(char, False)
    )

records.append(
    make_key("\r", True)
)
records.append(
    make_key("\r", False)
)

array_type = (
    INPUT_RECORD * len(records)
)

array = array_type(
    *records
)

written = wintypes.DWORD(0)

ok = kernel32.WriteConsoleInputW(
    conin,
    array,
    len(array),
    ctypes.byref(written),
)

if not ok:
    kernel32.CloseHandle(conout)
    kernel32.CloseHandle(conin)

    fail(
        "WriteConsoleInputW failed",
        35,
    )


deadline = (
    time.monotonic()
    + TIMEOUT
)

success = False

while time.monotonic() < deadline:

    current = read_tail(
        conout
    )

    if (
        current.count(expected)
        > before_count
    ):
        success = True
        break

    time.sleep(
        POLL_INTERVAL
    )


kernel32.CloseHandle(conout)
kernel32.CloseHandle(conin)
kernel32.FreeConsole()


if success:
    log(
        f"SUCCESS: {expected}"
    )

    raise SystemExit(0)


log(
    f"TIMEOUT waiting for: "
    f"{expected}"
)

raise SystemExit(20)
