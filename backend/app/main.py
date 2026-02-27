from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import assets, conditions, experiments, export, runs, scores

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
