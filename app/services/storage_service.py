import os
from typing import Optional


def evidence_dir(files_dir: str, hash_value: str) -> str:
    return os.path.join(files_dir, hash_value)


def ensure_evidence_dir(files_dir: str, hash_value: str) -> str:
    path = evidence_dir(files_dir, hash_value)
    os.makedirs(path, exist_ok=True)
    return path


def save_ots_file(files_dir: str, hash_value: str, content: bytes) -> str:
    base_dir = ensure_evidence_dir(files_dir, hash_value)
    target = os.path.join(base_dir, f"{hash_value}.ots")
    with open(target, "wb") as handle:
        handle.write(content)
    return target


def save_tsa_file(files_dir: str, hash_value: str, content: bytes) -> str:
    base_dir = ensure_evidence_dir(files_dir, hash_value)
    target = os.path.join(base_dir, f"{hash_value}.tsr")
    with open(target, "wb") as handle:
        handle.write(content)
    return target


def delete_evidence_files(files_dir: str, hash_value: str) -> None:
    base_dir = evidence_dir(files_dir, hash_value)
    if not os.path.isdir(base_dir):
        return
    for name in os.listdir(base_dir):
        path = os.path.join(base_dir, name)
        if os.path.isfile(path):
            os.remove(path)
    try:
        os.rmdir(base_dir)
    except OSError:
        pass


def read_file(path: Optional[str]) -> Optional[bytes]:
    if not path or not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()
