# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

划词翻译器 — a Windows desktop translation tool. It hooks global mouse events to detect text selection in any application, monitors clipboard changes, shows a floating "译" button, and displays translation results in a popup tooltip. The main window supports multi-language translation (Chinese/English/Japanese/Korean/French/German/Spanish/Russian). Selection and clipboard monitoring translate English to Chinese.

**Single-file Python application** (`translator.py`, ~1600 lines). Uses only the Python standard library (Tkinter for GUI, ctypes for Win32 hooks, urllib for API calls). No pip dependencies.

## Commands

```bash
# Run from source (requires Python 3.8+)
python translator.py

# Build Windows exe (requires pyinstaller)
pip install pyinstaller
pyinstaller --onefile --name Translator --noconsole translator.py
# Output: dist/Translator.exe

# Or use the batch script
build.bat
```

No test framework or linter is configured.

## Architecture

All code lives in `translator.py` with these key classes:

- **`HoverTranslatorApp`** — Main application. Manages the Tkinter window, orchestrates selection monitoring, clipboard monitoring, and translation flow.
- **`SelectionMonitor`** — Global mouse hook via `SetWindowsHookExW` (WH_MOUSE_LL) using ctypes. Detects drag-selection and double-click. Communicates events to the Tkinter main loop via `queue.Queue` polled every 50ms.
- **`ClipboardMonitor`** — Clipboard change listener via `AddClipboardFormatListener` using a dedicated Win32 message-only window in a daemon thread. Read-only — never modifies clipboard contents. 300ms debounce.
- **`Translator`** — Core translation engine. Calls OpenAI-compatible chat completion APIs via raw `urllib.request`. Rate-limited to 1 request/second. Deduplicates in-flight requests. Supports configurable source/target languages.
- **`LanguageDetector`** — Detects source language via Unicode range matching (CJK, Hiragana/Katakana, Hangul, Cyrillic, Latin accent chars). Falls back to LLM auto-detection for ambiguous cases. Generates dynamic translation prompts.
- **`FloatingButton`** — Borderless "译" button that appears near selected text. Auto-hides after 5 seconds.
- **`FloatingTooltip`** — Borderless popup showing translation results. Auto-hides after 8 seconds, pauses timer on hover.
- **`SettingsDialog`** — Configuration UI for 5 translation providers (OpenCode Zen, SiliconFlow, DeepSeek, OpenRouter, MyMemory).
- **`LRUCache`** — In-memory translation cache (500 entries, max 100-char text). Key includes target language for multi-language support.

### Selection Translation Flow

1. `SelectionMonitor` detects drag/double-click → calls `_on_global_selection(x, y)`
2. App simulates Ctrl+C via `keybd_event` to copy selected text
3. Reads clipboard after 500ms delay
4. Shows `FloatingButton` near selection
5. On button click → `Translator.translate()` in background thread (fixed English→Chinese)
6. On result → shows `FloatingTooltip`
7. Restores original clipboard contents

### Clipboard Monitoring Flow

1. `ClipboardMonitor` detects clipboard change via Win32 `WM_CLIPBOARDUPDATE`
2. Reads clipboard text (read-only, never writes)
3. Gets cursor position via `GetCursorPos`
4. Shows `FloatingButton` near cursor
5. On button click → `Translator.translate()` in background thread (fixed English→Chinese)
6. On result → shows `FloatingTooltip`

### Main Window Flow

- User selects source/target languages from toolbar dropdowns (8 languages + auto-detect)
- Types/pastes in left panel → auto-translates after 1 second of inactivity (`TRANSLATE_DELAY = 1000`)
- `LanguageDetector.detect()` identifies source language when set to "auto"
- Dynamic prompt generated via `LanguageDetector.get_prompt()`

## Configuration

`config.json` (auto-generated on first run, also editable via Settings dialog):

| Field | Description |
|-------|-------------|
| `provider` | Translation provider identifier |
| `api_base` | OpenAI-compatible API endpoint URL |
| `api_key` | API authentication key |
| `model` | LLM model name |
| `selection_translate` | Enable/disable global selection translation |
| `clipboard_translate` | Enable/disable clipboard monitoring translation |

## Platform Constraints

- Windows 10/11 only (uses Win32 API for global mouse hooks, clipboard listener, and keyboard simulation)
- Translation requires network access to call external APIs
- The `dist/` directory contains pre-built executables and should not be edited
