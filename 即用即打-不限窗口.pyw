# -*- coding: utf-8 -*-
"""备选：不限制窗口，双击后 8 秒倒计时开始打字（适合学习通是客户端、不是 Chrome 的情况）。"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import type_text  # noqa: E402

ARGS = [
    "--clipboard",
    "--clean",
    "--countdown", "8",
    "--beep",
    "--log", os.path.join(HERE, "输入日志.txt"),
]

if __name__ == "__main__":
    raise SystemExit(type_text.main(ARGS))
