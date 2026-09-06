"""
统一配置读取。
从 backend/.env 文件或环境变量加载所有配置项；
未填写密钥时使用空字符串默认值，不影响健康检查等不调用外部服务的接口。
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _clean_env_str(value: str) -> str:
    """去掉首尾空白、换行，以及整段被引号包裹的情况。"""
    cleaned = value.strip().strip("\ufeff")
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()
    return cleaned.replace("\r", "").replace("\n", "")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # 忽略 .env 中未声明的字段
    )

    # ── 阿里云百炼 ────────────────────────────────────────
    bailian_api_key: str = ""
    bailian_base_url: str = "https://dashscope.aliyuncs.com"
    bailian_compatible_url: str = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    bailian_tts_url: str = (
        "https://dashscope.aliyuncs.com/api/v1/services/aigc"
        "/multimodal-generation/generation"
    )

    # ── DeepSeek ─────────────────────────────────────────
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # ── 高德地图 ─────────────────────────────────────────
    amap_api_key: str = ""
    amap_geocode_url: str = "https://restapi.amap.com/v3/geocode/geo"
    amap_poi_url: str = "https://restapi.amap.com/v3/place/around"

    # ── 模型名称 ─────────────────────────────────────────
    asr_model: str = "qwen3-asr-flash"
    tts_model: str = "qwen3-tts-flash"
    tts_voice: str = "Cherry"
    extract_model: str = "deepseek-v4-flash"
    finalize_model: str = "deepseek-v4-flash"

    # ── 存储与有效期 ─────────────────────────────────────
    storage_dir: str = "storage"
    audio_expire_seconds: int = 86400

    @field_validator(
        "bailian_api_key",
        "bailian_base_url",
        "bailian_compatible_url",
        "bailian_tts_url",
        "deepseek_api_key",
        "deepseek_base_url",
        "amap_api_key",
        "amap_geocode_url",
        "amap_poi_url",
        "asr_model",
        "tts_model",
        "tts_voice",
        "extract_model",
        "finalize_model",
        "storage_dir",
        mode="before",
    )
    @classmethod
    def _strip_env_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return _clean_env_str(value)
        return value


@lru_cache
def get_settings() -> Settings:
    """返回全局唯一的 Settings 实例（lru_cache 保证单例）。"""
    return Settings()
