"""
音频真实容器 / 编码 / 时长校验。

依赖：PyAV（pip 包 `av`）
- PyAV 内置编译好的 FFmpeg 解封装（demux）库，可读取音频文件的真实容器和编码
  信息，不依赖文件扩展名，也不依赖前端上报的 Content-Type。
- 本模块只做 demux（解析包头、时间戳），不解码音频样本、不转码，符合
  "探测不等于转码" 的约束。

时长探测策略（兼容缺少 Duration 元数据的浏览器录音）：
1. 优先读取容器级 `container.duration`（微秒）。
2. 缺失时读取音频流级 `stream.duration`（配合 stream.time_base 换算）。
3. 仍缺失时遍历该音频流的所有 packet，取最后一个有效时间戳
   （pts + duration）作为总时长的估算——这正是 Chromium 系浏览器停止录制时
   Segment Info 里 Duration 为 0 的典型场景，遍历 packet 后依然可以得到
   准确时长，因此不会被误判为非法文件。
"""

from io import BytesIO

import av

from errors import AppError

MIN_DURATION_SEC = 1.0
MAX_DURATION_SEC = 60.0


def validate_audio(content: bytes) -> tuple[float, str]:
    """
    校验音频真实容器、编码与时长。

    返回：(时长秒数, 建议保存用的文件扩展名)
    失败时抛出 AppError：
      - 415 AUDIO_FORMAT_UNSUPPORTED：无法解封装 / 无音频轨道 / 无法确定时长
      - 422 AUDIO_TOO_SHORT / AUDIO_TOO_LONG：时长超出 1-60 秒范围
    """
    try:
        container = av.open(BytesIO(content))
    except Exception:
        raise AppError(
            code="AUDIO_FORMAT_UNSUPPORTED",
            message="无法识别音频格式，请使用受支持的录音格式（WebM/Opus 等）重新录音",
            stage="upload",
            status_code=415,
        )

    try:
        audio_streams = container.streams.audio
        if not audio_streams:
            raise AppError(
                code="AUDIO_FORMAT_UNSUPPORTED",
                message="文件中未找到有效的音频轨道",
                stage="upload",
                status_code=415,
            )

        stream = audio_streams[0]
        duration_sec = _probe_duration_seconds(container, stream)

        if duration_sec is None:
            raise AppError(
                code="AUDIO_FORMAT_UNSUPPORTED",
                message="无法读取有效的音频时长，请重新录音",
                stage="upload",
                status_code=415,
            )

        if duration_sec < MIN_DURATION_SEC:
            raise AppError(
                code="AUDIO_TOO_SHORT",
                message=f"录音时长至少 {int(MIN_DURATION_SEC)} 秒",
                stage="upload",
                status_code=422,
            )

        if duration_sec > MAX_DURATION_SEC:
            raise AppError(
                code="AUDIO_TOO_LONG",
                message=f"录音时长不能超过 {int(MAX_DURATION_SEC)} 秒",
                stage="upload",
                status_code=422,
            )

        ext = _extension_for_format(container.format.name)
        return duration_sec, ext
    finally:
        container.close()


def _probe_duration_seconds(container, stream) -> float | None:
    """按优先级探测时长（秒）；三种方式均失败返回 None。"""

    # 1. 容器级 duration（AV_TIME_BASE = 微秒）
    if container.duration:
        return container.duration / 1_000_000

    # 2. 流级 duration
    if stream.duration and stream.time_base:
        return float(stream.duration * stream.time_base)

    # 3. 遍历 packet 时间戳估算（demux only，不解码音频样本）
    last_end_sec = None
    try:
        for packet in container.demux(stream):
            if packet.pts is None:
                continue
            end_ts = packet.pts + (packet.duration or 0)
            end_sec = float(end_ts * stream.time_base)
            if last_end_sec is None or end_sec > last_end_sec:
                last_end_sec = end_sec
    except Exception:
        return None

    return last_end_sec


def _extension_for_format(format_name: str) -> str:
    """
    根据 PyAV 探测到的真实容器格式名决定保存扩展名。
    仅用于文件命名，不影响已完成的格式校验结果。
    """
    name = (format_name or "").lower()
    if "webm" in name or "matroska" in name:
        return "webm"
    if "ogg" in name:
        return "ogg"
    if "mp4" in name or "m4a" in name or "mov" in name:
        return "m4a"
    return "bin"
