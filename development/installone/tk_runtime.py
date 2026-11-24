"""Python 3.14의 로컬 Tcl ZIP 배포를 위한 프로세스 한정 경로 준비."""
import os
import sys
import zipfile
from pathlib import Path


def prepare_tk():
    source = Path(sys.base_prefix) / "tcl"
    destination = Path(__file__).resolve().parents[1] / "data" / "tk-runtime"
    for prefix, folder, env in (("libtcl", "tcl_library", "TCL_LIBRARY"), ("libtk", "tk_library", "TK_LIBRARY")):
        archives = sorted(source.glob(prefix + "*.zip"))
        if env in os.environ or len(archives) != 1:
            continue
        # 사용자 Python 설치에 포함된 런타임만 복사. 전역 Python/환경변수 변경 없음.
        with zipfile.ZipFile(archives[0]) as archive:
            for item in archive.infolist():
                target = (destination / item.filename).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise ValueError("잘못된 Tcl 런타임 경로")
            archive.extractall(destination)
        os.environ[env] = str(destination / folder)
