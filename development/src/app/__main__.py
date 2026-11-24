"""python -m src.app 로 서버 실행 (기본 http://127.0.0.1:8000)."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.app.main:app",
        host=os.environ.get("INSTALLONE_HOST", "127.0.0.1"),
        port=int(os.environ.get("INSTALLONE_PORT", "8000")),
    )
