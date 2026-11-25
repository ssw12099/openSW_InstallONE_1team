"""localhost 전용 Flask 웹 앱. SSH/실제 설치를 활성화하는 옵션이 없다."""
import argparse
import secrets
from pathlib import Path
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from installone.core import VERSION
from installone.web_jobs import WebJobs, Conflict

ROOT = Path(__file__).resolve().parent


def create_app(db_path=None, mode="mock", **worker_options):
    # HTTP 계층은 접근 제어를 맡고 작업 상태는 WebJobs에 위임한다.
    if mode not in ("mock", "haigpt"):
        raise ValueError("지원하지 않는 해석 모드")
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=8192, TRUSTED_HOSTS=["127.0.0.1", "localhost"])
    jobs = WebJobs(db_path or ROOT / "data/mock.db", mode, **worker_options)
    token = secrets.token_urlsafe(32)
    app.extensions["jobs"] = jobs
    app.extensions["request_token"] = token

    @app.before_request
    def protect_local_api():
        if request.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify(error="localhost에서만 사용할 수 있습니다."), 403
        if request.path.startswith("/api/"):
            if not secrets.compare_digest(request.headers.get("X-InstallONE-Token", "").encode(), token.encode()):
                return jsonify(error="페이지를 새로고침한 뒤 다시 요청하세요."), 403
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                return jsonify(error="다른 출처의 요청은 허용하지 않습니다."), 403
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                return jsonify(error="다른 출처의 요청은 허용하지 않습니다."), 403

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.errorhandler(Exception)
    def errors(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error="요청 주소·형식·크기를 확인하세요."), exc.code
        if isinstance(exc, LookupError):
            return jsonify(error="요청을 찾을 수 없습니다."), 404
        if isinstance(exc, Conflict):
            return jsonify(error=str(exc)), 409
        if isinstance(exc, ValueError):
            return jsonify(error="요청 값 또는 저장된 계획이 올바르지 않습니다."), 400
        return jsonify(error="서버 처리 오류. 실행 결과를 확인하세요."), 500

    @app.get("/")
    def index():
        return render_template("index.html", token=token, version=VERSION, seats=jobs.seats)

    @app.get("/api/status")
    def status():
        return jsonify(interpreter=mode, connection=jobs.connection, executor="mock", vm="VM 미검증", version=VERSION, seats=list(jobs.seats))

    @app.post("/api/requests")
    def submit():
        body = request.get_json()
        if type(body) is not dict or set(body) != {"text", "request_key"}:
            raise ValueError()
        task = jobs.submit(body["text"], body["request_key"])
        return jsonify(id=task), 202

    @app.get("/api/requests/<task>")
    def get_task(task):
        return jsonify(jobs.get(task))

    @app.post("/api/requests/<task>/execute")
    def execute(task):
        body = request.get_json()
        if type(body) is not dict or set(body) != {"confirmed"} or body["confirmed"] is not True:
            raise ValueError()
        job, started = jobs.execute(task)
        return jsonify(job_id=job, started=started), 202 if started else 200

    @app.get("/api/history")
    def history():
        return jsonify(requests=jobs.history(), legacy_results=jobs.legacy_history())

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interpreter", choices=("mock", "haigpt"), default="mock")
    args = parser.parse_args()
    from werkzeug.serving import make_server
    # 바인딩에 성공한 단일 서버만 DB 중단 작업 복구를 시작한다.
    server = make_server("127.0.0.1", 5000, lambda environ, start_response: [], threaded=True)
    app = create_app(mode=args.interpreter)
    server.app = app
    print("InstallONE: http://127.0.0.1:5000 | 모의 설치 — 실제 PC 변경 없음 | VM 미검증", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.extensions["jobs"].close()
        server.server_close()
