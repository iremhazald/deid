from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_API_DIR = Path(__file__).resolve().parents[2]


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".env").exists() or (parent / ".env.example").exists():
            return parent
    return here.parents[4]


_PROJECT_ROOT = _project_root()


def env_file_path() -> Path:
    return _PROJECT_ROOT / ".env"


def example_env_path() -> Path:
    return _PROJECT_ROOT / ".env.example"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(env_file_path()),
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
    )

    redaction_allowed_origin: str = "http://localhost:5173"
    redaction_job_ttl_seconds: int = 86400
    redaction_max_file_mb: int = 25
    redaction_max_extracted_chars: int = 1_500_000
    redaction_output_dir: str = "outputs"
    redaction_workspace_dir: str = ""
    debug_detection: bool = False
    # Optional on-device NER (LOCAL_CONTEXT only). Not loaded on startup.
    deid_tr_ner_model: str = "akdeniz27/bert-base-turkish-cased-ner"
    deid_tr_ner_backend: str = "onnx"
    deid_tr_ner_onnx_variant: str = "fp32"
    deid_en_ner_model: str = "en_core_web_sm"
    deid_ner_local_files_only: bool = True
    deid_ner_max_chars_per_chunk: int = 1200
    deid_ner_chunk_overlap_chars: int = 80
    # Development-only NER diagnostics. Never enable in production UI.
    deid_ner_debug: bool = False

    def cors_origins(self) -> list[str]:
        origin = self.redaction_allowed_origin
        origins = [origin]
        if "localhost" in origin:
            origins.append(origin.replace("localhost", "127.0.0.1"))
        elif "127.0.0.1" in origin:
            origins.append(origin.replace("127.0.0.1", "localhost"))
        return origins


def _load_settings() -> Settings:
    path = env_file_path()
    if path.exists():
        return Settings(_env_file=path, _env_file_encoding="utf-8")
    return Settings(_env_file=None)


@lru_cache
def get_settings() -> Settings:
    return _load_settings()


def reload_settings() -> Settings:
    """Re-read .env without restarting the process."""
    get_settings.cache_clear()
    return get_settings()


def ensure_env_file() -> Path:
    path = env_file_path()
    if path.exists():
        return path
    example = example_env_path()
    if example.exists():
        path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        path.write_text("REDACTION_ALLOWED_ORIGIN=http://localhost:5173\n", encoding="utf-8")
    return path


def upsert_env_values(updates: dict[str, str]) -> Path:
    """Write or replace keys in the project .env. Values are never logged."""
    path = ensure_env_file()
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    seen: set[str] = set()
    next_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in updates:
                next_lines.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        next_lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            next_lines.append(f"{key}={value}")
    path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
    return path
