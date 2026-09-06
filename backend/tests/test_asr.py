"""
POST /asr 路由测试。

只覆盖 audio_id 存在性/有效期校验与请求结构校验；真实识别调用通过
monkeypatch 替换为假函数，不发出真实网络请求，不产生调用费用。
"""

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

import api.asr as asr_module
from config import get_settings
from main import app

client = TestClient(app)


def _write_fake_audio(audio_id: str, created_at: float, ext: str = "webm") -> None:
    settings = get_settings()
    audio_dir = Path(settings.storage_dir) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    (audio_dir / f"{audio_id}.{ext}").write_bytes(b"fake-audio-bytes")
    meta = {
        "created_at": created_at,
        "duration_sec": 3.0,
        "size_bytes": 16,
        "ext": ext,
    }
    (audio_dir / f"{audio_id}.meta.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )


def test_asr_audio_id_not_found_returns_404():
    response = client.post("/asr", json={"audio_id": "aud_does_not_exist"})
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert body["error"]["stage"] == "asr"
    assert "request_id" in body


def test_asr_audio_id_expired_returns_404():
    audio_id = "aud_expired_test"
    _write_fake_audio(audio_id, created_at=time.time() - 90_000)  # 超过 24 小时

    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_asr_missing_audio_id_field_returns_422():
    response = client.post("/asr", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert body["error"]["stage"] == "asr"


def test_asr_success_with_mocked_transcribe(monkeypatch):
    audio_id = "aud_valid_test"
    _write_fake_audio(audio_id, created_at=time.time())

    async def fake_transcribe(content: bytes, ext: str) -> str:
        return "识别出的文字内容"

    monkeypatch.setattr(asr_module, "transcribe", fake_transcribe)

    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["text"] == "识别出的文字内容"
    assert "request_id" in body
