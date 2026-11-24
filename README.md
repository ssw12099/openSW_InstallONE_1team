# InstallONE · 1팀 협업 공간

오픈소스SW의 이해 기말 대체 프로젝트 — 실습실 개발환경 설치 서비스.
팀원: 소선웅, 강건우, 지재헌, 신정빈.

> 팀 협업을 위한 저장소입니다. 이 압축본에는 `development/`에 Windows 다운로드·배포 개인 프로토타입이 포함되어 있습니다. 선정 전 main 병합을 뜻하지 않습니다.

## 개발은 각자, 협업 기록은 공통
- `development/`: 각자 자기 프로토타입 브랜치에서 자유롭게 구성합니다. 내부 폴더·파일·실행 방법은 개발자가 정합니다.
- `docs/`: 일정, 개인별 개발 기록, 회의, 결정, 비교 결과를 함께 관리합니다.
- `.github/`: 이슈·PR 작성 양식입니다.
- 루트 README는 저장소 안내로 유지합니다. 각 프로토타입의 실행 안내는 `development/README.md`에 작성합니다.

## 진행 방식
1. 11/29(일)까지 각자 필수 기능 프로토타입 개발 및 Windows VM 테스트
2. 동일 기준으로 비교 후 기반 프로토타입 선정
3. 선정한 코드 중심으로 개발 3명·통합 및 관리 1명 체제로 공동 개발
4. 12/8 1차 발표, 12/15 최종 발표

이번 주 프로토타입 참여자와 이름별 역할 배정은 팀에서 확인합니다.
기술 방향은 HaiGPT·Python·SQL 사용. 세부 스택 및 개발 폴더 구조는 여기서 지정하지 않습니다.

## 프로토타입 실행
Windows PowerShell에서 압축을 푼 저장소의 `development/`로 이동한 뒤 [설치 및 실행 안내](development/README.md)의 순서대로 진행합니다.

```powershell
cd .\development
.\setup.bat
# .env의 PUBLIC_API_BASE 설정, AI 사용 시 Ollama 설치 후
.\start.bat
```

## 바로가기
- [프로토타입 상세 실행 안내](development/README.md)
- [협업·브랜치·병합 규칙](CONTRIBUTING.md)
- [팀 전체 현황](docs/progress.md)
- [개발 로그 작성 안내](docs/devlogs/README.md)
- [회의록 양식](docs/meetings/TEMPLATE.md)
- [프로토타입 비교·선정](docs/prototype-review.md)
- [결정 기록](docs/decisions.md)
- [문서 관리 안내](docs/README.md)
