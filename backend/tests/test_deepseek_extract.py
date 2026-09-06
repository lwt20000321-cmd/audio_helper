"""
services/deepseek_extract 单元测试。

使用 httpx.MockTransport，不发出真实网络请求，不产生调用费用。
"""

import json

import httpx
import pytest

from errors import AppError
from services.deepseek_extract import extract_meeting_info


def _complete_payload(**overrides) -> dict:
    payload = {
        "city_a": "杭州",
        "address_a": "杭州东站",
        "city_b": "杭州",
        "address_b": "西湖龙翔桥地铁站",
        "category": "咖啡店",
        "party_count": 2,
        "incomplete_reason": None,
    }
    payload.update(overrides)
    return payload


def _transport_with_content(content: object) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": content}}]}
        )

    return httpx.MockTransport(handler)


def _transport_with_json(payload: dict) -> httpx.MockTransport:
    return _transport_with_content(json.dumps(payload, ensure_ascii=False))


@pytest.fixture(autouse=True)
def fake_deepseek_settings(monkeypatch):
    class FakeSettings:
        deepseek_api_key = "sk-test-key"
        deepseek_base_url = "https://api.deepseek.com/v1"
        extract_model = "deepseek-v4-flash"

    monkeypatch.setattr(
        "services.deepseek_extract.get_settings", lambda: FakeSettings()
    )


@pytest.mark.asyncio
async def test_extract_success_returns_five_fields():
    result = await extract_meeting_info(
        "我在杭州东站，朋友在西湖龙翔桥地铁站",
        "杭州",
        transport=_transport_with_json(_complete_payload()),
    )
    assert result.model_dump() == {
        "city_a": "杭州",
        "address_a": "杭州东站",
        "city_b": "杭州",
        "address_b": "西湖龙翔桥地铁站",
        "category": "咖啡店",
    }


@pytest.mark.asyncio
async def test_extract_normalizes_coffee_category():
    result = await extract_meeting_info(
        "帮我们喝咖啡",
        "杭州",
        transport=_transport_with_json(_complete_payload(category="喝咖啡")),
    )
    assert result.category == "咖啡店"


@pytest.mark.asyncio
async def test_extract_same_city_with_shi_suffix():
    result = await extract_meeting_info(
        "同城",
        "杭州",
        transport=_transport_with_json(
            _complete_payload(city_a="杭州", city_b="杭州市")
        ),
    )
    assert result.city_a == "杭州"
    assert result.city_b == "杭州市"


@pytest.mark.asyncio
async def test_extract_party_count_mismatch():
    with pytest.raises(AppError) as exc_info:
        await extract_meeting_info(
            "三个人",
            "杭州",
            transport=_transport_with_json(_complete_payload(party_count=3)),
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "EXTRACT_PARTY_COUNT_MISMATCH"


@pytest.mark.asyncio
async def test_extract_missing_address():
    with pytest.raises(AppError) as exc_info:
        await extract_meeting_info(
            "只有我在西湖",
            "杭州",
            transport=_transport_with_json(
                _complete_payload(address_b=None, party_count=2)
            ),
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "EXTRACT_MISSING_ADDRESS"


@pytest.mark.asyncio
async def test_extract_vague_home_address():
    with pytest.raises(AppError) as exc_info:
        await extract_meeting_info(
            "我在我家，朋友在公司",
            "杭州",
            transport=_transport_with_json(
                _complete_payload(address_a="我家", address_b="公司")
            ),
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "EXTRACT_MISSING_ADDRESS"


@pytest.mark.asyncio
async def test_extract_cross_city():
    with pytest.raises(AppError) as exc_info:
        await extract_meeting_info(
            "杭州和上海",
            "杭州",
            transport=_transport_with_json(
                _complete_payload(city_a="杭州", city_b="上海")
            ),
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "EXTRACT_CROSS_CITY"


@pytest.mark.asyncio
async def test_extract_invalid_json_is_model_error_not_user_error():
    with pytest.raises(AppError) as exc_info:
        await extract_meeting_info(
            "任意文字",
            "杭州",
            transport=_transport_with_content("这不是 JSON"),
        )
    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "MODEL_OUTPUT_INVALID"


@pytest.mark.asyncio
async def test_extract_missing_model_field_is_model_error():
    payload = _complete_payload()
    del payload["party_count"]
    with pytest.raises(AppError) as exc_info:
        await extract_meeting_info(
            "任意文字",
            "杭州",
            transport=_transport_with_json(payload),
        )
    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "MODEL_OUTPUT_INVALID"


@pytest.mark.asyncio
async def test_extract_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout")

    with pytest.raises(AppError) as exc_info:
        await extract_meeting_info(
            "任意文字",
            "杭州",
            transport=httpx.MockTransport(handler),
        )
    assert exc_info.value.status_code == 504
    assert exc_info.value.code == "EXTERNAL_SERVICE_TIMEOUT"
