from backend.config import INSTALL_MODE
from backend.ai_service import PROFILES
from backend.database import (
    create_job,
    save_result,
    update_job_status,
    get_job_detail,
    get_pcs
)


def execute_installation(request, pc_ids, profiles):
    available_ids = {pc["id"] for pc in get_pcs()}

    pc_ids = sorted(set(pc_ids))
    profiles = list(dict.fromkeys(profiles))

    if not pc_ids:
        raise ValueError("대상 PC가 없습니다.")

    if not profiles:
        raise ValueError("설치 프로그램이 없습니다.")

    if any(pc_id not in available_ids for pc_id in pc_ids):
        raise ValueError("등록되지 않은 PC입니다.")

    if any(profile not in PROFILES for profile in profiles):
        raise ValueError("지원하지 않는 설치 프로필입니다.")

    if INSTALL_MODE != "mock":
        raise ValueError("실제 원격 설치가 아직 연결되지 않았습니다.")

    job_ids = []

    for profile in profiles:
        job_id = create_job(
            request=request,
            profile=profile,
            mode="mock"
        )

        try:
            for pc_id in pc_ids:
                save_result(
                    job_id=job_id,
                    pc_id=pc_id,
                    status="simulated",
                    installed_version=None,
                    verification="not_verified",
                    log=(
                        f"[MOCK] PC-{pc_id:02d}: "
                        f"{PROFILES[profile]['name']} "
                        "설치 작업 시뮬레이션 완료"
                    )
                )

            update_job_status(job_id, "simulated")

        except Exception:
            update_job_status(job_id, "failed")
            raise

        job_ids.append(job_id)

    return {
        "mode": "mock",
        "message": "모의 설치 작업이 완료되었습니다.",
        "jobs": [
            get_job_detail(job_id)
            for job_id in job_ids
        ]
    }