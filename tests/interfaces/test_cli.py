from ai_translate.core.models import ConfigStatus
from ai_translate.interfaces.cli import format_config_status, run


def _status(**overrides: object) -> ConfigStatus:
    payload = {
        "translate_ready": False,
        "translate_base_url": "",
        "translate_model": "",
        "translate_api_key_set": False,
        "translate_source_lang": "auto",
        "translate_target_lang": "zh",
        "ocr_ready": False,
        "ocr_base_url": "",
        "ocr_model": "",
        "ocr_api_key_set": False,
    }
    payload.update(overrides)
    return ConfigStatus(**payload)


def test_config_check_masks_secrets_and_exits_zero(capsys) -> None:
    status = _status(
        translate_ready=True,
        translate_base_url="https://translate.example/v1",
        translate_model="translate-model",
        translate_api_key_set=True,
        ocr_ready=True,
        ocr_base_url="https://ocr.example/v1",
        ocr_model="ocr-model",
        ocr_api_key_set=True,
    )

    code = run(["config-check"], status)
    output = capsys.readouterr().out

    assert code == 0
    assert "ready: true" in output
    assert "api_key: set" in output
    assert "translate-secret" not in output
    assert "ocr-secret" not in output
    assert "https://translate.example/v1" in output
    assert "https://ocr.example/v1" in output


def test_config_check_reports_empty_unready_state(capsys) -> None:
    code = run(["config-check"], _status())
    output = capsys.readouterr().out

    assert code == 0
    assert "ready: false" in output
    assert "base_url: (empty)" in output
    assert "api_key: unset" in output


def test_format_config_status_never_contains_secret_values() -> None:
    rendered = format_config_status(
        _status(translate_api_key_set=True, ocr_api_key_set=True)
    )
    assert "set" in rendered
    assert "sk-" not in rendered
    assert "Bearer" not in rendered
