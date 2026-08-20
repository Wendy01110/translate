from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ai_translate.config import LocalAdvancedOcrSettings
from ai_translate.core.models import JobStatus
from ai_translate.infrastructure.paddle_ocr import PaddleOcrEngine


class _Prediction:
    def __init__(self, texts: list[str], scores: list[float]) -> None:
        self.json = {"res": {"rec_texts": texts, "rec_scores": scores}}


class _Pipeline:
    def __init__(self, predictions: list[_Prediction]) -> None:
        self.predictions = predictions
        self.calls: list[Any] = []

    def predict(self, image: Any) -> list[_Prediction]:
        self.calls.append(image)
        return self.predictions


def test_paddle_ocr_is_lazy_and_extracts_text_and_confidence() -> None:
    created: list[dict[str, Any]] = []
    pipeline = _Pipeline([_Prediction(["第一行", "Second"], [0.9, 0.7])])

    def factory(**kwargs: Any) -> _Pipeline:
        created.append(kwargs)
        return pipeline

    engine = PaddleOcrEngine(
        LocalAdvancedOcrSettings(model_tier="small", _env_file=None),
        factory=factory,
        decoder=lambda _data: "decoded-image",
    )
    assert created == []

    result = engine.recognize(b"png", "image/png")

    assert result.status is JobStatus.SUCCESS
    assert result.text == "第一行\nSecond"
    assert result.model == "PP-OCRv6_small"
    assert result.engine == "paddle"
    assert result.confidence == 0.8
    assert pipeline.calls == ["decoded-image"]
    assert created == [
        {
            "text_detection_model_name": "PP-OCRv6_small_det",
            "text_recognition_model_name": "PP-OCRv6_small_rec",
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
            "device": "cpu",
        }
    ]


def test_paddle_ocr_reuses_pipeline_across_pages_and_calls() -> None:
    create_count = 0
    pipeline = _Pipeline([_Prediction(["page"], [0.75])])

    def factory(**_kwargs: Any) -> _Pipeline:
        nonlocal create_count
        create_count += 1
        return pipeline

    engine = PaddleOcrEngine(
        LocalAdvancedOcrSettings(_env_file=None),
        factory=factory,
        decoder=lambda data: data.decode("ascii"),
    )

    first = engine.recognize_pages(
        [(b"one", "image/png"), (b"two", "image/png")]
    )
    second = engine.recognize(b"three", "image/png")

    assert first.text == "page\npage"
    assert second.text == "page"
    assert create_count == 1
    assert pipeline.calls == ["one", "two", "three"]


def test_paddle_ocr_notifies_once_before_first_pipeline_initialization() -> None:
    events: list[str] = []
    pipeline = _Pipeline([_Prediction(["page"], [0.75])])

    def factory(**_kwargs: Any) -> _Pipeline:
        events.append("factory")
        return pipeline

    engine = PaddleOcrEngine(
        LocalAdvancedOcrSettings(model_tier="tiny", _env_file=None),
        factory=factory,
        decoder=lambda data: data,
        on_first_load=lambda model: events.append(f"notify:{model}"),
    )

    engine.recognize(b"one", "image/png")
    engine.recognize(b"two", "image/png")

    assert events == ["notify:PP-OCRv6_tiny", "factory"]


def test_paddle_ocr_notifies_once_during_concurrent_first_calls() -> None:
    notices: list[str] = []
    create_count = 0
    pipeline = _Pipeline([_Prediction(["page"], [0.75])])

    def factory(**_kwargs: Any) -> _Pipeline:
        nonlocal create_count
        create_count += 1
        return pipeline

    engine = PaddleOcrEngine(
        LocalAdvancedOcrSettings(_env_file=None),
        factory=factory,
        decoder=lambda data: data,
        on_first_load=notices.append,
    )

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda index: engine.recognize(bytes([index]), "image/png"),
                range(1, 5),
            )
        )

    assert all(result.status is JobStatus.SUCCESS for result in results)
    assert create_count == 1
    assert notices == ["PP-OCRv6_tiny"]


def test_paddle_ocr_does_not_repeat_notice_when_initialization_is_retried() -> None:
    notices: list[str] = []
    attempts = 0

    def factory(**_kwargs: Any) -> Any:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("init failed")

    engine = PaddleOcrEngine(
        LocalAdvancedOcrSettings(_env_file=None),
        factory=factory,
        decoder=lambda data: data,
        on_first_load=notices.append,
    )

    first = engine.recognize(b"one", "image/png")
    second = engine.recognize(b"two", "image/png")

    assert first.error == "paddle_ocr_init_failed"
    assert second.error == "paddle_ocr_init_failed"
    assert attempts == 2
    assert notices == ["PP-OCRv6_tiny"]


def test_paddle_ocr_ignores_first_load_notifier_failure() -> None:
    pipeline = _Pipeline([_Prediction(["page"], [0.75])])

    def failed_notice(_model: str) -> None:
        raise RuntimeError("presenter unavailable")

    engine = PaddleOcrEngine(
        LocalAdvancedOcrSettings(_env_file=None),
        factory=lambda **_kwargs: pipeline,
        decoder=lambda data: data,
        on_first_load=failed_notice,
    )

    result = engine.recognize(b"png", "image/png")

    assert result.status is JobStatus.SUCCESS
    assert result.text == "page"


def test_paddle_ocr_returns_stable_failure_without_leaking_exception() -> None:
    def factory(**_kwargs: Any) -> Any:
        raise RuntimeError("secret local path")

    engine = PaddleOcrEngine(
        LocalAdvancedOcrSettings(_env_file=None),
        factory=factory,
        decoder=lambda data: data,
    )

    result = engine.recognize(b"png", "image/png")

    assert result.status is JobStatus.FAILURE
    assert result.error == "paddle_ocr_init_failed"
    assert "secret" not in (result.error or "")


def test_paddle_ocr_rejects_empty_input_before_initialization() -> None:
    def factory(**_kwargs: Any) -> Any:
        raise AssertionError("must not initialize")

    engine = PaddleOcrEngine(
        LocalAdvancedOcrSettings(_env_file=None),
        factory=factory,
        decoder=lambda data: data,
    )

    result = engine.recognize(b"", "image/png")

    assert result.status is JobStatus.FAILURE
    assert result.error == "empty_image"
