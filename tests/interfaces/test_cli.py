from pathlib import Path

from ai_translate.app import _needs_runtime, _needs_windows_ui
from ai_translate.core.errors import ImageSourceError
from ai_translate.core.models import ConfigStatus, JobStatus
from ai_translate.features.ocr_translate import OcrTranslateService
from ai_translate.features.selection import SelectionTranslateService
from ai_translate.infrastructure.image_file import load_image_file
from ai_translate.interfaces.cli import CliServices, format_config_status, run
from tests.support import FakeOcrEngine, FakeTranslator


def _status(**overrides: object) -> ConfigStatus:
    payload = {
        "translate_ready": False,
        "translate_provider": "openai",
        "translate_base_url": "",
        "translate_model": "",
        "translate_api_key_set": False,
        "translate_source_lang": "auto",
        "translate_target_lang": "zh",
        "ocr_ready": False,
        "ocr_base_url": "",
        "ocr_model": "Unlimited-OCR",
        "ocr_api_key_set": False,
        "ocr_image_mode": "auto",
        "ocr_max_tokens": 24000,
        "ocr_engine": "auto",
        "ocr_vision_available": False,
        "ocr_local_advanced_available": False,
        "ocr_local_advanced_model": "PP-OCRv6_tiny",
        "hotkey_selection": "alt+e",
        "hotkey_ocr": "alt+w",
        "hotkey_live_ocr": "alt+q",
        "env_file": "",
        "ocr_standard_ready": False,
        "ocr_standard_base_url": "https://api.ocr.space/parse/image",
        "ocr_standard_api_key_set": False,
        "ocr_standard_engine": 2,
        "ocr_standard_max_image_bytes": 1_000_000,
        "ocr_advanced_ready": False,
    }
    payload.update(overrides)
    return ConfigStatus(**payload)


def test_config_check_does_not_construct_model_clients() -> None:
    assert _needs_runtime(["config-check"]) is False
    assert _needs_runtime(["--version"]) is False
    assert _needs_runtime(["ocr", "--image", "page.png"]) is True
    assert _needs_runtime(["ocr-translate", "--pages", "a.png"]) is True
    assert _needs_runtime(["text", "hello"]) is True
    assert _needs_runtime(["listen"]) is True
    assert _needs_runtime(["app"]) is True
    assert _needs_windows_ui(["ocr-translate", "--screenshot"]) is True
    assert _needs_windows_ui(["ocr", "--image", "page.png"]) is False
    assert _needs_windows_ui(["text", "app"]) is False
    assert _needs_windows_ui(["ocr", "--image", "listen"]) is False


def test_app_config_check_does_not_create_httpx_client(
    monkeypatch,
    capsys,
) -> None:
    from ai_translate.app import main

    def boom(*_args, **_kwargs):
        raise AssertionError("httpx.Client must not be created")

    monkeypatch.setattr("ai_translate.infrastructure.ocr_client.httpx.Client", boom)
    monkeypatch.setattr(
        "ai_translate.infrastructure.translate_client.httpx.Client",
        boom,
    )
    assert main(["config-check"]) == 0
    output = capsys.readouterr().out
    assert "translate:" in output
    assert "ocr:" in output


def test_config_check_masks_secrets_and_exits_zero(capsys) -> None:
    status = _status(
        translate_ready=True,
        translate_base_url="https://translate.example/v1",
        translate_model="translate-model",
        translate_router_thinking=False,
        translate_api_key_set=True,
        ocr_ready=True,
        ocr_base_url="https://ocr.example/v1",
        ocr_model="ocr-model",
        ocr_api_key_set=True,
        ocr_standard_ready=True,
        ocr_standard_api_key_set=True,
        ocr_advanced_ready=True,
        ocr_router_thinking=False,
    )

    code = run(["config-check"], status)
    output = capsys.readouterr().out

    assert code == 0
    assert "ready: true" in output
    assert "api_key: set" in output
    assert "translate-secret" not in output
    assert "ocr-secret" not in output
    assert "https://translate.example/v1" in output
    assert "router_thinking: false" in output
    assert output.count("router_thinking: false") == 2
    assert "https://ocr.example/v1" in output
    assert "https://api.ocr.space/parse/image" in output


def test_config_check_reports_empty_unready_state(capsys) -> None:
    code = run(["config-check"], _status())
    output = capsys.readouterr().out

    assert code == 0
    assert "ready: false" in output
    assert "base_url: (empty)" in output
    assert "api_key: unset" in output
    assert "max_image_bytes: 1000000" in output


def test_format_config_status_never_contains_secret_values() -> None:
    rendered = format_config_status(
        _status(translate_api_key_set=True, ocr_api_key_set=True)
    )
    assert "set" in rendered
    assert "sk-" not in rendered
    assert "Bearer" not in rendered
    assert "provider: openai" in rendered
    assert "live_ocr: alt+q" in rendered
    assert "engine: auto" in rendered
    assert "image_mode: auto" in rendered
    assert "max_tokens: 24000" in rendered
    assert "standard:" in rendered
    assert "advanced:" in rendered
    assert "local:" in rendered
    assert "api:" in rendered
    assert "selection: alt+e" in rendered
    assert "ocr: alt+w" in rendered
    assert "env_file:" in rendered


def test_ocr_command_prints_cleaned_text(tmp_path: Path, capsys) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"png-bytes")
    services = CliServices(
        ocr=FakeOcrEngine(text="Hello"),
        load_image=load_image_file,
    )

    code = run(["ocr", "--image", str(image)], _status(ocr_ready=True), services)
    output = capsys.readouterr()

    assert code == 0
    assert output.out.strip() == "Hello"
    assert "png-bytes" not in output.out
    assert "png-bytes" not in output.err


def test_ocr_command_missing_file_does_not_call_engine(tmp_path: Path, capsys) -> None:
    engine = FakeOcrEngine()
    services = CliServices(ocr=engine, load_image=load_image_file)

    code = run(
        ["ocr", "--image", str(tmp_path / "missing.png")],
        _status(ocr_ready=True),
        services,
    )
    output = capsys.readouterr()

    assert code == 2
    assert output.err.strip() == "image_not_found"
    assert engine.calls == []


def test_ocr_translate_command_prints_translation(tmp_path: Path, capsys) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"png-bytes")
    services = CliServices(
        ocr_translate=OcrTranslateService(
            FakeOcrEngine(text="Hello"),
            FakeTranslator(translated_text="你好"),
        ),
        load_image=load_image_file,
    )

    code = run(
        ["ocr-translate", "--image", str(image)],
        _status(ocr_ready=True, translate_ready=True),
        services,
    )
    output = capsys.readouterr()

    assert code == 0
    assert output.out.strip() == "你好"


def test_ocr_translate_partial_keeps_ocr_text(tmp_path: Path, capsys) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"png-bytes")
    services = CliServices(
        ocr_translate=OcrTranslateService(
            FakeOcrEngine(text="Hello"),
            FakeTranslator(
                translated_text=None,
                status=JobStatus.FAILURE,
                error="timeout",
            ),
        ),
        load_image=load_image_file,
    )

    code = run(
        ["ocr-translate", "--image", str(image)],
        _status(ocr_ready=True, translate_ready=True),
        services,
    )
    output = capsys.readouterr()

    assert code == 1
    assert output.err.strip() == "timeout"
    assert output.out.strip() == "Hello"


def test_text_command_prints_translation(capsys) -> None:
    services = CliServices(
        selection=SelectionTranslateService(FakeTranslator(translated_text="你好")),
    )
    code = run(["text", "Hello"], _status(translate_ready=True), services)
    output = capsys.readouterr()
    assert code == 0
    assert output.out.strip() == "你好"


def test_ocr_screenshot_uses_capture_region(capsys) -> None:
    captured: list[int] = []

    def capture_region() -> tuple[bytes, str]:
        captured.append(1)
        return b"png-bytes", "image/png"

    services = CliServices(
        ocr=FakeOcrEngine(text="Hello"),
        capture_region=capture_region,
    )
    code = run(["ocr", "--screenshot"], _status(ocr_ready=True), services)
    assert code == 0
    assert captured == [1]
    assert capsys.readouterr().out.strip() == "Hello"


def test_ocr_screenshot_cancelled_does_not_call_engine(capsys) -> None:
    engine = FakeOcrEngine()

    def capture_region() -> tuple[bytes, str]:
        raise ImageSourceError("screenshot_cancelled")

    services = CliServices(ocr=engine, capture_region=capture_region)
    code = run(["ocr", "--screenshot"], _status(ocr_ready=True), services)
    assert code == 2
    assert capsys.readouterr().err.strip() == "screenshot_cancelled"
    assert engine.calls == []


def test_listen_command_uses_injected_starter() -> None:
    called = {"n": 0}

    def start_listener() -> int:
        called["n"] += 1
        return 0

    code = run(["listen"], _status(), CliServices(start_listener=start_listener))
    assert code == 0
    assert called["n"] == 1


def test_app_command_uses_injected_starter() -> None:
    called = {"n": 0}

    def start_app() -> int:
        called["n"] += 1
        return 0

    code = run(["app"], _status(), CliServices(start_app=start_app))
    assert code == 0
    assert called["n"] == 1
