from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.routers import advisor, assets, conditions, experiments, export, runs, scores, slots

app = FastAPI(title="NBP Lab", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Dev: allow all origins (codespace port-forwarding, etc.)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(experiments.router)
app.include_router(conditions.router)
app.include_router(assets.router)
app.include_router(runs.router)
app.include_router(scores.router)
app.include_router(export.router)
app.include_router(advisor.router)
app.include_router(slots.router)

# Serve uploaded/generated images
_uploads_dir = Path(__file__).resolve().parent.parent.parent / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")
