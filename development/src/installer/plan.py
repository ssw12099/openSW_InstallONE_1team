"""선택한 프로필들을 하나의 설치 계획(InstallPlan)으로 합칩니다.

includes에 적은 프로필의 설치 항목도 함께 넣습니다. 그래서 python-data는 Python 자체를
따로 적지 않고 python-basic을 포함하기만 하면 되고, Python 버전은 python-basic 한 곳만 고치면 됩니다.
"""
from __future__ import annotations

from ..common.models import InstallPlan, Profile


def _with_includes(profile_ids: list[str], profiles: dict[str, Profile]) -> list[str]:
    """포함된 프로필을 먼저, 그다음 자기 자신 순서로 펼침 (중복·순환은 한 번만)."""
    order: list[str] = []
    seen: set[str] = set()

    def visit(pid: str, parent: str | None) -> None:
        if pid in seen:
            return
        if pid not in profiles:
            raise ValueError(f"{parent} 프로필이 포함하는 '{pid}' 프로필이 없어요" if parent else f"없는 프로필: {pid}")
        seen.add(pid)
        for included in profiles[pid].includes:
            visit(included, pid)
        order.append(pid)

    for pid in profile_ids:
        visit(pid, None)
    return order


def build_plan(profile_ids: list[str], profiles: dict[str, Profile]) -> InstallPlan:
    unknown = [pid for pid in profile_ids if pid not in profiles]
    if unknown:
        raise ValueError(f"없는 프로필: {', '.join(unknown)}")
    if not profile_ids:
        raise ValueError("설치할 프로필을 하나 이상 골라 주세요.")

    plan = InstallPlan(profiles=list(dict.fromkeys(profile_ids)))
    seen_choco: set[str] = set()
    seen_checks: set[str] = set()
    for pid in _with_includes(plan.profiles, profiles):
        profile = profiles[pid]
        for package in profile.choco:
            if package.name not in seen_choco:
                seen_choco.add(package.name)
                plan.choco.append(package)
        for name in profile.pip:
            if name not in plan.pip:
                plan.pip.append(name)
        for check in profile.checks:
            if check.label not in seen_checks:
                seen_checks.add(check.label)
                plan.checks.append(check)
        for name in profile.examples:
            if name not in plan.examples:
                plan.examples.append(name)
        for name in profile.imports:
            if name not in plan.imports:
                plan.imports.append(name)
    return plan
