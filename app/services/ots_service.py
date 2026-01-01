import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Callable, List, Tuple as Tup

import requests

from app.config import load_settings

logger = logging.getLogger("app")


@dataclass(frozen=True)
class OTSResult:
    success: bool
    error: Optional[str]
    info: Dict[str, Any]
    ots_bytes: Optional[bytes] = None
    updated_ots_bytes: Optional[bytes] = None


def _load_ots_client() -> Tuple[Optional[Tuple[Callable, Callable, Any]], Optional[str]]:
    try:
        from opentimestamps.client import stamp as ots_stamp  # type: ignore
        from opentimestamps.client import verify as ots_verify  # type: ignore
        from opentimestamps.core.timestamp import Timestamp  # type: ignore
        return (ots_stamp, ots_verify, Timestamp), None
    except Exception as exc:
        primary_error = f"import opentimestamps.client failed: {exc}"
    try:
        import opentimestamps  # type: ignore
        from opentimestamps.core.timestamp import Timestamp  # type: ignore
        ots_stamp = getattr(opentimestamps, "stamp", None)
        ots_verify = getattr(opentimestamps, "verify", None)
        if callable(ots_stamp) and callable(ots_verify):
            return (ots_stamp, ots_verify, Timestamp), None
    except Exception as exc:
        fallback_error = f"fallback opentimestamps import failed: {exc}"
        return None, f"{primary_error}; {fallback_error}"
    return None, primary_error


def _create_ots_with_calendar(hash_hex: str, calendars: List[str]) -> OTSResult:
    try:
        from opentimestamps.calendar import RemoteCalendar  # type: ignore
        from opentimestamps.core.op import OpSHA256  # type: ignore
        from opentimestamps.core.serialize import BytesSerializationContext  # type: ignore
        from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp  # type: ignore
    except Exception as exc:
        return OTSResult(success=False, error=f"opentimestamps core unavailable: {exc}", info={})

    if not calendars:
        return OTSResult(success=False, error="no calendars configured", info={})
    digest = bytes.fromhex(hash_hex)
    base_ts = Timestamp(digest)
    errors = []
    success_count = 0

    for url in calendars:
        try:
            cal = RemoteCalendar(url)
            cal_ts = cal.submit(digest)
            base_ts.merge(cal_ts)
            success_count += 1
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    if success_count == 0:
        return OTSResult(success=False, error="all calendars failed", info={"errors": errors})

    detached = DetachedTimestampFile(OpSHA256(), base_ts)
    ctx = BytesSerializationContext()
    detached.serialize(ctx)
    return OTSResult(
        success=True,
        error=None,
        info={"calendar_success": success_count, "calendar_errors": errors},
        ots_bytes=ctx.getbytes(),
    )


def _collect_attestation_info(timestamp) -> Dict[str, Any]:
    try:
        from opentimestamps.core import notary  # type: ignore
    except Exception:
        return {}
    types: List[str] = []
    has_blockchain = False
    has_pending = False
    for _msg, att in timestamp.all_attestations():
        types.append(att.__class__.__name__)
        if isinstance(att, (notary.BitcoinBlockHeaderAttestation, notary.LitecoinBlockHeaderAttestation)):
            has_blockchain = True
        if isinstance(att, notary.PendingAttestation):
            has_pending = True
    return {
        "attestations": len(types),
        "attestation_types": types,
        "has_blockchain_proof": has_blockchain,
        "has_pending_attestations": has_pending,
    }


def _lookup_block_hash(chain: str, height: int) -> Tuple[Optional[str], Optional[str]]:
    settings = load_settings()
    if chain == "bitcoin":
        api_template = settings.btc_block_hash_api
    elif chain == "litecoin":
        api_template = settings.ltc_block_hash_api
    else:
        return None, "unsupported chain"
    if not api_template:
        return None, "block hash api disabled"
    url = api_template.format(height=height)
    try:
        resp = requests.get(url, timeout=8)
        if not resp.ok:
            return None, f"api status {resp.status_code}"
        text = resp.text.strip()
        if not text:
            return None, "empty api response"
        if text.startswith("{"):
            data = resp.json()
            if isinstance(data, dict):
                if isinstance(data.get("data"), dict) and data["data"].get("hash"):
                    return str(data["data"]["hash"]), None
                if data.get("hash"):
                    return str(data["hash"]), None
            return None, "unexpected api response"
        return text, None
    except Exception as exc:
        return None, str(exc)


def _build_explorer_url(chain: str, height: int, block_hash: Optional[str]) -> Optional[str]:
    settings = load_settings()
    if chain == "bitcoin":
        block_template = settings.btc_explorer_block_url
        height_template = settings.btc_explorer_height_url
    elif chain == "litecoin":
        block_template = settings.ltc_explorer_block_url
        height_template = settings.ltc_explorer_height_url
    else:
        return None
    if block_hash and block_template:
        return block_template.format(hash=block_hash, height=height)
    if height_template:
        return height_template.format(height=height, hash=block_hash or "")
    return None


def _collect_blockchain_proofs(timestamp) -> List[Dict[str, Any]]:
    try:
        from opentimestamps.core import notary  # type: ignore
    except Exception:
        return []
    proofs: List[Dict[str, Any]] = []
    seen = set()
    cache: Dict[Tuple[str, int], Tuple[Optional[str], Optional[str]]] = {}
    for _msg, att in timestamp.all_attestations():
        chain = None
        if isinstance(att, notary.BitcoinBlockHeaderAttestation):
            chain = "bitcoin"
        elif isinstance(att, notary.LitecoinBlockHeaderAttestation):
            chain = "litecoin"
        if not chain:
            continue
        height = int(att.height)
        key = (chain, height)
        if key in seen:
            continue
        seen.add(key)
        if key not in cache:
            cache[key] = _lookup_block_hash(chain, height)
        block_hash, hash_error = cache[key]
        proof = {
            "chain": chain,
            "height": height,
            "block_hash": block_hash,
            "explorer_url": _build_explorer_url(chain, height, block_hash),
        }
        if hash_error:
            proof["block_hash_error"] = hash_error
        proofs.append(proof)
    return proofs


def _collect_pending_attestations(timestamp) -> List[Tuple[Any, Any]]:
    try:
        from opentimestamps.core import notary  # type: ignore
    except Exception:
        return []
    pending: List[Tuple[Any, Any]] = []

    def walk(node) -> None:
        for att in node.attestations:
            if isinstance(att, notary.PendingAttestation):
                pending.append((node, att))
        for child in node.ops.values():
            walk(child)

    walk(timestamp)
    return pending


def create_ots(hash_hex: str, calendars: Optional[List[str]] = None) -> OTSResult:
    try:
        client, error = _load_ots_client()
        if not client:
            return _create_ots_with_calendar(hash_hex, calendars or [])
        ots_stamp, _ots_verify, Timestamp = client
        digest = bytes.fromhex(hash_hex)
        timestamp = Timestamp(digest)
        ots_stamp(timestamp)
        ots_bytes = timestamp.serialize()
        return OTSResult(success=True, error=None, info={}, ots_bytes=ots_bytes)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("OTS stamp failed")
        return OTSResult(success=False, error=str(exc), info={}, ots_bytes=None)


def verify_ots(ots_bytes: bytes, hash_hex: Optional[str] = None) -> OTSResult:
    try:
        client, error = _load_ots_client()
        if not client:
            try:
                from opentimestamps.core.serialize import BytesDeserializationContext  # type: ignore
                from opentimestamps.core.timestamp import DetachedTimestampFile  # type: ignore
                from opentimestamps.calendar import RemoteCalendar  # type: ignore
                from opentimestamps.core import notary  # type: ignore
            except Exception as exc:
                return OTSResult(success=False, error=f"opentimestamps core unavailable: {exc}", info={})
            ctx = BytesDeserializationContext(ots_bytes)
            detached = DetachedTimestampFile.deserialize(ctx)
            info: Dict[str, Any] = _collect_attestation_info(detached.timestamp)
            if hash_hex:
                expected = bytes.fromhex(hash_hex)
                if detached.timestamp.msg != expected:
                    info["hash_match"] = False
                    return OTSResult(success=False, error="hash mismatch", info=info)
            pending = _collect_pending_attestations(detached.timestamp)
            upgraded = False
            upgrade_errors: List[str] = []
            calendar_results: List[Dict[str, Any]] = []
            if pending:
                for node, att in pending:
                    uri = att.uri
                    try:
                        cal = RemoteCalendar(uri)
                        cal_ts = cal.get_timestamp(node.msg)
                        node.merge(cal_ts)
                        upgraded = True
                        calendar_results.append(
                            {
                                "uri": uri,
                                "success": True,
                                "summary": _collect_attestation_info(cal_ts),
                            }
                        )
                    except Exception as exc:
                        upgrade_errors.append(f"{uri}: {exc}")
                        calendar_results.append(
                            {
                                "uri": uri,
                                "success": False,
                                "error": str(exc),
                            }
                        )
            info = _collect_attestation_info(detached.timestamp)
            proofs = _collect_blockchain_proofs(detached.timestamp)
            if proofs:
                info["blockchain_proofs"] = proofs
            if upgrade_errors:
                info["upgrade_errors"] = upgrade_errors
            if calendar_results:
                info["calendar_results"] = calendar_results
            updated_ots_bytes = None
            if upgraded:
                from opentimestamps.core.serialize import BytesSerializationContext  # type: ignore
                new_detached = DetachedTimestampFile(detached.file_hash_op, detached.timestamp)
                ctx_out = BytesSerializationContext()
                new_detached.serialize(ctx_out)
                updated_ots_bytes = ctx_out.getbytes()
            if hash_hex:
                expected = bytes.fromhex(hash_hex)
                if detached.timestamp.msg != expected:
                    return OTSResult(success=False, error="hash mismatch", info=info)
                info["hash_match"] = True
            return OTSResult(success=True, error=None, info=info, updated_ots_bytes=updated_ots_bytes)
        _ots_stamp, ots_verify, Timestamp = client
        timestamp = Timestamp.deserialize(ots_bytes)
        result = ots_verify(timestamp)
        info: Dict[str, Any] = _collect_attestation_info(timestamp)
        proofs = _collect_blockchain_proofs(timestamp)
        if proofs:
            info["blockchain_proofs"] = proofs
        if hash_hex:
            expected = bytes.fromhex(hash_hex)
            if timestamp.msg != expected:
                info["hash_match"] = False
                return OTSResult(success=False, error="hash mismatch", info=info)
            info["hash_match"] = True
        if result is not None:
            info["result"] = str(result)
        return OTSResult(success=True, error=None, info=info)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("OTS verify failed")
        return OTSResult(success=False, error=str(exc), info={})
