from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from ai_translate.core.models import JobKind, JobStatus, TranslateJob


@dataclass(frozen=True)
class OverlayContent:
    title: str
    source: str
    translation: str
    footnote: str
    source_editable: bool = False


OVERLAY_SOURCE_LABEL = "原文"
OVERLAY_RESULT_LABEL = "译文"
OVERLAY_COPY_BUTTON_TOOLTIP = "复制译文"
OVERLAY_COPY_SUCCESS_TOOLTIP = "已复制"
OVERLAY_COPY_SYMBOL_NAME = "doc.on.doc"
OVERLAY_COPY_SUCCESS_SYMBOL_NAME = "checkmark"
OVERLAY_TRANSLATE_BUTTON_TITLE = "翻译"
OVERLAY_TRANSLATING_BUTTON_TITLE = "翻译中…"
OVERLAY_TRANSLATE_BUTTON_TOOLTIP = "翻译原文（⌘↵）"
OVERLAY_TARGET_LANGUAGE_LABEL = "目标语言"
OVERLAY_TARGET_LANGUAGE_TOOLTIP = "切换本次运行的目标语言"

_OVERLAY_DEFAULT_WIDTH = 720.0
_OVERLAY_DEFAULT_HEIGHT = 520.0
_OVERLAY_MIN_WIDTH = 440.0
_OVERLAY_MIN_HEIGHT = 480.0
_OVERLAY_WIDE_BREAKPOINT = 640.0
_OVERLAY_COPY_FEEDBACK_SECONDS = 1.2


_ERROR_TEXT = {
    "accessibility_required": (
        "未开启辅助功能，无法读取选区。\n"
        "请打开：系统设置 → 隐私与安全性 → 辅助功能 → AI Translate。"
    ),
    "empty_text": "没有读到选中的文字。请先选中，或先复制后再按热键。",
    "copy_simulation_failed": "无法模拟复制。请先手动复制后再按热键。",
    "clipboard_read_failed": "无法读取剪贴板。",
    "clipboard_write_failed": "无法写入剪贴板。",
    "selection_too_long": "选中的文字太长。",
    "text_too_long": "文字太长。",
    "busy": "正在翻译，请稍后再试。",
    "unsupported_language": "当前翻译源不支持这个语言。",
    "http_403": "网页翻译被拒绝，可稍后再试或改用官方密钥源。",
    "http_429": "翻译请求太频繁，请稍后再试。",
    "translate_not_configured": "翻译模型未配置。",
    "screenshot_cancelled": "已取消圈选。",
    "region_too_small": "圈选区域太小。",
    "screenshot_failed": "无法截取该区域。",
    "empty_ocr_text": "没有识别到文字。",
    "ocr_not_configured": "OCR 尚未配置。",
    "vision_unavailable": "本地普通 Vision OCR 在当前系统不可用。",
    "paddle_unavailable": "本地高级 PaddleOCR 尚未安装。",
    "paddle_ocr_not_installed": "本地高级 PaddleOCR 尚未安装。",
    "paddle_ocr_init_failed": "本地高级 PaddleOCR 初始化失败。",
    "paddle_ocr_failed": "本地高级 PaddleOCR 识别失败。",
    "local_ocr_unavailable": "本地 OCR 当前不可用。",
    "ocr_standard_not_configured": "普通 OCR.space 尚未配置。",
    "ocr_standard_multi_page_unsupported": "API 普通 OCR 只支持单张图片，请改用本地或 API 高级 OCR。",
    "ocr_standard_image_too_large": "图片超过 API 普通 OCR 的 1 MB 上限，请改用本地或 API 高级 OCR。",
    "ocr_standard_image_type_unsupported": "API 普通 OCR 不支持这种图片格式，请改用本地或 API 高级 OCR。",
}


def format_overlay(job: TranslateJob) -> OverlayContent:
    title = "OCR" if job.kind is JobKind.OCR else "划词"
    if job.error == "accessibility_required":
        title = "需要权限"
    elif job.status is JobStatus.FAILURE:
        title = f"{title}失败"
    source = job.source_text or job.ocr_text or ""
    translation = job.translated_text or ""
    if job.status is JobStatus.FAILURE and job.error:
        translation = _ERROR_TEXT.get(job.error, job.error)
    elif job.status is JobStatus.PARTIAL and job.error and not translation:
        translation = _ERROR_TEXT.get(job.error, job.error)
    footnote = _footnote(job)
    return OverlayContent(
        title=title,
        source=source,
        translation=translation,
        footnote=footnote,
        source_editable=job.kind is JobKind.SELECTION,
    )


def format_translation_workspace(job: TranslateJob | None = None) -> OverlayContent:
    if job is None:
        return OverlayContent(
            title="翻译",
            source="",
            translation="",
            footnote="",
            source_editable=True,
        )
    content = format_overlay(job)
    return OverlayContent(
        title="翻译",
        source=content.source,
        translation=content.translation,
        footnote=content.footnote,
        source_editable=True,
    )


def format_macos_translation(job: TranslateJob | None = None) -> OverlayContent:
    return format_translation_workspace(job)


def format_status(message: str, source: str = "") -> OverlayContent:
    return OverlayContent(title="翻译", source=source, translation=message, footnote="")


def paddle_first_load_message(model: str) -> str:
    return (
        f"正在首次加载本地 OCR 模型 {model}。"
        "若本机尚无缓存，将自动下载，可能需要一些时间；后续识别通常会更快。"
    )


def should_center_overlay(*, created: bool) -> bool:
    return created


def should_focus_overlay(*, visible: bool) -> bool:
    return not visible


def overlay_pin_button_title(*, pinned: bool) -> str:
    return "取消置顶" if pinned else "置顶"


def overlay_pin_symbol_name(*, pinned: bool) -> str:
    return "pin.fill" if pinned else "pin"


def overlay_copy_button_title(*, copied: bool) -> str:
    return OVERLAY_COPY_SUCCESS_TOOLTIP if copied else OVERLAY_COPY_BUTTON_TOOLTIP


def overlay_copy_symbol_name(*, copied: bool) -> str:
    return OVERLAY_COPY_SUCCESS_SYMBOL_NAME if copied else OVERLAY_COPY_SYMBOL_NAME


def normalize_target_language_options(
    options: tuple[tuple[str, str], ...],
    current: str,
) -> tuple[tuple[str, str], ...]:
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_code, raw_label in options:
        code = raw_code.strip().lower()
        if not code or code in seen:
            continue
        label = raw_label.strip() or code
        normalized.append((code, label))
        seen.add(code)
    selected = current.strip().lower()
    if selected and selected not in seen:
        normalized.append((selected, selected))
    if not normalized:
        raise ValueError("at least one target language is required")
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class OverlayFrame:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y + self.height


@dataclass(frozen=True, slots=True)
class OverlayWindowLayout:
    mode: str
    helper: OverlayFrame
    target_language_label: OverlayFrame
    target_language_popup: OverlayFrame
    source_label: OverlayFrame
    source_editor: OverlayFrame
    result_label: OverlayFrame
    result_editor: OverlayFrame
    translate_button: OverlayFrame
    pin_button: OverlayFrame
    copy_button: OverlayFrame


def overlay_window_layout(width: float, height: float) -> OverlayWindowLayout:
    """Return AppKit frames for the wide and compact result-overlay layouts."""

    if width <= 0.0 or height <= 0.0:
        raise ValueError("overlay window dimensions must be positive")

    wide = width >= _OVERLAY_WIDE_BREAKPOINT
    margin = 28.0 if wide else 24.0
    button_size = 32.0
    button_gap = 8.0
    translate_button_width = 72.0
    button_y = height - 64.0
    copy_button = OverlayFrame(
        width - margin - button_size,
        button_y,
        button_size,
        button_size,
    )
    pin_button = OverlayFrame(
        copy_button.x - button_gap - button_size,
        button_y,
        button_size,
        button_size,
    )
    translate_button = OverlayFrame(
        pin_button.x - button_gap - translate_button_width,
        button_y,
        translate_button_width,
        button_size,
    )
    target_popup_width = 120.0 if wide else 104.0
    target_label_width = 64.0 if wide else 60.0
    target_gap = 8.0
    target_language_label = OverlayFrame(
        margin,
        button_y + 7.0,
        target_label_width,
        18.0,
    )
    target_language_popup = OverlayFrame(
        target_language_label.right + target_gap,
        button_y + 2.0,
        target_popup_width,
        28.0,
    )
    helper_x = target_language_popup.right + 12.0
    helper = OverlayFrame(
        helper_x,
        button_y + 7.0,
        max(0.0, translate_button.x - helper_x - 12.0),
        18.0,
    )
    label_top = height - 80.0
    editor_top = label_top - 26.0
    editor_bottom = margin
    label_height = 18.0
    label_gap = 8.0

    if wide:
        column_gap = 20.0
        editor_width = (width - (margin * 2.0) - column_gap) / 2.0
        editor_height = max(80.0, editor_top - editor_bottom)
        source_editor = OverlayFrame(
            margin,
            editor_bottom,
            editor_width,
            editor_height,
        )
        result_editor = OverlayFrame(
            margin + editor_width + column_gap,
            editor_bottom,
            editor_width,
            editor_height,
        )
        source_label = OverlayFrame(
            source_editor.x,
            source_editor.top + label_gap,
            source_editor.width,
            label_height,
        )
        result_label = OverlayFrame(
            result_editor.x,
            result_editor.top + label_gap,
            result_editor.width,
            label_height,
        )
        mode = "wide"
    else:
        block_gap = 16.0
        content_width = width - (margin * 2.0)
        editor_height = max(
            72.0,
            (
                label_top
                - editor_bottom
                - (label_height * 2.0)
                - (label_gap * 2.0)
                - block_gap
            )
            / 2.0,
        )
        result_editor = OverlayFrame(
            margin,
            editor_bottom,
            content_width,
            editor_height,
        )
        result_label = OverlayFrame(
            margin,
            result_editor.top + label_gap,
            content_width,
            label_height,
        )
        source_editor = OverlayFrame(
            margin,
            result_label.top + block_gap,
            content_width,
            editor_height,
        )
        source_label = OverlayFrame(
            margin,
            source_editor.top + label_gap,
            content_width,
            label_height,
        )
        mode = "compact"

    return OverlayWindowLayout(
        mode=mode,
        helper=helper,
        target_language_label=target_language_label,
        target_language_popup=target_language_popup,
        source_label=source_label,
        source_editor=source_editor,
        result_label=result_label,
        result_editor=result_editor,
        translate_button=translate_button,
        pin_button=pin_button,
        copy_button=copy_button,
    )


def overlay_window_origin_for_point(
    *,
    window_width: float,
    window_height: float,
    screens: tuple[OverlayFrame, ...],
    point: tuple[float, float],
) -> tuple[float, float]:
    if not screens:
        raise ValueError("at least one screen is required")
    point_x, point_y = point
    screen = next(
        (
            candidate
            for candidate in screens
            if candidate.x <= point_x < candidate.right
            and candidate.y <= point_y < candidate.top
        ),
        screens[0],
    )
    return (
        screen.x + max(0.0, (screen.width - window_width) / 2.0),
        screen.y + max(0.0, (screen.height - window_height) / 2.0),
    )


def overlay_becomes_key_only_if_needed() -> bool:
    return False


def overlay_text_for_copy(*, selection: str, full: str) -> str:
    return selection if selection else full


def edit_menu_commands() -> tuple[tuple[str, str, str], ...]:
    return (
        ("Cut", "cut:", "x"),
        ("Copy", "copy:", "c"),
        ("Paste", "paste:", "v"),
        ("Select All", "selectAll:", "a"),
    )


class StdoutPresenter:
    def show_status(self, message: str, source: str | None = None) -> None:
        return None

    def show(self, job: TranslateJob) -> None:
        content = format_overlay(job)
        print(f"{content.title}\n{content.source}\n\n{content.translation}")


class OverlayPresenter:
    def __init__(self) -> None:
        self._impl = _build_backend()

    def show_status(self, message: str, source: str | None = None) -> None:
        self._impl.show(format_status(message, source=source or ""))

    def show(self, job: TranslateJob) -> None:
        self._impl.show(format_macos_translation(job))

    def show_input(self) -> None:
        content = format_macos_translation()
        show_input = getattr(self._impl, "show_input", None)
        if callable(show_input):
            show_input(content)
            return
        self._impl.show(content)

    def set_translate(self, translate: Callable[[str], TranslateJob]) -> None:
        setter = getattr(self._impl, "set_translate", None)
        if callable(setter):
            setter(translate)

    def configure_target_languages(
        self,
        options: tuple[tuple[str, str], ...],
        *,
        current: str,
        on_change: Callable[[str], None],
    ) -> None:
        configure = getattr(self._impl, "configure_target_languages", None)
        if callable(configure):
            configure(options, current=current, on_change=on_change)

    def set_target_language(self, target_language: str) -> None:
        setter = getattr(self._impl, "set_target_language", None)
        if callable(setter):
            setter(target_language)


class _AppleScriptBackend:
    def show(self, content: OverlayContent) -> None:
        import subprocess

        body = "\n\n".join(part for part in (content.source, content.translation) if part)
        script = (
            f"display dialog {_applescript_string(body or content.title)} "
            f"with title {_applescript_string(content.title)} "
            'buttons {"OK"} default button "OK" giving up after 45'
        )
        subprocess.run(["osascript", "-e", script], check=False, timeout=60)


class _AppKitBackend:
    def __init__(self) -> None:
        from AppKit import (
            NSApplication,
            NSBackingStoreBuffered,
            NSButton,
            NSMakeRect,
            NSPanel,
            NSWindowStyleMaskClosable,
            NSWindowStyleMaskResizable,
            NSWindowStyleMaskTitled,
        )

        self._NSMakeRect = NSMakeRect
        self._NSPanel = NSPanel
        self._NSButton = NSButton
        self._style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskResizable
        )
        self._backing = NSBackingStoreBuffered
        self._window = None
        self._content = None
        self._helper = None
        self._target_language_label = None
        self._target_language_popup = None
        self._source_label = None
        self._source_scroll = None
        self._source = None
        self._result_label = None
        self._result_scroll = None
        self._translation = None
        self._translate_button = None
        self._pin_button = None
        self._copy_button = None
        self._translate: Callable[[str], TranslateJob] | None = None
        self._target_language_options: tuple[tuple[str, str], ...] = ()
        self._target_language = ""
        self._target_language_changed: Callable[[str], None] | None = None
        self._source_editable = False
        self._busy = False
        self._copy_feedback_generation = 0
        self._placed = False
        self._pinned = False
        self._needs_focus = False
        self._handling_resign_key = False
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(1)

    def set_translate(self, translate: Callable[[str], TranslateJob]) -> None:
        self._translate = translate
        self._sync_translate_button()

    def configure_target_languages(
        self,
        options: tuple[tuple[str, str], ...],
        *,
        current: str,
        on_change: Callable[[str], None],
    ) -> None:
        normalized = normalize_target_language_options(options, current)
        selected = current.strip().lower() or normalized[0][0]
        self._target_language_options = normalized
        self._target_language = selected
        self._target_language_changed = on_change
        self._sync_target_language_controls()

    def set_target_language(self, target_language: str) -> None:
        selected = target_language.strip().lower()
        if not selected:
            return
        self._target_language_options = normalize_target_language_options(
            self._target_language_options,
            selected,
        )
        self._target_language = selected
        self._sync_target_language_controls()

    def target_language_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._target_language_options):
            return
        selected = self._target_language_options[index][0]
        if selected == self._target_language:
            return
        self._target_language = selected
        callback = self._target_language_changed
        if callback is not None:
            callback(selected)

    def show(self, content: OverlayContent) -> None:
        from Foundation import NSThread
        from PyObjCTools.AppHelper import callAfter

        if NSThread.isMainThread():
            self._show_on_main(content)
            return
        callAfter(self._show_on_main, content)

    def show_input(self, content: OverlayContent) -> None:
        from Foundation import NSThread
        from PyObjCTools.AppHelper import callAfter

        if NSThread.isMainThread():
            self._show_input_on_main(content)
            return
        callAfter(self._show_input_on_main, content)

    def _show_input_on_main(self, content: OverlayContent) -> None:
        self._needs_focus = True
        self._show_on_main(content)

    def _show_on_main(self, content: OverlayContent) -> None:
        from AppKit import NSApp

        created = self._window is None
        if created:
            self._build_window()
        self._window.setTitle_(content.title)
        self._helper.setStringValue_(content.footnote)
        _set_scrollable_text(self._source, content.source)
        _set_scrollable_text(self._translation, content.translation)
        _configure_overlay_text_interaction(
            self._source,
            editable=content.source_editable,
        )
        self._source_editable = content.source_editable
        self._sync_translate_button()
        self._reset_copy_feedback()
        _prepare_overlay_window(self._window, pinned=self._pinned)
        visible = bool(self._window.isVisible())
        needs_focus = bool(getattr(self, "_needs_focus", False))
        if (
            should_center_overlay(created=created) and not self._placed
        ) or (needs_focus and not self._pinned):
            _place_overlay_on_pointer_screen(self._window)
            self._placed = True
        if should_focus_overlay(visible=visible) or needs_focus:
            NSApp.activateIgnoringOtherApps_(True)
            self._window.makeKeyAndOrderFront_(None)
            responder = self._source if content.source_editable else self._translation
            self._window.makeFirstResponder_(responder)
            self._needs_focus = False
        self._window.orderFrontRegardless()

    def _build_window(self) -> None:
        from AppKit import NSEventModifierFlagCommand, NSPopUpButton

        window = self._NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            self._NSMakeRect(
                0.0,
                0.0,
                _OVERLAY_DEFAULT_WIDTH,
                _OVERLAY_DEFAULT_HEIGHT,
            ),
            self._style,
            self._backing,
            False,
        )
        _prepare_overlay_chrome(window)
        ensure_edit_menu()
        _prepare_overlay_window(window, pinned=self._pinned)
        content = window.contentView()
        if content is None:
            raise RuntimeError("overlay window has no content view")
        _style_overlay_window_content(window, content)
        controller = _overlay_controller_class().alloc().init()
        controller.owner = self
        window.setDelegate_(controller)
        helper = _overlay_text_label(
            content,
            "",
            font_size=13.0,
            color="#6B7280",
        )
        target_language_label = _overlay_text_label(
            content,
            OVERLAY_TARGET_LANGUAGE_LABEL,
            font_size=12.0,
            weight="medium",
            color="#6B7280",
        )
        target_language_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            self._NSMakeRect(0.0, 0.0, 120.0, 28.0),
            False,
        )
        _style_target_language_popup(target_language_popup)
        target_language_popup.setTarget_(controller)
        target_language_popup.setAction_("changeTargetLanguage:")
        content.addSubview_(target_language_popup)
        source_label = _overlay_text_label(
            content,
            OVERLAY_SOURCE_LABEL,
            font_size=13.0,
            weight="medium",
            color="#1F2430",
        )
        source_scroll, source = _overlay_scrolling_text(
            content,
            accent_border=True,
            editable=False,
        )
        result_label = _overlay_text_label(
            content,
            OVERLAY_RESULT_LABEL,
            font_size=13.0,
            weight="medium",
            color="#1F2430",
        )
        result_scroll, translation = _overlay_scrolling_text(
            content,
            accent_border=False,
            editable=False,
        )
        translate_button = self._NSButton.alloc().initWithFrame_(
            self._NSMakeRect(0.0, 0.0, 72.0, 32.0)
        )
        _style_translate_button(translate_button, enabled=False, busy=False)
        translate_button.setTarget_(controller)
        translate_button.setAction_("translateSource:")
        translate_button.setKeyEquivalent_("\r")
        translate_button.setKeyEquivalentModifierMask_(NSEventModifierFlagCommand)
        pin_button = self._NSButton.alloc().initWithFrame_(
            self._NSMakeRect(0.0, 0.0, 32.0, 32.0)
        )
        _style_pin_button(pin_button, pinned=self._pinned)
        pin_button.setTarget_(controller)
        pin_button.setAction_("togglePin:")
        copy_button = self._NSButton.alloc().initWithFrame_(
            self._NSMakeRect(0.0, 0.0, 32.0, 32.0)
        )
        _style_copy_button(copy_button, copied=False)
        copy_button.setTarget_(controller)
        copy_button.setAction_("copyTranslation:")
        content.addSubview_(translate_button)
        content.addSubview_(pin_button)
        content.addSubview_(copy_button)
        self._window = window
        self._content = content
        self._helper = helper
        self._target_language_label = target_language_label
        self._target_language_popup = target_language_popup
        self._source_label = source_label
        self._source_scroll = source_scroll
        self._source = source
        self._result_label = result_label
        self._result_scroll = result_scroll
        self._translation = translation
        self._translate_button = translate_button
        self._pin_button = pin_button
        self._copy_button = copy_button
        self._controller = controller
        self._sync_target_language_controls()
        self._sync_translate_button()
        self.layout()

    def toggle_pin(self) -> None:
        if self._window is None or self._pin_button is None:
            return
        self._pinned = not self._pinned
        _set_overlay_pinned(self._window, pinned=self._pinned)
        _style_pin_button(self._pin_button, pinned=self._pinned)
        self._window.orderFrontRegardless()

    def window_did_resign_key(self) -> None:
        if (
            self._window is None
            or self._pinned
            or getattr(self, "_handling_resign_key", False)
        ):
            return
        self._handling_resign_key = True
        self._needs_focus = True
        try:
            self._window.orderOut_(None)
        finally:
            self._handling_resign_key = False

    def copy_translation(self) -> None:
        if self._translation is None:
            return
        text = str(self._translation.string() or "")
        if text:
            _copy_plain_text(text)

            copy_button = getattr(self, "_copy_button", None)
            if copy_button is not None:
                generation = getattr(self, "_copy_feedback_generation", 0) + 1
                self._copy_feedback_generation = generation
                _style_copy_button(copy_button, copied=True)
                _schedule_overlay_feedback(
                    _OVERLAY_COPY_FEEDBACK_SECONDS,
                    self._restore_copy_feedback,
                    generation,
                )

    def request_translate(self) -> None:
        translate = self._translate
        if (
            self._busy
            or not self._source_editable
            or translate is None
            or self._source is None
        ):
            return
        text = str(self._source.string() or "")
        self._busy = True
        self._sync_translate_button()
        if self._helper is not None:
            self._helper.setStringValue_(OVERLAY_TRANSLATING_BUTTON_TITLE)
        threading.Thread(
            target=self._run_typed_translation,
            args=(text, translate),
            daemon=True,
        ).start()

    def _run_typed_translation(
        self,
        text: str,
        translate: Callable[[str], TranslateJob],
    ) -> None:
        try:
            job = translate(text)
        except Exception as exc:
            job = TranslateJob(
                kind=JobKind.SELECTION,
                status=JobStatus.FAILURE,
                source_text=text,
                translated_text=None,
                error=str(exc),
            )
        self._apply_typed_translation(job)

    def _apply_typed_translation(self, job: TranslateJob) -> None:
        from Foundation import NSThread
        from PyObjCTools.AppHelper import callAfter

        if NSThread.isMainThread():
            self._show_typed_translation(job)
            return
        callAfter(self._show_typed_translation, job)

    def _show_typed_translation(self, job: TranslateJob) -> None:
        self._busy = False
        self._sync_translate_button()
        content = format_macos_translation(job)
        if self._window is not None:
            self._window.setTitle_(content.title)
        if self._helper is not None:
            self._helper.setStringValue_(content.footnote)
        translation = (
            "请输入要翻译的文字。"
            if job.error == "empty_text"
            else content.translation
        )
        if self._translation is not None:
            _set_scrollable_text(self._translation, translation)
        self._reset_copy_feedback()

    def _sync_translate_button(self) -> None:
        button = getattr(self, "_translate_button", None)
        if button is None:
            return
        available = self._source_editable and self._translate is not None
        button.setHidden_(not available)
        _style_translate_button(
            button,
            enabled=available and not self._busy,
            busy=self._busy,
        )
        target_language_popup = getattr(self, "_target_language_popup", None)
        if target_language_popup is not None:
            target_language_popup.setEnabled_(
                bool(getattr(self, "_target_language_options", ()))
                and not self._busy
            )

    def _sync_target_language_controls(self) -> None:
        label = getattr(self, "_target_language_label", None)
        popup = getattr(self, "_target_language_popup", None)
        if label is None or popup is None:
            return
        visible = bool(self._target_language_options)
        label.setHidden_(not visible)
        popup.setHidden_(not visible)
        popup.removeAllItems()
        if not visible:
            return
        popup.addItemsWithTitles_(
            [display for _code, display in self._target_language_options]
        )
        selected = next(
            (
                index
                for index, (code, _display) in enumerate(
                    self._target_language_options
                )
                if code == self._target_language
            ),
            0,
        )
        popup.selectItemAtIndex_(selected)
        popup.setEnabled_(not self._busy)

    def _reset_copy_feedback(self) -> None:
        self._copy_feedback_generation = (
            getattr(self, "_copy_feedback_generation", 0) + 1
        )
        copy_button = getattr(self, "_copy_button", None)
        if copy_button is not None:
            _style_copy_button(copy_button, copied=False)

    def _restore_copy_feedback(self, generation: int) -> None:
        if generation != getattr(self, "_copy_feedback_generation", 0):
            return
        copy_button = getattr(self, "_copy_button", None)
        if copy_button is not None:
            _style_copy_button(copy_button, copied=False)

    def layout(self) -> None:
        if self._content is None:
            return
        bounds = self._content.bounds()
        layout = overlay_window_layout(
            float(bounds.size.width),
            float(bounds.size.height),
        )
        for view, frame in (
            (self._helper, layout.helper),
            (self._target_language_label, layout.target_language_label),
            (self._target_language_popup, layout.target_language_popup),
            (self._source_label, layout.source_label),
            (self._source_scroll, layout.source_editor),
            (self._result_label, layout.result_label),
            (self._result_scroll, layout.result_editor),
            (self._translate_button, layout.translate_button),
            (self._pin_button, layout.pin_button),
            (self._copy_button, layout.copy_button),
        ):
            _set_overlay_frame(view, frame)


def _overlay_text_label(
    parent: object,
    title: str,
    *,
    font_size: float,
    color: str,
    weight: str = "regular",
):
    from AppKit import NSMakeRect, NSTextField

    label = NSTextField.alloc().initWithFrame_(NSMakeRect(0.0, 0.0, 1.0, 1.0))
    label.setStringValue_(title)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setFont_(_overlay_system_font(font_size, weight))
    label.setTextColor_(_overlay_color(color))
    parent.addSubview_(label)
    return label


def _overlay_scrolling_text(
    parent: object,
    *,
    accent_border: bool,
    editable: bool,
):
    from AppKit import (
        NSMakeRect,
        NSNoBorder,
        NSScrollView,
        NSView,
        NSViewHeightSizable,
        NSViewWidthSizable,
    )

    wrapper = NSView.alloc().initWithFrame_(NSMakeRect(0.0, 0.0, 3.0, 3.0))
    wrapper.setWantsLayer_(True)
    wrapper_layer = wrapper.layer()
    if wrapper_layer is not None:
        wrapper_layer.setBackgroundColor_(_overlay_cg_color("#F7F8FC"))
        wrapper_layer.setCornerRadius_(10.0)
        wrapper_layer.setBorderWidth_(1.0)
        border = "#7778FF" if accent_border else "#DDE1EA"
        wrapper_layer.setBorderColor_(_overlay_cg_color(border))
        wrapper_layer.setMasksToBounds_(True)
    scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(1.0, 1.0, 1.0, 1.0))
    scroll.setHasVerticalScroller_(True)
    scroll.setHasHorizontalScroller_(False)
    scroll.setAutohidesScrollers_(True)
    scroll.setBorderType_(NSNoBorder)
    scroll.setDrawsBackground_(True)
    scroll.setBackgroundColor_(_overlay_color("#F7F8FC"))
    scroll.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    text = _overlay_text_view_class().alloc().initWithFrame_(
        NSMakeRect(0.0, 0.0, 1.0, 1.0)
    )
    text.setRichText_(False)
    _configure_overlay_text_interaction(text, editable=editable)
    text.setFont_(_overlay_system_font(15.0, "regular"))
    text.setTextColor_(_overlay_color("#1F2430"))
    text.setDrawsBackground_(True)
    text.setBackgroundColor_(_overlay_color("#F7F8FC"))
    text.setTextContainerInset_((14.0, 12.0))
    text.setVerticallyResizable_(True)
    text.setHorizontallyResizable_(False)
    text.setAutoresizingMask_(NSViewWidthSizable)
    text.setMinSize_((0.0, 0.0))
    text.setMaxSize_((1.0e7, 1.0e7))
    container = text.textContainer()
    container.setWidthTracksTextView_(True)
    container.setContainerSize_((1.0, 1.0e7))
    scroll.setDocumentView_(text)
    wrapper.addSubview_(scroll)
    parent.addSubview_(wrapper)
    return wrapper, text


def _configure_overlay_text_interaction(view: object, *, editable: bool) -> None:
    view.setEditable_(editable)
    view.setSelectable_(True)
    set_allows_undo = getattr(view, "setAllowsUndo_", None)
    if callable(set_allows_undo):
        set_allows_undo(editable)
    for selector in (
        "setAutomaticQuoteSubstitutionEnabled_",
        "setAutomaticDashSubstitutionEnabled_",
        "setAutomaticTextReplacementEnabled_",
        "setAutomaticSpellingCorrectionEnabled_",
    ):
        setter = getattr(view, selector, None)
        if callable(setter):
            setter(False)


def _overlay_system_font(size: float, weight: str):
    from AppKit import (
        NSFont,
        NSFontWeightMedium,
        NSFontWeightRegular,
        NSFontWeightSemibold,
    )

    weights = {
        "regular": NSFontWeightRegular,
        "medium": NSFontWeightMedium,
        "semibold": NSFontWeightSemibold,
    }
    return NSFont.systemFontOfSize_weight_(size, weights[weight])


def _overlay_color(value: str):
    from AppKit import NSColor

    red, green, blue = _overlay_color_components(value)
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, 1.0)


def _overlay_cg_color(value: str):
    from Quartz import CGColorCreateGenericRGB

    red, green, blue = _overlay_color_components(value)
    return CGColorCreateGenericRGB(red, green, blue, 1.0)


def _overlay_color_components(value: str) -> tuple[float, float, float]:
    raw = value.removeprefix("#")
    if len(raw) != 6:
        raise ValueError("color must use six-digit hex notation")
    red, green, blue = (int(raw[index : index + 2], 16) for index in (0, 2, 4))
    return red / 255.0, green / 255.0, blue / 255.0


def _style_target_language_popup(popup: object) -> None:
    import AppKit

    popup.setFont_(_overlay_system_font(12.0, "medium"))
    popup.setToolTip_(OVERLAY_TARGET_LANGUAGE_TOOLTIP)
    set_accessibility_label = getattr(popup, "setAccessibilityLabel_", None)
    if callable(set_accessibility_label):
        set_accessibility_label(OVERLAY_TARGET_LANGUAGE_TOOLTIP)
    set_control_size = getattr(popup, "setControlSize_", None)
    if callable(set_control_size):
        set_control_size(getattr(AppKit, "NSControlSizeSmall", 1))
    set_bezel_style = getattr(popup, "setBezelStyle_", None)
    if callable(set_bezel_style):
        set_bezel_style(getattr(AppKit, "NSBezelStyleRounded", 1))


def _style_pin_button(button: object, *, pinned: bool) -> None:
    _style_icon_button(
        button,
        symbol=overlay_pin_symbol_name(pinned=pinned),
        accessibility_label=overlay_pin_button_title(pinned=pinned),
        background="#4F46E5" if pinned else "#E5E5FF",
        tint="#FFFFFF" if pinned else "#1F2430",
    )


def _style_copy_button(button: object, *, copied: bool) -> None:
    _style_icon_button(
        button,
        symbol=overlay_copy_symbol_name(copied=copied),
        accessibility_label=overlay_copy_button_title(copied=copied),
        background="#E5E5FF" if copied else "#F1F2F6",
        tint="#4F46E5" if copied else "#1F2430",
    )


def _style_translate_button(
    button: object,
    *,
    enabled: bool,
    busy: bool,
) -> None:
    import AppKit
    from Foundation import NSAttributedString

    button.setBordered_(False)
    set_button_type = getattr(button, "setButtonType_", None)
    if callable(set_button_type):
        set_button_type(getattr(AppKit, "NSButtonTypeMomentaryPushIn", 7))
    button.setWantsLayer_(True)
    button.setEnabled_(enabled)
    button.setToolTip_(OVERLAY_TRANSLATE_BUTTON_TOOLTIP)
    set_accessibility_label = getattr(button, "setAccessibilityLabel_", None)
    if callable(set_accessibility_label):
        set_accessibility_label(OVERLAY_TRANSLATE_BUTTON_TOOLTIP)
    layer = button.layer()
    if layer is not None:
        layer.setBackgroundColor_(
            _overlay_cg_color("#B9BBEA" if busy or not enabled else "#4F46E5")
        )
        layer.setCornerRadius_(8.0)
    title = NSAttributedString.alloc().initWithString_attributes_(
        OVERLAY_TRANSLATING_BUTTON_TITLE if busy else OVERLAY_TRANSLATE_BUTTON_TITLE,
        {
            AppKit.NSFontAttributeName: _overlay_system_font(13.0, "semibold"),
            AppKit.NSForegroundColorAttributeName: _overlay_color("#FFFFFF"),
        },
    )
    button.setAttributedTitle_(title)


def _style_icon_button(
    button: object,
    *,
    symbol: str,
    accessibility_label: str,
    background: str,
    tint: str,
) -> None:
    import AppKit

    button.setTitle_("")
    button.setBordered_(False)
    set_button_type = getattr(button, "setButtonType_", None)
    if callable(set_button_type):
        set_button_type(getattr(AppKit, "NSButtonTypeMomentaryChange", 5))
    button.setWantsLayer_(True)
    button.setImage_(_overlay_symbol_image(symbol, accessibility_label))
    button.setImagePosition_(AppKit.NSImageOnly)
    button.setImageScaling_(AppKit.NSImageScaleProportionallyDown)
    button.setToolTip_(accessibility_label)
    set_accessibility_label = getattr(button, "setAccessibilityLabel_", None)
    if callable(set_accessibility_label):
        set_accessibility_label(accessibility_label)
    set_tint = getattr(button, "setContentTintColor_", None)
    if callable(set_tint):
        set_tint(_overlay_color(tint))
    layer = button.layer()
    if layer is not None:
        layer.setBackgroundColor_(_overlay_cg_color(background))
        layer.setCornerRadius_(8.0)


def _schedule_overlay_feedback(
    delay: float,
    callback: object,
    *args: object,
) -> None:
    from PyObjCTools.AppHelper import callLater

    callLater(delay, callback, *args)


def _overlay_symbol_image(symbol: str, accessibility_label: str):
    from AppKit import NSFontWeightMedium, NSImage, NSImageSymbolConfiguration

    image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
        symbol,
        accessibility_label,
    )
    if image is None:
        return None
    configuration = NSImageSymbolConfiguration.configurationWithPointSize_weight_(
        15.0,
        NSFontWeightMedium,
    )
    configured = image.imageWithSymbolConfiguration_(configuration)
    return configured or image


def _style_overlay_window_content(window: object, content: object) -> None:
    background = _overlay_color("#FFFFFF")
    window.setBackgroundColor_(background)
    content.setWantsLayer_(True)
    layer = content.layer()
    if layer is not None:
        layer.setBackgroundColor_(_overlay_cg_color("#FFFFFF"))


def _prepare_overlay_chrome(window: object) -> None:
    import AppKit

    window.setTitle_("翻译")
    set_content_min_size = getattr(window, "setContentMinSize_", None)
    if callable(set_content_min_size):
        set_content_min_size((_OVERLAY_MIN_WIDTH, _OVERLAY_MIN_HEIGHT))
    else:
        window.setMinSize_((_OVERLAY_MIN_WIDTH, _OVERLAY_MIN_HEIGHT))
    set_title_visibility = getattr(window, "setTitleVisibility_", None)
    if callable(set_title_visibility):
        set_title_visibility(getattr(AppKit, "NSWindowTitleHidden", 1))
    set_titlebar_transparent = getattr(
        window,
        "setTitlebarAppearsTransparent_",
        None,
    )
    if callable(set_titlebar_transparent):
        set_titlebar_transparent(False)
    set_titlebar_separator = getattr(window, "setTitlebarSeparatorStyle_", None)
    if callable(set_titlebar_separator):
        separator_line = getattr(AppKit, "NSTitlebarSeparatorStyleLine", 2)
        set_titlebar_separator(separator_line)


def _set_overlay_frame(view: object, frame: OverlayFrame) -> None:
    from AppKit import NSMakeRect

    view.setFrame_(NSMakeRect(frame.x, frame.y, frame.width, frame.height))


def _set_scrollable_text(view: object, value: str) -> None:
    view.setString_(value or "")
    undo_manager = getattr(view, "undoManager", None)
    manager = undo_manager() if callable(undo_manager) else None
    remove_all_actions = getattr(manager, "removeAllActions", None)
    if callable(remove_all_actions):
        remove_all_actions()
    view.scrollRangeToVisible_((0, 0))


def _set_overlay_pinned(window: object, *, pinned: bool) -> None:
    from AppKit import (
        NSFloatingWindowLevel,
        NSNormalWindowLevel,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorMoveToActiveSpace,
    )

    window.setLevel_(NSFloatingWindowLevel if pinned else NSNormalWindowLevel)
    set_floating = getattr(window, "setFloatingPanel_", None)
    if callable(set_floating):
        set_floating(pinned)
    window.setCollectionBehavior_(
        (
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        if pinned
        else (
            NSWindowCollectionBehaviorMoveToActiveSpace
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
    )


def _place_overlay_on_pointer_screen(window: object) -> None:
    from AppKit import NSEvent, NSScreen

    screens = tuple(NSScreen.screens() or ())
    if not screens:
        window.center()
        return
    frames = tuple(
        OverlayFrame(
            float(screen.visibleFrame().origin.x),
            float(screen.visibleFrame().origin.y),
            float(screen.visibleFrame().size.width),
            float(screen.visibleFrame().size.height),
        )
        for screen in screens
    )
    pointer = NSEvent.mouseLocation()
    window_frame = window.frame()
    origin = overlay_window_origin_for_point(
        window_width=float(window_frame.size.width),
        window_height=float(window_frame.size.height),
        screens=frames,
        point=(float(pointer.x), float(pointer.y)),
    )
    window.setFrameOrigin_(origin)


def _prepare_overlay_window(window: object, *, pinned: bool) -> None:
    _set_overlay_pinned(window, pinned=pinned)
    window.setReleasedWhenClosed_(False)
    window.setHidesOnDeactivate_(False)
    set_needed = getattr(window, "setBecomesKeyOnlyIfNeeded_", None)
    if callable(set_needed):
        set_needed(overlay_becomes_key_only_if_needed())


def ensure_edit_menu() -> None:
    from AppKit import NSApp, NSMenu, NSMenuItem

    app = NSApp
    if app.mainMenu() is not None:
        return
    menu = NSMenu.alloc().init()
    edit = NSMenu.alloc().initWithTitle_("Edit")
    for title, action, key in edit_menu_commands():
        edit.addItemWithTitle_action_keyEquivalent_(title, action, key)
    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Edit", None, "")
    item.setSubmenu_(edit)
    menu.addItem_(item)
    app.setMainMenu_(menu)


def _overlay_controller_class() -> type:
    global _OverlayController
    if _OverlayController is not None:
        return _OverlayController
    from Foundation import NSObject

    class AITranslateOverlayController(NSObject):
        def togglePin_(self, _sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.toggle_pin()

        def copyTranslation_(self, _sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.copy_translation()

        def translateSource_(self, _sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.request_translate()

        def changeTargetLanguage_(self, sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.target_language_changed(int(sender.indexOfSelectedItem()))

        def windowDidResize_(self, _notification) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.layout()

        def windowDidResignKey_(self, _notification) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.window_did_resign_key()

    _OverlayController = AITranslateOverlayController
    return AITranslateOverlayController


def _overlay_text_view_class() -> type:
    global _OverlayTextView
    if _OverlayTextView is not None:
        return _OverlayTextView
    from AppKit import NSTextView
    import objc

    class AITranslateOverlayTextView(NSTextView):
        def copy_(self, _sender) -> None:
            _copy_plain_text(_text_view_copy_payload(self))

        def acceptsFirstResponder(self) -> bool:
            return True

    _OverlayTextView = AITranslateOverlayTextView
    return AITranslateOverlayTextView


def _text_view_copy_payload(view: object) -> str:
    full = str(view.string() or "")
    selected = view.selectedRange()
    start = int(getattr(selected, "location", selected[0]))
    length = int(getattr(selected, "length", selected[1]))
    piece = full[start : start + length] if length > 0 else ""
    return overlay_text_for_copy(selection=piece, full=full)


def _copy_plain_text(text: str) -> None:
    from AppKit import NSPasteboard, NSPasteboardTypeString

    board = NSPasteboard.generalPasteboard()
    board.clearContents()
    board.setString_forType_(text, NSPasteboardTypeString)


_OverlayController = None
_OverlayTextView = None


def _footnote(job: TranslateJob) -> str:
    if job.kind is JobKind.OCR and job.ocr_engine == "vision":
        return "本机"
    if job.kind is JobKind.OCR and job.ocr_engine == "paddle":
        return "本地高级"
    if job.kind is JobKind.OCR and job.ocr_engine == "standard":
        return "普通"
    if job.kind is JobKind.OCR and job.ocr_engine == "model":
        return "高级"
    labels = {
        "google_web": "Google 内置",
        "bing_web": "Bing 内置",
        "deepl_web": "DeepL 内置",
        "deepl": "DeepL",
        "microsoft": "Microsoft",
        "google": "Google",
    }
    if job.translate_model in labels:
        return labels[job.translate_model]
    return ""


def _build_backend() -> _AppleScriptBackend | _AppKitBackend:
    try:
        import AppKit  # noqa: F401
        from PyObjCTools.AppHelper import callAfter  # noqa: F401

        return _AppKitBackend()
    except Exception:
        return _AppleScriptBackend()


def _applescript_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
