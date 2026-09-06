"""
音频文件存储与 audio_id 管理。

设计要点：
- audio_id 是后端生成的临时编号（不是文件路径），格式：aud_{12位hex}。
- 音频内容与元数据分别保存：
    storage/audio/{audio_id}.{ext}          原始录音内容
    storage/audio/{audio_id}.meta.json      创建时间等元数据
- 本轮只负责保存 created_at，供后续 /asr、/audio 读取时做 24 小时有效期
  校验；本轮不实现读取校验逻辑本身。
"""

import json
import time
import uuid
from pathlib import Path

from config import get_settings


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
