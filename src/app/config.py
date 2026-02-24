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


settings = AppConfig()
