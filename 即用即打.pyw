# -*- coding: utf-8 -*-
"""
一键输入工具

读取剪贴板文本，等到 Chrome 在前台，然后模拟键盘逐字输入，打完自动退出。

用法
复制要输入的文本，双击本文件，切到 Chrome 并点一下目标输入框，听到提示音后开始输入。

提示音
低音一声表示程序已启动，中音一声表示开始输入，高音一声表示输入完成，
低沉长音表示剪贴板为空、没等到 Chrome 窗口或者权限不匹配。

排查
每次运行都会把过程写进同目录的 输入日志.txt，出问题时查看这个文件。
"""

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import type_text

LOG = os.path.join(HERE, "输入日志.txt")
type_text._LOG_PATH = LOG

ARGS = [
    "--clipboard",
    "--clean",
    "--wait-window", "Chrome",
    "--wait-timeout", "120",
    "--settle", "2",
    "--only-window", "Chrome",
    "--beep",
    "--no-gui",
    "--log", LOG,
]

if __name__ == "__main__":
    try:
        code = type_text.main(ARGS)
    except SystemExit:
        raise
    except BaseException as error:
        type_text.log("未捕获异常：" + repr(error))
        type_text.log(traceback.format_exc())
        type_text.beep(200, 400)
        raise SystemExit(1)
    raise SystemExit(code)
