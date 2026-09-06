"""
GET /health 接口测试。
使用 FastAPI TestClient（同步），不调用外部服务。
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_structure():
    response = client.get("/health")
    body = response.json()

    # 顶层必须有 request_id 和 data
    assert "request_id" in body, "响应缺少 request_id"
    assert "data" in body, "响应缺少 data"

    # request_id 为非空字符串
    assert isinstance(body["request_id"], str)
    assert len(body["request_id"]) > 0

    # data.status 必须为 "ok"
    assert body["data"]["status"] == "ok"


def test_health_request_id_is_unique():
    """每次调用应返回不同的 request_id（UUID）。"""
    r1 = client.get("/health").json()["request_id"]
    r2 = client.get("/health").json()["request_id"]
    assert r1 != r2
