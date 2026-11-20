#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟键盘输入工具（Windows，纯标准库，无需 pip 安装任何东西）

用途
----
把一段文本逐字“敲”进当前获得焦点的窗口。专门解决“输入框只能打字、不能粘贴”的场景
（例如某些 Web 输入框/远程环境粘贴被禁用）。

原理
----
调用 Windows 的 SendInput + KEYEVENTF_UNICODE，直接投递 UTF-16 码元。
优点：中文、英文、符号、emoji 都能输入；不依赖输入法，也不受键盘布局影响；不经过剪贴板。

怎么用（三步）
--------------
1. 准备文本，任选一种：
   - 把文本存成脚本同目录下的 input.txt（UTF-8 编码）；
   - 或者放进剪贴板（运行后自动读取）；
   - 或者双击 运行-模拟输入.bat，在弹出的窗口里粘贴/编辑。
2. 运行：双击 运行-模拟输入.bat，或命令行 python type_text.py
3. 把光标点进目标输入框 → 按 F8 开始（或按提示倒计时）→ 输入中随时按 F9 中止。

命令行
------
  python type_text.py                    自动挑选文本来源，等待 F8 开始
  python type_text.py 稿件.txt           用指定的文本文件（也可以把文件拖到 bat 上）
  python type_text.py --clipboard        强制使用剪贴板
  python type_text.py --text "你好"      直接用参数里的文本
  python type_text.py --gui              强制打开编辑窗口
  python type_text.py --delay 0.006      每个字符间隔秒数（默认 0.003，太慢可调小）
  python type_text.py --newline enter    换行用回车键（默认 shift+enter，防止误发送）
  python type_text.py --submit           打完后再按一次回车（多数聊天框=发送）
  python type_text.py --countdown 5      直接倒计时 5 秒后开始，不等 F8
  python type_text.py --only-window 学习通   只在前台窗口标题包含该关键字时才输入（防误打）
  python type_text.py --dry-run          只统计不输入，先确认内容

热键常驻模式（推荐，复制完直接按快捷键）
----------------------------------------
  python type_text.py --hotkey           常驻后台，监听全局热键
    复制文本 → 把光标点进输入框 → 按热键：
      Ctrl+Alt+V   把剪贴板内容打进当前焦点窗口（不发送）
      Ctrl+Alt+B   同上，并在结尾按一次回车（多数聊天框=发送）
      Ctrl+Alt+Q   退出常驻
  双击 热键-启动.vbs 可以无窗口静默启动。

注意
----
* 默认换行用 Shift+Enter，因为聊天输入框里单独的回车往往是“发送”。
* 运行前请确认目标窗口已获得焦点；程序开始前会打印“当前窗口”标题供你核对。
* 如果目标程序开着中文输入法且处于拼音组合状态，注入的字符可能被输入法吃掉；
  请先切到英文输入状态（按一次 Shift 或 Ctrl+Space）再运行。
* 打字过程中不要碰键盘鼠标，否则可能插入到别处。
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes


class _NullWriter:
    """pythonw.exe 下 sys.stdout 是 None，用空写入器兜底。"""

    def write(self, *_args):
        return 0

    def flush(self):
        pass

    def isatty(self):
        return False

    def reconfigure(self, **_kwargs):
        pass


if sys.stdout is None:
    sys.stdout = _NullWriter()
if sys.stderr is None:
    sys.stderr = _NullWriter()

# 输出被重定向/接到管道时统一用 UTF-8，避免中文变成乱码；
# 直接开在控制台窗口里则保持默认（Windows 控制台走宽字符接口，中文本来就正常）。
if not sys.stdout.isatty():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

_LOG_PATH = None


def log(message: str) -> None:
    """把诊断信息追加到日志文件（用 --log 指定；没指定就什么也不做）。"""
    if not _LOG_PATH:
        return
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Win32 基础
# ---------------------------------------------------------------------------

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t

VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_ESCAPE = 0x1B
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_F8 = 0x77
VK_F9 = 0x78
VK_V = 0x56
VK_B = 0x42
VK_Q = 0x51

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

CF_UNICODETEXT = 13

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001

HOTKEY_TYPE = 1
HOTKEY_SEND = 2
HOTKEY_QUIT = 3

ERROR_ALREADY_EXISTS = 183
_MUTEX = None  # 保持引用，避免被回收导致互斥体失效


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowTextW.restype = ctypes.c_int
user32.OpenClipboard.argtypes = (wintypes.HWND,)
user32.OpenClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = (wintypes.UINT,)
user32.GetClipboardData.restype = ctypes.c_void_p
user32.CloseClipboard.restype = wintypes.BOOL
kernel32.GlobalLock.argtypes = (ctypes.c_void_p,)
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = (ctypes.c_void_p,)
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateMutexW.restype = ctypes.c_void_p
user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
user32.GetMessageW.restype = ctypes.c_int
user32.PeekMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT)
user32.PeekMessageW.restype = wintypes.BOOL


# ---------------------------------------------------------------------------
# 键盘事件
# ---------------------------------------------------------------------------

def _make_key(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    ev = INPUT()
    ev.type = INPUT_KEYBOARD
    ev.ki.wVk = vk
    ev.ki.wScan = scan
    ev.ki.dwFlags = flags
    ev.ki.time = 0
    ev.ki.dwExtraInfo = 0
    return ev


def _send(events) -> None:
    arr = (INPUT * len(events))(*events)
    sent = user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))
    if sent != len(events):
        raise OSError(ctypes.get_last_error(), "SendInput 失败（可能有更高权限的窗口挡住了输入）")


def _utf16_units(ch: str):
    """把一个字符拆成 UTF-16 码元（emoji 等补充平面字符 = 两个码元）。"""
    raw = ch.encode("utf-16-le")
    for i in range(0, len(raw), 2):
        yield int.from_bytes(raw[i:i + 2], "little")


def send_char(ch: str) -> None:
    for unit in _utf16_units(ch):
        _send([
            _make_key(scan=unit, flags=KEYEVENTF_UNICODE),
            _make_key(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP),
        ])


def send_key(vk: int, shift: bool = False) -> None:
    events = []
    if shift:
        events.append(_make_key(vk=VK_SHIFT))
    events.append(_make_key(vk=vk))
    events.append(_make_key(vk=vk, flags=KEYEVENTF_KEYUP))
    if shift:
        events.append(_make_key(vk=VK_SHIFT, flags=KEYEVENTF_KEYUP))
    _send(events)


def key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


# --- 权限（完整性级别）诊断 -------------------------------------------------
# Windows 的 UIPI 规则：低完整性级别的进程无法向高完整性级别的窗口注入输入，
# 而且 SendInput 不会报错（它照样返回成功），所以必须主动查两边的级别。

TOKEN_QUERY = 0x0008
TOKEN_INTEGRITY_LEVEL = 25
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_INTEGRITY_NAMES = {
    0x0000: "Untrusted",
    0x1000: "Low",
    0x2000: "Medium",
    0x2100: "Medium Plus",
    0x3000: "High",
    0x4000: "System",
}

advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
advapi32.OpenProcessToken.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                      ctypes.POINTER(wintypes.HANDLE))
advapi32.OpenProcessToken.restype = wintypes.BOOL
advapi32.GetTokenInformation.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                         wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
advapi32.GetTokenInformation.restype = wintypes.BOOL
advapi32.GetSidSubAuthorityCount.argtypes = (ctypes.c_void_p,)
advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
advapi32.GetSidSubAuthority.argtypes = (ctypes.c_void_p, wintypes.DWORD)
advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)


def process_integrity_level(pid: int) -> str:
    """返回进程的完整性级别名称（Low / Medium / High / System / Unknown）。"""
    if pid <= 0:
        return "Unknown"
    process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not process:
        return "Unknown"
    token = wintypes.HANDLE()
    try:
        if not advapi32.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
            return "Unknown"
        try:
            size = wintypes.DWORD(0)
            advapi32.GetTokenInformation(token, TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(size))
            buffer = ctypes.create_string_buffer(max(size.value, 16))
            if not advapi32.GetTokenInformation(token, TOKEN_INTEGRITY_LEVEL, buffer,
                                                size.value, ctypes.byref(size)):
                return "Unknown"
            sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
            count = advapi32.GetSidSubAuthorityCount(sid)[0]
            rid = advapi32.GetSidSubAuthority(sid, count - 1)[0]
            return _INTEGRITY_NAMES.get(rid, f"0x{rid:X}")
        finally:
            kernel32.CloseHandle(token)
    finally:
        kernel32.CloseHandle(process)


def window_pid(hwnd) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def foreground_info() -> str:
    """一行描述前台窗口、它的进程和完整性级别，用于诊断。"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "（无前台窗口）"
    title = foreground_title()
    pid = window_pid(hwnd)
    return f"{title!r} pid={pid} 完整性={process_integrity_level(pid)}"


def integrity_warning() -> str:
    """比较本进程与前台窗口进程的完整性级别，给出 UIPI 风险提示。"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    mine = process_integrity_level(kernel32.GetCurrentProcessId())
    target_pid = window_pid(hwnd)
    theirs = process_integrity_level(target_pid)
    rank = {"Untrusted": 0, "Low": 1, "Medium": 2, "Medium Plus": 2, "High": 3, "System": 4}
    if theirs == "Unknown" and target_pid != kernel32.GetCurrentProcessId():
        return (f"⚠ 读不到前台程序的权限级别（可能高于本程序 {mine}）。"
                f"Windows 会静默丢弃模拟输入：请右键本工具「以管理员身份运行」再试。")
    if rank.get(theirs, -1) > rank.get(mine, -1):
        return (f"⚠ 前台程序({theirs})比本程序({mine})权限更高，"
                f"Windows 会拦截模拟输入：请以管理员身份运行本工具。")
    return ""


kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                               wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL


def is_elevated() -> bool:
    """当前进程是否以管理员（高完整性）身份运行。"""
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY,
                                     ctypes.byref(token)):
        return False
    try:
        elevation = wintypes.DWORD(0)
        size = wintypes.DWORD(0)
        advapi32.GetTokenInformation(token, 20, ctypes.byref(elevation),
                                     ctypes.sizeof(elevation), ctypes.byref(size))
        return bool(elevation.value)
    finally:
        kernel32.CloseHandle(token)


def process_exe_name(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return "?"
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1]
        return "?"
    finally:
        kernel32.CloseHandle(handle)


def list_windows(limit: int = 20):
    """枚举可见顶层窗口：[(hwnd, 标题, pid, 进程名, 完整性级别)]。"""
    results = []
    proto = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if len(results) >= limit:
            return False
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = window_pid(hwnd)
        results.append((hwnd, buf.value, pid, process_exe_name(pid),
                        process_integrity_level(pid)))
        return True

    user32.EnumWindows(proto(callback), 0)
    return results


def diagnose() -> int:
    """打印一份权限与技术栈诊断，便于定位"发不出字"的原因。"""
    print("=" * 68)
    print("DSH 模拟输入诊断")
    print("=" * 68)
    print(f"Python      : {sys.version.split()[0]}  ({sys.executable})")
    print(f"管理员身份  : {'是' if is_elevated() else '否'}")
    print(f"本进程完整性: {process_integrity_level(os.getpid())}")
    print(f"前台窗口    : {foreground_info()}")
    clip = read_clipboard()
    print(f"剪贴板      : {len(clip)} 个字符  {clip[:30]!r}")
    print("-" * 68)
    print("可见窗口（标题 / 进程 / 完整性级别）：")
    for _hwnd, title, pid, exe, level in list_windows():
        print(f"  {level:<9} {exe:<22} pid={pid:<7} {title[:46]}")
    print("-" * 68)
    warning = integrity_warning()
    if warning:
        print(warning)
    else:
        print("权限对比：前台窗口的完整性级别不高于本进程，UIPI 不会拦截注入。")
    print("说明：'Unknown' 表示读不到对方 token，通常意味着对方权限高于本程序。")
    return 0


def foreground_title() -> str:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "（未知）"
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value or "（无标题）"


def wait_modifiers_up(timeout: float = 2.0) -> None:
    """等 Ctrl/Alt/Shift/Win 都松手，否则热键的修饰键会吃掉第一个字符。"""
    keys = (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not any(key_down(vk) for vk in keys):
            return
        time.sleep(0.01)


def beep(freq: int, ms: int) -> None:
    try:
        import winsound
        winsound.Beep(freq, ms)
    except Exception:
        pass


def single_instance(name: str = "dsh-type-text-hotkey") -> bool:
    """同名互斥体已存在则说明已经有一个在跑了。"""
    global _MUTEX
    _MUTEX = kernel32.CreateMutexW(None, False, f"Local\\{name}")
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


# ---------------------------------------------------------------------------
# 文本准备
# ---------------------------------------------------------------------------

def read_clipboard() -> str:
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
kernel32.GlobalAlloc.restype = ctypes.c_void_p
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = (wintypes.UINT, ctypes.c_void_p)
user32.SetClipboardData.restype = ctypes.c_void_p
user32.OpenClipboard.argtypes = (wintypes.HWND,)


def write_clipboard(text: str) -> bool:
    """把文本写回系统剪贴板（UTF-16 + 结尾 0）。"""
    data = text.encode("utf-16-le") + b"\x00\x00"
    handle = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    if not handle:
        return False
    ptr = kernel32.GlobalLock(handle)
    if not ptr:
        return False
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(handle)
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        return bool(user32.SetClipboardData(CF_UNICODETEXT, handle))
    finally:
        user32.CloseClipboard()


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig") as f:  # utf-8-sig 兼容记事本默认带 BOM
        return f.read()


def normalize(text: str) -> str:
    """统一换行、去掉结尾多余空行（避免多按一次回车）。"""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def strip_markdown(text: str) -> str:
    """把 Markdown 文本抹成纯文本：去掉标题井号、加粗/斜体星号、反引号、表格竖线等标记。

    按行处理表格、代码围栏、列表、引用，再做行内替换；尽量保守，只处理成对标记，
    普通文字（snake_case、a*b 这类）保持原样。
    """
    import re

    original = text
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    kept_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.match(r"^(```|~~~)", stripped):
            continue  # 代码围栏行丢掉，内容保留
        if re.match(r"^([-*_])[ \t]*(\1[ \t]*){2,}$", stripped):
            continue  # 水平分割线
        if "|" in stripped and re.match(r"^\|?[ \t:|-]*-[ \t:|-]*\|[ \t:|-]*$", stripped):
            continue  # 表格分隔行
        if stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 2:
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            kept_lines.append("  ".join(cell for cell in cells if cell))
            continue
        kept_lines.append(line)

    text = "\n".join(kept_lines)

    # 行内标记
    text = re.sub(r"`([^`\n]*)`", r"\1", text)                                   # 行内代码
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)                        # 图片
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)                         # 链接
    text = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", text)                        # 引用式链接
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)                             # 粗斜体
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)                                 # 粗体
    text = re.sub(r"___(.+?)___", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)                                     # 删除线
    text = re.sub(r"==(.+?)==", r"\1", text)                                     # 高亮
    # 斜体：前后不能紧贴 ASCII 字母数字，避免误伤 a*b / snake_case
    text = re.sub(r"(?<![A-Za-z0-9*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![A-Za-z0-9*])",
                  r"\1", text)
    text = re.sub(r"(?<![A-Za-z0-9_])_(?!\s)([^_\n]+?)(?<!\s)_(?![A-Za-z0-9_])",
                  r"\1", text)
    # 行首标记
    text = re.sub(r"(?m)^[ \t]*#{1,6}[ \t]+", "", text)                          # 标题
    text = re.sub(r"(?m)^[ \t]*>[ \t]?", "", text)                               # 引用
    text = re.sub(r"(?m)^([ \t]*)[-*+][ \t]+", r"\1· ", text)                    # 列表
    # 转义与残余
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>~=])", r"\1", text)
    text = text.replace("|", "  ")
    text = re.sub(r"</?[a-zA-Z][^>\n]{0,40}>", "", text)
    text = re.sub(r"(?m)[ \t]+$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    result = text.strip("\n")
    return result if result else original


# ---------------------------------------------------------------------------
# 富文本还原：LaTeX 公式、HTML 片段、编码乱码
# ---------------------------------------------------------------------------

_SUBSCRIPT = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
_SUPERSCRIPT = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")

_LATEX_SYMBOLS = {
    "times": "×", "cdot": "·", "div": "÷", "pm": "±", "mp": "∓",
    "ge": "≥", "geq": "≥", "le": "≤", "leq": "≤", "ne": "≠", "neq": "≠",
    "approx": "≈", "equiv": "≡", "propto": "∝", "infty": "∞",
    "to": "→", "rightarrow": "→", "leftarrow": "←", "Rightarrow": "⇒",
    "Leftarrow": "⇐", "leftrightarrow": "↔",
    "in": "∈", "notin": "∉", "subset": "⊂", "subseteq": "⊆", "supset": "⊃",
    "cup": "∪", "cap": "∩", "emptyset": "∅", "forall": "∀", "exists": "∃",
    "sum": "∑", "prod": "∏", "int": "∫", "partial": "∂", "nabla": "∇",
    "sqrt": "√",
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ", "phi": "φ",
    "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ",
    "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
    "ldots": "…", "cdots": "…", "dots": "…",
    "left": "", "right": "", "big": "", "Big": "", "bigg": "", "Bigg": "",
}

_LATEX_LOOKS = None  # 延迟编译


def latex_to_text(text: str, plain_sub: bool = False) -> str:
    """把 LaTeX 公式源码转成可读的 Unicode 纯文本。"""
    import re

    if not text:
        return text
    if not re.search(r"\\\(|\\\[|\\[A-Za-z]+|\$[^$\n]{1,200}\$|\^\{|_\{", text):
        return text  # 不像 LaTeX，原样返回，避免误伤普通文字

    value = text
    value = re.sub(r"\\[()\[\]]", "", value)      # 公式定界符 \( \) \[ \]
    value = value.replace("$$", "").replace("$", "")

    for _ in range(3):  # \frac 支持嵌套
        value = re.sub(r"\\(?:d|t)?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"\1/\2", value)

    def _root_root(match):
        index, radicand = match.group(1), match.group(2)
        return "√" + radicand if plain_sub else index.translate(_SUPERSCRIPT) + "√" + radicand

    value = re.sub(r"\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}", _root_root, value)
    value = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"√\1", value)
    value = re.sub(
        r"\\(?:text|textrm|textbf|textsf|texttt|mathrm|mathbf|mathit|mathsf|operatorname|mbox)"
        r"\s*\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\(?:begin|end)\s*\{[^{}]*\}", "", value)

    def _marker(match):
        marker, body = match.group(1), match.group(2)
        if plain_sub:
            return body
        table = _SUPERSCRIPT if marker == "^" else _SUBSCRIPT
        return body.translate(table)

    value = re.sub(r"([\^_])\s*\{([^{}]*)\}", _marker, value)
    value = re.sub(r"([\^_])\s*([0-9A-Za-z+\-=()])", _marker, value)

    value = value.replace("\\quad", " ").replace("\\qquad", " ")
    value = re.sub(r"\\[ ,;:]\s?", " ", value)     # \, \; \: 与 \ 空格
    value = re.sub(r"\\!", "", value)
    value = value.replace("\\\\", "\n")            # 换行

    value = re.sub(r"\\([A-Za-z]+)", lambda m: _LATEX_SYMBOLS.get(m.group(1), ""), value)
    value = re.sub(r"\\([%$&#_{}])", r"\1", value)  # 单字符转义
    value = re.sub(r"\\[A-Za-z]+", "", value)       # 未识别命令
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value


def html_to_text(fragment: str) -> str:
    """把 HTML 片段转成纯文本：块级换行、列表用圆点、解码实体、丢掉标签。"""
    import re
    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        BLOCK = {"p", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
                 "blockquote", "pre", "section", "article", "table"}

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
            self.skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "head"):
                self.skip += 1
            elif tag == "br":
                self.parts.append("\n")
            elif tag == "li":
                self.parts.append("\n· ")
            elif tag in ("td", "th"):
                self.parts.append("  ")
            elif tag in self.BLOCK:
                self.parts.append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style", "head"):
                self.skip = max(0, self.skip - 1)
            elif tag in self.BLOCK:
                self.parts.append("\n")

        def handle_data(self, data):
            if self.skip == 0:
                self.parts.append(data)

    parser = _TextExtractor()
    try:
        parser.feed(fragment)
        parser.close()
    except Exception:
        return ""

    value = "".join(parser.parts).replace("\u00a0", " ")
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


user32.RegisterClipboardFormatW.argtypes = (wintypes.LPCWSTR,)
user32.RegisterClipboardFormatW.restype = wintypes.UINT
kernel32.GlobalSize.argtypes = (ctypes.c_void_p,)
kernel32.GlobalSize.restype = ctypes.c_size_t

_HTML_FORMAT_ID = 0


def read_clipboard_html() -> str | None:
    """读取剪贴板里的 HTML Format 片段；没有或失败返回 None。"""
    global _HTML_FORMAT_ID
    if not _HTML_FORMAT_ID:
        _HTML_FORMAT_ID = user32.RegisterClipboardFormatW("HTML Format")
    if not _HTML_FORMAT_ID:
        return None
    if not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(_HTML_FORMAT_ID)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            size = kernel32.GlobalSize(handle) or 8192
            data = ctypes.string_at(ptr, size)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()

    raw = data.split(b"\x00", 1)[0].decode("utf-8", "replace")
    start_marker = "<!--StartFragment-->"
    end_marker = "<!--EndFragment-->"
    start = raw.find(start_marker)
    end = raw.find(end_marker)
    if start != -1 and end > start:
        return raw[start + len(start_marker):end]
    return raw


def repair_mojibake(text: str) -> str:
    """尝试修复 UTF-8/GBK 被当成 Latin-1 读出的乱码，只在明显变好时替换。"""
    if not text:
        return text

    def score(value: str) -> int:
        cjk = sum(1 for ch in value if "\u4e00" <= ch <= "\u9fff")
        bad = value.count("\ufffd") + sum(
            1 for ch in value if ord(ch) < 32 and ch not in "\n\t")
        suspicious = sum(1 for ch in value if ch in "ÃÂâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ")
        return cjk * 3 - bad * 10 - suspicious

    best, best_score = text, score(text)
    for enc_out in ("latin-1", "cp1252", "gbk"):
        for enc_in in ("utf-8", "gb18030"):
            try:
                candidate = text.encode(enc_out).decode(enc_in)
            except Exception:
                continue
            if "\ufffd" in candidate and "\ufffd" not in text:
                continue
            candidate_score = score(candidate)
            if candidate_score > best_score + 5:
                best, best_score = candidate, candidate_score
    return best


# 从网页/聊天窗口复制时常带进来的不可见字符
_INVISIBLE_CHARS = (
    "\u200b\u200c\u200d\u200e\u200f"  # 零宽字符与方向标记
    "\u202a\u202b\u202c\u202d\u202e"  # 双向文本控制符
    "\u2060\u2061\u2062\u2063\u2064"  # 各种不可见连接符
    "\ufeff\u00ad"                     # BOM、软连字符
)


def clean_text(text: str, aggressive: bool = False, latex: bool = True,
               repair: bool = True, plain_sub: bool = False) -> str:
    """把一段文字整理成干净纯文本：修编码乱码、还原 LaTeX、抹 Markdown、去不可见字符。"""
    import re

    if not text:
        return text
    cleaned = normalize(text)
    if repair:
        cleaned = repair_mojibake(cleaned)
    if latex:
        cleaned = latex_to_text(cleaned, plain_sub=plain_sub)
    cleaned = strip_markdown(cleaned)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    for ch in _INVISIBLE_CHARS:
        cleaned = cleaned.replace(ch, "")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    cleaned = cleaned.replace("\u00a0", " ")  # 不换行空格
    if aggressive:
        cleaned = re.sub(r"[_*#~`]+", "", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"(?m)[ \t]+$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _readability_score(value: str) -> float:
    """粗略评估一段文本有多"可读"：汉字和字母越多越好，反斜杠/花括号/替换字符越少越好。"""
    cjk = sum(1 for ch in value if "\u4e00" <= ch <= "\u9fff")
    letters = sum(1 for ch in value if ch.isalnum())
    bad = (value.count("\\") * 3 + value.count("{") * 2
           + value.count("}") * 2 + value.count("\ufffd") * 5)
    return cjk + letters * 0.5 - bad


def clean_from_clipboard(aggressive: bool = False, latex: bool = True, repair: bool = True,
                         use_html: bool = True, plain_sub: bool = False) -> tuple[str, str]:
    """从剪贴板取最干净的一份：纯文本与 HTML 各洗一遍，取可读性高的那个。"""
    candidates: list[tuple[str, str]] = []

    plain = read_clipboard_retry()
    if plain.strip():
        candidates.append(("纯文本", clean_text(plain, aggressive=aggressive, latex=latex,
                                                repair=repair, plain_sub=plain_sub)))

    if use_html:
        fragment = read_clipboard_html()
        if fragment:
            html_text = html_to_text(fragment)
            if html_text.strip():
                candidates.append(("HTML", clean_text(html_text, aggressive=aggressive,
                                                      latex=latex, repair=repair,
                                                      plain_sub=plain_sub)))
    if not candidates:
        return "", "无内容"
    candidates.sort(key=lambda item: _readability_score(item[1]), reverse=True)
    best_name, best_text = candidates[0]
    return best_text, best_name


def clean_clipboard_once(sound: bool = False, aggressive: bool = False, latex: bool = True,
                         repair: bool = True, use_html: bool = True,
                         plain_sub: bool = False) -> int:
    """就地整理系统剪贴板：读出来 → 洗干净 → 写回去。"""
    original = read_clipboard_retry()
    if not original.strip():
        print("剪贴板里没有文本。")
        if sound:
            beep(300, 200)
        return 4

    cleaned, used = clean_from_clipboard(aggressive=aggressive, latex=latex, repair=repair,
                                         use_html=use_html, plain_sub=plain_sub)
    if not cleaned:
        print("没有可用的文本内容。")
        if sound:
            beep(300, 200)
        return 4
    if cleaned == original:
        print("剪贴板已经是干净文本，未改动。")
        if sound:
            beep(1200, 60)
        return 0

    if not write_clipboard(cleaned):
        print("写回剪贴板失败（可能被其他程序占用），请重试。")
        if sound:
            beep(300, 300)
        return 1

    print(f"已整理并写回剪贴板（采用{used}）：{len(original)} → {len(cleaned)} 字符")
    preview = cleaned[:60].replace("\n", "⏎")
    print(f"预览：{preview}{'…' if len(cleaned) > 60 else ''}")
    if sound:
        beep(900, 80)
    return 0


def watch_clipboard(interval: float = 0.4, aggressive: bool = False, latex: bool = True,
                    repair: bool = True) -> int:
    """常驻监听剪贴板：每次复制后自动整理，并把干净文本写回剪贴板。"""
    if not single_instance("dsh-clean-clipboard"):
        print("已经有一个剪贴板整理程序在运行。")
        return 0

    print("剪贴板自动整理已启动：复制任何带格式的文字，会自动洗成纯文本。")
    print("按 Ctrl+C 退出。")
    sys.stdout.flush()

    last = read_clipboard()
    changed = 0
    try:
        while True:
            time.sleep(interval)
            current = read_clipboard()
            if not current or current == last:
                continue
            cleaned, used = clean_from_clipboard(aggressive=aggressive, latex=latex,
                                                 repair=repair)
            if cleaned and cleaned != current:
                if write_clipboard(cleaned):
                    changed += 1
                    preview = cleaned[:50].replace("\n", "⏎")
                    print(f"已整理第 {changed} 次（{used}）：{len(current)} → {len(cleaned)} 字符　{preview}")
                    sys.stdout.flush()
                last = cleaned
            else:
                last = current
    except KeyboardInterrupt:
        print("\n已退出。")
    return 0


def estimate(text: str, delay: float, newline: str) -> float:
    """粗估总耗时：字符数 * 间隔 + 换行额外开销。"""
    return len(text) * delay + text.count("\n") * 0.02


def read_clipboard_retry(attempts: int = 12, wait: float = 0.05) -> str:
    """剪贴板偶尔被别的程序占用，多试几次。"""
    text = ""
    for _ in range(attempts):
        text = read_clipboard()
        if text.strip():
            return text
        time.sleep(wait)
    return text


# ---------------------------------------------------------------------------
# 核心：把文本打出去
# ---------------------------------------------------------------------------

def type_text(text: str, delay: float = 0.003, newline: str = "shift",
              submit: bool = False, progress: bool = True) -> str:
    """输入文本。返回 'done' 或 'aborted'。"""
    text = normalize(text)
    total = len(text)
    started = time.time()

    for index, ch in enumerate(text, start=1):
        # 中止键：F9 或 Esc
        if key_down(VK_F9) or key_down(VK_ESCAPE):
            if progress:
                print(f"\n已中止：输入了 {index - 1}/{total} 个字符。")
            return "aborted"

        if ch == "\n":
            send_key(VK_RETURN, shift=(newline != "enter"))
        elif ch == "\t":
            send_key(VK_TAB)
        else:
            send_char(ch)

        if progress and (index % 20 == 0 or index == total):
            elapsed = time.time() - started
            speed = index / elapsed if elapsed > 0 else 0
            print(f"\r已输入 {index}/{total}（{index * 100 // max(total, 1)}%）"
                  f"  约 {speed:.0f} 字/秒", end="", flush=True)

        if delay > 0:
            time.sleep(delay)

    if progress:
        print()

    if submit:
        time.sleep(0.05)
        send_key(VK_RETURN)

    return "done"


def drain_hotkeys() -> None:
    """丢弃输入期间排队的重复热键，避免打完又触发一次。"""
    msg = wintypes.MSG()
    while user32.PeekMessageW(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, PM_REMOVE):
        pass


def run_hotkey(delay: float = 0.003, newline: str = "shift", sound: bool = True,
               only_window: str | None = None) -> int:
    """常驻后台：复制文本 → 焦点放进输入框 → 按热键直接打进去。"""
    if not single_instance():
        print("已经有一个热键守护在运行了，不用重复启动。")
        return 0

    mods = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
    binds = [
        (HOTKEY_TYPE, VK_V, "Ctrl+Alt+V   把剪贴板内容打进当前焦点窗口"),
        (HOTKEY_SEND, VK_B, "Ctrl+Alt+B   同上，并在结尾按回车发送"),
        (HOTKEY_QUIT, VK_Q, "Ctrl+Alt+Q   退出本程序"),
    ]
    registered = []
    for ident, vk, _desc in binds:
        if not user32.RegisterHotKey(None, ident, mods, vk):
            for done_id in registered:
                user32.UnregisterHotKey(None, done_id)
            raise SystemExit(f"注册热键失败（id={ident}），可能被其他程序占用。")

        registered.append(ident)

    print("热键已就绪：")
    for _ident, _vk, desc in binds:
        print(f"  {desc}")
    print("用法：复制文本 → 把光标点进输入框 → 按 Ctrl+Alt+V。")
    print("换行默认用 Shift+回车，避免聊天框直接把消息发出去；要发送请用 Ctrl+Alt+B。")
    if only_window:
        print(f"安全开关：只有前台窗口标题包含「{only_window}」时才会输入。")
    sys.stdout.flush()
    if sound:
        beep(880, 60)

    msg = wintypes.MSG()
    try:
        while True:
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) <= 0:
                break
            if msg.message != WM_HOTKEY:
                continue
            if msg.wParam == HOTKEY_QUIT:
                print("收到退出热键，结束。")
                break

            text = normalize(read_clipboard_retry())
            if not text.strip():
                print("剪贴板里没有文本，已忽略。")
                sys.stdout.flush()
                if sound:
                    beep(300, 120)
                continue

            if only_window:
                title_now = foreground_title()
                if only_window not in title_now:
                    print(f"前台不是「{only_window}」（当前：{title_now}），已跳过。")
                    sys.stdout.flush()
                    if sound:
                        beep(300, 120)
                    drain_hotkeys()
                    continue

            wait_modifiers_up()
            time.sleep(0.05)
            print(f"开始输入 {len(text)} 个字符 → {foreground_title()}")
            sys.stdout.flush()
            if sound:
                beep(1000, 40)

            result = type_text(text, delay=delay, newline=newline,
                               submit=(msg.wParam == HOTKEY_SEND), progress=False)

            if sound:
                if result == "done":
                    beep(1400, 40)
                else:
                    beep(300, 120)
            print("完成。" if result == "done" else "已中止。")
            sys.stdout.flush()
            drain_hotkeys()
    finally:
        for ident in registered:
            user32.UnregisterHotKey(None, ident)
    return 0


# ---------------------------------------------------------------------------
# 图形界面（可选）
# ---------------------------------------------------------------------------

def run_gui(initial_text: str = "", delay: float = 0.003, newline: str = "shift") -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception as err:  # tkinter 未安装的 Python 发行版
        print(f"无法打开编辑窗口（tkinter 不可用：{err}）")
        print("请改用：把文本存成 input.txt 放在脚本旁边，或复制到剪贴板后再运行。")
        return 1

    root = tk.Tk()
    root.title("模拟键盘输入（中文可输入）")
    root.geometry("760x560")
    root.attributes("-topmost", True)

    tip = tk.Label(
        root,
        text="把文本粘贴/输入到下面（也可以点“从剪贴板读取”），然后点“开始输入”。\n"
             "开始后窗口会隐藏，请立刻把光标点进目标输入框。",
        justify="left", anchor="w", padx=10, pady=6,
    )
    tip.pack(fill="x")

    box = tk.Text(root, wrap="word", undo=True, font=("Microsoft YaHei UI", 11))
    box.pack(fill="both", expand=True, padx=10, pady=4)
    if initial_text:
        box.insert("1.0", initial_text)

    status = tk.Label(root, text="", anchor="w", padx=10)
    status.pack(fill="x")

    row = tk.Frame(root)
    row.pack(fill="x", padx=10, pady=8)

    submit_var = tk.BooleanVar(value=False)
    slow_var = tk.BooleanVar(value=False)

    def refresh_count(*_):
        text = normalize(box.get("1.0", "end-1c"))
        d = 0.008 if slow_var.get() else delay
        status.config(text=f"{len(text)} 个字符 · 预计 {estimate(text, d, newline):.1f} 秒"
                           f" · 换行方式：{'回车' if newline == 'enter' else 'Shift+回车'}")

    box.bind("<KeyRelease>", refresh_count)
    refresh_count()

    def load_clipboard():
        text = normalize(read_clipboard())
        if not text:
            messagebox.showinfo("剪贴板", "剪贴板里没有文本。")
            return
        box.delete("1.0", "end")
        box.insert("1.0", text)
        refresh_count()

    def start():
        text = normalize(box.get("1.0", "end-1c"))
        if not text.strip():
            messagebox.showinfo("没有内容", "请先填写要输入的文本。")
            return
        d = 0.008 if slow_var.get() else delay
        root.withdraw()  # 隐藏自己，把焦点还给别的窗口
        try:
            for left in (3, 2, 1):
                print(f"  {left} 秒后开始，请把光标点进目标输入框…", flush=True)
                time.sleep(1)
            print(f"当前窗口：{foreground_title()}", flush=True)
            result = type_text(text, delay=d, newline=newline,
                               submit=submit_var.get(), progress=True)
        finally:
            root.deiconify()
            root.attributes("-topmost", True)
        if result == "aborted":
            messagebox.showwarning("已中止", "输入被中止（F9 / Esc）。")
        else:
            messagebox.showinfo("完成", f"已输入 {len(text)} 个字符。")

    ttk.Button(row, text="开始输入（3 秒后）", command=start).pack(side="left")
    ttk.Button(row, text="从剪贴板读取", command=load_clipboard).pack(side="left", padx=6)
    ttk.Checkbutton(row, text="结尾按回车（发送）", variable=submit_var).pack(side="left", padx=6)
    ttk.Checkbutton(row, text="慢速模式", variable=slow_var,
                    command=refresh_count).pack(side="left")

    root.mainloop()
    return 0


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def pick_text(path: str | None, use_clipboard: bool, text_arg: str | None) -> tuple[str, str]:
    """返回 (文本, 来源说明)。"""
    if text_arg is not None:
        return text_arg, "命令行 --text"
    if path:
        if not os.path.isfile(path):
            raise SystemExit(f"找不到文件：{path}")
        return read_file(path), f"文件 {path}"
    if use_clipboard:
        return read_clipboard_retry(), "剪贴板"
    here = os.path.dirname(os.path.abspath(__file__))
    default_file = os.path.join(here, "input.txt")
    if os.path.isfile(default_file):
        return read_file(default_file), "input.txt"
    clip = read_clipboard_retry(6, 0.05)
    if clip.strip():
        return clip, "剪贴板"
    return "", ""


def main(argv: list[str]) -> int:
    import argparse

    global _LOG_PATH

    parser = argparse.ArgumentParser(
        description="把文本模拟成键盘输入，打进当前焦点窗口（支持中文）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", nargs="?", help="文本文件路径（也可以把文件拖到 bat 上）")
    parser.add_argument("--file", dest="file_opt", help="文本文件路径（同位置参数）")
    parser.add_argument("--text", help="直接给出要输入的文本")
    parser.add_argument("--clipboard", action="store_true", help="使用剪贴板内容")
    parser.add_argument("--gui", action="store_true", help="打开编辑窗口")
    parser.add_argument("--delay", type=float, default=0.003, help="每个字符间隔秒数，默认 0.003")
    parser.add_argument("--newline", choices=("shift", "enter"), default="shift",
                        help="换行方式：shift=Shift+Enter（默认，防误发送）；enter=回车")
    parser.add_argument("--submit", action="store_true", help="打完后再按一次回车（发送）")
    parser.add_argument("--countdown", type=float, default=0, help="倒计时秒数后自动开始，不等 F8")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不输入")
    parser.add_argument("--hotkey", action="store_true",
                        help="常驻后台监听全局热键（Ctrl+Alt+V 输入 / B 输入并发送 / Q 退出）")
    parser.add_argument("--no-beep", action="store_true", help="热键模式不响提示音")
    parser.add_argument("--beep", action="store_true",
                        help="用提示音反馈（无窗口启动时用）：启动/开始/完成各响一声")
    parser.add_argument("--only-window", default=None, metavar="关键字",
                        help="只在前台窗口标题包含该关键字时才输入（例如 学习通）")
    parser.add_argument("--wait-window", default=None, metavar="关键字",
                        help="一直等到前台窗口标题包含该关键字，再开始输入（不限时压力）")
    parser.add_argument("--wait-timeout", type=float, default=60.0,
                        help="--wait-window 的最长等待秒数，默认 60")
    parser.add_argument("--settle", type=float, default=1.0,
                        help="等到窗口后额外静置秒数，留给你点进输入框，默认 1")
    parser.add_argument("--log", default=None, metavar="文件",
                        help="把诊断过程追加写入该文件，便于排查")
    parser.add_argument("--no-gui", action="store_true",
                        help="找不到文本时不要弹窗，直接报错退出（无窗口启动时用）")
    parser.add_argument("--diagnose", action="store_true",
                        help="只打印权限与技术栈诊断（窗口/进程/完整性级别/剪贴板），不输入")
    parser.add_argument("--force", action="store_true",
                        help="即使检测到权限可能不匹配，也照常尝试输入")
    parser.add_argument("--strip-md", action="store_true",
                        help="输入前抹除 Markdown 标记（标题井号、加粗星号、表格竖线、链接等）")
    parser.add_argument("--clean", action="store_true",
                        help="输入前做完整清洗：还原 LaTeX 公式、HTML 实体、编码乱码与 Markdown 标记")
    parser.add_argument("--no-latex", action="store_true", help="清洗时跳过 LaTeX 还原")
    parser.add_argument("--no-html", action="store_true", help="清洗时不要读取剪贴板的 HTML 格式")
    parser.add_argument("--no-repair", action="store_true", help="清洗时跳过编码乱码修复")
    parser.add_argument("--plain-sub", action="store_true",
                        help="数学上下标改用普通字符（x1）而不是 Unicode 下标（x₁）")
    parser.add_argument("--clean-raw", action="store_true",
                        help="整理剪贴板时只做旧版处理（仅 Markdown 标记），不还原 LaTeX/HTML")
    parser.add_argument("--clean-clipboard", action="store_true",
                        help="整理系统剪贴板：抹掉标记和不可见字符后写回剪贴板，不输入")
    parser.add_argument("--clean-aggressive", action="store_true",
                        help="整理时更激进：连残留的 _ * # ~ ` 符号一起删掉")
    parser.add_argument("--watch-clipboard", action="store_true",
                        help="常驻监听，每次复制后自动整理剪贴板（Ctrl+C 退出）")
    args = parser.parse_args(argv)

    if args.watch_clipboard:
        return watch_clipboard(aggressive=args.clean_aggressive,
                               latex=not args.no_latex, repair=not args.no_repair)

    if args.clean_clipboard:
        return clean_clipboard_once(
            sound=args.beep,
            aggressive=args.clean_aggressive,
            latex=not (args.no_latex or args.clean_raw),
            repair=not (args.no_repair or args.clean_raw),
            use_html=not (args.no_html or args.clean_raw),
            plain_sub=args.plain_sub,
        )

    if args.diagnose:
        return diagnose()

    if args.log:
        _LOG_PATH = os.path.abspath(args.log)

    if args.hotkey:
        return run_hotkey(delay=args.delay, newline=args.newline,
                          sound=not args.no_beep, only_window=args.only_window)

    path = args.file_opt or args.path
    already_cleaned = False
    if args.clean and not path and args.text is None and args.clipboard:
        text, used = clean_from_clipboard(
            aggressive=args.clean_aggressive,
            latex=not args.no_latex,
            repair=not args.no_repair,
            use_html=not args.no_html,
            plain_sub=args.plain_sub,
        )
        source = f"剪贴板（采用{used}）"
        already_cleaned = True
        log(f"清洗：采用{used}，结果长度={len(text)}")
    else:
        text, source = pick_text(path, args.clipboard, args.text)
    log(f"启动 argv={argv} 来源={source} 文本长度={len(text)}")

    if args.gui or (not text.strip() and not args.no_gui):
        if not args.gui and not text.strip():
            print("没有找到现成文本（input.txt / 剪贴板都是空的），打开编辑窗口。")
            log("没有可用文本，改为打开编辑窗口")
        return run_gui(text, delay=args.delay, newline=args.newline)

    if not text.strip():
        log("没有可用文本（剪贴板为空），退出")
        print("剪贴板里没有文本（或读取失败）。请先复制要输入的内容。")
        if args.beep:
            beep(300, 200)
        return 4

    text = normalize(text)
    if already_cleaned:
        pass
    elif args.clean:
        original_len = len(text)
        text = clean_text(text, aggressive=args.clean_aggressive, latex=not args.no_latex,
                          repair=not args.no_repair, plain_sub=args.plain_sub)
        log(f"已完整清洗：{original_len} → {len(text)} 字符")
    elif args.strip_md:
        original_len = len(text)
        text = normalize(strip_markdown(text))
        log(f"已抹除 Markdown 标记：{original_len} → {len(text)} 字符")
    log(f"文本字符数={len(text)} 预览={text[:40]!r}")
    print(f"文本来源：{source}")
    print(f"字符数：{len(text)}　预计耗时：{estimate(text, args.delay, args.newline):.1f} 秒")
    print(f"换行方式：{'回车' if args.newline == 'enter' else 'Shift+回车'}"
          f"　结尾发送：{'是' if args.submit else '否'}")
    preview = text[:80].replace("\n", "⏎")
    print(f"内容预览：{preview}{'…' if len(text) > 80 else ''}")
    print("=" * 60)

    if args.dry_run:
        print("（--dry-run：未输入任何内容）")
        return 0

    if args.beep:
        beep(500, 80)  # 已启动

    if args.wait_window:
        keyword = args.wait_window
        print(f"等待你切到标题包含「{keyword}」的窗口（最多 {args.wait_timeout:g} 秒，Esc 取消）…")
        log(f"等待窗口匹配 keyword={keyword} timeout={args.wait_timeout:g}")
        deadline = time.time() + args.wait_timeout
        matched_title = None
        seen = []
        while time.time() < deadline:
            title_now = foreground_title()
            if title_now not in seen:
                seen.append(title_now)
                if len(seen) <= 6:
                    log(f"等待中见到前台窗口：{title_now!r}")
                    print(f"（当前前台：{title_now}）")
            if keyword in title_now:
                matched_title = title_now
                break
            if key_down(VK_ESCAPE):
                log("用户按 Esc 取消等待")
                print("已取消。")
                return 0
            time.sleep(0.1)
        if matched_title is None:
            log(f"等待超时，最后前台窗口={foreground_title()!r}")
            print(f"超时：没有等到包含「{keyword}」的窗口，未输入。")
            if args.beep:
                beep(300, 200)
            return 3
        log(f"窗口匹配={matched_title!r} 静置={args.settle:g}s")
        print(f"已切到目标窗口，{args.settle:g} 秒后开始输入…")
        time.sleep(args.settle)

    elif args.countdown > 0:
        print(f"{args.countdown:g} 秒倒计时内请把光标点进目标输入框；"
              f"按 F8 可立即开始，按 Esc 取消。")
        log(f"倒计时 {args.countdown:g}s 开始")
        deadline = time.time() + args.countdown
        while time.time() < deadline:
            if key_down(VK_F8):
                break
            if key_down(VK_ESCAPE):
                log("用户按 Esc 取消倒计时")
                print("已取消。")
                return 0
            time.sleep(0.03)

    else:
        print("请把光标点进目标输入框，然后按 F8 开始；按 Esc 取消。")
        while True:
            if key_down(VK_F8):
                break
            if key_down(VK_ESCAPE):
                log("用户按 Esc 取消")
                print("已取消。")
                return 0
            time.sleep(0.03)

    title_now = foreground_title()
    print(f"当前窗口：{title_now}")
    log(f"输入前前台窗口={title_now!r}")
    if args.only_window and args.only_window not in title_now:
        log(f"守卫拒绝：标题不含「{args.only_window}」")
        print(f"当前窗口标题不含「{args.only_window}」，为安全起见已取消输入。")
        if args.beep:
            beep(300, 120)
        return 2
    warning = integrity_warning()
    if warning and not args.force:
        log(warning)
        print(warning)
        if args.beep:
            for _ in range(3):  # 三声低音 = 权限不匹配，必须提权运行
                beep(220, 250)
        return 5
    if warning:
        log("已用 --force 忽略权限警告继续尝试")
    time.sleep(0.2)
    if args.beep:
        beep(1000, 40)
    result = type_text(text, delay=args.delay, newline=args.newline, submit=args.submit)
    log(f"输入结束 result={result}")
    if args.beep:
        if result == "done":
            beep(1400, 40)
        else:
            beep(300, 120)

    if result == "aborted":
        print("已中止（F9 / Esc）。")
        return 1
    print("完成。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\n已中断。")
        sys.exit(130)
    except SystemExit:
        raise
    except BaseException as error:  # 记录后照常抛出，方便排查
        import traceback
        log("未捕获异常：" + repr(error) + "\n" + traceback.format_exc())
        raise
