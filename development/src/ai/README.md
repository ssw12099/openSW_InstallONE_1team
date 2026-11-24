# AI 요청 해석
현재 구현은 Ollama + Qwen 기반입니다. HaiGPT 연동은 API 규격 및 인증 방식이 확정되면 별도 어댑터를 추가합니다. 공통 반환 타입은 `src.common.models.Decision`입니다. AI가 임의 명령을 실행하지 않습니다.
