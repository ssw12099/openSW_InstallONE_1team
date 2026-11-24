import hashlib
import re
from pathlib import Path
from fastapi import HTTPException

MAX_SIZE = 200 * 1024 * 1024
EXTENSIONS = {'.exe', '.msi', '.msix', '.msixbundle', '.zip', '.pdf', '.txt'}

def validate_filename(name: str):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,149}', name) or Path(name).suffix.lower() not in EXTENSIONS:
        raise HTTPException(400, '영문·숫자 파일명 및 허용된 확장자를 사용하세요.')
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
        raise HTTPException(400, 'Windows 예약 파일명입니다.')


def save_and_hash(source, destination: Path):
    size = 0
    digest = hashlib.sha256()
    with destination.open('xb') as out:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_SIZE:
                raise HTTPException(413, '최대 200 MiB까지 등록할 수 있습니다.')
            digest.update(chunk)
            out.write(chunk)
    if not size:
        raise HTTPException(400, '빈 파일은 등록할 수 없습니다.')
    return size, digest.hexdigest()
