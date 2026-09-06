"""
POST /upload 接口测试。

只覆盖不需要真实有效音频编码的异常分支（缺字段、文件过大、格式不支持、空文件）。
"正常上传 → 返回 audio_id" 的分支依赖真实编码的音频数据，本轮不提供合成
fixture（避免依赖 PyAV 编码器/libopus 是否可用带来的不稳定），需由你在
/docs 上使用真实录音文件手动验证。
"""

import io

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_upload_missing_file_returns_422():
    response = client.post("/upload")
    assert response.status_code == 422
    body = response.json()
    assert "request_id" in body
    assert body["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert body["error"]["stage"] == "upload"


def test_upload_empty_file_returns_415():
    files = {"file": ("empty.webm", io.BytesIO(b""), "audio/webm")}
    response = client.post("/upload", files=files)
    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "AUDIO_FORMAT_UNSUPPORTED"
    assert body["error"]["stage"] == "upload"


def test_upload_too_large_returns_413():
    # 大小校验发生在格式校验之前，不需要是有效音频
    big_content = b"0" * (5 * 1024 * 1024 + 1)
    files = {"file": ("big.webm", io.BytesIO(big_content), "audio/webm")}
    response = client.post("/upload", files=files)
    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "AUDIO_TOO_LARGE"
    assert body["error"]["stage"] == "upload"


def test_upload_invalid_format_returns_415():
    garbage = b"this is not a real audio file" * 10
    files = {"file": ("fake.webm", io.BytesIO(garbage), "audio/webm")}
    response = client.post("/upload", files=files)
    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "AUDIO_FORMAT_UNSUPPORTED"
    assert body["error"]["stage"] == "upload"
