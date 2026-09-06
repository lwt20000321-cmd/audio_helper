"""
音频文件存储与 audio_id 管理。

设计要点：
- audio_id 是后端生成的临时编号（不是文件路径），格式：aud_{12位hex}。
- 音频内容与元数据分别保存：
    storage/audio/{audio_id}.{ext}          原始录音内容
    storage/audio/{audio_id}.meta.json      创建时间等元数据
- load_audio_file 在读取时校验存在性与 24 小时有效期（created_at 由
  save_audio_file 写入）；过期或不存在均返回统一的 404 错误，不在此处
  删除文件——清理由启动时的独立任务负责（读取时校验 ≠ 清理任务）。
"""

import json
import time
import uuid
from pathlib import Path

from config import get_settings
from errors import AppError


def _audio_dir() -> Path:
    settings = get_settings()
    d = Path(settings.storage_dir) / "audio"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_audio_file(content: bytes, duration_sec: float, ext: str) -> str:
    """
    保存音频内容与元数据，返回新生成的 audio_id。
    """
    audio_id = f"aud_{uuid.uuid4().hex[:12]}"
    audio_dir = _audio_dir()

    (audio_dir / f"{audio_id}.{ext}").write_bytes(content)

    meta = {
        "created_at": time.time(),
        "duration_sec": round(duration_sec, 2),
        "size_bytes": len(content),
        "ext": ext,
    }
    (audio_dir / f"{audio_id}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    return audio_id


def load_audio_file(audio_id: str, stage: str) -> tuple[bytes, str]:
    """
    读取 audio_id 对应的录音内容。

    校验顺序：元数据文件存在 → JSON 可解析 → 未超过 24 小时有效期 → 音频文件本身存在。
    任一环节失败均抛出 AppError(404, RESOURCE_NOT_FOUND)，不区分具体原因
    （不向客户端暴露内部细节，如"是文件丢失还是过期"）。

    参数 stage 由调用方传入（如 "asr"），用于错误响应里标注出错阶段。
    """
    settings = get_settings()
    audio_dir = _audio_dir()
    meta_path = audio_dir / f"{audio_id}.meta.json"

    not_found_error = AppError(
        code="RESOURCE_NOT_FOUND",
        message="录音不存在或已过期，请重新录音",
        stage=stage,
        status_code=404,
    )

    if not meta_path.exists():
        raise not_found_error

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raise not_found_error

    created_at = meta.get("created_at")
    ext = meta.get("ext")
    if created_at is None or ext is None:
        raise not_found_error

    if time.time() - created_at > settings.audio_expire_seconds:
        raise not_found_error

    audio_path = audio_dir / f"{audio_id}.{ext}"
    if not audio_path.exists():
        raise not_found_error

    return audio_path.read_bytes(), ext
