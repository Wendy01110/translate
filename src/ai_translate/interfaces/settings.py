from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

from ai_translate.config import (
    OCR_ENGINES,
    OCR_IMAGE_MODES,
    TRANSLATE_PROVIDERS,
    AppPreferences,
    normalize_api_base_url,
)
from ai_translate.core.hotkeys import (
    format_hotkey_spec,
    hotkey_button_title,
    interpret_hotkey_press,
    parse_hotkey,
)

PROVIDER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("google_web", "Google（内置）"),
    ("bing_web", "Bing（内置）"),
    ("deepl_web", "DeepL（内置）"),
    ("openai", "OpenAI 兼容"),
    ("deepl", "DeepL 官方"),
    ("microsoft", "Microsoft 官方"),
    ("google", "Google 官方"),
)
ENGINE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("auto", "自动（本机优先）"),
    ("vision", "只本机 Vision"),
    ("model", "只 OCR 模型"),
)
IMAGE_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("auto", "自动"),
    ("tiny", "tiny"),
    ("small", "small"),
    ("base", "base"),
    ("large", "large"),
    ("gundam", "gundam"),
)
SOURCE_LANG_OPTIONS: tuple[tuple[str, str], ...] = (
    ("auto", "自动"),
    ("en", "英语"),
    ("zh", "中文"),
    ("ja", "日语"),
    ("ko", "韩语"),
)
TARGET_LANG_OPTIONS: tuple[tuple[str, str], ...] = (
    ("zh", "中文"),
    ("en", "英语"),
    ("ja", "日语"),
    ("ko", "韩语"),
)


@dataclass(frozen=True)
class ProviderForm:
    needs_url: bool
    needs_key: bool
    needs_region: bool
    needs_model: bool
    hint: str

    @property
    def extra_rows(self) -> int:
        return (
            int(self.needs_url)
            + int(self.needs_key)
            + int(self.needs_region)
            + int(self.needs_model)
        )


def provider_form(provider: str) -> ProviderForm:
    if provider in {"google_web", "bing_web", "deepl_web"}:
        return ProviderForm(
            False,
            False,
            False,
            False,
            "内置网页源，不需要密钥。对方可能会限制访问。",
        )
    if provider == "openai":
        return ProviderForm(
            True,
            True,
            False,
            True,
            "需要 API 地址和模型名。本地网关的密钥可留空。",
        )
    if provider == "deepl":
        return ProviderForm(False, True, False, False, "DeepL 官方 API，需要密钥。")
    if provider == "microsoft":
        return ProviderForm(
            False,
            True,
            True,
            False,
            "Microsoft 官方 API，需要密钥和区域（例如 eastus）。",
        )
    if provider == "google":
        return ProviderForm(False, True, False, False, "Google Cloud Translation，需要密钥。")
    return ProviderForm(True, True, False, True, "翻译来源不支持。")


SETTINGS_ALWAYS_ROWS = 11


def settings_window_height(*, extra_rows: int) -> float:
    return 46.0 + 32.0 + 40.0 + extra_rows * 40.0 + SETTINGS_ALWAYS_ROWS * 40.0 + 108.0


def parse_settings_form(
    *,
    ocr_engine: str,
    ocr_min_confidence: str,
    ocr_image_mode: str,
    source_lang: str,
    target_lang: str,
    hotkey_selection: str,
    hotkey_ocr: str,
    hotkey_live_ocr: str,
    translate_model: str,
    ocr_model: str,
    translate_base_url: str,
    ocr_base_url: str,
    translate_api_key: str,
    ocr_api_key: str,
    translate_provider: str,
    translate_region: str,
) -> AppPreferences:
    engine = ocr_engine.strip().lower()
    if engine not in OCR_ENGINES:
        raise ValueError("OCR 方法必须是 auto、vision 或 model")
    try:
        confidence = float(ocr_min_confidence.strip())
    except ValueError as exc:
        raise ValueError("本机置信度必须是 0 到 1 之间的数字") from exc
    if confidence < 0 or confidence > 1:
        raise ValueError("本机置信度必须是 0 到 1 之间的数字")
    mode = ocr_image_mode.strip().lower() or "auto"
    if mode != "auto" and mode not in OCR_IMAGE_MODES:
        raise ValueError("切图模式不支持")
    source = source_lang.strip().lower() or "auto"
    target = target_lang.strip().lower() or "zh"
    translate = translate_model.strip()
    ocr = ocr_model.strip()
    translate_url = normalize_api_base_url(translate_base_url, side="翻译")
    ocr_url = normalize_api_base_url(ocr_base_url, side="OCR")
    translate_key = translate_api_key.strip()
    ocr_key = ocr_api_key.strip()
    provider = translate_provider.strip().lower() or "google_web"
    if provider not in TRANSLATE_PROVIDERS:
        raise ValueError("翻译来源不支持")
    region = translate_region.strip()
    if any(ch.isspace() for ch in region):
        raise ValueError("Microsoft 区域不能包含空白")
    if provider == "microsoft" and not region:
        raise ValueError("Microsoft 需要填写区域，例如 eastus")
    selection = format_hotkey_spec(parse_hotkey(hotkey_selection.strip().lower()))
    ocr_hotkey = format_hotkey_spec(parse_hotkey(hotkey_ocr.strip().lower()))
    live_hotkey = format_hotkey_spec(parse_hotkey(hotkey_live_ocr.strip().lower()))
    parsed = {parse_hotkey(selection), parse_hotkey(ocr_hotkey), parse_hotkey(live_hotkey)}
    if len(parsed) != 3:
        raise ValueError("划词、OCR 和实时翻译热键不能相同")
    return AppPreferences(
        ocr_engine=engine,
        ocr_min_confidence=confidence,
        ocr_image_mode=mode,
        source_lang=source,
        target_lang=target,
        hotkey_selection=selection,
        hotkey_ocr=ocr_hotkey,
        hotkey_live_ocr=live_hotkey,
        translate_model=translate,
        ocr_model=ocr,
        translate_base_url=translate_url,
        ocr_base_url=ocr_url,
        translate_api_key=translate_key,
        ocr_api_key=ocr_key,
        translate_provider=provider,
        translate_region=region,
    )


def fallback_preferences() -> AppPreferences:
    return AppPreferences(
        ocr_engine="auto",
        ocr_min_confidence=0.5,
        ocr_image_mode="auto",
        source_lang="auto",
        target_lang="zh",
        hotkey_selection="alt+e",
        hotkey_ocr="alt+w",
        hotkey_live_ocr="alt+q",
        translate_model="",
        ocr_model="Unlimited-OCR",
        translate_base_url="",
        ocr_base_url="",
        translate_api_key="",
        ocr_api_key="",
        translate_provider="google_web",
        translate_region="",
    )


class SettingsPresenter:
    def __init__(
        self,
        *,
        load: Callable[[], AppPreferences],
        save: Callable[[AppPreferences], None],
    ) -> None:
        self._load = load
        self._save = save
        self._window: _SettingsWindow | None = None

    def show(self) -> None:
        if self._window is None:
            self._window = _SettingsWindow(load=self._load, save=self._save)
        self._window.show()


class _SettingsWindow:
    def __init__(
        self,
        *,
        load: Callable[[], AppPreferences],
        save: Callable[[AppPreferences], None],
    ) -> None:
        from AppKit import (
            NSBackingStoreBuffered,
            NSButton,
            NSMakeRect,
            NSPopUpButton,
            NSTextField,
            NSWindow,
            NSWindowStyleMaskClosable,
            NSWindowStyleMaskTitled,
        )

        self._load = load
        self._save_prefs = save
        self._recording: str | None = None
        self._monitor = None
        self._monitor_handler = None
        self._hotkey_selection_spec = "alt+e"
        self._hotkey_ocr_spec = "alt+w"
        self._hotkey_live_ocr_spec = "alt+q"
        self._width = 480.0
        height = settings_window_height(extra_rows=4)
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0.0, 0.0, self._width, height),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            False,
        )
        window.setTitle_("设置")
        _prepare_settings_window(window)
        content = window.contentView()
        if content is None:
            raise RuntimeError("settings window has no content view")

        controller = _settings_controller_class().alloc().init()
        controller.owner = self
        y = height - 46
        self._translate_provider, self._provider_label = self._popup(
            content,
            "翻译来源",
            PROVIDER_OPTIONS,
            16,
            y,
        )
        self._translate_provider.setTarget_(controller)
        self._translate_provider.setAction_("providerChanged:")
        y -= 36
        self._hint = NSTextField.alloc().initWithFrame_(NSMakeRect(16, y, 448, 28))
        self._hint.setBezeled_(False)
        self._hint.setDrawsBackground_(False)
        self._hint.setEditable_(False)
        self._hint.setSelectable_(False)
        content.addSubview_(self._hint)
        y -= 40
        self._translate_base_url, self._url_label = self._field(
            content, "翻译 API", 16, y
        )
        y -= 40
        self._translate_api_key, self._key_label = self._secure_field(
            content, "翻译密钥", 16, y
        )
        y -= 40
        self._translate_region, self._region_label = self._field(
            content, "翻译区域", 16, y
        )
        y -= 40
        self._translate_model, self._model_label = self._combo(
            content, "翻译模型", 16, y
        )
        y -= 40
        self._ocr_base_url, self._ocr_url_label = self._field(content, "OCR API", 16, y)
        y -= 40
        self._ocr_api_key, self._ocr_key_label = self._secure_field(
            content, "OCR 密钥", 16, y
        )
        y -= 40
        self._ocr_model, self._ocr_model_label = self._combo(content, "OCR 模型", 16, y)
        y -= 40
        self._engine, self._engine_label = self._popup(
            content,
            "OCR 方法",
            ENGINE_OPTIONS,
            16,
            y,
        )
        y -= 40
        self._confidence, self._confidence_label = self._field(
            content, "本机置信度", 16, y
        )
        y -= 40
        self._image_mode, self._image_mode_label = self._popup(
            content, "切图模式", IMAGE_MODE_OPTIONS, 16, y
        )
        y -= 40
        self._source_lang, self._source_label = self._popup(
            content, "源语言", SOURCE_LANG_OPTIONS, 16, y
        )
        y -= 40
        self._target_lang, self._target_label = self._popup(
            content, "目标语言", TARGET_LANG_OPTIONS, 16, y
        )
        y -= 40
        self._hotkey_selection, self._selection_label = self._hotkey_button(
            content,
            "划词热键",
            16,
            y,
            "recordSelectionHotkey:",
            controller,
        )
        y -= 40
        self._hotkey_ocr, self._ocr_hotkey_label = self._hotkey_button(
            content,
            "OCR 热键",
            16,
            y,
            "recordOcrHotkey:",
            controller,
        )
        y -= 40
        self._hotkey_live, self._live_hotkey_label = self._hotkey_button(
            content,
            "实时热键",
            16,
            y,
            "recordLiveHotkey:",
            controller,
        )
        self._status = NSTextField.alloc().initWithFrame_(NSMakeRect(16, 56, 448, 36))
        self._status.setBezeled_(False)
        self._status.setDrawsBackground_(False)
        self._status.setEditable_(False)
        self._status.setSelectable_(False)
        content.addSubview_(self._status)
        apply = NSButton.alloc().initWithFrame_(NSMakeRect(174, 16, 90, 28))
        apply.setTitle_("应用")
        apply.setBezelStyle_(1)
        apply.setTarget_(controller)
        apply.setAction_("applySettings:")
        save = NSButton.alloc().initWithFrame_(NSMakeRect(272, 16, 90, 28))
        save.setTitle_("保存")
        save.setBezelStyle_(1)
        save.setTarget_(controller)
        save.setAction_("saveSettings:")
        cancel = NSButton.alloc().initWithFrame_(NSMakeRect(370, 16, 90, 28))
        cancel.setTitle_("取消")
        cancel.setBezelStyle_(1)
        cancel.setTarget_(controller)
        cancel.setAction_("cancelSettings:")
        content.addSubview_(apply)
        content.addSubview_(save)
        content.addSubview_(cancel)
        self._window = window
        self._controller = controller
        self._NSPopUpButton = NSPopUpButton
        self._NSTextField = NSTextField
        self._NSMakeRect = NSMakeRect
        self.apply_provider_layout()

    def show(self) -> None:
        from AppKit import NSApp, NSApplicationActivationPolicyRegular

        try:
            prefs = self._load()
        except Exception as exc:
            print(f"settings load failed: {exc}", file=sys.stderr)
            prefs = fallback_preferences()
            self._status.setStringValue_("配置读取失败，已显示默认值。")
        else:
            self._status.setStringValue_("")
        self._fill(prefs)
        visible = bool(self._window.isVisible())
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        unhide = getattr(NSApp, "unhide_", None)
        if callable(unhide):
            unhide(None)
        NSApp.activateIgnoringOtherApps_(True)
        if should_center_settings(visible=visible):
            self._window.center()
        self._window.makeKeyAndOrderFront_(None)
        self._window.orderFrontRegardless()
        make_main = getattr(self._window, "makeMainWindow", None)
        if callable(make_main):
            make_main()

    def close(self) -> None:
        from AppKit import NSApp

        self._cancel_hotkey_record()
        self._window.orderOut_(None)
        NSApp.setActivationPolicy_(1)

    def apply(self) -> bool:
        self._cancel_hotkey_record()
        try:
            prefs = parse_settings_form(
                ocr_engine=_selected_value(self._engine, ENGINE_OPTIONS),
                ocr_min_confidence=self._confidence.stringValue(),
                ocr_image_mode=_selected_value(self._image_mode, IMAGE_MODE_OPTIONS),
                source_lang=_selected_value(self._source_lang, SOURCE_LANG_OPTIONS),
                target_lang=_selected_value(self._target_lang, TARGET_LANG_OPTIONS),
                hotkey_selection=self._hotkey_selection_spec,
                hotkey_ocr=self._hotkey_ocr_spec,
                hotkey_live_ocr=self._hotkey_live_ocr_spec,
                translate_model=self._translate_model.stringValue(),
                ocr_model=self._ocr_model.stringValue(),
                translate_base_url=self._translate_base_url.stringValue(),
                ocr_base_url=self._ocr_base_url.stringValue(),
                translate_api_key=self._translate_api_key.stringValue(),
                ocr_api_key=self._ocr_api_key.stringValue(),
                translate_provider=_selected_value(
                    self._translate_provider,
                    PROVIDER_OPTIONS,
                ),
                translate_region=self._translate_region.stringValue(),
            )
            self._save_prefs(prefs)
        except ValueError as exc:
            self._status.setStringValue_(str(exc))
            return False
        self._status.setStringValue_("已应用")
        return True

    def save(self) -> None:
        if self.apply() and should_close_settings_after_commit("save"):
            self.close()

    def begin_hotkey_record(self, which: str) -> None:
        if self._recording == which:
            self._cancel_hotkey_record()
            return
        self._stop_hotkey_monitor()
        self._recording = which
        self._sync_hotkey_buttons()
        self._status.setStringValue_("按下快捷键，Esc 取消")
        self._install_hotkey_monitor()

    def _fill(self, prefs: AppPreferences) -> None:
        self._cancel_hotkey_record()
        _select_value(
            self._translate_provider,
            PROVIDER_OPTIONS,
            prefs.translate_provider,
        )
        self._translate_base_url.setStringValue_(prefs.translate_base_url)
        self._translate_api_key.setStringValue_(prefs.translate_api_key)
        self._translate_region.setStringValue_(prefs.translate_region)
        _fill_combo(
            self._translate_model,
            prefs.translate_model_choices,
            prefs.translate_model,
        )
        self._ocr_base_url.setStringValue_(prefs.ocr_base_url)
        self._ocr_api_key.setStringValue_(prefs.ocr_api_key)
        _fill_combo(self._ocr_model, prefs.ocr_model_choices, prefs.ocr_model)
        _select_value(self._engine, ENGINE_OPTIONS, prefs.ocr_engine)
        self._confidence.setStringValue_(f"{prefs.ocr_min_confidence:g}")
        _select_value(self._image_mode, IMAGE_MODE_OPTIONS, prefs.ocr_image_mode)
        _select_value(self._source_lang, SOURCE_LANG_OPTIONS, prefs.source_lang)
        _select_value(self._target_lang, TARGET_LANG_OPTIONS, prefs.target_lang)
        self._hotkey_selection_spec = prefs.hotkey_selection
        self._hotkey_ocr_spec = prefs.hotkey_ocr
        self._hotkey_live_ocr_spec = prefs.hotkey_live_ocr
        self._sync_hotkey_buttons()
        self.apply_provider_layout()

    def apply_provider_layout(self) -> None:
        from AppKit import NSMakeRect

        provider = _selected_value(self._translate_provider, PROVIDER_OPTIONS)
        form = provider_form(provider)
        height = settings_window_height(extra_rows=form.extra_rows)
        self._window.setContentSize_((self._width, height))
        self._hint.setStringValue_(form.hint)
        y = height - 46.0
        self._place(self._provider_label, self._translate_provider, y)
        y -= 36.0
        self._hint.setHidden_(False)
        self._hint.setFrame_(NSMakeRect(16.0, y, 448.0, 28.0))
        y -= 32.0
        optional = (
            (self._url_label, self._translate_base_url, form.needs_url),
            (self._key_label, self._translate_api_key, form.needs_key),
            (self._region_label, self._translate_region, form.needs_region),
            (self._model_label, self._translate_model, form.needs_model),
        )
        for label, control, show in optional:
            label.setHidden_(not show)
            control.setHidden_(not show)
            if show:
                self._place(label, control, y)
                y -= 40.0
        always = (
            (self._ocr_url_label, self._ocr_base_url),
            (self._ocr_key_label, self._ocr_api_key),
            (self._ocr_model_label, self._ocr_model),
            (self._engine_label, self._engine),
            (self._confidence_label, self._confidence),
            (self._image_mode_label, self._image_mode),
            (self._source_label, self._source_lang),
            (self._target_label, self._target_lang),
            (self._selection_label, self._hotkey_selection),
            (self._ocr_hotkey_label, self._hotkey_ocr),
            (self._live_hotkey_label, self._hotkey_live),
        )
        for label, control in always:
            self._place(label, control, y)
            y -= 40.0

    def _place(self, label, control, y: float) -> None:
        from AppKit import NSMakeRect

        label.setFrame_(NSMakeRect(16.0, y + 4.0, 100.0, 18.0))
        control.setFrame_(NSMakeRect(126.0, y, 340.0, 26.0))

    def _popup(self, parent, title: str, options: tuple[tuple[str, str], ...], x: float, y: float):
        from AppKit import NSMakeRect, NSPopUpButton

        label = self._label(parent, title, x, y + 4)
        popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(x + 110, y, 340, 26),
            False,
        )
        popup.addItemsWithTitles_([item for _value, item in options])
        parent.addSubview_(popup)
        return popup, label

    def _field(self, parent, title: str, x: float, y: float):
        from AppKit import NSMakeRect, NSTextField

        label = self._label(parent, title, x, y + 4)
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(x + 110, y, 340, 24))
        parent.addSubview_(field)
        return field, label

    def _secure_field(self, parent, title: str, x: float, y: float):
        from AppKit import NSMakeRect, NSSecureTextField

        label = self._label(parent, title, x, y + 4)
        field = NSSecureTextField.alloc().initWithFrame_(NSMakeRect(x + 110, y, 340, 24))
        parent.addSubview_(field)
        return field, label

    def _combo(self, parent, title: str, x: float, y: float):
        from AppKit import NSComboBox, NSMakeRect

        label = self._label(parent, title, x, y + 4)
        combo = NSComboBox.alloc().initWithFrame_(NSMakeRect(x + 110, y, 340, 26))
        combo.setCompletes_(True)
        parent.addSubview_(combo)
        return combo, label

    def _hotkey_button(self, parent, title: str, x: float, y: float, action: str, controller):
        from AppKit import NSButton, NSMakeRect

        label = self._label(parent, title, x, y + 4)
        button = NSButton.alloc().initWithFrame_(NSMakeRect(x + 110, y, 340, 26))
        button.setBezelStyle_(1)
        button.setTarget_(controller)
        button.setAction_(action)
        parent.addSubview_(button)
        return button, label

    def _sync_hotkey_buttons(self) -> None:
        self._hotkey_selection.setTitle_(
            hotkey_button_title(
                self._hotkey_selection_spec,
                recording=self._recording == "selection",
            )
        )
        self._hotkey_ocr.setTitle_(
            hotkey_button_title(
                self._hotkey_ocr_spec,
                recording=self._recording == "ocr",
            )
        )
        self._hotkey_live.setTitle_(
            hotkey_button_title(
                self._hotkey_live_ocr_spec,
                recording=self._recording == "live",
            )
        )

    def _install_hotkey_monitor(self) -> None:
        from AppKit import NSEvent, NSEventMaskKeyDown

        def handler(event):
            return self._handle_hotkey_event(event)

        self._monitor_handler = handler
        self._monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown,
            handler,
        )

    def _handle_hotkey_event(self, event):
        result = interpret_hotkey_press(
            key_code=int(event.keyCode()),
            modifier_flags=int(event.modifierFlags()),
        )
        if result.kind == "ignore":
            return None
        if result.kind == "cancel":
            self._cancel_hotkey_record()
            return None
        if result.kind == "invalid":
            self._status.setStringValue_(result.error or "快捷键无效")
            return None
        if result.spec:
            self._apply_recorded_hotkey(result.spec)
        return None

    def _apply_recorded_hotkey(self, spec: str) -> None:
        current = {
            "selection": self._hotkey_selection_spec,
            "ocr": self._hotkey_ocr_spec,
            "live": self._hotkey_live_ocr_spec,
        }
        others = [
            parse_hotkey(value)
            for key, value in current.items()
            if key != self._recording
        ]
        if parse_hotkey(spec) in others:
            self._status.setStringValue_("划词、OCR 和实时翻译热键不能相同")
            return
        if self._recording == "selection":
            self._hotkey_selection_spec = spec
        elif self._recording == "ocr":
            self._hotkey_ocr_spec = spec
        elif self._recording == "live":
            self._hotkey_live_ocr_spec = spec
        self._stop_hotkey_monitor()
        self._recording = None
        self._sync_hotkey_buttons()
        self._status.setStringValue_("")

    def _cancel_hotkey_record(self) -> None:
        self._stop_hotkey_monitor()
        if self._recording is None:
            return
        self._recording = None
        self._sync_hotkey_buttons()
        self._status.setStringValue_("")

    def _stop_hotkey_monitor(self) -> None:
        from AppKit import NSEvent

        if self._monitor is not None:
            NSEvent.removeMonitor_(self._monitor)
        self._monitor = None
        self._monitor_handler = None

    def _label(self, parent, title: str, x: float, y: float):
        from AppKit import NSMakeRect, NSTextField

        label = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, 100, 18))
        label.setStringValue_(title)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        parent.addSubview_(label)
        return label


def should_center_settings(*, visible: bool) -> bool:
    return not visible


def should_close_settings_after_commit(action: str) -> bool:
    if action == "apply":
        return False
    if action == "save":
        return True
    raise ValueError("settings commit action must be apply or save")


def _fill_combo(combo, choices: tuple[str, ...], current: str) -> None:
    combo.removeAllItems()
    values = list(choices)
    if current and current not in values:
        values.insert(0, current)
    if values:
        combo.addItemsWithObjectValues_(values)
    combo.setStringValue_(current)


def _settings_controller_class() -> type:
    global _SettingsController
    if _SettingsController is not None:
        return _SettingsController
    from Foundation import NSObject

    class AITranslateSettingsController(NSObject):
        def applySettings_(self, _sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.apply()

        def saveSettings_(self, _sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.save()

        def cancelSettings_(self, _sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.close()

        def recordSelectionHotkey_(self, _sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.begin_hotkey_record("selection")

        def recordOcrHotkey_(self, _sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.begin_hotkey_record("ocr")

        def recordLiveHotkey_(self, _sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.begin_hotkey_record("live")

        def providerChanged_(self, _sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.apply_provider_layout()

    _SettingsController = AITranslateSettingsController
    return AITranslateSettingsController


_SettingsController = None


def _prepare_settings_window(window: object) -> None:
    from AppKit import (
        NSFloatingWindowLevel,
        NSWindowCollectionBehaviorMoveToActiveSpace,
    )

    window.setLevel_(NSFloatingWindowLevel)
    window.setReleasedWhenClosed_(False)
    window.setHidesOnDeactivate_(False)
    set_floating = getattr(window, "setFloatingPanel_", None)
    if callable(set_floating):
        set_floating(True)
    window.setCollectionBehavior_(NSWindowCollectionBehaviorMoveToActiveSpace)


def _selected_value(popup, options: tuple[tuple[str, str], ...]) -> str:
    index = int(popup.indexOfSelectedItem())
    if index < 0 or index >= len(options):
        return options[0][0]
    return options[index][0]


def _select_value(popup, options: tuple[tuple[str, str], ...], value: str) -> None:
    keys = [item[0] for item in options]
    if value not in keys:
        popup.addItemWithTitle_(value)
        popup.selectItemAtIndex_(len(keys))
        return
    popup.selectItemAtIndex_(keys.index(value))
