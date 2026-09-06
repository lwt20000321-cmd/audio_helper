"""
POST /asr — 语音识别。

请求体：{"audio_id": "..."}
响应 data：{"text": "识别出的用户原话"}

流程：读取 audio_id 对应录音（校验存在性与 24 小时有效期）→ 调用百炼 ASR →
返回识别文字。不使用固定文本代替真实识别结果。
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from services.bailian_asr import transcribe
from services.storage import load_audio_file

router = APIRouter(tags=["asr"])


class AsrRequest(BaseModel):
    audio_id: str


@router.post("/asr", summary="语音识别")
async def asr(request: Request, body: AsrRequest) -> dict:
    content, ext = load_audio_file(body.audio_id, stage="asr")
    text = await transcribe(content, ext)

    return {
        "request_id": request.state.request_id,
        "data": {"text": text},
    }
