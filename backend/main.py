"""
FastAPI 服务入口。
启动时确保 storage 子目录存在；后续各轮次的接口逐步在此注册。
"""

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.health import router as health_router
from api.upload import router as upload_router
from config import get_settings
from errors import AppError

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


# ── request_id 中间件 ──────────────────────────────────────
# 每个请求生成唯一 request_id，供成功响应和异常处理器共用，
# 保证同一次请求在日志、成功/错误响应中的编号一致。
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    return response


# ── 错误阶段映射 ────────────────────────────────────────────
def _stage_from_path(path: str) -> str:
    if path.startswith("/upload"):
        return "upload"
    if path.startswith("/asr"):
        return "asr"
    if path.startswith("/extract"):
        return "extract"
    if path.startswith("/search"):
        return "search"
    if path.startswith("/finalize"):
        return "finalize"
    if path.startswith("/audio"):
        return "audio_download"
    return "unknown"


# ── 全局异常处理器 ──────────────────────────────────────────
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.warning(
        "业务错误 stage=%s code=%s message=%s", exc.stage, exc.code, exc.message
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": request_id,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "stage": exc.stage,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    stage = _stage_from_path(request.url.path)

    message = "请求参数不合法，请检查字段"
    if stage == "upload" and any(
        "file" in str(err.get("loc", ())) for err in exc.errors()
    ):
        message = "请求缺少录音文件"

    logger.warning("请求校验失败 stage=%s path=%s", stage, request.url.path)
    return JSONResponse(
        status_code=422,
        content={
            "request_id": request_id,
            "error": {
                "code": "REQUEST_VALIDATION_ERROR",
                "message": message,
                "stage": stage,
            },
        },
    )


# ── 路由注册 ──────────────────────────────────────────────
app.include_router(health_router)
app.include_router(upload_router)


# ── 本地直接运行入口 ───────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8003, reload=True)
