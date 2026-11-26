"""FastAPI 서버: 관리 웹(ui)과 API를 함께 띄웁니다.

실행: development 폴더에서  python -m src.app   (또는 uvicorn src.app.main:app --reload)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..ai import get_provider, interpret
from ..common.catalog import CatalogError, load_catalog
from ..common.config import UI_DIR, get_settings
from ..installer import build_plan
from ..storage import repository as repo
from .jobs import SeatBusyError, close_interrupted_jobs, submit_job

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    repo.init_db()
    closed = close_interrupted_jobs()
    if closed:
        log.warning("서버가 꺼지기 전에 끝나지 않은 작업을 오류로 마감했어요: %s", closed)
    yield


app = FastAPI(title="InstallONE FR-01 프로토타입", lifespan=lifespan)
app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")


@app.exception_handler(CatalogError)
async def catalog_error(_: Request, exc: CatalogError) -> JSONResponse:
    """seats.yml·프로필 파일 실수는 '서버 오류' 대신 어디가 틀렸는지 알려 줌."""
    return JSONResponse(status_code=500, content={"detail": f"설정 파일을 확인해 주세요. {exc}"})


class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class JobRequest(BaseModel):
    request_id: int | None = None
    seats: list[int]
    profiles: list[str]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/catalog")
def catalog() -> dict:
    """좌석·프로필 목록과 AI 설정 상태 (관리 웹 첫 화면용)."""
    c = load_catalog()
    settings = get_settings()
    plans = {pid: build_plan([pid], c.profiles) for pid in c.profiles}  # 포함한 프로필 항목까지 펼쳐서 보여 줌
    return {
        "seats": [s.model_dump(mode="json", exclude={"host"}) for s in c.seats.values()],
        "profiles": [
            {
                "id": p.id, "name": p.name, "description": p.description, "includes": p.includes,
                "items": [f"{x.name} {x.version}" if x.version else x.name for x in plans[p.id].choco] + plans[p.id].pip,
            }
            for p in c.profiles.values()
        ],
        "ai": {"enabled": settings.llm_enabled, "provider": settings.llm_provider if settings.llm_enabled else None},
    }


@app.post("/api/parse")
def parse(request: ParseRequest) -> dict:
    """자연어 요청 → 좌석·프로필 해석 (아직 실행하지 않음)."""
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="요청 문장을 입력해 주세요.")
    result = interpret(text, load_catalog(), get_provider())
    request_id = repo.create_request(text, result)
    return {"request_id": request_id, **result.model_dump()}


@app.post("/api/jobs", status_code=201)
def create_job(request: JobRequest) -> dict:
    """조교가 확인한 좌석·프로필로 설치 실행."""
    try:
        job_id = submit_job(request.request_id, request.seats, request.profiles)
    except SeatBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job_id": job_id}


@app.get("/api/jobs")
def jobs(limit: int = 20) -> dict:
    return {"jobs": repo.list_jobs(min(max(limit, 1), 100))}


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: int) -> dict:
    job = repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없어요.")
    return job


@app.get("/api/jobs/{job_id}/events")
def job_events(job_id: int, seat: int | None = None) -> dict:
    if repo.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없어요.")
    return {"events": repo.get_events(job_id, seat)}
