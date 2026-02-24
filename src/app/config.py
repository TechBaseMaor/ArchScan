import os
from pathlib import Path
from pydantic import BaseModel


class ToleranceConfig(BaseModel):
    distance_cm: float = 1.0
    area_pct: float = 0.5
    angle_deg: float = 0.5


class KPIThresholds(BaseModel):
    area_mae_pct: float = 0.5
    height_mae_m: float = 0.01
    precision_min: float = 0.95
    recall_min: float = 0.90


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
    max_concurrent_validations: int = 20
    base_units_length: str = "m"
    base_units_area: str = "m2"
    base_units_volume: str = "m3"
    database_url: str = ""
    allowed_origins: list[str] = _DEFAULT_ORIGINS

    @property
    def use_postgres(self) -> bool:
        return bool(self.database_url)


def _build_settings() -> AppConfig:
    overrides: dict = {}
    if db_url := os.environ.get("DATABASE_URL"):
        overrides["database_url"] = db_url
    if origins_raw := os.environ.get("ALLOWED_ORIGINS"):
        extra = [o.strip() for o in origins_raw.split(",") if o.strip()]
        overrides["allowed_origins"] = _DEFAULT_ORIGINS + extra
    return AppConfig(**overrides)


settings = _build_settings()
