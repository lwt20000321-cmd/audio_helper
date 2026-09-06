"""
POST /upload — 上传录音。

请求：multipart/form-data，字段名 file。
响应 data：{"audio_id": "..."}

校验顺序（先物理有效性，再语义有效性）：
1. 大小（> 5MB → 413；空文件 → 415）
2. 真实容器/编码可解析（PyAV）→ 不可解析或无音频轨 → 415
3. 时长探测 → 无法确定 → 415；超出 1-60 秒范围 → 422
"""

from fastapi import APIRouter, File, Request, UploadFile

from errors import AppError
from services.audio_validator import validate_audio
from services.storage import save_audio_file

router = APIRouter(tags=["upload"])

MAX_SIZE_BYTES = 5 * 1024 * 1024


@router.post("/upload", summary="上传录音")
async def upload_audio(request: Request, file: UploadFile = File(...)) -> dict:
    content = await file.read()

    if len(content) == 0:
        raise AppError(
            code="AUDIO_FORMAT_UNSUPPORTED",
            message="上传的文件为空",
            stage="upload",
            status_code=415,
        )

    if len(content) > MAX_SIZE_BYTES:
        raise AppError(
            code="AUDIO_TOO_LARGE",
            message="录音文件不能超过 5 MB",
            stage="upload",
            status_code=413,
        )

    duration_sec, ext = validate_audio(content)
    audio_id = save_audio_file(content, duration_sec, ext)

    return {
        "request_id": request.state.request_id,
        "data": {"audio_id": audio_id},
    }
