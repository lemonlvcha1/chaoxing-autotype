# -*- coding: utf-8 -*-
"""自检：双击我，工具会往自己的窗口里打一段中英混排 + emoji 文本，然后报告结果。

目的：把"工具本身不会打字"和"目标页面不接收"分开。
  ✅ 自检通过 → 注入功能正常，问题在目标页面（焦点没进输入框 / 编辑器不接收）
  ❌ 自检失败 → 系统层面拦住了注入，请看窗口里显示的权限对比

细节会追加写入 自检结果.txt。
"""

import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import type_text as tt  # noqa: E402

SAMPLE = "自检OK中文ABC123🙂\n第二行"
RESULT_FILE = os.path.join(HERE, "自检结果.txt")
AUTO_CLOSE = "--auto" in sys.argv


def write_result(text):
    try:
        with open(RESULT_FILE, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    except Exception:
        pass


def force_foreground(root):
    """尽量把自检窗口提到前台；抢不到就由后面的检查负责拒绝打字。"""
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    hwnd = user32.GetAncestor(root.winfo_id(), 2)
    foreground = user32.GetForegroundWindow()
    foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
    current_thread = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(current_thread, foreground_thread, True)
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        user32.AttachThreadInput(current_thread, foreground_thread, False)


def main():
    import tkinter as tk

    root = tk.Tk()
    root.title("输入自检 - 中文模拟输入")
    root.geometry("680x360+160+140")
    root.attributes("-topmost", True)

    info = tk.Label(root, anchor="w", justify="left", padx=10, pady=6, text="准备自检…")
    info.pack(fill="x")

    box = tk.Text(root, width=74, height=6, font=("Microsoft YaHei UI", 12))
    box.pack(fill="both", expand=True, padx=10, pady=4)

    verdict = tk.Label(root, text="检测中…", anchor="w", padx=10, wraplength=650,
                       justify="left", font=("Microsoft YaHei UI", 11))
    verdict.pack(fill="x", pady=6)

    state = {"started": 0.0, "exc": None, "typed": False}

    def worker():
        try:
            tt.type_text(SAMPLE, delay=0.004, progress=False)
            state["typed"] = True
        except BaseException as error:
            state["exc"] = error

    def finalize(got):
        elapsed = time.time() - state["started"]
        ok = got == SAMPLE
        mine = tt.process_integrity_level(os.getpid())
        fg = tt.foreground_info()
        if state["exc"] is not None:
            verdict.config(text=f"❌ 注入抛错：{state['exc']}", fg="#b00020")
        elif ok:
            verdict.config(text=f"✅ 自检通过：注入功能正常（{len(got)} 字符，用时 {elapsed:.1f}s）",
                           fg="#0b6b2f")
        else:
            warn = tt.integrity_warning()
            verdict.config(
                text=(f"❌ 自检失败：期望 {len(SAMPLE)} 字符，实际收到 {len(got)} 字符。\n"
                      f"本程序完整性={mine}　前台={fg}\n{warn}").strip(),
                fg="#b00020",
            )
        info.config(text=f"Python {sys.version.split()[0]}　本程序完整性={mine}　"
                         f"剪贴板长度={len(tt.read_clipboard())}")
        write_result(
            f"{'PASS' if ok else 'FAIL'} chars={len(got)}/{len(SAMPLE)} elapsed={elapsed:.1f}s "
            f"mine_il={mine} fg={fg} exc={state['exc']!r} got={got!r}"
        )
        if AUTO_CLOSE:
            root.after(800, root.destroy)

    def poll():
        got = box.get("1.0", "end-1c")
        if got == SAMPLE or state["exc"] is not None or time.time() - state["started"] > 6:
            finalize(got)
            return
        root.after(100, poll)

    def run_check():
        force_foreground(root)
        box.focus_force()
        root.update()
        before = tt.foreground_title()
        # 保护：前台不是自检窗口就绝不打字，避免文字跑进别的程序
        if "输入自检" not in before:
            verdict.config(
                text=f"⚠ 自检窗口未获得前台（当前：{before}），已放弃，避免误输入到其它程序。",
                fg="#b00020",
            )
            write_result(f"SKIP foreground={before!r}")
            if AUTO_CLOSE:
                root.after(600, root.destroy)
            return
        state["started"] = time.time()
        # 关键：在后台线程打字，Tk 的事件循环要留空去接收按键；
        # 如果在 after 回调里同步打字，字符还在消息队列里就会读成空。
        threading.Thread(target=worker, daemon=True).start()
        root.after(100, poll)

    root.after(900, run_check)
    if AUTO_CLOSE:
        root.after(9000, root.destroy)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
