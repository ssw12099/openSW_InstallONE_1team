# Windows 배포 에이전트
`agent.ps1` 기본 모드는 다운로드 전용입니다. `-AllowPythonInstall` 실행 시 별도로 검증한 해시를 입력하고 INSTALL로 동의한 세션에서만 공식 Python 3.13 x64 자동 설치 작업을 수행합니다. `install_python.ps1`을 같은 폴더에 복사해야 하며 고정된 사용자별 설치 옵션 및 버전·예제 검사를 수행합니다. 관리자 권한으로 실행하지 마세요. [실행 안내](../../README.md#4-1-python-원격-자동-설치-windows-x64-현재-사용자-계정) 참고.
