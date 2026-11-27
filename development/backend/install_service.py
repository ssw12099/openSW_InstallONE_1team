from backend.config import (
    INSTALL_MODE,
    INSTALL_ENGINE,
    WINRM_HOST,
    is_ansible_configured
)

from backend.ai_service import PROFILES
from backend.remote_service import install_program, PACKAGE_CONFIG
from backend.ansible_service import install_program_ansible

from backend.database import (
    create_job,
    save_result,
    update_job_status,
    get_job_detail,
    get_pcs
)


def execute_installation(request, pc_ids, profiles):
    available_pcs = {
        pc["id"]: pc for pc in get_pcs()
    }

    pc_ids = sorted(set(pc_ids))
    profiles = list(dict.fromkeys(profiles))

    # 1. 설치 요청 유효성 검사
    if not pc_ids:
        raise ValueError("선택된 PC가 없습니다.")

    if not profiles:
        raise ValueError("설치 프로그램이 없습니다.")

    if any(pc_id not in available_pcs for pc_id in pc_ids):
        raise ValueError("등록되지 않은 PC입니다.")

    if any(profile not in PROFILES for profile in profiles):
        raise ValueError("지원하지 않는 설치 프로필입니다.")

    if INSTALL_MODE not in ("mock", "real"):
        raise ValueError("지원하지 않는 설치 모드입니다.")

    # 2. 실제 설치 엔진 및 대상 검사
    if INSTALL_MODE == "real":

        if INSTALL_ENGINE not in ("pywinrm", "ansible"):
            raise ValueError("지원하지 않는 설치 엔진입니다.")

        if INSTALL_ENGINE == "ansible" and not is_ansible_configured():
            raise ValueError("Ansible 실행 설정이 완료되지 않았습니다.")

        for pc_id in pc_ids:
            pc = available_pcs[pc_id]

            if (
                pc_id != 1
                or not WINRM_HOST
                or pc["ip_address"] != WINRM_HOST
            ):
                raise ValueError(
                    f"PC-{pc_id:02d}는 실제 원격 설치 대상이 아닙니다."
                )

        if any(p not in PACKAGE_CONFIG for p in profiles):
            raise ValueError("실제 설치를 지원하지 않는 프로그램입니다.")

    job_ids = []

    # 3. 프로그램별 설치 작업 생성
    for profile in profiles:
        job_id = create_job(
            request=request,
            profile=profile,
            mode=INSTALL_MODE
        )

        failed_count = 0

        try:
            for pc_id in pc_ids:

                # 4. 모의 설치
                if INSTALL_MODE == "mock":
                    result = {
                        "status": "simulated",
                        "installed_version": None,
                        "verification": "not_verified",
                        "log": (
                            f"[MOCK] PC-{pc_id:02d}: "
                            f"{PROFILES[profile]['name']} "
                            "설치 시뮬레이션 완료"
                        )
                    }

                # 5. 실제 원격 설치
                else:
                    try:

                        # Ansible 설치 방식
                        if INSTALL_ENGINE == "ansible":
                            result = install_program_ansible(profile)

                        # 기존 pywinrm 설치 방식
                        else:
                            result = install_program(profile)

                    except Exception as e:
                        result = {
                            "status": "failed",
                            "installed_version": None,
                            "verification": "not_verified",
                            "log": (
                                "[ERROR] 원격 작업 실패: "
                                f"{type(e).__name__}"
                            )
                        }

                # 6. 설치 실패 횟수 확인
                if result["status"] == "failed":
                    failed_count += 1

                # 7. SQLite에 설치 결과 저장
                save_result(
                    job_id=job_id,
                    pc_id=pc_id,
                    status=result["status"],
                    installed_version=result["installed_version"],
                    verification=result["verification"],
                    log=result["log"]
                )

            # 8. 최종 작업 상태 결정
            if INSTALL_MODE == "mock":
                final_status = "simulated"

            elif failed_count == 0:
                final_status = "success"

            elif failed_count == len(pc_ids):
                final_status = "failed"

            else:
                final_status = "partial_success"

            update_job_status(job_id, final_status)

        except Exception:
            update_job_status(job_id, "failed")
            raise

        job_ids.append(job_id)

    # 9. 최종 설치 결과 반환
    return {
        "mode": INSTALL_MODE,
        "message": (
            "모의 설치 작업이 완료되었습니다."
            if INSTALL_MODE == "mock"
            else "실제 원격 설치 요청 처리가 완료되었습니다."
        ),
        "jobs": [
            get_job_detail(job_id)
            for job_id in job_ids
        ]
    }