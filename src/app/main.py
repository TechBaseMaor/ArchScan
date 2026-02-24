from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.api.projects import router as projects_router
from src.app.api.validations import router as validations_router
from src.app.api.rulesets import router as rulesets_router
from src.app.api.benchmarks import router as benchmarks_router
from src.app.config import settings
from src.app.validation.worker import validation_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    for d in [
        settings.data_dir,
        settings.data_dir / "projects",
        settings.data_dir / "validations",
        settings.data_dir / "findings",
        settings.data_dir / "reports",
        settings.data_dir / "audit",
        settings.upload_dir,
        settings.rulesets_dir,
        settings.benchmark_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    await validation_manager.start()
    yield
    await validation_manager.stop()


app = FastAPI(
    title="ArchScan Deterministic",
    version="0.1.0",
    description="Deterministic architectural plan analysis and regulatory compliance checking.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router, prefix="/projects", tags=["projects"])
app.include_router(validations_router, prefix="/validations", tags=["validations"])
app.include_router(rulesets_router, prefix="/rulesets", tags=["rulesets"])
app.include_router(benchmarks_router, prefix="/benchmarks", tags=["benchmarks"])


@app.get("/health")
async def health():
    return {"status": "ok"}
