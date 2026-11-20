# -*- coding: utf-8 -*-
"""
剪贴板整理工具

把系统剪贴板里的文字洗成干净纯文本，然后写回剪贴板，直接粘贴即可。

用法
复制任意带格式的文字，双击本文件，听到提示音后剪贴板已经是干净文本。

提示音
低音一声表示已整理好；两声短促高音表示本来就是干净的；低沉长音表示剪贴板为空或失败。

说明
会还原 LaTeX 公式源码（如 \times 变成 ×、x_1 变成 x₁），把 HTML 标签与实体转成纯文本，
抹掉 Markdown 标记（#、**、_、`、表格竖线、链接等）和零宽字符等不可见符号，
修复 UTF-8/GBK 被误读产生的乱码，并压缩多余空格与空行。
"""

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import type_text

if __name__ == "__main__":
    try:
        code = type_text.clean_clipboard_once(sound=True)
    except BaseException as error:
        try:
            with open(os.path.join(HERE, "剪贴板整理日志.txt"), "a", encoding="utf-8") as handle:
                handle.write(traceback.format_exc() + "\n")
        except Exception:
            pass
        type_text.beep(200, 400)
        raise SystemExit(1)
    raise SystemExit(code)
