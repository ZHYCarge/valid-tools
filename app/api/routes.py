import base64
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from app.config import load_settings
from app.services import evidence_service
from app.storage import evidence_repo
from app.storage.db import get_connection
from app.utils.logging_config import close_log_handlers, configure_logging
from app.utils.session import create_session, delete_session, get_session


router = APIRouter()


def get_db():
    settings = load_settings()
    conn = get_connection(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def require_login(request: Request):
    token = request.cookies.get("session_id")
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=403, detail="forbidden")
    return session


@router.post("/api/auth/login")
def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    settings = load_settings()
    if not (
        username == settings.basic_auth_user
        and password == settings.basic_auth_pass
    ):
        raise HTTPException(status_code=401, detail="unauthorized")
    token = create_session(username)
    response.set_cookie("session_id", token, httponly=True, samesite="lax")
    return {"authenticated": True}


@router.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("session_id")
    delete_session(token)
    response.delete_cookie("session_id")
    return {"authenticated": False}


@router.get("/api/auth/me")
def auth_me(request: Request):
    token = request.cookies.get("session_id")
    session = get_session(token)
    if not session:
        return {"authenticated": False}
    return {"authenticated": True, "user": session.get("user")}


@router.get("/api/site-info")
def site_info():
    settings = load_settings()
    return {
        "icp_info": settings.icp_info,
        "mps_info": settings.mps_info,
        "mps_code": settings.mps_code,
    }


@router.post("/api/evidence/upload")
async def upload_evidence(
    request: Request,
    hash_value: Optional[str] = Form(None),
    ots_option: Optional[str] = Form(None),
    tsa_option: Optional[str] = Form(None),
    save_option: Optional[str] = Form(None),
    source_name: Optional[str] = Form(None),
    db=Depends(get_db),
):
    if not hash_value:
        raise HTTPException(status_code=400, detail="hash is required")
    ots_enabled = (ots_option or "enable").lower() != "disable"
    tsa_enabled = (tsa_option or "enable").lower() != "disable"
    save_enabled = (save_option or "enable").lower() != "disable"
    if save_enabled and not get_session(request.cookies.get("session_id")):
        raise HTTPException(status_code=403, detail="login required to save")
    if not ots_enabled and not tsa_enabled:
        raise HTTPException(status_code=400, detail="at least one option required")
    name_base = os.path.basename(source_name) if source_name else hash_value
    settings = load_settings()
    result = evidence_service.process_submission(
        db,
        settings.files_dir,
        settings.tsa_url,
        hash_value,
        ots_enabled,
        tsa_enabled,
        save_record=save_enabled,
        download_name_base=name_base,
    )
    response = {
        "hash": result.hash_value,
        "ots_status": result.ots_status,
        "tsa_status": result.tsa_status,
        "ots_error": result.ots_error,
        "tsa_error": result.tsa_error,
        "tsa_info": result.tsa_info,
        "record": result.record,
        "saved": result.saved,
        "download_name_base": result.download_name_base,
    }
    if result.saved:
        response["download"] = {
            "ots": f"/api/files/{result.hash_value}/ots",
            "tsa": f"/api/files/{result.hash_value}/tsa",
        }
    else:
        response["download_inline"] = {
            "ots": {
                "filename": f"{name_base}.ots",
                "content_base64": base64.b64encode(result.ots_bytes).decode("ascii"),
            }
            if result.ots_bytes
            else None,
            "tsa": {
                "filename": f"{name_base}.tsr",
                "content_base64": base64.b64encode(result.tsa_bytes).decode("ascii"),
            }
            if result.tsa_bytes
            else None,
        }
    return response


@router.post("/api/evidence/verify")
async def verify_evidence(
    hash_value: Optional[str] = Form(None),
    ots_file: Optional[UploadFile] = File(None),
    tsa_file: Optional[UploadFile] = File(None),
    ots_option: Optional[str] = Form(None),
    tsa_option: Optional[str] = Form(None),
    db=Depends(get_db),
):
    if not hash_value:
        raise HTTPException(status_code=400, detail="hash is required")
    ots_enabled = (ots_option or "enable").lower() != "disable"
    tsa_enabled = (tsa_option or "enable").lower() != "disable"
    if not ots_enabled and not tsa_enabled:
        raise HTTPException(status_code=400, detail="at least one option required")
    settings = load_settings()
    ots_bytes = await ots_file.read() if ots_file else None
    tsr_bytes = await tsa_file.read() if tsa_file else None
    result = evidence_service.verify_submission(
        db,
        settings.files_dir,
        hash_value,
        ots_enabled,
        tsa_enabled,
        ots_bytes_override=ots_bytes,
        tsr_bytes_override=tsr_bytes,
    )
    if not result.get("exists"):
        if ots_enabled and not ots_bytes:
            raise HTTPException(status_code=400, detail="ots file required when record missing")
        if tsa_enabled and not tsr_bytes:
            raise HTTPException(status_code=400, detail="tsa file required when record missing")
    return result


@router.get("/api/evidence/list", dependencies=[Depends(require_login)])
def list_evidence(db=Depends(get_db)):
    items = evidence_repo.list_all(db)
    return {"items": items}


@router.get("/api/evidence/{hash_value}", dependencies=[Depends(require_login)])
def get_evidence(hash_value: str, db=Depends(get_db)):
    record = evidence_repo.fetch_by_hash(db, hash_value)
    if not record:
        raise HTTPException(status_code=404, detail="record not found")
    return {"record": record}


@router.delete("/api/evidence/{hash_value}", dependencies=[Depends(require_login)])
def delete_evidence(hash_value: str, keep_files: bool = False, db=Depends(get_db)):
    settings = load_settings()
    ok = evidence_service.delete_evidence(db, settings.files_dir, hash_value, keep_files)
    if not ok:
        raise HTTPException(status_code=404, detail="record not found")
    return {"deleted": True, "hash": hash_value, "keep_files": keep_files}


def _file_response(path: Optional[str], filename: str):
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path, filename=filename)


@router.get("/api/files/{hash_value}/ots")
def download_ots(hash_value: str, db=Depends(get_db)):
    record = evidence_repo.fetch_by_hash(db, hash_value)
    if not record:
        raise HTTPException(status_code=404, detail="record not found")
    if record.get("ots_status") != "success":
        raise HTTPException(status_code=403, detail="ots file not available")
    return _file_response(record.get("ots_path"), f"{hash_value}.ots")


@router.get("/api/files/{hash_value}/tsa")
def download_tsa(hash_value: str, db=Depends(get_db)):
    record = evidence_repo.fetch_by_hash(db, hash_value)
    if not record:
        raise HTTPException(status_code=404, detail="record not found")
    if record.get("tsa_status") != "success":
        raise HTTPException(status_code=403, detail="tsa file not available")
    return _file_response(record.get("tsa_path"), f"{hash_value}.tsr")


@router.get("/api/logs", dependencies=[Depends(require_login)])
def list_logs():
    settings = load_settings()
    if not os.path.isdir(settings.logs_dir):
        return {"items": []}
    items = []
    for name in sorted(os.listdir(settings.logs_dir)):
        if not name.endswith(".log"):
            continue
        path = os.path.join(settings.logs_dir, name)
        items.append({"name": name, "size": os.path.getsize(path)})
    return {"items": items}


@router.get("/api/logs/{name}", dependencies=[Depends(require_login)])
def download_log(name: str):
    settings = load_settings()
    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="invalid log name")
    path = os.path.join(settings.logs_dir, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="log not found")
    return FileResponse(path, filename=name)


@router.get("/api/logs/{name}/view", dependencies=[Depends(require_login)])
def view_log(name: str, limit: int = 200):
    settings = load_settings()
    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="invalid log name")
    path = os.path.join(settings.logs_dir, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="log not found")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError:
        raise HTTPException(status_code=500, detail="read log failed")
    if limit > 0:
        lines = lines[-limit:]
    content = "".join(lines)
    return PlainTextResponse(content)


@router.delete("/api/logs/{name}", dependencies=[Depends(require_login)])
def delete_log(name: str):
    settings = load_settings()
    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="invalid log name")
    path = os.path.join(settings.logs_dir, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="log not found")
    try:
        close_log_handlers(path)
        os.remove(path)
        configure_logging(settings.logs_dir)
        return JSONResponse({"deleted": True, "name": name})
    except PermissionError:
        with open(path, "w", encoding="utf-8"):
            pass
        return JSONResponse({"deleted": False, "cleared": True, "name": name})
