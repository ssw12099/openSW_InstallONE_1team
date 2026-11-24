"""API 전체 흐름 테스트 (모의 좌석): 요청 해석 → 확인 후 실행 → 좌석별 결과·기록."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.app.jobs import wait_for_job
from src.app.main import app


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
        assert by_seat[1]["versions"]["Python"] == "Python 3.12.10"
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


def test_ui_is_served():
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200 and "InstallONE" in page.text
        assert client.get("/ui/app.js").status_code == 200
