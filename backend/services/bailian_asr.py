"""
百炼 qwen3-asr-flash 语音识别调用（北京地域，OpenAI 兼容同步接口）。

官方文档已确认的事实：
- 端点：POST {BAILIAN_COMPATIBLE_URL}/chat/completions
  （即 https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions）
- 认证：Authorization: Bearer $BAILIAN_API_KEY
- 音频以 Data URL 形式传入 messages[].content[].input_audio.data：
    "data:<mime>;base64,<base64编码音频>"
- asr_options.enable_itn 默认 False（是否将中文数字转阿拉伯数字），本项目沿用默认值
- 最长支持 5 分钟音频（本项目上传限制已收紧到 60 秒，远低于该上限）

本项目默认值（非百炼官方文档确认数字，用于提前拦截明显异常，真实上限需
真实调用验证）：
- MAX_BASE64_SIZE_BYTES = 10MB：Base64 编码后体积的防御性上限。
  由于 /upload 已限制原文件 ≤5MB，Base64 编码后体积 ≤ 5MB × 4/3 ≈ 6.7MB，
  正常流程下不会触发此上限；此校验用于防御性拦截（如未来放宽上传限制、
  或存储文件被意外篡改等异常情况）。

响应结构假设（遵循 OpenAI 兼容 chat completions 惯例，未逐字对照官方样例，
真实联调时需确认）：
    {"choices": [{"message": {"content": "识别出的文字"}}], ...}
"""

import base64
import logging

import httpx

from config import get_settings
from errors import AppError

logger = logging.getLogger(__name__)

# 外部调用超时预算（秒）——对应技术方案中 /asr 接口的 25s 外部调用预算
ASR_HTTP_TIMEOUT_SECONDS = 25.0

# Base64 编码体积防御性上限（见模块顶部说明，非百炼官方确认数字）
MAX_BASE64_SIZE_BYTES = 10 * 1024 * 1024

_MIME_BY_EXT = {
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
}


async def transcribe(
    content: bytes,
    ext: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """
    调用百炼 ASR 识别音频文字。

    参数 transport 仅用于单元测试注入 httpx.MockTransport，生产环境不传。

    失败时抛出 AppError：
      - 413：Base64 编码体积超过防御性上限
      - 502：百炼返回非 200 / 响应结构不符合预期
      - 504：请求超时
      - 422：识别结果为空
    """
    settings = get_settings()
    api_key = (
        settings.bailian_api_key.strip()
        .replace("\r", "")
        .replace("\n", "")
    )
    if not api_key:
        raise AppError(
            code="EXTERNAL_SERVICE_ERROR",
            message="语音识别服务未配置密钥，请在 backend/.env 填写 BAILIAN_API_KEY 后重启服务",
            stage="asr",
            status_code=502,
        )
    if not api_key.isascii() or any(ord(ch) < 32 for ch in api_key):
        # HTTP 请求头不允许换行或非 ASCII；常见原因是 .env 粘贴时带了回车。
        raise AppError(
            code="EXTERNAL_SERVICE_ERROR",
            message="语音识别密钥含非法字符，请检查 .env 中 BAILIAN_API_KEY 是否有换行、空格或引号后重启服务",
            stage="asr",
            status_code=502,
        )

    mime = _MIME_BY_EXT.get(ext, "application/octet-stream")
    b64 = base64.b64encode(content).decode("ascii")

    if len(b64) > MAX_BASE64_SIZE_BYTES:
        # 正常流程下不会触发（原文件已被 /upload 限制在 5MB 以内），
        # 这里是防御性拦截，避免向百炼发送异常大的请求体。
        raise AppError(
            code="AUDIO_TOO_LARGE",
            message="录音文件编码后体积过大，请缩短录音时长",
            stage="asr",
            status_code=413,
        )

    url = f"{settings.bailian_compatible_url}/chat/completions"
    payload = {
        "model": settings.asr_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {"data": f"data:{mime};base64,{b64}"},
                    }
                ],
            }
        ],
        "asr_options": {"enable_itn": False},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info(
        "调用百炼 ASR: model=%s ext=%s size_bytes=%d",
        settings.asr_model,
        ext,
        len(content),
    )
    # 注意：绝不记录 headers（含密钥）或 payload（含 Base64 音频）到日志

    async with httpx.AsyncClient(
        timeout=ASR_HTTP_TIMEOUT_SECONDS, transport=transport
    ) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            logger.warning("百炼 ASR 请求超时")
            raise AppError(
                code="EXTERNAL_SERVICE_TIMEOUT",
                message="语音识别超时，请稍后重试",
                stage="asr",
                status_code=504,
            )
        except httpx.LocalProtocolError:
            # 不记录 str(exc)：h11 可能把非法请求头的完整值写进异常信息。
            logger.warning(
                "百炼 ASR 请求协议错误 LocalProtocolError（常见原因：Authorization 含换行）"
            )
            raise AppError(
                code="EXTERNAL_SERVICE_ERROR",
                message="语音识别请求头不合法，请检查 .env 中 BAILIAN_API_KEY 是否含换行或引号后重启服务",
                stage="asr",
                status_code=502,
            )
        except httpx.RequestError as exc:
            logger.warning("百炼 ASR 请求异常: %s", type(exc).__name__)
            raise AppError(
                code="EXTERNAL_SERVICE_ERROR",
                message="语音识别服务异常，请稍后重试",
                stage="asr",
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
            "百炼 ASR 返回非 200 状态码: %s error=%s",
            resp.status_code,
            error_code,
        )
        raise AppError(
            code="EXTERNAL_SERVICE_ERROR",
            message="语音识别服务异常，请稍后重试",
            stage="asr",
            status_code=502,
        )

    try:
        data = resp.json()
        raw_content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError, TypeError):
        logger.warning("百炼 ASR 响应结构不符合预期")
        raise AppError(
            code="EXTERNAL_SERVICE_ERROR",
            message="语音识别服务异常，请稍后重试",
            stage="asr",
            status_code=502,
        )

    # 兼容 content 可能是字符串或多段结构（防御性处理，未逐字确认官方样例）
    if isinstance(raw_content, list):
        text = "".join(
            part.get("text", "") for part in raw_content if isinstance(part, dict)
        )
    else:
        text = str(raw_content or "")

    text = text.strip()
    if not text:
        raise AppError(
            code="ASR_EMPTY_RESULT",
            message="未能识别出任何文字，请重新录音并靠近麦克风",
            stage="asr",
            status_code=422,
        )

    return text
