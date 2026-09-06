"""
services/bailian_asr.transcribe 单元测试。

使用 httpx.MockTransport 模拟百炼响应，不发出真实网络请求，不产生调用费用。
"""

import httpx
import pytest

from errors import AppError
from services.bailian_asr import transcribe


@pytest.fixture(autouse=True)
def fake_bailian_settings(monkeypatch):
    class FakeSettings:
        bailian_api_key = "sk-test-key"
        bailian_compatible_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        asr_model = "qwen3-asr-flash"

    monkeypatch.setattr("services.bailian_asr.get_settings", lambda: FakeSettings())


@pytest.mark.asyncio
async def test_transcribe_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "我在杭州东站"}}]}
        )

    text = await transcribe(b"fake-audio-bytes", "webm", transport=httpx.MockTransport(handler))
    assert text == "我在杭州东站"


@pytest.mark.asyncio
async def test_transcribe_empty_result_raises_422():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]})

    with pytest.raises(AppError) as exc_info:
        await transcribe(b"fake-audio-bytes", "webm", transport=httpx.MockTransport(handler))

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "ASR_EMPTY_RESULT"


@pytest.mark.asyncio
async def test_transcribe_non_200_raises_502():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal server error"})

    with pytest.raises(AppError) as exc_info:
        await transcribe(b"fake-audio-bytes", "webm", transport=httpx.MockTransport(handler))

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "EXTERNAL_SERVICE_ERROR"


@pytest.mark.asyncio
async def test_transcribe_malformed_response_raises_502():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    with pytest.raises(AppError) as exc_info:
        await transcribe(b"fake-audio-bytes", "webm", transport=httpx.MockTransport(handler))

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "EXTERNAL_SERVICE_ERROR"


@pytest.mark.asyncio
async def test_transcribe_timeout_raises_504():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout")

    with pytest.raises(AppError) as exc_info:
        await transcribe(b"fake-audio-bytes", "webm", transport=httpx.MockTransport(handler))

    assert exc_info.value.status_code == 504
    assert exc_info.value.code == "EXTERNAL_SERVICE_TIMEOUT"


@pytest.mark.asyncio
async def test_transcribe_empty_api_key_raises_502(monkeypatch):
    class FakeSettings:
        bailian_api_key = ""
        bailian_compatible_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        asr_model = "qwen3-asr-flash"

    monkeypatch.setattr("services.bailian_asr.get_settings", lambda: FakeSettings())

    with pytest.raises(AppError) as exc_info:
        await transcribe(b"fake-audio-bytes", "webm")

    assert exc_info.value.status_code == 502
    assert "未配置密钥" in exc_info.value.message


@pytest.mark.asyncio
async def test_transcribe_strips_newlines_from_api_key(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "识别成功"}}]}
        )

    class FakeSettings:
        bailian_api_key = "sk-test-key\n"
        bailian_compatible_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        asr_model = "qwen3-asr-flash"

    monkeypatch.setattr("services.bailian_asr.get_settings", lambda: FakeSettings())
    text = await transcribe(
        b"fake-audio-bytes", "webm", transport=httpx.MockTransport(handler)
    )
    assert text == "识别成功"
    assert captured["authorization"] == "Bearer sk-test-key"
    assert "\n" not in captured["authorization"]
    assert "\r" not in captured["authorization"]


@pytest.mark.asyncio
async def test_transcribe_base64_too_large_raises_413(monkeypatch):
    import services.bailian_asr as asr_module

    monkeypatch.setattr(asr_module, "MAX_BASE64_SIZE_BYTES", 10)  # 人为调低阈值触发拦截

    with pytest.raises(AppError) as exc_info:
        await transcribe(b"0123456789012345", "webm")

    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "AUDIO_TOO_LARGE"
