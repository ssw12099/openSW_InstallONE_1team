# 커밋 전 호환성·보안 검사

Git pre-commit Hook이 **실제로 staged된 내용**을 임시 폴더에 복원해 검사합니다. 코드·테스트·검사기 모두 index 버전을 사용합니다. 작업 폴더를 stash/reset/수정하거나 자동 stage하지 않습니다. 성공은 한 줄, 실패는 파일/검사 이름과 제한된 진단을 출력합니다. 실제 API·VM 설치는 실행하지 않습니다.

## 현재 저장소와 새 클론 설치

저장소 루트 PowerShell에서:

```powershell
python -m venv development/.venv
development/.venv/Scripts/python.exe -m pip install -r development/requirements.txt
python development/quality/install_hooks.py
```

이미 가상환경이 있으면 재생성하지 않아도 됩니다. Python 3.11 이상이 필요하며 현재 검증 환경은 Windows/Python 3.14.7입니다. 웹 또는 고위험 변경은 requirements의 정확한 버전이 필요합니다. JavaScript 변경은 Node.js, PowerShell 변경은 PowerShell, 고위험 변경은 둘 다 필요합니다. Git for Windows에 포함된 `sh`도 Hook 구문 검사에 사용합니다.

설치기는 `.git/installone-hooks/pre-commit`에 작은 실행기를 복사하고 **현재 저장소의** `core.hooksPath`만 지정합니다. 전역 설정은 바꾸지 않습니다. 기존 사용자 Hook·다른 hooksPath·수동 수정된 설치 Hook이 있으면 덮어쓰지 않고 중단합니다. 버전 관리되는 Hook을 수정했다면 같은 설치 명령으로 갱신합니다. 새 클론에는 설치 명령을 다시 실행해야 합니다.

첫 커밋에는 `development/quality/`, `development/hooks/`, `AGENTS.md` 등 새 검사 파일도 stage해야 합니다. Hook을 설치했지만 index에 gate.py가 없으면 커밋을 차단합니다. Hook 설치와 커밋·푸시는 별개이며 설치 명령은 파일을 stage하거나 커밋하지 않습니다.

보통은 `git commit`이 자동으로 검사합니다. 커밋 없이 현재 staged 내용을 검사하려면:

```powershell
git hook run pre-commit
```

staged된 비밀정보는 작업 폴더에서만 지워도 해결되지 않습니다. 로컬에서 수정한 내용을 다시 stage하고 검사해야 합니다. 필수 검사 실패/실행 환경 누락/테스트 skip/시간 초과는 모두 차단합니다. 사용자 승인 없는 `--no-verify`, Hook 비활성화, 기준 완화·검사 생략은 금지합니다.

## 자동 선택 범위

| 변경 | 실행 검사 | 예상 시간(이 PC) |
|---|---|---|
| 문서 등 기본 | staged 경로·민감정보·공백/충돌·변경 Python/JSON 구문 + 기존 기본 테스트 3개 | 약 1~2초 |
| HTML/CSS/JavaScript | 기본 검사 + requirements 버전 일치 + 웹 테스트 + 변경 JS 구문 | 약 3~4초 |
| Python/API/인증/DB/설치/의존성/테스트/Hook·검사 정책/AGENTS/CI 설정 및 미분류 구현 변경 | staged 전체 민감정보·Python/JSON 구문 + 고정 의존성/pip check + 전체 앱·정책 테스트 + JS/PowerShell/Hook 구문 | 약 5~8초 |

기본 테스트는 입력 검증·좌석 혼합 결과/중복 실행·원격 검증 응답 검사를 기존 `test_flow.py`에서 재사용합니다. 기능 추가/변경 시 개발자는 관련 회귀 테스트도 추가·수정해야 합니다. 검사기가 기능 의미나 테스트 충분성을 자동 판단하지는 않습니다. Python 구현은 아직 작은 규모이고 API/DB/실행 경계와 밀접하므로 보수적으로 고위험으로 분류합니다.

고위험이 아닌 커밋에는 전체 분석·전체 테스트·Git 이력 검색을 반복하지 않습니다. 모든 단계는 오프라인이며 외부 LLM 비용이 없습니다. 전체 앱 테스트도 현재 수 초 규모입니다. 각 외부 검사 시간 제한은 90초입니다.

## 보안·변경 보호 방식

- Git index의 OID와 blob을 직접 읽습니다. checkout/smudge 필터와 unstaged 코드·테스트·설정은 사용하지 않습니다. 끝에서 index가 바뀌지 않았는지도 확인합니다.
- `.venv`는 실행 환경으로만 재사용합니다. Python `-I`, 임시 스냅샷 import 경로, 테스트의 네트워크·외부 프로세스 차단을 사용합니다. 테스트 사본에 키·DB·로컬 설정을 복사하지 않습니다.
- 비밀 설정·DB·개인 키·VM 이미지·설치 파일·가상환경이 강제로 stage되어도 차단합니다. symlink/submodule·unmerged index도 자동 처리하지 않고 차단합니다.
- provider 토큰, 개인 키 헤더, literal credential 할당, Bearer 토큰을 검사합니다. 알려진 비밀 없는 예시값만 허용하며 테스트 파일을 통째로 제외하지 않습니다. 찾은 값/원문은 출력하지 않습니다. ZIP/Office는 제한된 크기 내에서 내부도 검사합니다.
- 파일 5 MiB/스냅샷 50 MiB/2,000파일 제한을 넘으면 검사 생략 대신 차단합니다. 검사기 자체도 index 버전이며, unstaged 검사기 수정으로 기준을 바꿀 수 없습니다.
- `check_security.py`는 기존의 **수동 심화 검사**로 남깁니다. 로컬 키와 작업 폴더/이력을 읽으므로 staged-only Hook에 넣지 않았습니다.

## 실제 Hook 통합 검증

```powershell
development/.venv/Scripts/python.exe -X utf8 development/quality/test_hooks.py
```

스크립트가 소유한 임시 저장소에 현재 소스를 복사하고, 그곳에서 실제 커밋을 시도합니다. 원래 저장소는 stage/커밋/푸시하지 않습니다. 정상·실패·환경 누락뿐 아니라 staged/unstaged 불일치, 중복 정책 실행, 사용자 Hook 설정 보존을 검사합니다. 임시 저장소는 종료 시 정리하고, 요약은 Git 제외된 `development/data/hook-verification.json`에 남깁니다. 테스트용 Python 환경은 기존 패키지를 읽기 전용으로 재사용하며 네트워크 설치를 하지 않습니다. 이 통합 검증 전체는 매 커밋마다 실행하지 않습니다.

최종 검증 결과(2026-11-24 실행, 11-25 재개 시 확인): 16개 시나리오 모두 예상 동작. 정상 기본/웹/고위험 커밋 통과, staged 비밀정보·구문 오류·관련 테스트 실패·의존성 불일치·Python/Node/PowerShell 누락·Hook 구문 오류·필수 테스트/gate 누락에서 실제 커밋 차단. unstaged 변경 및 사용자 Hook 설정 보존 확인. 고위험 검사에서는 앱 25개와 정책 5개 테스트를 실행했습니다. 전체 임시 저장소 검증 25.79초, 기본/웹/고위험 개별 커밋 약 0.94/2.87/4.55초였습니다.

## 한계

- 현재 공통 CI workflow는 없으며 이번에 추가하지 않았습니다. 로컬 Hook은 Git이 지원하는 `--no-verify`·설정 변경을 기술적으로 막을 수 없습니다. 규칙상 승인 없이 우회하지 않으며, 원격 강제 검증이 필요하면 별도 CI/브랜치 보호가 필요합니다.
- 패턴 기반 검사로 모든 종류의 비밀정보를 보증하지 않습니다. 인코딩·암호화·이미지/PDF 내부 등은 탐지 한계가 있습니다. 의존성 pin/pip check는 호환성 검사이지 최신 CVE 데이터베이스 취약점 감사가 아닙니다.
- 로컬 테스트는 OS 보안 샌드박스가 아닙니다. 신뢰하지 않는 외부 PR 코드를 실행하기 위한 격리 환경으로 사용하지 않습니다. 악의적 staged 검사기·테스트 변경 자체를 막는 서명/승인 체계는 없습니다.
- 실제 HaiGPT, 브라우저 렌더링, Windows VM 설치, 학교 네트워크, Linux/macOS Hook 실행은 이 자동 검사의 성공 범위가 아닙니다. 필요한 시점에 별도 검증합니다.

공식 근거: [Git Hook](https://git-scm.com/docs/githooks), [core.hooksPath](https://git-scm.com/docs/git-config#Documentation/git-config.txt-corehooksPath), [index 파일 조회](https://git-scm.com/docs/git-ls-files).
