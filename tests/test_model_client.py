import pytest

from app.config import SETTINGS
from app.model_client import FatalError, MockModelClient, ThrottleError, complete_with_retry


def test_retries_on_throttle_then_succeeds():
    model = MockModelClient(
        [
            ThrottleError("429"),
            ThrottleError("429"),
            '{"intent": "final", "answer": "hi"}',
        ]
    )

    result = complete_with_retry(model, messages=[], settings=SETTINGS)

    assert result == '{"intent": "final", "answer": "hi"}'
    assert model.calls == 3


def test_fatal_error_is_not_retried():
    model = MockModelClient([FatalError("bad key"), '{"intent": "final", "answer": "hi"}'])

    with pytest.raises(FatalError):
        complete_with_retry(model, messages=[], settings=SETTINGS)

    assert model.calls == 1


def test_throttle_error_propagates_once_retries_are_exhausted():
    from dataclasses import replace

    tight_settings = replace(SETTINGS, model_max_retries=1, model_backoff_base_seconds=0.001)
    model = MockModelClient([ThrottleError("429"), ThrottleError("429"), ThrottleError("429")])

    with pytest.raises(ThrottleError):
        complete_with_retry(model, messages=[], settings=tight_settings)

    assert model.calls == 2  # 1 initial call + 1 retry, then it gives up