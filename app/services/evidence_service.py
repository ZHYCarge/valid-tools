import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.config import load_settings
from app.services.ots_service import create_ots, verify_ots
from app.services.tsa_service import create_tsa, verify_tsa
from app.services.storage_service import (
    delete_evidence_files,
    read_file,
    save_ots_file,
    save_tsa_file,
)
from app.storage import evidence_repo


logger = logging.getLogger("ops")


@dataclass(frozen=True)
class EvidenceResult:
    hash_value: str
    ots_status: str
    tsa_status: str
    ots_error: Optional[str]
    tsa_error: Optional[str]
    tsa_info: Dict[str, Any]
    record: Dict[str, Any]
    saved: bool
    ots_bytes: Optional[bytes]
    tsa_bytes: Optional[bytes]
    download_name_base: Optional[str]


def _status_from_result(success: bool) -> str:
    return "success" if success else "failed"


def process_submission(
    conn,
    files_dir: str,
    tsa_url: str,
    hash_value: str,
    ots_enabled: bool,
    tsa_enabled: bool,
    save_record: bool = True,
    download_name_base: Optional[str] = None,
) -> EvidenceResult:
    ots_error = None
    tsa_error = None
    tsa_info: Dict[str, Any] = {}
    ots_bytes: Optional[bytes] = None
    tsa_bytes: Optional[bytes] = None

    if save_record:
        existing = evidence_repo.fetch_by_hash(conn, hash_value)
        if existing:
            ots_status = existing["ots_status"]
            tsa_status = existing["tsa_status"]
        else:
            ots_status = "pending"
            tsa_status = "pending"
            evidence_repo.insert_or_ignore(
                conn,
                {
                    "hash": hash_value,
                    "ots_status": ots_status,
                    "tsa_status": tsa_status,
                    "ots_path": None,
                    "tsa_path": None,
                },
            )
            existing = evidence_repo.fetch_by_hash(conn, hash_value)

        ots_path = existing.get("ots_path") if existing else None
        tsa_path = existing.get("tsa_path") if existing else None
        if ots_status == "success" and not read_file(ots_path):
            ots_status = "failed"
        if tsa_status == "success" and not read_file(tsa_path):
            tsa_status = "failed"

        if ots_status != "success":
            if ots_enabled:
                ots_result = create_ots(hash_value, calendars=load_settings().ots_calendar_urls)
                ots_status = _status_from_result(ots_result.success)
                ots_error = ots_result.error
                if ots_result.success and ots_result.ots_bytes:
                    ots_path = save_ots_file(files_dir, hash_value, ots_result.ots_bytes)
            else:
                ots_status = "disabled"
                ots_error = "ots disabled"

        if tsa_status != "success":
            if tsa_enabled:
                tsa_result = create_tsa(hash_value, tsa_url)
                tsa_status = _status_from_result(tsa_result.success)
                tsa_error = tsa_result.error
                tsa_info = tsa_result.info or {}
                if tsa_result.success and tsa_result.tsr_bytes:
                    tsa_path = save_tsa_file(files_dir, hash_value, tsa_result.tsr_bytes)
            else:
                tsa_status = "disabled"
                tsa_error = "tsa disabled"
                tsa_info = {}

        evidence_repo.update_statuses(conn, hash_value, ots_status, tsa_status, ots_path, tsa_path)
        record = evidence_repo.fetch_by_hash(conn, hash_value) or {}
    else:
        ots_status = "pending"
        tsa_status = "pending"

        if ots_enabled:
            ots_result = create_ots(hash_value, calendars=load_settings().ots_calendar_urls)
            ots_status = _status_from_result(ots_result.success)
            ots_error = ots_result.error
            if ots_result.success and ots_result.ots_bytes:
                ots_bytes = ots_result.ots_bytes
        else:
            ots_status = "disabled"
            ots_error = "ots disabled"

        if tsa_enabled:
            tsa_result = create_tsa(hash_value, tsa_url)
            tsa_status = _status_from_result(tsa_result.success)
            tsa_error = tsa_result.error
            tsa_info = tsa_result.info or {}
            if tsa_result.success and tsa_result.tsr_bytes:
                tsa_bytes = tsa_result.tsr_bytes
        else:
            tsa_status = "disabled"
            tsa_error = "tsa disabled"
            tsa_info = {}

        record = {}

    logger.info(
        "evidence processed hash=%s ots=%s tsa=%s",
        hash_value,
        ots_status,
        tsa_status,
    )
    return EvidenceResult(
        hash_value=hash_value,
        ots_status=ots_status,
        tsa_status=tsa_status,
        ots_error=ots_error,
        tsa_error=tsa_error,
        tsa_info=tsa_info,
        record=record,
        saved=save_record,
        ots_bytes=ots_bytes,
        tsa_bytes=tsa_bytes,
        download_name_base=download_name_base,
    )


def verify_submission(
    conn,
    files_dir: str,
    hash_value: str,
    ots_enabled: bool,
    tsa_enabled: bool,
    ots_bytes_override: Optional[bytes] = None,
    tsr_bytes_override: Optional[bytes] = None,
) -> Dict[str, Any]:
    record = evidence_repo.fetch_by_hash(conn, hash_value)
    ots_info: Dict[str, Any] = {"success": False}
    tsa_info: Dict[str, Any] = {"success": False}

    ots_bytes = ots_bytes_override
    if ots_enabled:
        if not ots_bytes and record:
            ots_bytes = read_file(record.get("ots_path"))
        if ots_bytes:
            ots_result = verify_ots(ots_bytes, hash_hex=hash_value)
            ots_info = {"success": ots_result.success, "error": ots_result.error, "info": ots_result.info}
            if record and ots_result.updated_ots_bytes and record.get("ots_path"):
                with open(record["ots_path"], "wb") as handle:
                    handle.write(ots_result.updated_ots_bytes)
        elif not record:
            ots_info = {"success": False, "error": "ots file required when record missing"}
        else:
            ots_info = {"success": False, "error": "ots file missing"}
    else:
        ots_info = {"success": False, "error": "ots disabled"}

    tsr_bytes = tsr_bytes_override
    if tsa_enabled:
        if not tsr_bytes and record:
            tsr_bytes = read_file(record.get("tsa_path"))
        if tsr_bytes:
            tsa_result = verify_tsa(tsr_bytes, hash_hex=hash_value)
            tsa_info = {"success": tsa_result.success, "error": tsa_result.error, "info": tsa_result.info}
        elif not record:
            tsa_info = {"success": False, "error": "tsa file required when record missing"}
        else:
            tsa_info = {"success": False, "error": "tsa file missing"}
    else:
        tsa_info = {"success": False, "error": "tsa disabled"}

    return {
        "hash": hash_value,
        "exists": bool(record),
        "record": record,
        "ots": ots_info,
        "tsa": tsa_info,
    }


def delete_evidence(conn, files_dir: str, hash_value: str, keep_files: bool) -> bool:
    record = evidence_repo.fetch_by_hash(conn, hash_value)
    if not record:
        return False
    if not keep_files:
        delete_evidence_files(files_dir, hash_value)
    evidence_repo.delete_by_hash(conn, hash_value)
    logger.info("evidence deleted hash=%s keep_files=%s", hash_value, keep_files)
    return True
