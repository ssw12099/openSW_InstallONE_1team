import re

from backend.config import AI_MODE
from backend.database import get_pcs


PROFILES = {
    "python": {
        "name": "Python",
        "keywords": ["python", "파이썬"]
    },
    "java": {
        "name": "Java JDK",
        "keywords": ["java", "자바", "jdk"]
    },
    "nodejs": {
        "name": "Node.js",
        "keywords": ["node.js", "nodejs", "node", "노드"]
    },
    "vscode": {
        "name": "Visual Studio Code",
        "keywords": ["vscode", "vs code", "visual studio code", "vs코드"]
    },
    "git": {
        "name": "Git",
        "keywords": ["git", "깃"]
    }
}


def extract_pc_ids(request):
    available_ids = {pc["id"] for pc in get_pcs()}
    pc_ids = set()

    # 전체 PC 요청
    if re.search(r"전체|모든|전부", request):
        return sorted(available_ids)

    # 범위 요청: 1번부터 4번, 1~4번
    ranges = re.findall(
        r"(\d+)\s*번?\s*(?:부터|~|～|-)\s*(\d+)\s*번?",
        request
    )

    for start, end in ranges:
        start, end = int(start), int(end)

        if start > end:
            raise ValueError("PC 번호 범위가 올바르지 않습니다.")

        if start not in available_ids or end not in available_ids:
            raise ValueError("등록되지 않은 PC 번호입니다.")

        pc_ids.update(range(start, end + 1))

    # 개별 PC 번호 요청
    numbers = re.findall(
        r"(\d+)\s*번|PC[-\s]*(\d+)",
        request,
        re.IGNORECASE
    )

    for first, second in numbers:
        pc_ids.add(int(first or second))

    if pc_ids - available_ids:
        raise ValueError("등록되지 않은 PC 번호입니다.")

    return sorted(pc_ids)


def extract_profiles(request):
    request = request.lower()
    profiles = []

    for profile_id, profile in PROFILES.items():
        if any(
            keyword in request
            for keyword in profile["keywords"]
        ):
            profiles.append(profile_id)

    return profiles


def analyze_mock(request):
    pc_ids = extract_pc_ids(request)
    profiles = extract_profiles(request)

    if not pc_ids:
        raise ValueError("대상 PC 번호를 확인할 수 없습니다.")

    if not profiles:
        raise ValueError("지원하는 설치 프로그램을 확인할 수 없습니다.")

    return {
        "request": request,
        "pc_ids": pc_ids,
        "pc_names": [
            f"PC-{pc_id:02d}" for pc_id in pc_ids
        ],
        "profiles": profiles,
        "profile_names": [
            PROFILES[p]["name"] for p in profiles
        ],
        "action": "install",
        "analysis_mode": "mock",
        "status": "pending_approval"
    }


def analyze_request(request):
    if AI_MODE == "mock":
        return analyze_mock(request)

    raise ValueError("실제 HaiGPT API 연동이 아직 설정되지 않았습니다.")