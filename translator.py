import tkinter as tk
from tkinter import ttk
import urllib.request
import urllib.parse
import json
import threading
import re
import time
import ctypes
import ctypes.wintypes
import sys
import os
import logging
import queue
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_PATH = os.path.join(_APP_DIR, "debug.log")
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("translator")


class Theme:
    THEMES = {
        "light": {
            "bg": "#f0f0f0",
            "toolbar_bg": "#ffffff",
            "panel_bg": "#ffffff",
            "panel_fg": "#333333",
            "input_bg": "#fafafa",
            "input_fg": "#333333",
            "input_cursor": "#333333",
            "output_bg": "#f5f5f5",
            "output_fg": "#333333",
            "btn_bg": "#4a90d9",
            "btn_fg": "#ffffff",
            "btn_hover": "#3a7bc8",
            "btn_frame_bg": "#f0f0f0",
            "border": "#e0e0e0",
            "title_fg": "#222222",
            "status_fg": "#999999",
            "label_fg": "#888888",
            "sep_color": "#e0e0e0",
            "checkbutton_bg": "#ffffff",
            "entry_bg": "#ffffff",
            "entry_fg": "#333333",
            "combobox_bg": "#ffffff",
            "dialog_bg": "#ffffff",
        },
        "dark": {
            "bg": "#1e1e2e",
            "toolbar_bg": "#2d2d3f",
            "panel_bg": "#282838",
            "panel_fg": "#e0e0e0",
            "input_bg": "#1a1a2a",
            "input_fg": "#d4d4d4",
            "input_cursor": "#d4d4d4",
            "output_bg": "#1a1a2a",
            "output_fg": "#d4d4d4",
            "btn_bg": "#5b9bd5",
            "btn_fg": "#ffffff",
            "btn_hover": "#4a8bc5",
            "btn_frame_bg": "#2d2d3f",
            "border": "#3d3d4f",
            "title_fg": "#e0e0e0",
            "status_fg": "#888888",
            "label_fg": "#aaaaaa",
            "sep_color": "#3d3d4f",
            "checkbutton_bg": "#2d2d3f",
            "entry_bg": "#2a2a3a",
            "entry_fg": "#d4d4d4",
            "combobox_bg": "#2a2a3a",
            "dialog_bg": "#2d2d3f",
        },
    }

    def __init__(self, name="light"):
        self.name = name
        self._colors = dict(self.THEMES.get(name, self.THEMES["light"]))

    def switch(self, name):
        self.name = name
        self._colors = dict(self.THEMES.get(name, self.THEMES["light"]))

    def toggle(self):
        self.switch("dark" if self.name == "light" else "light")

    def __getattr__(self, key):
        if key.startswith("_"):
            raise AttributeError(key)
        return self._colors.get(key, "#000000")


CONFIG_PATH = os.path.join(_APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "api_base": "https://opencode.ai/zen/v1",
    "api_key": "",
    "model": "big-pickle",
    "provider": "opencode-zen",
    "selection_translate": True,
    "clipboard_translate": False,
    "theme": "light",
}


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception:
        log.warning("Failed to load config, using defaults", exc_info=True)
        return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class LRUCache:
    MAX_SIZE = 500
    MAX_TEXT_LEN = 100

    def __init__(self):
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    def get(self, text, target_lang=None):
        key = (text.lower().strip(), target_lang) if target_lang else text.lower().strip()
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        return None

    def set(self, text, translation, target_lang=None):
        if len(text.strip()) > self.MAX_TEXT_LEN:
            return
        key = (text.lower().strip(), target_lang) if target_lang else text.lower().strip()
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = translation
            while len(self._cache) > self.MAX_SIZE:
                self._cache.popitem(last=False)

    def delete(self, text, target_lang=None):
        key = (text.lower().strip(), target_lang) if target_lang else text.lower().strip()
        with self._lock:
            self._cache.pop(key, None)


# ── Timing constants (ms) ──────────────────────────────────────────
TOOLTIP_AUTO_HIDE_MS       = 8000   # FloatingTooltip auto-hide after show
TOOLTIP_LEAVE_HIDE_MS      = 800    # FloatingTooltip hide delay after mouse leave
BUTTON_AUTO_HIDE_MS        = 5000   # FloatingButton default auto-hide
BUTTON_LEAVE_HIDE_MS       = 3000   # FloatingButton auto-hide after mouse leave
CLIPBOARD_CAPTURE_DELAY_MS = 500    # wait after Ctrl+C before reading clipboard
DRAG_END_DELAY_MS          = 300    # delay before processing drag-end selection
DBLCLICK_END_DELAY_MS      = 400    # delay before processing double-click selection
PASTE_TRANSLATE_DELAY_MS   = 200    # delay before translating after paste event
CANCEL_DELAY_MS            = 200    # delay before cancelling selection on mouse-down
QUEUE_POLL_INTERVAL_MS     = 50     # interval for polling the mouse-hook queue (active)
QUEUE_IDLE_INTERVAL_MS     = 150    # interval for polling the mouse-hook queue (idle)
CLIPBOARD_RESTORE_DELAY_MS = 100    # delay before restoring original clipboard
BTN_CLICK_TRANSLATE_DELAY  = 50     # delay between button click and translate start


class LanguageDetector:
    LANGUAGES = {
        "zh": "中文", "en": "English", "ja": "日本語", "ko": "한국어",
        "fr": "Français", "de": "Deutsch", "es": "Español", "ru": "Русский",
    }
    LANGUAGE_NAMES = {v: k for k, v in LANGUAGES.items()}
    LANGUAGE_OPTIONS = ["自动检测"] + list(LANGUAGES.values())
    TARGET_OPTIONS = list(LANGUAGES.values())

    # Unicode ranges
    _CJK = set(range(0x4E00, 0x9FFF + 1)) | set(range(0x3400, 0x4DBF + 1))
    _HIRAGANA = set(range(0x3040, 0x309F + 1))
    _KATAKANA = set(range(0x30A0, 0x30FF + 1))
    _HANGUL = set(range(0xAC00, 0xD7AF + 1)) | set(range(0x1100, 0x11FF + 1))
    _CYRILLIC = set(range(0x0400, 0x04FF + 1))
    _LATIN_EXTENDED = set(range(0x00C0, 0x024F + 1))

    # Accent character sets for disambiguation
    _FR_ACCENTS = set("àâæçéèêëîïôùûüÿœÀÂÆÇÉÈÊËÎÏÔÙÛÜŸŒ")
    _DE_ACCENTS = set("äöüßÄÖÜ")
    _ES_ACCENTS = set("ñ¿¡Ñ")

    @staticmethod
    def detect(text):
        """Detect language from text. Returns lang code or None if uncertain."""
        if not text or not text.strip():
            return None
        sample = text[:200]
        cjk = hira = kata = hangul = cyrillic = latin_ext = 0
        fr_score = de_score = es_score = 0
        for ch in sample:
            cp = ord(ch)
            if cp in LanguageDetector._CJK:
                cjk += 1
            elif cp in LanguageDetector._HIRAGANA:
                hira += 1
            elif cp in LanguageDetector._KATAKANA:
                kata += 1
            elif cp in LanguageDetector._HANGUL:
                hangul += 1
            elif cp in LanguageDetector._CYRILLIC:
                cyrillic += 1
            elif cp in LanguageDetector._LATIN_EXTENDED:
                latin_ext += 1
                if ch in LanguageDetector._FR_ACCENTS:
                    fr_score += 1
                if ch in LanguageDetector._DE_ACCENTS:
                    de_score += 1
                if ch in LanguageDetector._ES_ACCENTS:
                    es_score += 1
        if hira > 0 or kata > 0:
            return "ja"
        if hangul > 0:
            return "ko"
        if cyrillic > 0 and cyrillic >= cjk:
            return "ru"
        if cjk > 0:
            return "zh"
        if latin_ext > 0:
            scores = {"fr": fr_score, "de": de_score, "es": es_score}
            non_zero = {k: v for k, v in scores.items() if v > 0}
            if len(non_zero) == 1:
                return next(iter(non_zero))
            return None
        return "en"

    @staticmethod
    def get_prompt(source_lang=None, target_lang=None):
        """Build translation system prompt. Returns v1 default prompt if both None."""
        default_prompt = (
            "You are a professional English to Chinese translator. "
            "Translate the following English text to Chinese. "
            "Only output the translation result, nothing else."
        )
        if source_lang is None and target_lang is None:
            return default_prompt
        target_name = LanguageDetector.LANGUAGES.get(target_lang or "zh", "Chinese")
        if source_lang is None or source_lang == "auto":
            return (
                f"Auto-detect the source language and translate to {target_name}. "
                "Only output the translation result, nothing else."
            )
        source_name = LanguageDetector.LANGUAGES.get(source_lang, source_lang)
        return (
            f"You are a professional translator. Translate from {source_name} to {target_name}. "
            "Only output the translation result, nothing else."
        )


class Translator:
    MIN_INTERVAL = 1.0

    def __init__(self, config, root=None):
        self.config = config
        self.cache = LRUCache()
        self._lock = threading.Lock()
        self._last_request_time = 0
        self._pending = {}
        self.root = root
        self._executor = ThreadPoolExecutor(max_workers=3)

    def update_config(self, config):
        self.config = config

    def translate(self, text, callback, source_lang=None, target_lang=None):
        text = text.strip()
        if not text:
            callback("", None)
            return
        cached = self.cache.get(text, target_lang)
        if cached:
            callback(cached, None)
            return
        with self._lock:
            if text in self._pending:
                old_callback = self._pending[text]

                def merged(result, error):
                    old_callback(result, error)
                    callback(result, error)

                self._pending[text] = merged
                return
            self._pending[text] = callback

        def worker():
            cfg = dict(self.config)
            with self._lock:
                elapsed = time.time() - self._last_request_time
                if elapsed < self.MIN_INTERVAL:
                    time.sleep(self.MIN_INTERVAL - elapsed)
                self._last_request_time = time.time()
            log.info(f"API CALL: text={repr(text[:80])}")
            result, error = self._call_api_with_config(text, cfg, source_lang, target_lang)
            log.info(f"API RESPONSE: result={repr(result[:80] if result else None)}, error={error}")
            if result and not error:
                self.cache.set(text, result, target_lang)
            with self._lock:
                cb = self._pending.pop(text, None)
            if cb:
                try:
                    if self.root:
                        self.root.after(0, lambda: cb(result, error))
                    else:
                        cb(result, error)
                except Exception as e:
                    log.error(f"CALLBACK ERROR: {e}")

        self._executor.submit(worker)

    @staticmethod
    def _handle_api_error(e, context=""):
        prefix = f"{context}: " if context else ""
        if isinstance(e, urllib.error.HTTPError):
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass  # non-critical: reading error body is best-effort
            if e.code == 401:
                return f"{prefix}API Key 无效，请检查设置"
            elif e.code == 429:
                return f"{prefix}API 请求过于频繁，请稍后再试"
            return f"{prefix}HTTP 错误 {e.code}: {err_body[:200]}"
        elif isinstance(e, urllib.error.URLError):
            return f"{prefix}网络错误: {e.reason}"
        elif isinstance(e, KeyError):
            return f"{prefix}API 返回格式异常"
        else:
            return f"{prefix}翻译失败: {e}"

    def _call_api_with_config(self, text, cfg, source_lang=None, target_lang=None):
        """Call API using a config snapshot (for thread-safety)."""
        provider = cfg.get("provider", "mymemory")
        if provider == "mymemory":
            return self._call_mymemory(text, source_lang, target_lang)
        else:
            return self._call_openai_compatible_with_config(text, cfg, source_lang, target_lang)

    def _call_openai_compatible_with_config(self, text, cfg, source_lang=None, target_lang=None):
        """OpenAI-compatible API call using a config snapshot."""
        api_base = cfg.get("api_base", "").rstrip("/")
        api_key = cfg.get("api_key", "")
        model = cfg.get("model", "big-pickle")
        if not api_base:
            return None, "未配置 API 地址，请在设置中配置"
        if not api_key:
            return None, "未配置 API Key，请在设置中配置"
        url = f"{api_base}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": LanguageDetector.get_prompt(source_lang, target_lang),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                result = data["choices"][0]["message"]["content"].strip()
                return result, None
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError, Exception) as e:
            return None, self._handle_api_error(e)

    def _call_mymemory(self, text, source_lang=None, target_lang=None):
        try:
            src = source_lang if source_lang and source_lang != "auto" else "en"
            tgt = target_lang or "zh"
            lang_map = {"zh": "zh-CN"}
            src_pair = lang_map.get(src, src)
            tgt_pair = lang_map.get(tgt, tgt)
            url = "https://api.mymemory.translated.net/get"
            params = {
                "q": text,
                "langpair": f"{src_pair}|{tgt_pair}",
                "de": "hovertranslator@local.dev",
            }
            full_url = url + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(full_url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                status = data.get("responseStatus")
                if status == 200:
                    return data["responseData"]["translatedText"], None
                elif status == 429:
                    return None, "MyMemory 请求过于频繁，请稍后再试"
                else:
                    return None, f"MyMemory 错误: 状态码 {status}"
        except (urllib.error.HTTPError, urllib.error.URLError, Exception) as e:
            return None, self._handle_api_error(e, "MyMemory")


class FloatingTooltip:
    def __init__(self, root):
        self.root = root
        self.tooltip = None
        self._hide_job = None

    def show(self, source, translation, x, y):
        self.hide()
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_attributes("-topmost", True)
        self.tooltip.bind("<Enter>", self._on_enter)
        self.tooltip.bind("<Leave>", self._on_leave)
        screen_w = self.tooltip.winfo_screenwidth()
        screen_h = self.tooltip.winfo_screenheight()

        container = tk.Frame(
            self.tooltip,
            background="#ffffff",
            highlightbackground="#c8c8c8",
            highlightthickness=1,
        )
        container.pack()

        result_label = tk.Label(
            container,
            text=translation,
            background="#ffffff",
            foreground="#333333",
            font=("Microsoft YaHei UI", 11),
            anchor="nw",
            padx=10,
            pady=8,
            wraplength=360,
            justify="left",
        )
        result_label.pack(fill="x")

        self.tooltip.update_idletasks()
        tw = self.tooltip.winfo_width()
        th = self.tooltip.winfo_height()
        if x + tw > screen_w:
            x = screen_w - tw - 10
        if y + th > screen_h:
            y = y - th - 10
        if x < 0:
            x = 10
        if y < 0:
            y = 10
        self.tooltip.wm_geometry(f"+{x}+{y}")
        self.schedule_hide(TOOLTIP_AUTO_HIDE_MS)

    def _on_enter(self, event):
        if self._hide_job:
            self.root.after_cancel(self._hide_job)
            self._hide_job = None

    def _on_leave(self, event):
        self.schedule_hide(TOOLTIP_LEAVE_HIDE_MS)

    def schedule_hide(self, ms=BUTTON_AUTO_HIDE_MS):
        if self._hide_job:
            self.root.after_cancel(self._hide_job)
        self._hide_job = self.root.after(ms, self.hide)

    def hide(self):
        if self._hide_job:
            self.root.after_cancel(self._hide_job)
            self._hide_job = None
        if self.tooltip:
            try:
                self.tooltip.destroy()
            except tk.TclError:
                pass
            self.tooltip = None


class FloatingButton:
    _BG = "#ffffff"
    _BORDER = "#c8c8c8"
    _TEXT = "#333333"
    _HOVER_BG = "#f0f4ff"
    _HOVER_BORDER = "#a0b8e8"
    _LOADING_BG = "#fffbe6"
    _LOADING_BORDER = "#e0d080"

    def __init__(self, root, on_click):
        self.root = root
        self.on_click = on_click
        self.win = None
        self._hide_job = None
        self._hover = False
        self._loading = False
        self._frame = None
        self._label = None

    def show(self, x, y):
        self.hide()
        self._loading = False
        self.win = tk.Toplevel(self.root)
        self.win.wm_overrideredirect(True)
        self.win.wm_attributes("-topmost", True)
        self.win.wm_attributes("-toolwindow", True)
        try:
            self.win.wm_attributes("-alpha", 0.96)
        except Exception:
            pass

        self._frame = tk.Frame(
            self.win,
            background=self._BG,
            highlightbackground=self._BORDER,
            highlightthickness=1,
        )
        self._frame.pack()

        self._label = tk.Label(
            self._frame,
            text="译",
            background=self._BG,
            foreground=self._TEXT,
            font=("Microsoft YaHei UI", 10),
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self._label.pack()

        for w in (self._label, self._frame):
            w.bind("<ButtonPress>", self._on_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

        screen_w = self.win.winfo_screenwidth()
        if x + 40 > screen_w:
            x = screen_w - 50
        self.win.wm_geometry(f"+{x}+{y}")
        self._schedule_auto_hide(BUTTON_AUTO_HIDE_MS)

    def set_loading(self):
        self._loading = True
        if self._hide_job:
            self.root.after_cancel(self._hide_job)
            self._hide_job = None
        if self._frame and self._label:
            self._frame.configure(
                highlightbackground=self._LOADING_BORDER,
                background=self._LOADING_BG,
            )
            self._label.configure(
                text="翻译中...",
                background=self._LOADING_BG,
                foreground="#8a7a30",
                cursor="arrow",
                font=("Microsoft YaHei UI", 10),
            )

    def _on_click(self, event):
        if self._loading:
            return
        if self._hide_job:
            self.root.after_cancel(self._hide_job)
            self._hide_job = None
        self.on_click()

    def _on_enter(self, event):
        self._hover = True
        if not self._loading and self._frame and self._label:
            self._frame.configure(
                highlightbackground=self._HOVER_BORDER,
                background=self._HOVER_BG,
            )
            self._label.configure(background=self._HOVER_BG)
        if self._hide_job:
            self.root.after_cancel(self._hide_job)
            self._hide_job = None

    def _on_leave(self, event):
        self._hover = False
        if not self._loading and self._frame and self._label:
            self._frame.configure(
                highlightbackground=self._BORDER,
                background=self._BG,
            )
            self._label.configure(background=self._BG)
            self._schedule_auto_hide(BUTTON_LEAVE_HIDE_MS)

    def _schedule_auto_hide(self, ms):
        if self._hide_job:
            self.root.after_cancel(self._hide_job)
        self._hide_job = self.root.after(ms, self.hide)

    def hide(self):
        if self._hide_job:
            self.root.after_cancel(self._hide_job)
            self._hide_job = None
        if self.win:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None
            self._frame = None
            self._label = None


class SelectionMonitor:
    WH_MOUSE_LL = 14
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_MOUSEMOVE = 0x0200
    DRAG_THRESHOLD = 10
    LEAVE_DISTANCE = 150
    DBLCLICK_TIME = 500
    DBLCLICK_DISTANCE = 10

    def __init__(self, root, on_selection_callback, on_cancel_callback=None):
        self.root = root
        self.on_selection = on_selection_callback
        self.on_cancel = on_cancel_callback
        self._hook = None
        self._mouse_down_pos = None
        self._is_dragging = False
        self._enabled = True
        self._hook_thread = None
        self._selection_center = None
        self._tracking = False
        self._cancel_job = None
        self._cancel_suppressed = False
        self._queue = queue.Queue()
        self._hook_thread_id = None
        self._last_up_time = 0
        self._last_up_pos = None

    def set_enabled(self, enabled):
        self._enabled = enabled

    def suppress_cancel(self):
        self._cancel_suppressed = True
        if self._cancel_job:
            self.root.after_cancel(self._cancel_job)
            self._cancel_job = None

    def start(self):
        self._hook_thread = threading.Thread(target=self._hook_loop, daemon=True)
        self._hook_thread.start()
        self._poll_queue()

    def _hook_loop(self):
        CMPFUNC = ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)
        )
        self._hook_callback = CMPFUNC(self._low_level_mouse_proc)
        self._hook = ctypes.windll.user32.SetWindowsHookExW(
            self.WH_MOUSE_LL, self._hook_callback, None, 0
        )
        if not self._hook:
            return
        self._hook_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        msg = ctypes.wintypes.MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        ctypes.windll.user32.UnhookWindowsHookEx(self._hook)

    def _low_level_mouse_proc(self, nCode, wParam, lParam):
        if nCode >= 0 and self._enabled:
            try:
                if wParam == self.WM_LBUTTONDOWN:
                    pt = ctypes.cast(lParam, ctypes.POINTER(ctypes.wintypes.POINT)).contents
                    self._mouse_down_pos = (pt.x, pt.y)
                    self._is_dragging = False
                    if self._tracking:
                        self._tracking = False
                        self._selection_center = None
                        if self.on_cancel:
                            self._cancel_suppressed = False
                            self._queue.put(self._reschedule_cancel)
                elif wParam == self.WM_MOUSEMOVE:
                    pt = ctypes.cast(lParam, ctypes.POINTER(ctypes.wintypes.POINT)).contents
                    if self._mouse_down_pos:
                        dx = pt.x - self._mouse_down_pos[0]
                        dy = pt.y - self._mouse_down_pos[1]
                        if dx * dx + dy * dy > self.DRAG_THRESHOLD * self.DRAG_THRESHOLD:
                            self._is_dragging = True
                    if self._tracking and self._selection_center:
                        dx = pt.x - self._selection_center[0]
                        dy = pt.y - self._selection_center[1]
                        if dx * dx + dy * dy > self.LEAVE_DISTANCE * self.LEAVE_DISTANCE:
                            self._tracking = False
                            self._selection_center = None
                            if self.on_cancel:
                                self._queue.put(self.on_cancel)
                elif wParam == self.WM_LBUTTONUP and self._is_dragging:
                    pt = ctypes.cast(lParam, ctypes.POINTER(ctypes.wintypes.POINT)).contents
                    self._is_dragging = False
                    self._mouse_down_pos = None
                    x, y = pt.x, pt.y
                    self._selection_center = (x, y)
                    self._tracking = True
                    self._last_up_time = 0
                    self._last_up_pos = None
                    self._queue.put(lambda: self.root.after(DRAG_END_DELAY_MS, lambda: self._on_drag_end(x, y)))
                elif wParam == self.WM_LBUTTONUP:
                    pt = ctypes.cast(lParam, ctypes.POINTER(ctypes.wintypes.POINT)).contents
                    x, y = pt.x, pt.y
                    now = time.time()
                    is_dblclick = False
                    if self._last_up_pos:
                        dx = x - self._last_up_pos[0]
                        dy = y - self._last_up_pos[1]
                        if (now - self._last_up_time < self.DBLCLICK_TIME / 1000.0
                                and dx * dx + dy * dy < self.DBLCLICK_DISTANCE * self.DBLCLICK_DISTANCE):
                            is_dblclick = True
                    self._last_up_time = now
                    self._last_up_pos = (x, y)
                    self._mouse_down_pos = None
                    self._is_dragging = False
                    if is_dblclick:
                        self._selection_center = (x, y)
                        self._tracking = True
                        self._queue.put(lambda: self.root.after(DBLCLICK_END_DELAY_MS, lambda: self._on_drag_end(x, y)))
            except Exception:
                log.error("mouse hook callback error", exc_info=True)
        return ctypes.windll.user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

    def _poll_queue(self):
        count = 0
        try:
            while True:
                action = self._queue.get_nowait()
                try:
                    action()
                    count += 1
                except Exception:
                    log.error("queue action error", exc_info=True)
        except queue.Empty:
            pass
        interval = QUEUE_POLL_INTERVAL_MS if count > 0 else QUEUE_IDLE_INTERVAL_MS
        self.root.after(interval, self._poll_queue)

    def _reschedule_cancel(self):
        if self._cancel_job:
            self.root.after_cancel(self._cancel_job)
        self._cancel_job = self.root.after(CANCEL_DELAY_MS, self._delayed_cancel)

    def _on_drag_end(self, x, y):
        if not self._enabled:
            return
        self.on_selection(x, y)

    def _delayed_cancel(self):
        self._cancel_job = None
        if not self._cancel_suppressed and self.on_cancel:
            self.on_cancel()
        self._cancel_suppressed = False

    def stop(self):
        if self._hook:
            try:
                ctypes.windll.user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                log.warning("Failed to unhook mouse hook", exc_info=True)
            self._hook = None
        if self._hook_thread_id:
            ctypes.windll.user32.PostThreadMessageW(
                self._hook_thread_id, 0x0012, 0, 0
            )


class ClipboardMonitor:
    """Monitors clipboard changes via Win32 AddClipboardFormatListener."""
    WM_CLIPBOARDUPDATE = 0x031D
    WM_DESTROY = 0x0002
    DEBOUNCE_MS = 300
    MIN_TEXT_LEN = 2

    def __init__(self, root, on_clipboard_text):
        self.root = root
        self.on_clipboard_text = on_clipboard_text  # callback(text, x, y)
        self._enabled = False
        self._last_text = ""
        self._debounce_job = None
        self._queue = queue.Queue()
        self._hwnd = None
        self._thread = None
        self._wndproc = None
        self._running = False

    def set_enabled(self, enabled):
        self._enabled = enabled
        if not enabled:
            self._last_text = ""

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()
        self.root.after(200, self._poll_queue)

    def stop(self):
        self._running = False
        if self._hwnd:
            ctypes.windll.user32.PostMessageW(self._hwnd, self.WM_DESTROY, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _message_loop(self):
        WNDPROC = ctypes.CFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_uint,
            ctypes.c_void_p, ctypes.c_void_p
        )

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == self.WM_CLIPBOARDUPDATE and self._enabled:
                self._queue.put("clip")
            elif msg == self.WM_DESTROY:
                ctypes.windll.user32.PostQuitMessage(0)
            return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = WNDPROC(wndproc)

        wnd_class = ctypes.create_unicode_buffer("ClipboardMonitorClass")
        h_instance = ctypes.windll.kernel32.GetModuleHandleW(None)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", ctypes.c_uint),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p),
                ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", ctypes.c_wchar_p),
                ("lpszClassName", ctypes.c_wchar_p),
            ]

        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = h_instance
        wc.lpszClassName = wnd_class.value
        ctypes.windll.user32.RegisterClassW(ctypes.byref(wc))

        self._hwnd = ctypes.windll.user32.CreateWindowExW(
            0, wnd_class, "ClipboardMonitor", 0,
            0, 0, 0, 0, -3, 0, h_instance, 0  # HWND_MESSAGE = -3
        )

        ctypes.windll.user32.AddClipboardFormatListener(self._hwnd)

        msg = ctypes.wintypes.MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0):
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

        ctypes.windll.user32.RemoveClipboardFormatListener(self._hwnd)
        ctypes.windll.user32.DestroyWindow(self._hwnd)
        ctypes.windll.user32.UnregisterClassW(wnd_class, h_instance)

    def _poll_queue(self):
        if not self._running:
            return
        try:
            while True:
                self._queue.get_nowait()
                self._on_clipboard_event()
        except queue.Empty:
            pass
        self.root.after(200, self._poll_queue)

    def _on_clipboard_event(self):
        if not self._enabled:
            return
        if self._debounce_job:
            self.root.after_cancel(self._debounce_job)
        self._debounce_job = self.root.after(self.DEBOUNCE_MS, self._read_clipboard)

    def _read_clipboard(self):
        self._debounce_job = None
        if not self._enabled:
            return
        try:
            text = self.root.clipboard_get().strip()
        except tk.TclError:
            return
        if not text or len(text) < self.MIN_TEXT_LEN:
            return
        if text == self._last_text:
            return
        self._last_text = text
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        self.on_clipboard_text(text, pt.x, pt.y)


class SettingsDialog:
    PROVIDERS = {
        "opencode-zen": {
            "name": "OpenCode Zen（推荐，有免费模型）",
            "api_base": "https://opencode.ai/zen/v1",
            "models": [
                "big-pickle",
                "minimax-m2.5-free",
                "ling-2.6-flash",
                "hy3-preview-free",
                "nemotron-3-super-free",
                "gpt-5-nano",
                "qwen3.5-plus",
                "glm-5.1",
            ],
            "need_key": True,
            "key_hint": "在 opencode.ai/auth 登录获取 API Key（免费模型无需充值）",
        },
        "siliconflow": {
            "name": "硅基流动 SiliconFlow",
            "api_base": "https://api.siliconflow.cn/v1",
            "models": [
                "Qwen/Qwen3-8B",
                "THUDM/glm-4-9b-chat",
                "deepseek-ai/DeepSeek-V3",
            ],
            "need_key": True,
            "key_hint": "在 siliconflow.cn 免费注册获取",
        },
        "deepseek": {
            "name": "DeepSeek",
            "api_base": "https://api.deepseek.com/v1",
            "models": ["deepseek-chat"],
            "need_key": True,
            "key_hint": "在 platform.deepseek.com 获取",
        },
        "openrouter": {
            "name": "OpenRouter",
            "api_base": "https://openrouter.ai/api/v1",
            "models": [
                "deepseek/deepseek-chat:free",
                "google/gemma-3-4b-it:free",
            ],
            "need_key": True,
            "key_hint": "在 openrouter.ai 获取",
        },
        "mymemory": {
            "name": "MyMemory（免配置，但有限流）",
            "api_base": "",
            "models": [],
            "need_key": False,
            "key_hint": "无需 API Key",
        },
    }

    def __init__(self, parent, config, on_save):
        self.parent = parent
        self.config = dict(config)
        self.on_save = on_save
        self._build()

    def _build(self):
        self.win = tk.Toplevel(self.parent)
        self.win.title("⚙️ 翻译设置")
        self.win.geometry("540x480")
        self.win.resizable(False, False)
        self.win.transient(self.parent)
        self.win.protocol("WM_DELETE_WINDOW", self.win.destroy)
        self.win.grab_set()

        main = tk.Frame(self.win, padx=20, pady=15)
        main.pack(fill="both", expand=True)

        tk.Label(
            main, text="翻译引擎设置", font=("Microsoft YaHei UI", 14, "bold")
        ).pack(anchor="w", pady=(0, 10))

        row1 = tk.Frame(main)
        row1.pack(fill="x", pady=4)
        tk.Label(row1, text="翻译服务:", font=("Microsoft YaHei UI", 10)).pack(
            side="left"
        )
        self.provider_var = tk.StringVar(value=self.config.get("provider", "mymemory"))
        provider_names = [
            (v["name"], k) for k, v in self.PROVIDERS.items()
        ]
        self.provider_combo = ttk.Combobox(
            row1,
            values=[p[0] for p in provider_names],
            state="readonly",
            width=35,
        )
        self.provider_combo.pack(side="left", padx=8)
        self._provider_map = {p[0]: p[1] for p in provider_names}
        self._name_map = {p[1]: p[0] for p in provider_names}
        self.provider_combo.set(self._name_map.get(self.provider_var.get(), ""))
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)

        row2 = tk.Frame(main)
        row2.pack(fill="x", pady=4)
        tk.Label(row2, text="API 地址:", font=("Microsoft YaHei UI", 10)).pack(
            side="left"
        )
        self.base_var = tk.StringVar(value=self.config.get("api_base", ""))
        self.base_entry = tk.Entry(row2, textvariable=self.base_var, width=40)
        self.base_entry.pack(side="left", padx=8)

        row3 = tk.Frame(main)
        row3.pack(fill="x", pady=4)
        tk.Label(row3, text="API Key:", font=("Microsoft YaHei UI", 10)).pack(
            side="left"
        )
        self.key_var = tk.StringVar(value=self.config.get("api_key", ""))
        self.key_entry = tk.Entry(row3, textvariable=self.key_var, width=40, show="*")
        self.key_entry.pack(side="left", padx=8)

        self.key_hint_label = tk.Label(
            main, text="", font=("Microsoft YaHei UI", 8), fg="#888888"
        )
        self.key_hint_label.pack(anchor="w", padx=70)

        row4 = tk.Frame(main)
        row4.pack(fill="x", pady=4)
        tk.Label(row4, text="模型:", font=("Microsoft YaHei UI", 10)).pack(
            side="left"
        )
        self.model_var = tk.StringVar(value=self.config.get("model", ""))
        self.model_combo = ttk.Combobox(
            row4, textvariable=self.model_var, width=38
        )
        self.model_combo.pack(side="left", padx=8)

        self._update_provider_ui(loading=True)

        sep = ttk.Separator(main, orient="horizontal")
        sep.pack(fill="x", pady=10)

        self.sel_var = tk.BooleanVar(value=self.config.get("selection_translate", True))
        sel_check = tk.Checkbutton(
            main,
            text=" 启用划词翻译（在其他应用中拖选文字后弹出翻译按钮）",
            variable=self.sel_var,
            font=("Microsoft YaHei UI", 10),
        )
        sel_check.pack(anchor="w", pady=4)

        self.clip_var = tk.BooleanVar(value=self.config.get("clipboard_translate", False))
        clip_check = tk.Checkbutton(
            main,
            text=" 启用剪贴板监听翻译（复制文字后弹出翻译按钮）",
            variable=self.clip_var,
            font=("Microsoft YaHei UI", 10),
        )
        clip_check.pack(anchor="w", pady=4)

        btn_frame = tk.Frame(main)
        btn_frame.pack(fill="x", pady=(15, 0))
        tk.Button(
            btn_frame,
            text="💾 保存",
            command=self._save,
            font=("Microsoft YaHei UI", 10),
            bg="#4a90d9",
            fg="white",
            padx=20,
        ).pack(side="left", padx=5)
        tk.Button(
            btn_frame,
            text="取消",
            command=self.win.destroy,
            font=("Microsoft YaHei UI", 10),
            padx=20,
        ).pack(side="left", padx=5)

    def _on_provider_change(self, event=None):
        self._update_provider_ui(loading=False)

    def _update_provider_ui(self, loading=False):
        name = self.provider_combo.get()
        pid = self._provider_map.get(name, "mymemory")
        info = self.PROVIDERS[pid]
        if not loading:
            self.base_var.set(info["api_base"])
        self.key_hint_label.config(text=info["key_hint"])
        if info["models"]:
            self.model_combo["values"] = info["models"]
            current_model = self.model_var.get()
            if loading and current_model and current_model in info["models"]:
                self.model_combo.set(current_model)
            elif not loading or not current_model:
                self.model_combo.set(info["models"][0])
            self.model_combo.config(state="readonly")
        else:
            self.model_combo["values"] = []
            self.model_combo.set("")
            self.model_combo.config(state="disabled")
        if not info["need_key"]:
            self.key_entry.config(state="disabled")
            if not loading:
                self.key_var.set("")
        else:
            self.key_entry.config(state="normal")

    def _save(self):
        name = self.provider_combo.get()
        pid = self._provider_map.get(name, "mymemory")
        cfg = {
            "provider": pid,
            "api_base": self.base_var.get().strip(),
            "api_key": self.key_var.get().strip(),
            "model": self.model_var.get().strip(),
            "selection_translate": self.sel_var.get(),
            "clipboard_translate": self.clip_var.get(),
        }
        save_config(cfg)
        self.on_save(cfg)
        self.win.destroy()


class HoverTranslatorApp:
    TRANSLATE_DELAY = 1000

    def __init__(self, root):
        self.root = root
        self.root.title("悬停翻译器")
        self.root.geometry("960x600")
        self.root.minsize(600, 400)

        self.config = load_config()
        self.translator = Translator(self.config, root)
        self.floating = FloatingTooltip(root)
        self.floating_btn = FloatingButton(root, self._on_floating_btn_click)
        self._translate_job = None
        self._last_text = ""
        self._is_translating = False
        self._selection_pos = (0, 0)
        self._clipboard_before = ""
        self._clipboard_backup = None
        self._captured_text = ""
        self._btn_clicked = False
        self._clipboard_restore_job = None
        self._selection_seq = 0
        self._source_lang = None
        self._target_lang = "zh"
        self._clipboard_monitor = None
        self.theme = Theme(self.config.get("theme", "light"))

        self._build_ui()
        self._start_selection_monitor()
        self._start_clipboard_monitor()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _build_ui(self):
        t = self.theme
        self.root.configure(bg=t.bg)

        # ── Toolbar ──
        self.toolbar = tk.Frame(self.root, bg=t.toolbar_bg, padx=10, pady=6)
        self.toolbar.pack(fill="x")

        self.title_label = tk.Label(
            self.toolbar, text="📖 悬停翻译器",
            font=("Microsoft YaHei UI", 13, "bold"),
            bg=t.toolbar_bg, fg=t.title_fg,
        )
        self.title_label.pack(side="left")

        provider_name = SettingsDialog.PROVIDERS.get(
            self.config.get("provider", "mymemory"), {}
        ).get("name", "MyMemory")
        self.provider_label = tk.Label(
            self.toolbar, text=f"引擎: {provider_name}",
            font=("Microsoft YaHei UI", 9),
            bg=t.toolbar_bg, fg=t.label_fg,
        )
        self.provider_label.pack(side="left", padx=10)

        # ── Language dropdowns ──
        self.lang_frame = tk.Frame(self.toolbar, bg=t.toolbar_bg)
        self.lang_frame.pack(side="left", padx=6)

        self.src_lang_label = tk.Label(
            self.lang_frame, text="源:", font=("Microsoft YaHei UI", 9),
            bg=t.toolbar_bg, fg=t.title_fg,
        )
        self.src_lang_label.pack(side="left")
        self._source_combo = ttk.Combobox(
            self.lang_frame, values=LanguageDetector.LANGUAGE_OPTIONS,
            width=8, state="readonly", font=("Microsoft YaHei UI", 9),
        )
        self._source_combo.set("自动检测")
        self._source_combo.pack(side="left", padx=(0, 6))
        self._source_combo.bind("<<ComboboxSelected>>", self._on_language_change)

        self.arrow_label = tk.Label(
            self.lang_frame, text="→", font=("Microsoft YaHei UI", 9),
            bg=t.toolbar_bg, fg=t.title_fg,
        )
        self.arrow_label.pack(side="left")
        self._target_combo = ttk.Combobox(
            self.lang_frame, values=LanguageDetector.TARGET_OPTIONS,
            width=8, state="readonly", font=("Microsoft YaHei UI", 9),
        )
        self._target_combo.set("中文")
        self._target_combo.pack(side="left", padx=(0, 4))
        self._target_combo.bind("<<ComboboxSelected>>", self._on_language_change)

        # ── Right-side buttons ──
        btn_frame = tk.Frame(self.toolbar, bg=t.toolbar_bg)
        btn_frame.pack(side="right")

        self.theme_btn = tk.Button(
            btn_frame, text="🌙" if t.name == "light" else "☀️",
            command=self._toggle_theme, font=("Microsoft YaHei UI", 10),
            relief="flat", padx=6, cursor="hand2",
            bg=t.toolbar_bg, fg=t.title_fg,
        )
        self.theme_btn.pack(side="left", padx=2)

        self.settings_btn = tk.Button(
            btn_frame, text="⚙️ 设置",
            command=self._open_settings,
            font=("Microsoft YaHei UI", 9), relief="flat", padx=8,
            bg=t.toolbar_bg, fg=t.title_fg, cursor="hand2",
        )
        self.settings_btn.pack(side="left", padx=2)

        self.translate_btn = tk.Button(
            btn_frame, text="🔄 翻译",
            command=self._manual_translate,
            font=("Microsoft YaHei UI", 9), relief="flat", padx=8,
            bg=t.btn_bg, fg=t.btn_fg, cursor="hand2",
        )
        self.translate_btn.pack(side="left", padx=2)

        self.retranslate_btn = tk.Button(
            btn_frame, text="🔁",
            command=self._retranslate,
            font=("Microsoft YaHei UI", 9), relief="flat", padx=4,
            bg=t.toolbar_bg, fg=t.title_fg, cursor="hand2",
        )
        self.retranslate_btn.pack(side="left", padx=2)

        self.paste_btn = tk.Button(
            btn_frame, text="📋 粘贴并翻译",
            command=self._paste_text,
            font=("Microsoft YaHei UI", 9), relief="flat", padx=8,
            bg=t.toolbar_bg, fg=t.title_fg, cursor="hand2",
        )
        self.paste_btn.pack(side="left", padx=2)

        self.clear_btn = tk.Button(
            btn_frame, text="🗑️ 清空",
            command=self._clear_text,
            font=("Microsoft YaHei UI", 9), relief="flat", padx=8,
            bg=t.toolbar_bg, fg=t.title_fg, cursor="hand2",
        )
        self.clear_btn.pack(side="left", padx=2)

        # ── Separator ──
        self.sep_frame = tk.Frame(self.root, height=1, bg=t.sep_color)
        self.sep_frame.pack(fill="x")

        # ── Panels ──
        self.panels = tk.PanedWindow(
            self.root, orient="horizontal", sashwidth=4,
            bg=t.bg, sashrelief="flat",
        )
        self.panels.pack(fill="both", expand=True, padx=8, pady=(6, 0))

        self.left_frame = tk.LabelFrame(
            self.panels, text=" 📝 源文本 (自动检测) ",
            font=("Microsoft YaHei UI", 10),
            bg=t.panel_bg, fg=t.panel_fg,
            padx=4, pady=4, relief="groove", bd=1,
        )
        self.panels.add(self.left_frame, stretch="always")

        self.src_text = tk.Text(
            self.left_frame,
            font=("Consolas", 12), wrap="word", spacing3=3,
            padx=8, pady=8, relief="flat",
            bg=t.input_bg, fg=t.input_fg,
            insertbackground=t.input_cursor,
        )
        src_scroll = ttk.Scrollbar(self.left_frame, command=self.src_text.yview)
        self.src_text.configure(yscrollcommand=src_scroll.set)
        src_scroll.pack(side="right", fill="y")
        self.src_text.pack(side="left", fill="both", expand=True)

        self.right_frame = tk.LabelFrame(
            self.panels, text=" 🌏 中文 ",
            font=("Microsoft YaHei UI", 10),
            bg=t.panel_bg, fg=t.panel_fg,
            padx=4, pady=4, relief="groove", bd=1,
        )
        self.panels.add(self.right_frame, stretch="always")

        self.dst_text = tk.Text(
            self.right_frame,
            font=("Microsoft YaHei UI", 12), wrap="word", spacing3=3,
            padx=8, pady=8, relief="flat",
            bg=t.output_bg, fg=t.output_fg,
            state="disabled",
        )
        dst_scroll = ttk.Scrollbar(self.right_frame, command=self.dst_text.yview)
        self.dst_text.configure(yscrollcommand=dst_scroll.set)
        dst_scroll.pack(side="right", fill="y")
        self.dst_text.pack(side="left", fill="both", expand=True)

        # ── Status bar ──
        self.status_var = tk.StringVar(
            value="就绪 — 在其他应用中拖选文字，点击「译」按钮翻译"
        )
        self.status_bar = tk.Label(
            self.root, textvariable=self.status_var,
            font=("Microsoft YaHei UI", 9),
            bg=t.bg, fg=t.status_fg,
            anchor="w", padx=10, pady=3, relief="flat",
        )
        self.status_bar.pack(fill="x")

        self.src_text.bind("<KeyRelease>", self._on_text_change)
        self.src_text.bind("<<Paste>>", self._on_paste_event)

    def _on_text_change(self, event=None):
        if self._translate_job:
            self.root.after_cancel(self._translate_job)
        self._translate_job = self.root.after(
            self.TRANSLATE_DELAY, self._do_translate
        )

    def _on_paste_event(self, event=None):
        self.root.after(PASTE_TRANSLATE_DELAY_MS, self._do_translate)

    def _on_language_change(self, event=None):
        src_display = self._source_combo.get()
        tgt_display = self._target_combo.get()
        self._source_lang = LanguageDetector.LANGUAGE_NAMES.get(src_display)
        if src_display == "自动检测":
            self._source_lang = None
        self._target_lang = LanguageDetector.LANGUAGE_NAMES.get(tgt_display, "zh")
        self.left_frame.configure(text=f" 📝 源文本 ({src_display}) ")
        self.right_frame.configure(text=f" 🌏 {tgt_display} ")
        self._last_text = ""
        self._do_translate()

    def _toggle_theme(self):
        self.theme.toggle()
        self.config["theme"] = self.theme.name
        save_config(self.config)
        self._apply_theme()

    def _apply_theme(self):
        t = self.theme
        self.root.configure(bg=t.bg)

        # Toolbar
        self._theme_widget(self.toolbar, t.toolbar_bg)
        self._theme_widget(self.title_label, t.toolbar_bg, t.title_fg)
        self._theme_widget(self.provider_label, t.toolbar_bg, t.label_fg)
        self._theme_widget(self.lang_frame, t.toolbar_bg)
        self._theme_widget(self.src_lang_label, t.toolbar_bg, t.title_fg)
        self._theme_widget(self.arrow_label, t.toolbar_bg, t.title_fg)

        # Buttons
        self.theme_btn.configure(
            text="🌙" if t.name == "light" else "☀️",
            bg=t.toolbar_bg, fg=t.title_fg,
        )
        self.settings_btn.configure(bg=t.toolbar_bg, fg=t.title_fg)
        self.translate_btn.configure(bg=t.btn_bg, fg=t.btn_fg)
        self.retranslate_btn.configure(bg=t.toolbar_bg, fg=t.title_fg)
        self.paste_btn.configure(bg=t.toolbar_bg, fg=t.title_fg)
        self.clear_btn.configure(bg=t.toolbar_bg, fg=t.title_fg)

        # Separator
        self.sep_frame.configure(bg=t.sep_color)

        # Panels
        self.panels.configure(bg=t.bg)
        self.left_frame.configure(bg=t.panel_bg, fg=t.panel_fg)
        self.right_frame.configure(bg=t.panel_bg, fg=t.panel_fg)
        self.src_text.configure(bg=t.input_bg, fg=t.input_fg, insertbackground=t.input_cursor)
        self.dst_text.configure(bg=t.output_bg, fg=t.output_fg)

        # Status bar
        self.status_bar.configure(bg=t.bg, fg=t.status_fg)

    def _theme_widget(self, widget, bg, fg=None):
        widget.configure(bg=bg)
        if fg is not None:
            widget.configure(fg=fg)

    def _manual_translate(self):
        self._do_translate()

    def _retranslate(self):
        text = self.src_text.get("1.0", "end").strip()
        if not text:
            return
        self.translator.cache.delete(text, self._target_lang)
        self._last_text = ""
        self._do_translate()

    def _do_translate(self):
        text = self.src_text.get("1.0", "end").strip()
        if not text:
            self._set_dst_text("")
            self._set_status("就绪", "#999999")
            return
        if text == self._last_text and self._is_translating:
            return
        self._last_text = text
        self._is_translating = True
        self._set_status("⏳ 正在翻译...", "#d4a017")
        self.translate_btn.configure(state="disabled")

        def on_result(result, error):
            self._is_translating = False
            self.translate_btn.configure(state="normal")
            if error:
                self._set_dst_text("")
                self._set_status(f"❌ {error}", "#cc3333")
            elif result:
                self._set_dst_text(result)
                self._set_status("✅ 翻译完成", "#339933")
            else:
                self._set_dst_text("")
                self._set_status("❌ 未获取到翻译结果", "#cc3333")

        self.translator.translate(text, on_result, source_lang=self._source_lang, target_lang=self._target_lang)

    def _set_dst_text(self, text):
        self.dst_text.configure(state="normal")
        self.dst_text.delete("1.0", "end")
        if text:
            self.dst_text.insert("1.0", text)
        self.dst_text.configure(state="disabled")

    def _set_status(self, text, color="#999999"):
        self.status_var.set(text)
        self.status_bar.configure(fg=color)

    def _paste_text(self):
        try:
            clipboard = self.root.clipboard_get()
            self.src_text.delete("1.0", "end")
            self.src_text.insert("1.0", clipboard)
            self._last_text = ""
            self._do_translate()
        except tk.TclError:
            self._set_status("❌ 剪贴板为空", "#cc3333")

    def _clear_text(self):
        self.src_text.delete("1.0", "end")
        self._set_dst_text("")
        self._last_text = ""
        self._set_status("已清空", "#999999")

    def _open_settings(self):
        SettingsDialog(self.root, self.config, self._on_settings_saved)

    def _on_settings_saved(self, cfg):
        self.config = cfg
        self.translator.update_config(cfg)
        provider_name = SettingsDialog.PROVIDERS.get(
            cfg.get("provider", "mymemory"), {}
        ).get("name", "MyMemory")
        self.provider_label.config(text=f"引擎: {provider_name}")
        self.selection_monitor.set_enabled(cfg.get("selection_translate", True))
        if self._clipboard_monitor:
            self._clipboard_monitor.set_enabled(cfg.get("clipboard_translate", False))
        sel_status = "已启用" if cfg.get("selection_translate", True) else "已关闭"
        clip_status = "已启用" if cfg.get("clipboard_translate", False) else "已关闭"
        self._set_status(f"✅ 设置已保存 | 划词翻译{sel_status} | 剪贴板翻译{clip_status}", "#339933")

    def _start_selection_monitor(self):
        self.selection_monitor = SelectionMonitor(
            self.root, self._on_global_selection, self._on_selection_cancel
        )
        enabled = self.config.get("selection_translate", True)
        self.selection_monitor.set_enabled(enabled)
        self.selection_monitor.start()

    def _start_clipboard_monitor(self):
        self._clipboard_monitor = ClipboardMonitor(
            self.root, self._on_clipboard_text
        )
        enabled = self.config.get("clipboard_translate", False)
        self._clipboard_monitor.set_enabled(enabled)
        self._clipboard_monitor.start()

    def _on_clipboard_text(self, text, x, y):
        if self._clipboard_backup is not None:
            return
        if len(text.strip()) < ClipboardMonitor.MIN_TEXT_LEN:
            return
        self._captured_text = text.strip()
        self._selection_pos = (x, y)
        self.floating_btn.show(x, y)

    def _on_closing(self):
        if hasattr(self, 'selection_monitor'):
            self.selection_monitor.stop()
        if self._clipboard_monitor:
            self._clipboard_monitor.stop()
        self.root.destroy()

    def _on_selection_cancel(self):
        if self._btn_clicked:
            return
        self.floating_btn.hide()
        if not self._is_mouse_over_tooltip():
            self.floating.hide()
        self._restore_clipboard()

    def _is_mouse_over_tooltip(self):
        tip = self.floating.tooltip
        if not tip:
            return False
        try:
            x, y = tip.winfo_rootx(), tip.winfo_rooty()
            w, h = tip.winfo_width(), tip.winfo_height()
            mx, my = tip.winfo_pointerx(), tip.winfo_pointery()
            return x <= mx <= x + w and y <= my <= y + h
        except tk.TclError:
            return False

    def _backup_clipboard_win32(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        backup = {}
        if not user32.OpenClipboard(0):
            return backup
        try:
            fmt = 0
            while True:
                fmt = user32.EnumClipboardFormats(fmt)
                if fmt == 0:
                    break
                handle = user32.GetClipboardData(fmt)
                if not handle:
                    continue
                ptr = kernel32.GlobalLock(handle)
                if not ptr:
                    continue
                try:
                    size = kernel32.GlobalSize(handle)
                    if size > 0:
                        buf = ctypes.create_string_buffer(size)
                        ctypes.memmove(buf, ptr, size)
                        backup[fmt] = bytes(buf)
                finally:
                    kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
        return backup

    def _restore_clipboard_win32(self, backup):
        if not backup:
            return
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        if not user32.OpenClipboard(0):
            return
        try:
            user32.EmptyClipboard()
            for fmt, data in backup.items():
                size = len(data)
                handle = kernel32.GlobalAlloc(0x0042, size)  # GMEM_MOVEABLE | GMEM_ZEROINIT
                if not handle:
                    continue
                ptr = kernel32.GlobalLock(handle)
                if not ptr:
                    kernel32.GlobalFree(handle)
                    continue
                try:
                    ctypes.memmove(ptr, data, size)
                finally:
                    kernel32.GlobalUnlock(ptr)
                user32.SetClipboardData(fmt, handle)
        finally:
            user32.CloseClipboard()

    def _on_global_selection(self, x, y):
        if not self.config.get("selection_translate", True):
            return
        self._selection_seq += 1
        seq = self._selection_seq
        self._selection_pos = (x, y)
        self._captured_text = ""
        self._clipboard_backup = self._backup_clipboard_win32()
        log.info(f"SELECTION at ({x},{y}) seq={seq}, backup_formats={len(self._clipboard_backup)}")
        self._copy_selection()
        self.root.after(CLIPBOARD_CAPTURE_DELAY_MS, lambda: self._capture_text_and_show_btn(seq))

    def _copy_selection(self):
        ctypes.windll.user32.keybd_event(0x11, 0x1D, 0, 0)
        ctypes.windll.user32.keybd_event(0x43, 0x2E, 0, 0)
        ctypes.windll.user32.keybd_event(0x43, 0x2E, 2, 0)
        ctypes.windll.user32.keybd_event(0x11, 0x1D, 2, 0)

    def _capture_text_and_show_btn(self, seq, _retry=False):
        if seq != self._selection_seq:
            log.info(f"CAPTURE: seq {seq} is stale (current={self._selection_seq}), ignoring")
            return
        try:
            text = self.root.clipboard_get().strip()
        except tk.TclError:
            text = ""
        log.info(f"CAPTURE: clipboard={repr(text[:80])}, before={repr(self._clipboard_before[:80])}, retry={_retry}")
        if not text:
            if not _retry:
                log.info("CAPTURE: empty clipboard, retrying Ctrl+C...")
                self._copy_selection()
                self.root.after(CLIPBOARD_CAPTURE_DELAY_MS, lambda: self._capture_text_and_show_btn(seq, _retry=True))
                return
            log.warning("CAPTURE: clipboard still empty after retry")
            self._set_status("⚠️ 剪贴板为空（Ctrl+C可能未生效）", "#d4a017")
            self._restore_clipboard()
            return
        if not re.search(r"[a-zA-Z]", text):
            log.warning(f"CAPTURE: no English in text: {repr(text[:50])}")
            self._set_status(f"选中文本不含英文: {text[:30]}", "#d4a017")
            self._restore_clipboard()
            return
        self._captured_text = text
        x, y = self._selection_pos
        self.floating_btn.show(x + 12, y + 12)
        log.info(f"CAPTURE OK, showing button, text={repr(text[:80])}")
        self._set_status(f"已捕获: {text[:40]}... 点击「译」翻译", "#339933")

    def _on_floating_btn_click(self):
        log.info("BTN CLICKED")
        self.selection_monitor.suppress_cancel()
        self._btn_clicked = True
        self.floating_btn.set_loading()
        self.root.after(BTN_CLICK_TRANSLATE_DELAY, self._translate_captured)

    def _translate_captured(self):
        text = self._captured_text
        log.info(f"TRANSLATE: captured_text={repr(text[:80])}")
        if not text:
            self._btn_clicked = False
            self.floating_btn.hide()
            self._restore_clipboard()
            self._set_status("❌ 未捕获到文字", "#cc3333")
            return

        cached = self.translator.cache.get(text)
        if cached:
            log.info(f"TRANSLATE: cache hit={repr(cached[:80])}")
            self._btn_clicked = False
            try:
                self.floating_btn.hide()
                self._restore_clipboard()
                self._show_translation_at(text, cached)
                self._set_status(f"✅ [缓存] {text[:30]} → {cached[:30]}", "#339933")
            except Exception:
                log.error("cache hit display error", exc_info=True)
            return

        self._set_status(f"⏳ 正在翻译: {text[:40]}...", "#d4a017")

        def on_result(result, error):
            try:
                log.info(f"TRANSLATE RESULT: result={repr(result[:80] if result else None)}, error={error}")
                self._btn_clicked = False
                self.floating_btn.hide()
                self._restore_clipboard()
                if error:
                    self._set_status(f"❌ {error}", "#cc3333")
                elif result:
                    self._show_translation_at(text, result)
                    self._set_status(f"✅ {text[:30]} → {result[:30]}", "#339933")
                else:
                    self._set_status("❌ 未获取到翻译结果", "#cc3333")
            except Exception:
                log.error("on_result callback error", exc_info=True)

        self.translator.translate(text, on_result)

    def _show_translation_at(self, source, translation):
        x, y = self._selection_pos
        y += 20
        log.info(f"SHOW BUBBLE at ({x},{y}), translation={repr(translation[:60])}")
        self.floating.show(source, translation, x, y)

    def _restore_clipboard(self):
        if self._clipboard_restore_job:
            self.root.after_cancel(self._clipboard_restore_job)
        self._clipboard_restore_job = self.root.after(CLIPBOARD_RESTORE_DELAY_MS, self._do_restore_clipboard)

    def _do_restore_clipboard(self):
        self._clipboard_restore_job = None
        backup = getattr(self, '_clipboard_backup', None)
        if backup is None:
            if self._clipboard_before:
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(self._clipboard_before)
                    self.root.update()
                except Exception:
                    log.warning("clipboard text restore failed", exc_info=True)
            return
        try:
            self._restore_clipboard_win32(backup)
        except Exception:
            log.warning("clipboard restore failed", exc_info=True)
        finally:
            self._clipboard_backup = None


def main():
    root = tk.Tk()
    app = HoverTranslatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
