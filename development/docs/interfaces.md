# 모듈 인터페이스

`src/common/models.py`의 Pydantic 모델이 요청 데이터 규칙을 정의합니다. 모든 API는 8000 포트에서 제공되며 보호 API는 `Authorization: Bearer <token>`을 사용합니다. 사용자 웹은 CLIENT_TOKEN 외에 `X-PC-Name`, `X-PC-Token` 헤더가 필요합니다. `/me`, `/files`, `/chat`, `/files/{fid}/link`에 적용합니다. 관리자와 에이전트 인증은 그대로 유지합니다.

| 요청 | 권한 | 데이터 / 결과 |
|---|---|---|
| GET /health | 없음 | status |
| GET /me | 사용자/관리자 | role, pc |
| GET /files | 사용자/관리자 | 관리자 전체 / 사용자 PC별 배포 파일 배열 |
| POST /files | 관리자 | multipart: label, description, upload |
| POST /files/{fid}/link | 사용자/관리자 | file, url |
| GET /download/{fid} | 서명 링크 | exp, scope, sig → 파일 |
| POST /chat | 사용자/관리자 | prompt → action, message, (file, url, source) |
| POST /agents | 관리자 | name → name, token |
| GET /hosts | 관리자 | name, last_seen 배열 |
| POST /jobs | 관리자 | file_id, hosts, operation (download 또는 install_python) → id, status |
| GET /jobs | 관리자 | 작업 및 tasks 배열 |
| POST /agents/{name}/poll | 해당 PC | task 또는 null; 설치 수신에는 X-Approved-Python-Sha256 헤더 필요 |
| POST /agents/{name}/tasks/{tid}/result | 해당 PC | claim, success, log → ok |

AI 인터페이스: `choose_file(prompt, files, admin) -> Decision`; AI 출력은 API에서 검증합니다. 설치 작업은 task.operation으로 구분하며 서버는 명령어 및 실행 인수를 전달하지 않습니다. HaiGPT 인터페이스는 통합 단계에 확정합니다.

사용자 파일 권한: jobs.file_id와 tasks.host의 관리자 요청 이력으로 판단합니다. 서명 링크는 해당 PC의 권한을 다시 확인하지만 링크 소지자가 사용할 수 있으므로 공유하지 않습니다.
