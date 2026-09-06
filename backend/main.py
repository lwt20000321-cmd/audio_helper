"""
FastAPI 服务入口。
启动时确保 storage 子目录存在；后续各轮次的接口逐步在此注册。
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.health import router as health_router
from config import get_settings

# ── 日志配置 ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── 生命周期：启动初始化 ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    storage = Path(settings.storage_dir)

    # 确保临时存储目录存在
    (storage / "audio").mkdir(parents=True, exist_ok=True)
    (storage / "search").mkdir(parents=True, exist_ok=True)
    logger.info("存储目录已就绪: %s", storage.resolve())

    yield
    # 后续可在此添加优雅关闭逻辑


# ── 应用实例 ──────────────────────────────────────────────
app = FastAPI(
    title="语音约碰面地点 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS：仅放行前端本地开发地址
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由注册 ──────────────────────────────────────────────
app.include_router(health_router)


# ── 本地直接运行入口 ───────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8003, reload=True)
