# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

划词翻译器 — a Windows desktop tool that translates English to Chinese. It hooks global mouse events to detect text selection in any application, shows a floating "译" button, and displays translation results in a popup tooltip. Also has a main window for manual input translation.

**Single-file Python application** (`translator.py`, ~1200 lines). Uses only the Python standard library (Tkinter for GUI, ctypes for Win32 hooks, urllib for API calls). No pip dependencies.

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

- **`HoverTranslatorApp`** — Main application. Manages the Tkinter window, orchestrates selection monitoring, clipboard operations, and translation flow.
- **`SelectionMonitor`** — Global mouse hook via `SetWindowsHookExW` (WH_MOUSE_LL) using ctypes. Detects drag-selection and double-click. Communicates events to the Tkinter main loop via `queue.Queue` polled every 50ms.
- **`Translator`** — Core translation engine. Calls OpenAI-compatible chat completion APIs via raw `urllib.request`. Rate-limited to 1 request/second. Deduplicates in-flight requests. Runs API calls in daemon threads, delivers results via `root.after(0, callback)`.
- **`FloatingButton`** — Borderless "译" button that appears near selected text. Auto-hides after 5 seconds.
- **`FloatingTooltip`** — Borderless popup showing translation results. Auto-hides after 8 seconds, pauses timer on hover.
- **`SettingsDialog`** — Configuration UI for 5 translation providers (OpenCode Zen, SiliconFlow, DeepSeek, OpenRouter, MyMemory).
- **`LRUCache`** — In-memory translation cache (500 entries, max 100-char text). Uses `OrderedDict`.

### Selection Translation Flow

1. `SelectionMonitor` detects drag/double-click → calls `_on_global_selection(x, y)`
2. App simulates Ctrl+C via `keybd_event` to copy selected text
3. Reads clipboard after 500ms delay
4. Shows `FloatingButton` near selection
5. On button click → `Translator.translate()` in background thread
6. On result → shows `FloatingTooltip`
7. Restores original clipboard contents

### Main Window Flow

- User types/pastes in left panel → auto-translates after 1 second of inactivity (`TRANSLATE_DELAY = 1000`)

## Configuration

`config.json` (auto-generated on first run, also editable via Settings dialog):

| Field | Description |
|-------|-------------|
| `provider` | Translation provider identifier |
| `api_base` | OpenAI-compatible API endpoint URL |
| `api_key` | API authentication key |
| `model` | LLM model name |
| `selection_translate` | Enable/disable global selection translation |

## Platform Constraints

- Windows 10/11 only (uses Win32 API for global mouse hooks and keyboard simulation)
- Translation requires network access to call external APIs
- The `dist/` directory contains pre-built executables and should not be edited
