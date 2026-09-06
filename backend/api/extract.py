"""
POST /extract — 地址与需求提取。

请求体：{"text": "识别出的用户原话", "city": "杭州"}
成功时 data 仅含五个业务字段：city_a、address_a、city_b、address_b、category。
"""

from fastapi import APIRouter, Request

from schemas import ExtractRequest
from services.deepseek_extract import extract_meeting_info

router = APIRouter(tags=["extract"])


@router.post("/extract", summary="地址与需求提取")
async def extract(request: Request, body: ExtractRequest) -> dict:
    result = await extract_meeting_info(body.text, body.city)
    return {
        "request_id": request.state.request_id,
        "data": result.model_dump(),
    }
