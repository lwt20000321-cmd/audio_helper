"""
GET /health — 健康检查。
不依赖外部服务，密钥未填写时同样返回 200。
"""

import uuid
from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health", summary="健康检查")
async def health_check(request: Request) -> dict:
    # request_id 优先复用 main.py 中间件生成的编号，保持全链路一致；
    # 兜底分支仅用于绕过中间件直接调用的极端情况（如单元测试不经过 ASGI 栈）。
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return {
        "request_id": request_id,
        "data": {"status": "ok"},
    }
