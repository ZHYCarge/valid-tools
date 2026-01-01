import base64
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


logger = logging.getLogger("app")


@dataclass(frozen=True)
class TSAResult:
    success: bool
    error: Optional[str]
    info: Dict[str, Any]
    tsr_bytes: Optional[bytes] = None


def _response_to_bytes(response: Any) -> Optional[bytes]:
    if response is None:
        return None
    if isinstance(response, (bytes, bytearray)):
        return bytes(response)
    if isinstance(response, str):
        return response.encode("utf-8")
    if hasattr(response, "binary"):
        return response.binary
    if hasattr(response, "content"):
        return response.content
    if hasattr(response, "data"):
        return response.data
    return None


def create_tsa(hash_hex: str, tsa_url: str) -> TSAResult:
    try:
        if not tsa_url:
            return TSAResult(success=False, error="TSA_URL not configured", info={})
        try:
            from rfc3161ng import RemoteTimestamper  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            return TSAResult(success=False, error=str(exc), info={})
        digest = bytes.fromhex(hash_hex)
        timestamper = RemoteTimestamper(tsa_url, hashname="sha256")
        response = timestamper(digest=digest)
        tsr_bytes = _response_to_bytes(response)
        if not tsr_bytes:
            return TSAResult(success=False, error="TSA response empty", info={})
        info, error = _extract_tsa_info(tsr_bytes)
        if error:
            preview = tsr_bytes[:200]
            return TSAResult(
                success=False,
                error=error,
                info={"preview": preview.decode("utf-8", errors="replace")},
            )
        return TSAResult(success=True, error=None, info=info, tsr_bytes=tsr_bytes)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("TSA stamp failed")
        return TSAResult(success=False, error=str(exc), info={})


def verify_tsa(tsr_bytes: bytes, hash_hex: Optional[str] = None) -> TSAResult:
    try:
        try:
            import rfc3161ng  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            return TSAResult(success=False, error=str(exc), info={})
        info, error = _extract_tsa_info(tsr_bytes)
        if error:
            return TSAResult(success=False, error=error, info=info)
        if hash_hex:
            hash_error = _check_tsa_hash(rfc3161ng, tsr_bytes, hash_hex)
            if hash_error:
                return TSAResult(success=False, error=hash_error, info=info)
        return TSAResult(success=True, error=None, info=info)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("TSA verify failed")
        return TSAResult(success=False, error=str(exc), info={})


def _decode_tsa_response(decoder, tsr_bytes: bytes):
    try:
        return decoder(tsr_bytes)
    except Exception:
        try:
            tsr_bytes.decode("ascii")
        except UnicodeDecodeError:
            raise ValueError("tsa response is binary but not RFC3161 TimeStampResp")
        text = tsr_bytes.strip()
        if text.startswith(b"-----BEGIN"):
            parts = text.splitlines()
            b64 = b"".join(line for line in parts if not line.startswith(b"-----"))
            return decoder(base64.b64decode(b64))
        b64_text = text.replace(b"\n", b"").replace(b"\r", b"")
        allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        if any(ch not in allowed for ch in b64_text):
            raise ValueError("tsa response is not base64 or ASN.1 data")
        missing = (-len(b64_text)) % 4
        if missing:
            b64_text += b"=" * missing
        try:
            return decoder(base64.b64decode(b64_text, validate=True))
        except Exception:
            return decoder(base64.b64decode(b64_text))


def _extract_tsa_info(tsr_bytes: bytes) -> Tuple[Dict[str, Any], Optional[str]]:
    try:
        import rfc3161ng  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        return {}, str(exc)
    info: Dict[str, Any] = {}
    decoder = getattr(rfc3161ng, "decode_timestamp_response", None)
    if decoder:
        try:
            tsr = _decode_tsa_response(decoder, tsr_bytes)
            status = getattr(tsr, "status", None)
            if status is not None:
                info["status"] = str(status)
            time_value = getattr(tsr, "time", None)
            if time_value is not None:
                info["time"] = str(time_value)
            info["format"] = "tsr"
            return info, None
        except Exception:
            pass
    token_parser = getattr(rfc3161ng, "get_timestamp", None)
    if callable(token_parser):
        try:
            timestamp = token_parser(tsr_bytes)
            info["time"] = str(timestamp)
            info["format"] = "tst"
            return info, None
        except Exception as exc:
            return info, f"invalid tsa response: {exc}"
    return info, "invalid tsa response: decoder unavailable"


def _check_tsa_hash(rfc3161ng, tsr_bytes: bytes, hash_hex: str) -> Optional[str]:
    try:
        digest = bytes.fromhex(hash_hex)
    except ValueError:
        return "invalid hash hex"
    try:
        tst = _extract_tst_token(rfc3161ng, tsr_bytes)
        if tst is None:
            return "invalid tsa response: missing timestamp token"
        imprint, debug_info = _extract_message_imprint(rfc3161ng, tst)
        if imprint is None:
            return "invalid tsa response: missing message imprint"
        if imprint != digest:
            return f"hash mismatch: digest not equal ({debug_info})"
        return None
    except Exception as exc:
        return f"hash mismatch: {exc}"


def _extract_tst_token(rfc3161ng, tsr_bytes: bytes):
    decoder = getattr(rfc3161ng, "decode_timestamp_response", None)
    if decoder:
        try:
            tsr = _decode_tsa_response(decoder, tsr_bytes)
            tst = getattr(tsr, "time_stamp_token", None)
            if tst is not None:
                return tst
        except Exception:
            pass
    try:
        from pyasn1.codec.der import decoder as der_decoder  # type: ignore
        return der_decoder.decode(tsr_bytes, asn1Spec=rfc3161ng.TimeStampToken())[0]
    except Exception:
        return None


def _extract_message_imprint(rfc3161ng, tst) -> Tuple[Optional[bytes], Dict[str, Any]]:
    try:
        debug_info: Dict[str, Any] = {}
        tst_info = None
        if hasattr(tst, "tst_info"):
            tst_info = tst.tst_info
        else:
            from pyasn1.codec.ber import decoder as ber_decoder  # type: ignore
            content = tst.getComponentByName("content").getComponentByName("contentInfo").getComponentByName("content")
            inner, substrate = ber_decoder.decode(bytes(content))
            if substrate:
                return None, debug_info
            tst_info, substrate = ber_decoder.decode(bytes(inner), asn1Spec=rfc3161ng.TSTInfo())
            if substrate:
                return None, debug_info
        if tst_info is None:
            return None, debug_info
        message_imprint = tst_info.getComponentByName("messageImprint")
        if message_imprint is None:
            return None, debug_info
        try:
            algorithm = message_imprint.getComponentByName("hashAlgorithm")
            if algorithm is not None:
                oid = str(algorithm.getComponentByName("algorithm"))
                debug_info["hash_oid"] = oid
                debug_info["hash_alg"] = rfc3161ng.oid_to_hash.get(oid)
        except Exception:
            pass
        digest_bytes = bytes(message_imprint.getComponentByName("hashedMessage"))
        debug_info["imprint_hex"] = digest_bytes.hex()
        return digest_bytes, debug_info
    except Exception:
        return None, {}
