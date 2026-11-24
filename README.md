# Clipboard Cleaner · Keystroke Typer

![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

Clean clipboard text, then type it into fields that reject paste.
清洗剪贴板里的 LaTeX / HTML / Markdown，再用模拟键盘把纯文本输入到禁止粘贴的输入框。

A zero-dependency Windows utility: it reads the clipboard, normalises rich-text
artefacts into readable plain text, and injects the result as real keystrokes into
whatever input control has focus.

## Features

- **Rich-text normalisation** — LaTeX math, HTML tags/entities, Markdown markers, zero-width/BOM/bidi characters and UTF-8/GBK mojibake all become plain text.
- **Keystroke injection** — Windows `SendInput` with `KEYEVENTF_UNICODE`; works with Chinese, symbols and emoji, without an IME or keyboard-layout dependency.
- **Three modes** — type on demand, clean the clipboard, or watch it continuously.
- **Safety guards** — types only when the expected window is in the foreground; detects UIPI permission mismatches instead of failing silently.
- **Observable** — beeps, an append-only log, and a built-in self-test / diagnostics report.
- **No third-party packages** — standard library only.

## Requirements

| Item | Requirement |
|---|---|
| OS | **Windows 10 / 11 (x64)** — Win32 APIs are used; macOS/Linux unsupported |
| Python | **3.8+** (verified on 3.12); tick *Add python.exe to PATH* |
| Third-party packages | **None** — see [requirements.txt](requirements.txt) |
| tkinter | Bundled with the python.org installer; used by `--self-test` and `--gui` |
| Administrator | Only when the **target application** runs elevated (see Troubleshooting) |

## Files

| File | Purpose |
|---|---|
| [type_text.py](type_text.py) | Entire implementation (cleaning, injection, self-test, diagnostics) |
| [即用即打.bat](即用即打.bat) | **Main entry** — clean and type into the focused field (no console window) |
| [即用即打-可见.bat](即用即打-可见.bat) | Same, but keeps a console window for troubleshooting |
| [整理剪贴板.bat](整理剪贴板.bat) | Clean the clipboard in place; start with `--watch` to clean every copy |
| [自检.bat](自检.bat) | Opens a window, types a sample into it and reports pass/fail |
| [诊断.bat](诊断.bat) | Prints integrity levels, window list and clipboard length |

Script variants and one-click shortcuts are intentionally not shipped: a
Windows shortcut can be created locally, and `.pyw` files depend on a file
association that may be broken.

## Quick start

```bash
git clone <repository-url>
cd <repository-directory>
py -3 -c "import type_text; print('ok')"
```

1. **Copy** the text (`Ctrl+C`).
2. **Double-click** `即用即打.bat`.
3. **Click into the target field**; after the beep sequence the text is typed and the process exits.

Cleaning is automatic. By default the tool waits up to 120 s for a window whose
title contains `Chrome` (change the keyword in the `.bat` for other browsers).

## Usage

| Mode | How | What happens |
|---|---|---|
| Type | `即用即打.bat` | Waits for Chrome, settles 2 s, types the cleaned clipboard |
| Clean | `整理剪贴板.bat` | Clipboard is rewritten in place; before/after preview printed |
| Watch | `整理剪贴板.bat --watch` | Every new clipboard content is cleaned automatically (Ctrl+C to stop) |
| Self-test | `自检.bat` | Verifies the whole injection chain in a throw-away window |
| Diagnose | `诊断.bat` | Integrity levels, visible windows, clipboard length |

<details>
<summary><b>Full command-line reference</b></summary>

All launchers forward to `type_text.py`:

```
py -3 type_text.py --clipboard --clean --wait-window Chrome --settle 2 --beep
```

**Input source**: `PATH` · `--file FILE` · `--text "TEXT"` · `--clipboard` · `--gui` · `--clean-clipboard` · `--watch-clipboard`

**Timing and safety**

| Argument | Default | Description |
|---|---|---|
| `--wait-window KEYWORD` | off | Wait until the foreground title contains `KEYWORD` |
| `--wait-timeout` / `--settle` | 60 / 1 | Wait bound / extra delay after matching |
| `--only-window KEYWORD` | off | Re-check before typing (exit code 2 when mismatched) |
| `--countdown SECONDS` | 0 | Auto-start after a countdown (`F8` starts early, `Esc` cancels) |
| `--delay` | 0.003 | Per-character delay; raise if characters are dropped |
| `--newline shift\|enter` | shift | Newline strategy (`shift` avoids accidental sending) |
| `--submit` · `--force` | off | Press `Enter` at the end · ignore permission warning |
| `--beep` / `--no-beep` · `--no-gui` | off | Audible feedback · fail instead of opening a window |
| `--hotkey` | off | Daemon: `Ctrl+Alt+V` type, `Ctrl+Alt+B` type+send, `Ctrl+Alt+Q` quit |

**Cleaning**: `--clean` (full) · `--strip-md` (Markdown only) · `--no-latex` · `--no-html` · `--no-repair` · `--plain-sub` (`x1` instead of `x₁`) · `--clean-raw` · `--clean-aggressive`

**Diagnostics**: `--dry-run` · `--diagnose` · `--self-test` · `--log FILE`

**Exit codes**: `0` ok · `1` aborted/write failed · `2` window mismatch · `3` wait timeout · `4` no text · `5` permission mismatch

</details>

<details>
<summary><b>Cleaning rules</b></summary>

| Input | Output |
|---|---|
| `\(x_1=2,\ w_1=0.5\)` | `x₁=2, w₁=0.5` |
| `z\ge0` · `a\times b` · `\frac{a}{b}` · `\sqrt{x}` | `z≥0` · `a×b` · `a/b` · `√x` |
| `\alpha` · `x^{2}` | `α` · `x²` |
| `**bold**` · `*italic*` · `~~strike~~` | `bold` · `italic` · `strike` |
| `# Heading` · `> quote` · `- item` | `Heading` · `quote` · `· item` |
| `\| A \| B \|` + `\|---\|` | `A B` (flattened) |
| `[text](url)` · `` `code` `` | `text` · `code` |
| `<p>` · `&lt;` · `&nbsp;` | newline · `<` · space |
| zero-width chars · BOM · bidi controls | removed |
| `æµ‹è¯•` (UTF-8 read as Latin-1) | `测试` |

Preserved verbatim: `snake_case`, `a*b`, `C#`, `第#1项`, `café résumé`
(verified against 34 assertions during development).

</details>

## Troubleshooting

| Symptom | Cause and remedy |
|---|---|
| Double-click opens an editor | A `.pyw`/`.py` association issue — use the `.bat` launchers |
| Three low beeps, nothing typed | UIPI blocked injection (target runs elevated). Run the launcher as administrator, or start the target unelevated; `诊断.bat` shows both levels |
| Beeps but no text | The caret is not inside an editable control — click into the field first |
| Some symbols missing | Rare controls drop `U+0080–U+00FF`; Chromium and native Win32 controls are unaffected. Raise `--delay` if it persists |
| Newline sends the message | The target treats `Enter` as submit — keep `--newline shift` |
| Target is not Chrome | Change the `--wait-window` / `--only-window` keyword in `即用即打.bat` |
| Antivirus alert | Keystroke injection is often flagged heuristically; the full source is in `type_text.py` |

## How it works

1. Read `CF_UNICODETEXT` and the `HTML Format` payload from the clipboard.
2. Run both through the pipeline: mojibake repair → LaTeX → HTML → Markdown → invisible characters/whitespace.
3. Pick the more readable result (the log records which source was used).
4. Poll the foreground window title until it matches the expected keyword.
5. Inject with `SendInput` + `KEYEVENTF_UNICODE`, then exit.

## Development

```bash
py -3 -m py_compile type_text.py    # syntax check
py -3 type_text.py --self-test      # end-to-end self-test
py -3 type_text.py --diagnose       # environment report
```

Packaging to a standalone executable (build machine only, not a runtime dependency):

```bash
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --onefile --noconsole --name clipclean type_text.py
```

## License

Released under the [MIT License](LICENSE). Copyright (c) 2026 lemonlvcha1.
