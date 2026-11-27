"""API 전체 흐름 테스트 (모의 좌석): 요청 해석 → 확인 후 실행 → 좌석별 결과·기록."""
from __future__ import annotations

import threading

from fastapi.testclient import TestClient

from src.app import jobs
from src.app.jobs import wait_for_job
from src.app.main import app
from src.common.catalog import load_profiles
from src.common.models import Seat, SeatMode, SeatStatus
from src.storage import repository


def test_full_mock_flow():
    with TestClient(app) as client:
        catalog = client.get("/api/catalog").json()
        assert [s["number"] for s in catalog["seats"]] == [1, 2, 3, 4, 5]
        assert all("host" not in s for s in catalog["seats"])
        assert catalog["ai"]["enabled"] is False

        parsed = client.post("/api/parse", json={"text": "1번부터 5번 PC에 Python 실습환경 설치해 줘"}).json()
        assert parsed["seats"] == [1, 2, 3, 4, 5] and parsed["profiles"] == ["python-basic"]

        created = client.post("/api/jobs", json={
            "request_id": parsed["request_id"], "seats": parsed["seats"], "profiles": parsed["profiles"],
        })
        assert created.status_code == 201
        job_id = created.json()["job_id"]
        assert wait_for_job(job_id, timeout=30)

        job = client.get(f"/api/jobs/{job_id}").json()
        assert job["status"] == "done"
        assert job["request_text"].startswith("1번부터 5번")
        by_seat = {s["seat_no"]: s for s in job["seats"]}
        assert by_seat[1]["status"] == "success"
        profile_version = load_profiles()["python-basic"].choco[0].version  # 프로필 버전을 바꿔도 테스트가 따라감
        assert by_seat[1]["versions"]["Python"] == f"Python {profile_version}"
        assert "squares_sum=55" in by_seat[1]["example_output"]
        assert by_seat[2]["status"] == "already_installed"
        assert by_seat[3]["status"] == "install_failed"
        assert by_seat[4]["status"] == "verify_failed"
        assert by_seat[5]["status"] == "connect_failed"
        assert all(s["mode"] == "mock" and "(모의)" in s["message"] for s in job["seats"])
        assert job["counts"] == {"success": 1, "already_installed": 1, "install_failed": 1,
                                 "verify_failed": 1, "connect_failed": 1}

        events = client.get(f"/api/jobs/{job_id}/events", params={"seat": 3}).json()["events"]
        assert events and all(e["seat_no"] == 3 for e in events)
        assert any(e["kind"] == "failed" and e["stage"] == "install" for e in events)

        history = client.get("/api/jobs").json()["jobs"]
        assert history[0]["id"] == job_id and history[0]["counts"]["success"] == 1


def test_bad_job_requests_are_rejected():
    with TestClient(app) as client:
        assert client.post("/api/jobs", json={"seats": [], "profiles": ["git"]}).status_code == 400
        assert client.post("/api/jobs", json={"seats": [99], "profiles": ["git"]}).status_code == 400
        response = client.post("/api/jobs", json={"seats": [1], "profiles": ["no-such-profile"]})
        assert response.status_code == 400 and "없는 프로필" in response.json()["detail"]
        assert client.post("/api/parse", json={"text": "   "}).status_code == 422
        assert client.get("/api/jobs/999").status_code == 404


def test_unknown_request_id_is_rejected():
    with TestClient(app) as client:
        response = client.post("/api/jobs", json={"request_id": 999, "seats": [1], "profiles": ["git"]})
        assert response.status_code == 400 and "해석 기록 999번" in response.json()["detail"]


def test_same_seat_cannot_run_two_jobs_at_once(monkeypatch):
    gate = threading.Event()

    def slow_seat(seat, plan, reporter):  # 첫 작업이 끝나지 않은 상태를 만들기 위한 가짜 좌석
        gate.wait(10)
        reporter.finish(seat.number, SeatStatus.SUCCESS, message="(테스트)")

    monkeypatch.setattr(jobs, "run_mock_seat", slow_seat)
    with TestClient(app) as client:
        try:
            first = client.post("/api/jobs", json={"seats": [1, 2], "profiles": ["git"]}).json()["job_id"]
            busy = client.post("/api/jobs", json={"seats": [2, 3], "profiles": ["git"]})
            assert busy.status_code == 409
            assert f"2번 좌석은 아직 작업 #{first}에서 설치 중" in busy.json()["detail"]
            other = client.post("/api/jobs", json={"seats": [4], "profiles": ["git"]})  # 겹치지 않으면 바로 실행
            assert other.status_code == 201
        finally:
            gate.set()
        assert wait_for_job(first, timeout=10) and wait_for_job(other.json()["job_id"], timeout=10)
        again = client.post("/api/jobs", json={"seats": [2, 3], "profiles": ["git"]})
        assert again.status_code == 201
        assert wait_for_job(again.json()["job_id"], timeout=10)
        assert client.get(f"/api/jobs/{first}").json()["status"] == "done"


def test_jobs_left_running_are_closed_when_server_starts():
    seat = Seat(number=1, name="PC-01", mode=SeatMode.MOCK)
    job_id = repository.create_job(None, [seat], ["git"])
    repository.set_job_status(job_id, "running")  # 서버가 이 상태에서 꺼졌다고 가정
    with TestClient(app) as client:
        job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "error"
    assert job["seats"][0]["status"] == "error" and "다시 시작" in job["seats"][0]["message"]


def test_ui_is_served():
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200 and "InstallONE" in page.text
        assert client.get("/ui/app.js").status_code == 200
