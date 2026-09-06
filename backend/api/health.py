"""
GET /health — 健康检查。
不依赖外部服务，密钥未填写时同样返回 200。
"""

import uuid
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="健康检查")
async def health_check() -> dict:
    return {
        "request_id": str(uuid.uuid4()),
        "data": {"status": "ok"},
    }
