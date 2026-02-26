import logging
import os
import re
from pathlib import Path
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ToleranceConfig(BaseModel):
    distance_cm: float = 1.0
    area_pct: float = 0.5
    angle_deg: float = 0.5


class KPIThresholds(BaseModel):
    area_mae_pct: float = 0.5
    height_mae_m: float = 0.01
    precision_min: float = 0.95
    recall_min: float = 0.90
    unknown_field_rate_max: float = 0.30
    proposal_acceptance_min: float = 0.60
    false_positive_rate_max: float = 0.15


class LLMProviderConfig(BaseModel):
    """Server-side LLM provider configuration — keys come from env vars only."""
    enabled: bool = False
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    max_tokens: int = 4096
    temperature: float = 0.1
    timeout_seconds: int = 60
    max_retries: int = 2


_DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]


class AppConfig(BaseModel):
    data_dir: Path = Path("data")
    rulesets_dir: Path = Path("rulesets")
    upload_dir: Path = Path("data/uploads")
    golden_dataset_dir: Path = Path("golden-dataset")
    benchmark_dir: Path = Path("data/benchmarks")
    tolerance: ToleranceConfig = ToleranceConfig()
    kpi_thresholds: KPIThresholds = KPIThresholds()
    llm: LLMProviderConfig = LLMProviderConfig()
    max_concurrent_validations: int = 20
    base_units_length: str = "m"
    base_units_area: str = "m2"
    base_units_volume: str = "m3"
    database_url: str = ""
    allowed_origins: list[str] = _DEFAULT_ORIGINS

    @property
    def use_postgres(self) -> bool:
        return bool(self.database_url)

    @property
    def llm_available(self) -> bool:
        return self.llm.enabled and bool(self.llm.api_key)


def _sanitize_db_url(url: str) -> str:
    """Strip channel_binding param that Neon adds but older libpq doesn't support."""
    return re.sub(r"[&?]channel_binding=[^&]*", "", url)


def _mask_url(url: str) -> str:
    """Show scheme + host only, hiding credentials and path details."""
    if not url:
        return "(empty)"
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        return f"{p.scheme}://{p.hostname or '?'}:***"
    except Exception:
        return "***"


def _build_llm_config() -> LLMProviderConfig:
    """Build LLM config from environment variables."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return LLMProviderConfig(enabled=False)

    return LLMProviderConfig(
        enabled=True,
        provider=os.environ.get("LLM_PROVIDER", "openai"),
        model=os.environ.get("LLM_MODEL", "gpt-4o"),
        api_key=api_key,
        max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "4096")),
        temperature=float(os.environ.get("LLM_TEMPERATURE", "0.1")),
        timeout_seconds=int(os.environ.get("LLM_TIMEOUT_SECONDS", "60")),
        max_retries=int(os.environ.get("LLM_MAX_RETRIES", "2")),
    )


def _build_settings() -> AppConfig:
    overrides: dict = {}
    if db_url := os.environ.get("DATABASE_URL"):
        overrides["database_url"] = _sanitize_db_url(db_url)
    if origins_raw := os.environ.get("ALLOWED_ORIGINS"):
        extra = [o.strip() for o in origins_raw.split(",") if o.strip()]
        overrides["allowed_origins"] = _DEFAULT_ORIGINS + extra

    overrides["llm"] = _build_llm_config()

    cfg = AppConfig(**overrides)
    _validate_production_env(cfg)
    return cfg


def _validate_production_env(cfg: AppConfig) -> None:
    """Log environment status; warn loudly if production config is incomplete."""
    is_production = cfg.use_postgres

    if is_production:
        logger.info("Environment: PRODUCTION (DATABASE_URL → %s)", _mask_url(cfg.database_url))

        if not os.environ.get("ALLOWED_ORIGINS"):
            logger.warning(
                "ALLOWED_ORIGINS is missing in production. "
                "Only localhost origins will be allowed — the frontend will get CORS errors. "
                "Set ALLOWED_ORIGINS=https://archscan-planandgo.netlify.app in Render → Environment."
            )
    else:
        logger.info("Environment: LOCAL DEV (no DATABASE_URL, using file storage)")

    logger.info("CORS allowed_origins (%d): %s", len(cfg.allowed_origins), cfg.allowed_origins)

    if cfg.llm.enabled:
        logger.info(
            "LLM provider: %s model=%s max_tokens=%d (key present)",
            cfg.llm.provider, cfg.llm.model, cfg.llm.max_tokens,
        )
    else:
        logger.info("LLM provider: disabled (no OPENAI_API_KEY set)")


settings = _build_settings()
