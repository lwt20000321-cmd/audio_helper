"""
POST /extract 路由测试。

真实 DeepSeek 调用通过 monkeypatch 替换，不产生调用费用。
"""

from fastapi.testclient import TestClient

import api.extract as extract_module
from errors import AppError
from main import app
from schemas import ExtractData

client = TestClient(app)


def test_extract_missing_fields_returns_422():
    response = client.post("/extract", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert body["error"]["stage"] == "extract"
    assert "request_id" in body


def test_extract_success_returns_five_fields(monkeypatch):
    async def fake_extract(text: str, city: str) -> ExtractData:
        return ExtractData(
            city_a="杭州",
            address_a="杭州东站",
            city_b="杭州",
            address_b="西湖龙翔桥地铁站",
            category="咖啡店",
        )

    monkeypatch.setattr(extract_module, "extract_meeting_info", fake_extract)

    response = client.post(
        "/extract",
        json={
            "text": "我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间的咖啡店",
            "city": "杭州",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body["data"].keys()) == {
        "city_a",
        "address_a",
        "city_b",
        "address_b",
        "category",
    }
    assert "party_count" not in body["data"]
    assert "incomplete_reason" not in body["data"]


def test_extract_business_error_passthrough(monkeypatch):
    async def fake_extract(text: str, city: str) -> ExtractData:
        raise AppError(
            code="EXTRACT_CROSS_CITY",
            message="两人所在城市不同，当前版本只支持同城搜索",
            stage="extract",
            status_code=422,
        )

    monkeypatch.setattr(extract_module, "extract_meeting_info", fake_extract)

    response = client.post(
        "/extract",
        json={"text": "我在杭州，朋友在上海", "city": "杭州"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "EXTRACT_CROSS_CITY"
    assert body["error"]["stage"] == "extract"
