"""
全局请求与响应数据结构。
所有业务接口的响应均使用 SuccessResponse 或 ErrorResponse 包装。
音频下载接口（GET /audio/{audio_id}）返回二进制流，不使用本文件的结构。
"""

from typing import Any
from pydantic import BaseModel


# ── 统一成功响应 ──────────────────────────────────────────

class SuccessResponse(BaseModel):
    request_id: str
    data: Any


# ── 统一错误响应 ──────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str        # 机器可读的错误代号，如 AUDIO_TOO_LARGE
    message: str     # 给用户看的中文提示
    stage: str       # 出错阶段，如 upload / asr / extract / search / finalize


class ErrorResponse(BaseModel):
    request_id: str
    error: ErrorDetail
