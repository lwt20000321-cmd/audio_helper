"""
DeepSeek 信息提取：调用模型、校验 JSON 结构、再校验业务完整性。

调用约定（官方文档 / 已确认方案）：
- POST {DEEPSEEK_BASE_URL}/chat/completions
- model = deepseek-v4-flash
- response_format = {"type": "json_object"}
- 关闭思考：请求体带 thinking={"type":"disabled"}
  （官方写法；若真实联调发现无效，再改配置，不在本轮猜测第二种写法）

分层：
1. 非法 JSON / 缺字段 / 类型错误 → 502 MODEL_OUTPUT_INVALID（模型异常，不是用户没说清）
2. 结构合法后再做业务完整性：人数、地址、跨城 → 422
3. 完整时只返回五个业务字段
"""

import json
import logging
import re

import httpx
from pydantic import ValidationError

from config import get_settings
from errors import AppError
from prompts.extract import EXTRACT_SYSTEM_PROMPT, build_extract_user_prompt
from schemas import ExtractData, ExtractModelOutput

logger = logging.getLogger(__name__)

EXTRACT_HTTP_TIMEOUT_SECONDS = 15.0
STAGE = "extract"

# 确认产品规则：不把这些含糊说法当成可定位地址。
_VAGUE_ADDRESSES = {
    "家",
    "我家",
    "你家",
    "他家",
    "公司",
    "单位",
    "学校",
    "宿舍",
}

_CATEGORY_ALIASES = {
    "喝咖啡": "咖啡店",
    "咖啡": "咖啡店",
    "咖啡厅": "咖啡店",
    "咖啡馆": "咖啡店",
}

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


async def extract_meeting_info(
    text: str,
    default_city: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ExtractData:
    settings = get_settings()
    api_key = (
        settings.deepseek_api_key.strip()
        .replace("\r", "")
        .replace("\n", "")
    )
    if not api_key:
        raise AppError(
            code="EXTERNAL_SERVICE_ERROR",
            message="信息提取服务未配置密钥，请在 backend/.env 填写 DEEPSEEK_API_KEY 后重启服务",
            stage=STAGE,
            status_code=502,
        )
    if not api_key.isascii() or any(ord(ch) < 32 for ch in api_key):
        raise AppError(
            code="EXTERNAL_SERVICE_ERROR",
            message="信息提取密钥含非法字符，请检查 .env 中 DEEPSEEK_API_KEY 后重启服务",
            stage=STAGE,
            status_code=502,
        )

    url = f"{settings.deepseek_base_url}/chat/completions"
    payload = {
        "model": settings.extract_model,
        "messages": [
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_extract_user_prompt(text, default_city),
            },
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info("调用 DeepSeek 提取: model=%s", settings.extract_model)

    async with httpx.AsyncClient(
        timeout=EXTRACT_HTTP_TIMEOUT_SECONDS, transport=transport
    ) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            logger.warning("DeepSeek 提取请求超时")
            raise AppError(
                code="EXTERNAL_SERVICE_TIMEOUT",
                message="信息提取超时，请稍后重试",
                stage=STAGE,
                status_code=504,
            )
        except httpx.LocalProtocolError:
            logger.warning("DeepSeek 提取请求协议错误 LocalProtocolError")
            raise AppError(
                code="EXTERNAL_SERVICE_ERROR",
                message="信息提取请求头不合法，请检查 .env 中 DEEPSEEK_API_KEY 后重启服务",
                stage=STAGE,
                status_code=502,
            )
        except httpx.RequestError as exc:
            logger.warning("DeepSeek 提取请求异常: %s", type(exc).__name__)
            raise AppError(
                code="EXTERNAL_SERVICE_ERROR",
                message="信息提取服务异常，请稍后重试",
                stage=STAGE,
                status_code=502,
            )

    if resp.status_code != 200:
        error_code = None
        try:
            error_body = resp.json()
            if isinstance(error_body, dict):
                error_code = error_body.get("code") or error_body.get("error")
        except ValueError:
            error_code = None
        logger.warning(
            "DeepSeek 提取返回非 200 状态码: %s error=%s",
            resp.status_code,
            error_code,
        )
        raise AppError(
            code="EXTERNAL_SERVICE_ERROR",
            message="信息提取服务异常，请稍后重试",
            stage=STAGE,
            status_code=502,
        )

    try:
        data = resp.json()
        raw_content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError, TypeError):
        logger.warning("DeepSeek 提取 HTTP 响应结构不符合预期")
        raise AppError(
            code="MODEL_OUTPUT_INVALID",
            message="信息提取服务返回格式异常，请稍后重试",
            stage=STAGE,
            status_code=502,
        )

    model_output = _parse_model_output(raw_content)
    return _evaluate_business_completeness(model_output, default_city)


def _parse_model_output(raw_content: object) -> ExtractModelOutput:
    """结构校验：失败一律 502，不视为用户信息不足。"""
    if not isinstance(raw_content, str):
        logger.warning("DeepSeek 提取 content 不是字符串")
        raise AppError(
            code="MODEL_OUTPUT_INVALID",
            message="信息提取服务返回格式异常，请稍后重试",
            stage=STAGE,
            status_code=502,
        )

    text = raw_content.strip()
    if not text:
        logger.warning("DeepSeek 提取 content 为空")
        raise AppError(
            code="MODEL_OUTPUT_INVALID",
            message="信息提取服务返回格式异常，请稍后重试",
            stage=STAGE,
            status_code=502,
        )

    parsed = _loads_json_object(text)
    try:
        return ExtractModelOutput.model_validate(parsed)
    except ValidationError:
        logger.warning("DeepSeek 提取 JSON 字段类型或必填项不符合约定")
        raise AppError(
            code="MODEL_OUTPUT_INVALID",
            message="信息提取服务返回格式异常，请稍后重试",
            stage=STAGE,
            status_code=502,
        )


def _loads_json_object(text: str) -> dict:
    candidates = [text, _FENCE_RE.sub("", text).strip()]
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed
        last_error = ValueError("JSON 根节点不是对象")

    logger.warning("DeepSeek 提取输出不是合法 JSON 对象: %s", type(last_error).__name__)
    raise AppError(
        code="MODEL_OUTPUT_INVALID",
        message="信息提取服务返回格式异常，请稍后重试",
        stage=STAGE,
        status_code=502,
    )


def _evaluate_business_completeness(
    model_output: ExtractModelOutput, default_city: str
) -> ExtractData:
    city_a = _normalize_city(model_output.city_a, default_city)
    city_b = _normalize_city(model_output.city_b, default_city)
    address_a = _normalize_address(model_output.address_a)
    address_b = _normalize_address(model_output.address_b)
    category = _normalize_category(model_output.category)

    logger.info(
        "提取结构校验通过 party_count=%s incomplete_reason=%s",
        model_output.party_count,
        model_output.incomplete_reason,
    )

    if model_output.party_count != 2:
        raise AppError(
            code="EXTRACT_PARTY_COUNT_MISMATCH",
            message="当前版本只支持两人约碰面，请重新描述",
            stage=STAGE,
            status_code=422,
        )

    if address_a is None or address_b is None:
        raise AppError(
            code="EXTRACT_MISSING_ADDRESS",
            message="只听到了一方的位置，请同时告诉我两人各在哪里",
            stage=STAGE,
            status_code=422,
        )

    if city_a is None or city_b is None:
        raise AppError(
            code="EXTRACT_MISSING_ADDRESS",
            message="无法确定两人所在城市，请重新说明城市和具体地点",
            stage=STAGE,
            status_code=422,
        )

    if _city_key(city_a) != _city_key(city_b):
        raise AppError(
            code="EXTRACT_CROSS_CITY",
            message="两人所在城市不同，当前版本只支持同城搜索",
            stage=STAGE,
            status_code=422,
        )

    return ExtractData(
        city_a=city_a,
        address_a=address_a,
        city_b=city_b,
        address_b=address_b,
        category=category,
    )


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_city(value: str | None, default_city: str) -> str | None:
    city = _blank_to_none(value)
    if city is None:
        return _blank_to_none(default_city)
    return city


def _normalize_address(value: str | None) -> str | None:
    address = _blank_to_none(value)
    if address is None:
        return None
    if address in _VAGUE_ADDRESSES:
        return None
    return address


def _normalize_category(value: str | None) -> str:
    category = _blank_to_none(value)
    if category is None:
        return "咖啡店"
    return _CATEGORY_ALIASES.get(category, category)


def _city_key(city: str) -> str:
    """比较城市时去掉末尾「市」，避免「杭州」与「杭州市」被判跨城。"""
    key = city.strip()
    if key.endswith("市") and len(key) > 1:
        key = key[:-1]
    return key
