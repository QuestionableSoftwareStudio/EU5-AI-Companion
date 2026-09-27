import ctypes
from ctypes import wintypes
from pathlib import Path
import sys

from runtime_paths import (
    CONSOLE_LOG,
    initialize_runtime,
)

if len(sys.argv) < 3:
    raise SystemExit(
        "Usage: send_eu5_console.py EU5_PID COMMAND"
    )

pid = int(sys.argv[1])
text = " ".join(sys.argv[2:])

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

initialize_runtime()

log = CONSOLE_LOG


def write_log(message):
    with log.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000

FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002

OPEN_EXISTING = 3

KEY_EVENT = 0x0001
VK_RETURN = 0x0D

INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


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


kernel32.FreeConsole.restype = wintypes.BOOL

kernel32.AttachConsole.argtypes = [wintypes.DWORD]
kernel32.AttachConsole.restype = wintypes.BOOL

kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
kernel32.CreateFileW.restype = wintypes.HANDLE

kernel32.WriteConsoleInputW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(INPUT_RECORD),
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.WriteConsoleInputW.restype = wintypes.BOOL

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
user32.VkKeyScanW.restype = ctypes.c_short

user32.MapVirtualKeyW.argtypes = [
    wintypes.UINT,
    wintypes.UINT,
]
user32.MapVirtualKeyW.restype = wintypes.UINT


write_log("=" * 60)
write_log(f"PID: {pid}")
write_log(f"Command: {text}")

# Detach from PowerShell's console.
kernel32.FreeConsole()

if not kernel32.AttachConsole(pid):
    err = ctypes.get_last_error()
    write_log(f"AttachConsole FAILED: {err}")
    raise OSError(err, "AttachConsole failed")

write_log("AttachConsole succeeded")

# Explicitly open the console we just attached to.
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
    err = ctypes.get_last_error()
    write_log(f"CreateFile(CONIN$) FAILED: {err}")
    raise OSError(err, "Could not open CONIN$")

write_log("CONIN$ opened successfully")


def make_key(char, down=True):
    record = INPUT_RECORD()
    record.EventType = KEY_EVENT

    key = record.Event.KeyEvent
    key.bKeyDown = bool(down)
    key.wRepeatCount = 1
    key.dwControlKeyState = 0

    if char == "\r":
        vk = VK_RETURN
        scan = user32.MapVirtualKeyW(vk, 0)

        key.wVirtualKeyCode = vk
        key.wVirtualScanCode = scan
        key.uChar.UnicodeChar = "\r"

    else:
        vk_result = user32.VkKeyScanW(char)

        if vk_result == -1:
            vk = 0
        else:
            vk = vk_result & 0xFF

        scan = (
            user32.MapVirtualKeyW(vk, 0)
            if vk
            else 0
        )

        key.wVirtualKeyCode = vk
        key.wVirtualScanCode = scan
        key.uChar.UnicodeChar = char

    return record


records = []

for char in text:
    records.append(make_key(char, True))
    records.append(make_key(char, False))

# Real Enter key.
records.append(make_key("\r", True))
records.append(make_key("\r", False))

array_type = INPUT_RECORD * len(records)
array = array_type(*records)

written = wintypes.DWORD(0)

ok = kernel32.WriteConsoleInputW(
    conin,
    array,
    len(array),
    ctypes.byref(written),
)

if not ok:
    err = ctypes.get_last_error()
    write_log(f"WriteConsoleInputW FAILED: {err}")
    raise OSError(err, "WriteConsoleInputW failed")

write_log(
    f"WriteConsoleInputW succeeded: "
    f"{written.value}/{len(records)} events"
)

kernel32.CloseHandle(conin)
kernel32.FreeConsole()

write_log("Finished")
