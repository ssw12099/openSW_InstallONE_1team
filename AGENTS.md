# 프로젝트 커밋 검증 규칙

- 개발 전 해당 폴더의 AGENTS.md·CONTEXT.md와 최신 개인 로그, 브랜치·git status를 확인하고 사용자 변경을 보존한다.
- 모든 커밋 전 저장소 로컬 pre-commit Hook을 설치하고 **staged 스냅샷** 검증을 통과해야 한다. 새 클론: `python development/quality/install_hooks.py` (먼저 development/.venv와 requirements 준비).
- 공통 검사/범위/실행법은 `development/quality/README.md`. 기능 변경에는 관련 회귀 테스트를 추가·수정하고, 인증/API/DB/의존성/검사 정책 변경은 강화 검사를 수행한다.
- 필수 검사 실패·런타임 누락·검사 미실행은 통과가 아니다. 사용자 승인 없는 `--no-verify`, Hook 비활성화, 검사 생략·기준 완화는 금지한다.
- 작업 폴더를 임의 stash/reset하지 않는다. 검사에 실제 API 키·VM·설치 실행을 사용하지 않는다. 전역 Git/Codex 설정을 변경하지 않는다.
- 커밋·푸시·병합은 사용자 요청이 있을 때만 한다. 검사 실행과 커밋 권한은 별개다.
