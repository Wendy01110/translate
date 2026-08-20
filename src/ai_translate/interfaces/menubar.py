from __future__ import annotations

import fcntl
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from ai_translate.core.hotkeys import display_hotkey
from ai_translate.interfaces.listen import DesktopListener

_STATUS_TITLE = "译"


def menu_spec(
    selection_hotkey: str,
    ocr_hotkey: str,
    *,
    accessibility_ok: bool = True,
) -> list[tuple[str, str]]:
    permission = (
        "辅助功能：已开启" if accessibility_ok else "辅助功能：未开启，点此去设置"
    )
    return [
        (f"划词翻译  {display_hotkey(selection_hotkey)}", "selection"),
        (f"截图翻译  {display_hotkey(ocr_hotkey)}", "ocr"),
        ("输入翻译…", "input"),
        (permission, "accessibility"),
        ("设置…", "settings"),
        ("退出", "quit"),
    ]


MENU_ACTION_DELAY = 0.2


def consume_pending_settings(holder: object) -> bool:
    return _consume_pending(holder, "pending_settings")


def consume_pending_input(holder: object) -> bool:
    return _consume_pending(holder, "pending_input")


def _consume_pending(holder: object, attr: str) -> bool:
    if not bool(getattr(holder, attr, False)):
        return False
    setattr(holder, attr, False)
    return True


def defer_menu_action(
    callback: Callable[[], None],
    delay: float = MENU_ACTION_DELAY,
    scheduler: Callable[[float, Callable[[], None]], None] | None = None,
) -> None:
    def run() -> None:
        try:
            callback()
        except Exception as exc:
            print(f"menu action failed: {exc}", file=sys.stderr)

    if scheduler is not None:
        scheduler(delay, run)
        return
    if not _schedule_retained(run, delay):
        run()


def open_accessibility_settings() -> None:
    import subprocess

    subprocess.run(
        [
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        ],
        check=False,
    )


def run_status_app(
    listener: DesktopListener,
    *,
    open_settings: Callable[[], None] | None = None,
    open_input: Callable[[], None] | None = None,
) -> int:
    if sys.platform != "darwin":
        print("app is only supported on macOS", file=sys.stderr)
        return 2
    if not _acquire_single_instance():
        print("AI Translate is already running", file=sys.stderr)
        return 1
    _install_status_item(
        listener,
        open_settings=open_settings,
        open_input=open_input,
    )
    return listener.run()


def cocoa_app_loop() -> None:
    from AppKit import NSApplication

    NSApplication.sharedApplication().run()


def _install_status_item(
    listener: DesktopListener,
    *,
    open_settings: Callable[[], None] | None = None,
    open_input: Callable[[], None] | None = None,
) -> None:
    from AppKit import (
        NSApplication,
        NSMenu,
        NSMenuItem,
        NSStatusBar,
        NSVariableStatusItemLength,
    )

    from ai_translate.interfaces.overlay import ensure_edit_menu

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)
    ensure_edit_menu()
    menu = NSMenu.alloc().init()
    selection_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        f"划词翻译  {display_hotkey(listener.selection_hotkey)}",
        "translateSelection:",
        "",
    )
    ocr_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        f"截图翻译  {display_hotkey(listener.ocr_hotkey)}",
        "translateOcr:",
        "",
    )
    permission_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "辅助功能：未开启，点此去设置",
        "openAccessibility:",
        "",
    )
    input_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "输入翻译…",
        "openInput:",
        "",
    )
    settings_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "设置…",
        "openSettings:",
        ",",
    )
    quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "退出",
        "quitApp:",
        "q",
    )
    controller = (
        _menu_controller_class()
        .alloc()
        .initWithListener_permissionItem_openSettings_openInput_(
            listener,
            permission_item,
            open_settings,
            open_input,
        )
    )
    for item in (
        selection_item,
        ocr_item,
        input_item,
        permission_item,
        settings_item,
        quit_item,
    ):
        item.setTarget_(controller)
    menu.addItem_(selection_item)
    menu.addItem_(ocr_item)
    menu.addItem_(input_item)
    menu.addItem_(NSMenuItem.separatorItem())
    menu.addItem_(permission_item)
    menu.addItem_(settings_item)
    menu.addItem_(quit_item)
    menu.setDelegate_(controller)
    status = NSStatusBar.systemStatusBar().statusItemWithLength_(
        NSVariableStatusItemLength
    )
    button = status.button()
    if button is not None:
        button.setTitle_(_STATUS_TITLE)
    status.setMenu_(menu)
    _retain(controller, status, menu)


def _acquire_single_instance() -> bool:
    support = Path.home() / "Library" / "Application Support" / "AI Translate"
    support.mkdir(parents=True, exist_ok=True)
    handle = (support / "instance.lock").open("w")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    _retain(handle)
    return True


def _retain(*objects: object) -> None:
    _LIVE.extend(objects)


def _drop(obj: object) -> None:
    try:
        _LIVE.remove(obj)
    except ValueError:
        return


def _menu_controller_class() -> type:
    global _MenuBarController
    if _MenuBarController is not None:
        return _MenuBarController
    from Foundation import NSObject
    import objc

    class AITranslateMenuBarController(NSObject):
        def initWithListener_permissionItem_openSettings_openInput_(
            self,
            hosted,
            permission_item,
            open_settings_cb,
            open_input_cb,
        ):
            self = objc.super(AITranslateMenuBarController, self).init()
            if self is None:
                return None
            self.listener = hosted
            self.permission_item = permission_item
            self.open_settings_cb = open_settings_cb
            self.open_input_cb = open_input_cb
            self.pending_settings = False
            self.pending_input = False
            return self

        def translateSelection_(self, _sender) -> None:
            threading.Thread(
                target=self.listener.handle_selection,
                daemon=True,
            ).start()

        def translateOcr_(self, _sender) -> None:
            threading.Thread(target=self.listener.handle_ocr, daemon=True).start()

        def openAccessibility_(self, _sender) -> None:
            open_accessibility_settings()

        def openSettings_(self, _sender) -> None:
            if self.open_settings_cb is None:
                return
            self.pending_settings = True
            self.performSelector_withObject_afterDelay_(
                "openSettingsNow:",
                None,
                MENU_ACTION_DELAY,
            )

        def openInput_(self, _sender) -> None:
            if self.open_input_cb is None:
                return
            self.pending_input = True
            self.performSelector_withObject_afterDelay_(
                "openInputNow:",
                None,
                MENU_ACTION_DELAY,
            )

        def menuDidClose_(self, _menu) -> None:
            if self.pending_settings:
                NSObject.cancelPreviousPerformRequestsWithTarget_(self)
                self.performSelector_withObject_afterDelay_(
                    "openSettingsNow:",
                    None,
                    0.05,
                )
                return
            if self.pending_input:
                NSObject.cancelPreviousPerformRequestsWithTarget_(self)
                self.performSelector_withObject_afterDelay_("openInputNow:", None, 0.05)

        def openSettingsNow_(self, _sender) -> None:
            if not consume_pending_settings(self):
                return
            callback = self.open_settings_cb
            if callback is None:
                return
            try:
                callback()
            except Exception as exc:
                print(f"settings failed: {exc}", file=sys.stderr)
                present = getattr(self.listener, "present_error", None)
                if callable(present):
                    present(f"设置页打不开：{exc}")

        def openInputNow_(self, _sender) -> None:
            if not consume_pending_input(self):
                return
            callback = self.open_input_cb
            if callback is None:
                return
            try:
                callback()
            except Exception as exc:
                print(f"input window failed: {exc}", file=sys.stderr)
                present = getattr(self.listener, "present_error", None)
                if callable(present):
                    present(f"输入翻译打不开：{exc}")

        def quitApp_(self, _sender) -> None:
            from AppKit import NSApp

            NSApp.stop_(None)

        def menuNeedsUpdate_(self, _menu) -> None:
            ok = self.listener.accessibility_ready
            self.permission_item.setTitle_(
                "辅助功能：已开启" if ok else "辅助功能：未开启，点此去设置"
            )

    _MenuBarController = AITranslateMenuBarController
    return AITranslateMenuBarController


def _schedule_retained(callback: Callable[[], None], delay: float) -> bool:
    global _DeferredAction
    try:
        from Foundation import NSObject
        import objc
    except Exception:
        return False
    if _DeferredAction is None:

        class AITranslateDeferredAction(NSObject):
            def initWithCallback_(self, cb):
                self = objc.super(AITranslateDeferredAction, self).init()
                if self is None:
                    return None
                self.callback = cb
                return self

            def fire_(self, _sender) -> None:
                cb = getattr(self, "callback", None)
                self.callback = None
                try:
                    if cb is not None:
                        cb()
                finally:
                    _drop(self)

        _DeferredAction = AITranslateDeferredAction
    helper = _DeferredAction.alloc().initWithCallback_(callback)
    if helper is None:
        return False
    _retain(helper)
    helper.performSelector_withObject_afterDelay_("fire:", None, delay)
    return True


_LIVE: list[object] = []
_DeferredAction = None
_MenuBarController = None
