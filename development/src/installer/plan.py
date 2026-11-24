"""선택한 프로필들을 하나의 설치 계획(InstallPlan)으로 합칩니다."""
from __future__ import annotations

from ..common.models import InstallPlan, Profile


def build_plan(profile_ids: list[str], profiles: dict[str, Profile]) -> InstallPlan:
    unknown = [pid for pid in profile_ids if pid not in profiles]
    if unknown:
        raise ValueError(f"없는 프로필: {', '.join(unknown)}")
    if not profile_ids:
        raise ValueError("설치할 프로필을 하나 이상 골라 주세요.")

    plan = InstallPlan(profiles=list(dict.fromkeys(profile_ids)))
    seen_choco: set[str] = set()
    seen_checks: set[str] = set()
    for pid in plan.profiles:
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
