from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import init_db, get_db_session, seed_strategies
from backend.routers import stocks, scores, trigger, analysis

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    session = get_db_session()
    try:
        seed_strategies(session)
    finally:
        session.close()
    from backend.scheduler import start_scheduler
    start_scheduler()
    yield


app = FastAPI(title="A股评分系统", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(stocks.router)
app.include_router(scores.router)
app.include_router(trigger.router)
app.include_router(analysis.router)

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        return FileResponse(FRONTEND_DIST / "index.html")
