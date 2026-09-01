"""Compatibility exports for the Windows settings interface.

The active Windows UI lives in :mod:`ai_translate.interfaces.windows_qt`.
This module remains as a stable import route for callers that only need the
settings presenter or its option contracts.
"""

from ai_translate.interfaces.windows_qt import (
    WindowsSettingsPresenter,
    windows_settings_engine_options,
    windows_settings_model_tier_options,
)

__all__ = [
    "WindowsSettingsPresenter",
    "windows_settings_engine_options",
    "windows_settings_model_tier_options",
]
