from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="InstallONE API",
    description="AI 기반 실습실 개발환경 설치 서비스",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/")
def root():
    return {
        "service": "InstallONE",
        "version": "0.1.0",
        "message": "InstallONE API 서버가 실행 중입니다."
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "InstallONE"
    }
from backend.database import init_db, get_pcs

init_db()


@app.get("/api/pcs")
def list_pcs():
    return get_pcs()
from backend.config import (
    AI_MODE,
    INSTALL_MODE,
    is_ai_configured
)


@app.get("/api/config")
def get_config():
    return {
        "ai_mode": AI_MODE,
        "install_mode": INSTALL_MODE,
        "ai_configured": is_ai_configured()
    }
from pydantic import BaseModel, Field
from fastapi import HTTPException
from backend.ai_service import analyze_request, PROFILES


class AnalyzeRequest(BaseModel):
    request: str = Field(min_length=1, max_length=1000)


@app.get("/api/profiles")
def list_profiles():
    return PROFILES


@app.post("/api/analyze")
def analyze(data: AnalyzeRequest):
    try:
        return analyze_request(data.request)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

from backend.install_service import execute_installation
from backend.database import get_jobs, get_job_detail


class InstallRequest(BaseModel):
    request: str = Field(min_length=1, max_length=1000)
    pc_ids: list[int] = Field(min_length=1)
    profiles: list[str] = Field(min_length=1)
    approved: bool = False


@app.post("/api/install")
def install(data: InstallRequest):
    if not data.approved:
        raise HTTPException(
            status_code=400,
            detail="설치 작업에 대한 승인이 필요합니다."
        )

    try:
        return execute_installation(
            request=data.request,
            pc_ids=data.pc_ids,
            profiles=data.profiles
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@app.get("/api/jobs")
def list_jobs():
    return get_jobs()


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: int):
    job = get_job_detail(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="설치 작업을 찾을 수 없습니다."
        )

    return job