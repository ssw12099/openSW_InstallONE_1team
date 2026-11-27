"""[개발 B] Windows 설치 실행.

plan.py        : 선택한 프로필들을 하나의 실행 계획으로 합침
ansible_exec.py: 실제 좌석 — ansible-runner로 플레이북 실행 (Linux/WSL2 필요)
mock_runner.py : 모의 좌석 — 같은 단계·같은 기록 형식으로 흐름만 재현
events.py      : Ansible 이벤트 → 좌석별 상태(연결/설치/검증 실패 구분)
"""
from .plan import build_plan

__all__ = ["build_plan"]
