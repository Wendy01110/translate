from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from ai_translate.core.history import MAX_HISTORY_RECORDS, HistoryEntry
from ai_translate.features.history import TranslationHistory

if TYPE_CHECKING:
    from ai_translate.interfaces.windows_qt import WindowsUiRuntime


class HistoryBrowser:
    def __init__(
        self, history: TranslationHistory, on_reuse: Callable[[HistoryEntry], bool | None],
    ) -> None:
        self.history = history
        self._on_reuse = on_reuse
        self.entries: tuple[HistoryEntry, ...] = ()
        self.index = -1
        self._reuse_notice: str | None = None

    def refresh(self) -> None:
        self._reuse_notice = None
        selected = self.selected
        self.entries = self.history.state.entries
        self.index = self.entries.index(selected) if selected in self.entries else 0
        if not self.entries:
            self.index = -1

    @property
    def selected(self) -> HistoryEntry | None:
        return self.entries[self.index] if 0 <= self.index < len(self.entries) else None

    @property
    def labels(self) -> list[str]:
        return [
            f"{datetime.fromisoformat(entry.created_at).astimezone():%m-%d %H:%M}"
            f" · {entry.source_lang} → {entry.target_lang} · "
            + " ".join(entry.source_text.split())[:32]
            for entry in self.entries
        ]

    @property
    def status(self) -> str:
        if self.history.error:
            return self.history.error
        if self._reuse_notice:
            return self._reuse_notice
        mode = "保存已开启" if self.history.state.enabled else "保存已关闭，已有记录仍可查看"
        return f"{mode} · {len(self.entries)}/{MAX_HISTORY_RECORDS} 条"

    def select(self, index: int) -> None:
        self.index = index if 0 <= index < len(self.entries) else -1

    def set_enabled(self, enabled: bool) -> None:
        self.history.set_enabled(enabled)
        self.refresh()

    def clear(self) -> None:
        self.history.clear()
        self.refresh()

    def reuse(self) -> None:
        if self.selected is not None:
            self._reuse_notice = (
                "正在翻译，请完成后再复用历史。"
                if self._on_reuse(self.selected) is False else None
            )


class HistoryPresenter:
    def __init__(
        self, history: TranslationHistory, on_reuse: Callable[[HistoryEntry], bool | None],
    ) -> None:
        self._browser = HistoryBrowser(history, on_reuse)
        self._window: _HistoryWindow | None = None

    def show(self) -> None:
        if self._window is None:
            self._window = _HistoryWindow(self._browser)
        self._browser.refresh()
        self._window.refresh()
        from AppKit import NSApplication

        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self._window.window.makeKeyAndOrderFront_(None)


class _HistoryWindow:
    def __init__(self, browser: HistoryBrowser) -> None:
        from AppKit import (
            NSBackingStoreBuffered, NSButton, NSButtonTypeSwitch, NSColor, NSMakeRect,
            NSPopUpButton, NSWindow, NSWindowStyleMaskClosable,
            NSWindowStyleMaskResizable, NSWindowStyleMaskTitled,
        )
        from ai_translate.interfaces.overlay import (
            _overlay_scrolling_text, _overlay_text_label,
        )

        self.browser = browser
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 760, 500),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable,
            NSBackingStoreBuffered, False,
        )
        self.window.setTitle_("翻译历史")
        self.window.setBackgroundColor_(NSColor.whiteColor())
        self.window.setReleasedWhenClosed_(False)
        self.window.setMinSize_((640, 360))
        self.window.center()
        content = self.window.contentView()
        self.controller = _history_controller_class().alloc().init()
        self.controller.owner = self
        self.window.setDelegate_(self.controller)

        def button(title: str, action: str):
            view = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 0, 0))
            view.setTitle_(title)
            view.setTarget_(self.controller)
            view.setAction_(action)
            content.addSubview_(view)
            return view

        self.enabled = button("保留翻译历史（仅本机）", "toggleSaving:")
        self.enabled.setButtonType_(NSButtonTypeSwitch)
        self.popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(NSMakeRect(0, 0, 0, 0), False)
        self.popup.setTarget_(self.controller)
        self.popup.setAction_("selectEntry:")
        content.addSubview_(self.popup)
        self.source_label = _overlay_text_label(content, "原文", font_size=13, color="#1F2430", weight="medium")
        self.translation_label = _overlay_text_label(content, "译文", font_size=13, color="#1F2430", weight="medium")
        self.source_scroll, self.source = _overlay_scrolling_text(content, accent_border=False, editable=False)
        self.translation_scroll, self.translation = _overlay_scrolling_text(content, accent_border=False, editable=False)
        self.status = _overlay_text_label(content, "", font_size=12, color="#667085")
        self.reuse = button("放回翻译窗口", "reuseEntry:")
        self.clear = button("清空历史…", "clearEntries:")
        self.layout()

    def layout(self) -> None:
        from AppKit import NSMakeRect

        bounds = self.window.contentView().bounds().size
        width, height = bounds.width, bounds.height
        column = (width - 48) / 2
        self.enabled.setFrame_(NSMakeRect(16, height - 42, width - 32, 26))
        self.popup.setFrame_(NSMakeRect(16, height - 82, width - 32, 30))
        for label, scroll, x in (
            (self.source_label, self.source_scroll, 16),
            (self.translation_label, self.translation_scroll, 32 + column),
        ):
            label.setFrame_(NSMakeRect(x, height - 112, column, 22))
            scroll.setFrame_(NSMakeRect(x, 94, column, max(100, height - 210)))
        self.status.setFrame_(NSMakeRect(16, 62, width - 32, 22))
        self.clear.setFrame_(NSMakeRect(16, 16, 112, 32))
        self.reuse.setFrame_(NSMakeRect(width - 156, 16, 140, 32))

    def refresh(self) -> None:
        self.enabled.setState_(int(self.browser.history.state.enabled))
        self.popup.removeAllItems()
        self.popup.addItemsWithTitles_(self.browser.labels or ["暂无历史记录"])
        self.popup.setEnabled_(bool(self.browser.entries))
        self.popup.selectItemAtIndex_(max(0, self.browser.index))
        self.preview()

    def preview(self) -> None:
        from ai_translate.interfaces.overlay import _set_scrollable_text

        entry = self.browser.selected
        _set_scrollable_text(self.source, entry.source_text if entry else "")
        _set_scrollable_text(self.translation, entry.translated_text if entry else "")
        self.status.setStringValue_(self.browser.status)
        self.reuse.setEnabled_(entry is not None)
        self.clear.setEnabled_(bool(self.browser.entries) or bool(self.browser.history.error))


_HistoryController = None


def _history_controller_class() -> type:
    global _HistoryController
    if _HistoryController is not None:
        return _HistoryController
    from Foundation import NSObject

    class AITranslateHistoryController(NSObject):
        def toggleSaving_(self, sender) -> None:
            self.owner.browser.set_enabled(bool(sender.state()))
            self.owner.refresh()

        def selectEntry_(self, sender) -> None:
            self.owner.browser.select(sender.indexOfSelectedItem())
            self.owner.preview()

        def reuseEntry_(self, _sender) -> None:
            self.owner.browser.reuse()
            self.owner.preview()

        def clearEntries_(self, _sender) -> None:
            from AppKit import NSAlert, NSAlertFirstButtonReturn

            alert = NSAlert.alloc().init()
            alert.setMessageText_("清空全部翻译历史？")
            alert.setInformativeText_("清空后无法恢复，当前翻译窗口的内容会保留。")
            alert.addButtonWithTitle_("清空")
            alert.addButtonWithTitle_("取消")
            if alert.runModal() == NSAlertFirstButtonReturn:
                self.owner.browser.clear()
                self.owner.refresh()

        def windowDidResize_(self, _notification) -> None:
            self.owner.layout()

    _HistoryController = AITranslateHistoryController
    return _HistoryController


class WindowsHistoryPresenter:
    def __init__(
        self, runtime: WindowsUiRuntime, history: TranslationHistory,
        on_reuse: Callable[[HistoryEntry], bool | None],
    ) -> None:
        self._runtime = runtime
        self._browser = HistoryBrowser(history, on_reuse)
        self._window: object | None = None

    def show(self) -> None:
        self._runtime.call_soon(self._show)

    def _show(self) -> None:
        if self._window is None:
            self._window = self._runtime.create_window("History.qml")
            self._runtime.connect_signal(self._window, "savingToggled(bool)", self._toggle)
            self._runtime.connect_signal(self._window, "entrySelected(int)", self._select)
            self._runtime.connect_signal(self._window, "reuseRequested()", self._reuse)
            self._runtime.connect_signal(self._window, "clearRequested()", self._clear)
            self._runtime.center_window(self._window)
        self._browser.refresh()
        self._refresh()
        self._runtime.present_window(self._window)

    def _refresh(self) -> None:
        self._window.setProperty("savingEnabled", self._browser.history.state.enabled)
        self._window.setProperty("entryLabels", self._browser.labels)
        self._window.setProperty("selectedIndex", self._browser.index)
        self._preview()

    def _preview(self) -> None:
        entry = self._browser.selected
        for name, value in {
            "sourceText": entry.source_text if entry else "",
            "translatedText": entry.translated_text if entry else "",
            "statusText": self._browser.status,
            "canReuse": entry is not None,
            "canClear": bool(self._browser.entries) or bool(self._browser.history.error),
        }.items():
            self._window.setProperty(name, value)

    def _toggle(self, enabled: bool) -> None:
        self._browser.set_enabled(enabled)
        self._refresh()

    def _select(self, index: int) -> None:
        self._browser.select(index)
        self._preview()

    def _clear(self) -> None:
        self._browser.clear()
        self._refresh()

    def _reuse(self) -> None:
        self._browser.reuse()
        self._preview()
