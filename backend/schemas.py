"""
全局请求与响应数据结构。
所有业务接口的响应均使用 SuccessResponse 或 ErrorResponse 包装。
音频下载接口（GET /audio/{audio_id}）返回二进制流，不使用本文件的结构。
"""

from typing import Any
from pydantic import BaseModel, Field


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


# ── /extract ──────────────────────────────────────────────

class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)


class ExtractData(BaseModel):
    """接口成功时返回给前端的五个业务字段。"""

    city_a: str
    address_a: str
    city_b: str
    address_b: str
    category: str


class ExtractModelOutput(BaseModel):
    """
    模型内部 JSON。结构校验失败视为模型输出异常（502），
    不能解释成用户没说清楚。
    """

    city_a: str | None
    address_a: str | None
    city_b: str | None
    address_b: str | None
    category: str | None
    party_count: int | None
    incomplete_reason: str | None



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
