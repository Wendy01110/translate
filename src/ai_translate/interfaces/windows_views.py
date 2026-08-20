from __future__ import annotations

import threading
from collections.abc import Callable

from ai_translate.config import AppPreferences
from ai_translate.core.models import JobKind, JobStatus, TranslateJob
from ai_translate.interfaces.input_box import format_input_translation
from ai_translate.interfaces.settings import (
    IMAGE_MODE_OPTIONS,
    LOCAL_ADVANCED_MODEL_TIER_OPTIONS,
    PROVIDER_OPTIONS,
    SOURCE_LANG_OPTIONS,
    TARGET_LANG_OPTIONS,
    parse_settings_form,
)
from ai_translate.interfaces.windows_desktop import WindowsUiRuntime

_WINDOWS_ENGINE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("auto", "自动（本地高级 → API 两层）"),
    ("paddle", "只本地高级（PaddleOCR）"),
    ("standard", "只 API 普通（OCR.space）"),
    ("model", "只 API 高级模型"),
)


class WindowsSettingsPresenter:
    def __init__(
        self,
        runtime: WindowsUiRuntime,
        *,
        load: Callable[[], AppPreferences],
        save: Callable[[AppPreferences], None],
    ) -> None:
        self._runtime = runtime
        self._load = load
        self._save = save
        self._window: object | None = None
        self._vars: dict[str, object] = {}
        self._translate_model: object | None = None
        self._ocr_model: object | None = None
        self._status: object | None = None
        self._apply_button: object | None = None
        self._save_button: object | None = None

    def show(self) -> None:
        self._runtime.call_soon(self._show_ui)

    def _show_ui(self) -> None:
        if self._window is None:
            self._create()
        try:
            preferences = self._load()
        except Exception as exc:
            self._status.configure(text=f"读取设置失败：{exc}")
            return
        self._fill(preferences)
        self._window.deiconify()
        self._window.lift()
        self._window.focus_force()

    def _create(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        window = tk.Toplevel(self._runtime.root)
        window.withdraw()
        window.title("AI Translate 设置")
        window.geometry("640x610")
        window.minsize(560, 520)
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        notebook = ttk.Notebook(window)
        notebook.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 6))
        translate_tab = ttk.Frame(notebook, padding=14)
        ocr_tab = ttk.Frame(notebook, padding=14)
        general_tab = ttk.Frame(notebook, padding=14)
        notebook.add(translate_tab, text="翻译")
        notebook.add(ocr_tab, text="OCR")
        notebook.add(general_tab, text="语言与热键")
        for tab in (translate_tab, ocr_tab, general_tab):
            tab.columnconfigure(1, weight=1)

        self._add_combo(
            translate_tab,
            0,
            "翻译来源",
            "translate_provider",
            tuple(label for _value, label in PROVIDER_OPTIONS),
        )
        self._add_entry(translate_tab, 1, "API 地址", "translate_base_url")
        self._add_entry(translate_tab, 2, "API 密钥", "translate_api_key", secret=True)
        self._translate_model = self._add_combo(
            translate_tab,
            3,
            "模型",
            "translate_model",
            (),
            editable=True,
        )
        self._add_entry(translate_tab, 4, "Microsoft 区域", "translate_region")
        ttk.Label(
            translate_tab,
            text="内置 Google / Bing / DeepL 不需要密钥；其它来源按需填写。",
            foreground="#666666",
            wraplength=500,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(16, 0))

        self._add_combo(
            ocr_tab,
            0,
            "OCR 方法",
            "ocr_engine",
            tuple(label for _value, label in _WINDOWS_ENGINE_OPTIONS),
        )
        self._add_combo(
            ocr_tab,
            1,
            "本地 Paddle 档位",
            "ocr_local_advanced_model_tier",
            tuple(label for _value, label in LOCAL_ADVANCED_MODEL_TIER_OPTIONS),
        )
        self._add_entry(
            ocr_tab,
            2,
            "普通 OCR 密钥",
            "ocr_standard_api_key",
            secret=True,
        )
        self._add_entry(ocr_tab, 3, "高级 API 地址", "ocr_base_url")
        self._add_entry(ocr_tab, 4, "高级 API 密钥", "ocr_api_key", secret=True)
        self._ocr_model = self._add_combo(
            ocr_tab,
            5,
            "高级模型",
            "ocr_model",
            (),
            editable=True,
        )
        self._add_entry(ocr_tab, 6, "本机置信度", "ocr_min_confidence")
        self._add_combo(
            ocr_tab,
            7,
            "切图模式",
            "ocr_image_mode",
            tuple(label for _value, label in IMAGE_MODE_OPTIONS),
        )
        ttk.Label(
            ocr_tab,
            text="Windows 没有本地普通 OCR；安装 PaddleOCR 后，自动模式会先用本地高级，再进入 API 两层。",
            foreground="#9A3412",
            wraplength=500,
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(16, 0))

        self._add_combo(
            general_tab,
            0,
            "源语言",
            "source_lang",
            tuple(label for _value, label in SOURCE_LANG_OPTIONS),
        )
        self._add_combo(
            general_tab,
            1,
            "目标语言",
            "target_lang",
            tuple(label for _value, label in TARGET_LANG_OPTIONS),
        )
        self._add_entry(general_tab, 2, "划词热键", "hotkey_selection")
        self._add_entry(general_tab, 3, "截图热键", "hotkey_ocr")
        self._add_entry(general_tab, 4, "实时热键", "hotkey_live_ocr")
        ttk.Label(
            general_tab,
            text="格式示例：alt+e、ctrl+alt+w。三组热键不能相同。",
            foreground="#666666",
            wraplength=500,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(16, 0))

        status = ttk.Label(window, anchor="w", foreground="#B42318")
        status.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 6))
        buttons = ttk.Frame(window)
        buttons.grid(row=2, column=0, sticky="e", padx=16, pady=(0, 14))
        apply_button = ttk.Button(
            buttons,
            text="应用",
            command=lambda: self._commit(close=False),
        )
        apply_button.pack(side="left", padx=(0, 8))
        save_button = ttk.Button(
            buttons,
            text="保存",
            command=lambda: self._commit(close=True),
        )
        save_button.pack(side="left")
        self._window = window
        self._status = status
        self._apply_button = apply_button
        self._save_button = save_button

    def _add_entry(
        self,
        parent: object,
        row: int,
        label: str,
        name: str,
        *,
        secret: bool = False,
    ) -> object:
        import tkinter as tk
        from tkinter import ttk

        variable = tk.StringVar(master=self._runtime.root)
        self._vars[name] = variable
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        entry = ttk.Entry(parent, textvariable=variable, show="•" if secret else "")
        entry.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=6)
        return entry

    def _add_combo(
        self,
        parent: object,
        row: int,
        label: str,
        name: str,
        values: tuple[str, ...],
        *,
        editable: bool = False,
    ) -> object:
        import tkinter as tk
        from tkinter import ttk

        variable = tk.StringVar(master=self._runtime.root)
        self._vars[name] = variable
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        combo = ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            state="normal" if editable else "readonly",
        )
        combo.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=6)
        return combo

    def _fill(self, preferences: AppPreferences) -> None:
        provider_labels = dict(PROVIDER_OPTIONS)
        engine_labels = dict(_WINDOWS_ENGINE_OPTIONS)
        local_advanced_model_tier_labels = dict(LOCAL_ADVANCED_MODEL_TIER_OPTIONS)
        image_labels = dict(IMAGE_MODE_OPTIONS)
        source_labels = dict(SOURCE_LANG_OPTIONS)
        target_labels = dict(TARGET_LANG_OPTIONS)
        values = {
            "translate_provider": provider_labels.get(
                preferences.translate_provider,
                preferences.translate_provider,
            ),
            "translate_base_url": preferences.translate_base_url,
            "translate_api_key": preferences.translate_api_key,
            "translate_model": preferences.translate_model,
            "translate_region": preferences.translate_region,
            "ocr_engine": engine_labels.get(preferences.ocr_engine, engine_labels["auto"]),
            "ocr_local_advanced_model_tier": local_advanced_model_tier_labels.get(
                preferences.ocr_local_advanced_model_tier,
                preferences.ocr_local_advanced_model_tier,
            ),
            "ocr_base_url": preferences.ocr_base_url,
            "ocr_api_key": preferences.ocr_api_key,
            "ocr_standard_api_key": preferences.ocr_standard_api_key,
            "ocr_model": preferences.ocr_model,
            "ocr_min_confidence": f"{preferences.ocr_min_confidence:g}",
            "ocr_image_mode": image_labels.get(
                preferences.ocr_image_mode,
                preferences.ocr_image_mode,
            ),
            "source_lang": source_labels.get(preferences.source_lang, preferences.source_lang),
            "target_lang": target_labels.get(preferences.target_lang, preferences.target_lang),
            "hotkey_selection": preferences.hotkey_selection,
            "hotkey_ocr": preferences.hotkey_ocr,
            "hotkey_live_ocr": preferences.hotkey_live_ocr,
        }
        for name, value in values.items():
            self._vars[name].set(value)
        self._translate_model.configure(values=preferences.translate_model_choices)
        self._ocr_model.configure(values=preferences.ocr_model_choices)
        self._status.configure(text="")

    def _commit(self, *, close: bool) -> None:
        provider_values = {label: value for value, label in PROVIDER_OPTIONS}
        engine_values = {label: value for value, label in _WINDOWS_ENGINE_OPTIONS}
        local_advanced_model_tier_values = {
            label: value for value, label in LOCAL_ADVANCED_MODEL_TIER_OPTIONS
        }
        image_values = {label: value for value, label in IMAGE_MODE_OPTIONS}
        source_values = {label: value for value, label in SOURCE_LANG_OPTIONS}
        target_values = {label: value for value, label in TARGET_LANG_OPTIONS}

        def value(name: str) -> str:
            return str(self._vars[name].get())

        try:
            preferences = parse_settings_form(
                ocr_engine=engine_values.get(value("ocr_engine"), value("ocr_engine")),
                ocr_local_advanced_model_tier=local_advanced_model_tier_values.get(
                    value("ocr_local_advanced_model_tier"),
                    value("ocr_local_advanced_model_tier"),
                ),
                ocr_min_confidence=value("ocr_min_confidence"),
                ocr_image_mode=image_values.get(
                    value("ocr_image_mode"),
                    value("ocr_image_mode"),
                ),
                source_lang=source_values.get(value("source_lang"), value("source_lang")),
                target_lang=target_values.get(value("target_lang"), value("target_lang")),
                hotkey_selection=value("hotkey_selection"),
                hotkey_ocr=value("hotkey_ocr"),
                hotkey_live_ocr=value("hotkey_live_ocr"),
                translate_model=value("translate_model"),
                ocr_model=value("ocr_model"),
                translate_base_url=value("translate_base_url"),
                ocr_base_url=value("ocr_base_url"),
                translate_api_key=value("translate_api_key"),
                ocr_api_key=value("ocr_api_key"),
                ocr_standard_api_key=value("ocr_standard_api_key"),
                translate_provider=provider_values.get(
                    value("translate_provider"),
                    value("translate_provider"),
                ),
                translate_region=value("translate_region"),
            )
        except ValueError as exc:
            self._status.configure(text=str(exc))
            return
        self._set_busy(True)
        self._status.configure(text="正在保存…")

        def run() -> None:
            try:
                self._save(preferences)
            except Exception as exc:
                self._runtime.call_soon(lambda: self._saved(error=str(exc), close=False))
                return
            self._runtime.call_soon(lambda: self._saved(error=None, close=close))

        threading.Thread(target=run, daemon=True).start()

    def _saved(self, *, error: str | None, close: bool) -> None:
        self._set_busy(False)
        if error is not None:
            self._status.configure(text=f"保存失败：{error}")
            return
        self._status.configure(text="已应用")
        if close:
            self._window.withdraw()

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self._apply_button.configure(state=state)
        self._save_button.configure(state=state)


class WindowsInputTranslatePresenter:
    def __init__(
        self,
        runtime: WindowsUiRuntime,
        *,
        translate: Callable[[str], TranslateJob],
    ) -> None:
        self._runtime = runtime
        self._translate = translate
        self._window: object | None = None
        self._source: object | None = None
        self._result: object | None = None
        self._status: object | None = None
        self._button: object | None = None
        self._busy = False

    def show(self) -> None:
        self._runtime.call_soon(self._show_ui)

    def _show_ui(self) -> None:
        if self._window is None:
            self._create()
        self._window.deiconify()
        self._window.lift()
        self._window.focus_force()
        self._source.focus_set()

    def _create(self) -> None:
        import tkinter as tk
        from tkinter import ttk
        from tkinter.scrolledtext import ScrolledText

        window = tk.Toplevel(self._runtime.root)
        window.withdraw()
        window.title("输入翻译")
        window.geometry("600x520")
        window.minsize(460, 380)
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        window.rowconfigure(4, weight=1)
        ttk.Label(window, text="原文").grid(
            row=0,
            column=0,
            sticky="w",
            padx=14,
            pady=(12, 4),
        )
        source = ScrolledText(window, wrap="word", font=("Segoe UI", 11))
        source.grid(row=1, column=0, sticky="nsew", padx=14)
        button = ttk.Button(window, text="翻译", command=self._request_translate)
        button.grid(row=2, column=0, sticky="e", padx=14, pady=8)
        ttk.Label(window, text="译文").grid(row=3, column=0, sticky="w", padx=14)
        result = ScrolledText(window, wrap="word", font=("Segoe UI", 12))
        result.grid(row=4, column=0, sticky="nsew", padx=14, pady=(4, 6))
        result.configure(state="disabled")
        status = ttk.Label(window, anchor="w", foreground="#B42318")
        status.grid(row=5, column=0, sticky="ew", padx=14, pady=(0, 12))
        window.bind("<Control-Return>", lambda _event: self._request_translate())
        self._window = window
        self._source = source
        self._result = result
        self._status = status
        self._button = button

    def _request_translate(self) -> None:
        if self._busy:
            self._status.configure(text="正在翻译，请稍后再试。")
            return
        text = str(self._source.get("1.0", "end-1c"))
        self._busy = True
        self._button.configure(state="disabled")
        self._status.configure(text="翻译中…")
        _replace_result(self._result, "")

        def run() -> None:
            try:
                job = self._translate(text)
            except Exception as exc:
                job = TranslateJob(
                    kind=JobKind.SELECTION,
                    status=JobStatus.FAILURE,
                    source_text=text,
                    translated_text=None,
                    error=str(exc),
                )
            self._runtime.call_soon(lambda: self._show_result(job))

        threading.Thread(target=run, daemon=True).start()

    def _show_result(self, job: TranslateJob) -> None:
        self._busy = False
        self._button.configure(state="normal")
        _replace_result(self._result, format_input_translation(job))
        self._status.configure(
            text="请输入要翻译的文字。" if job.error == "empty_text" else ""
        )


def windows_settings_engine_options() -> tuple[tuple[str, str], ...]:
    return _WINDOWS_ENGINE_OPTIONS


def windows_settings_model_tier_options() -> tuple[tuple[str, str], ...]:
    return LOCAL_ADVANCED_MODEL_TIER_OPTIONS


def _replace_result(widget: object, value: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value)
    widget.configure(state="disabled")
