# dropbox_io.py
import os
import json
import time
from dataclasses import dataclass
from typing import List, Optional

import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError

ACTIVE_POINTER_NAME = "active_dataset.json"


def _get_secret(key: str, default: str = "") -> str:
    # 1) env var
    v = os.getenv(key, "")
    if v:
        return v.strip()
    # 2) st.secrets
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return default


DROPBOX_ACCESS_TOKEN = _get_secret("DROPBOX_ACCESS_TOKEN")
DROPBOX_BASE_PATH = _get_secret("DROPBOX_BASE_PATH")


@dataclass
class DbxFile:
    name: str
    path_lower: str
    size: Optional[int] = None
    client_modified: Optional[str] = None


def get_dbx() -> dropbox.Dropbox:
    if not DROPBOX_ACCESS_TOKEN:
        raise RuntimeError("Falta DROPBOX_ACCESS_TOKEN (env var o st.secrets).")
    return dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)


def normalize_path(p: str) -> str:
    p = (p or "").strip()
    if not p:
        return ""
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/")


def resolve_base_path() -> str:
    base = normalize_path(DROPBOX_BASE_PATH)
    if not base:
        raise RuntimeError("Falta DROPBOX_BASE_PATH (env var o st.secrets).")
    return base


def ensure_folder(dbx: dropbox.Dropbox, folder_path: str) -> None:
    folder_path = normalize_path(folder_path)
    try:
        dbx.files_get_metadata(folder_path)
    except ApiError:
        dbx.files_create_folder_v2(folder_path)


def list_folder_files(
    dbx: dropbox.Dropbox,
    folder_path: str,
    exts_allowed: Optional[List[str]] = None
) -> List[DbxFile]:
    folder_path = normalize_path(folder_path)
    res = dbx.files_list_folder(folder_path)

    out: List[DbxFile] = []
    while True:
        for e in res.entries:
            if isinstance(e, dropbox.files.FileMetadata):
                ext = os.path.splitext(e.name)[1].lower()
                if exts_allowed is None or ext in exts_allowed:
                    out.append(
                        DbxFile(
                            name=e.name,
                            path_lower=e.path_lower,
                            size=int(getattr(e, "size", 0)),
                            client_modified=str(getattr(e, "client_modified", "")) or None,
                        )
                    )
        if not res.has_more:
            break
        res = dbx.files_list_folder_continue(res.cursor)

    out.sort(key=lambda x: x.name.lower())
    return out


def download_bytes(dbx: dropbox.Dropbox, path_lower: str) -> bytes:
    _md, resp = dbx.files_download(path_lower)
    return resp.content


def upload_bytes(dbx: dropbox.Dropbox, dest_path: str, content: bytes, overwrite: bool = True) -> str:
    dest_path = normalize_path(dest_path)
    mode = WriteMode.overwrite if overwrite else WriteMode.add
    md = dbx.files_upload(content, dest_path, mode=mode, mute=True)
    return md.path_lower


def put_json(dbx: dropbox.Dropbox, dest_path: str, obj: dict) -> str:
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    return upload_bytes(dbx, dest_path, data, overwrite=True)


def get_json(dbx: dropbox.Dropbox, path_lower: str) -> Optional[dict]:
    try:
        raw = download_bytes(dbx, path_lower)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def active_pointer_path(base_path: str) -> str:
    base_path = normalize_path(base_path)
    return f"{base_path}/{ACTIVE_POINTER_NAME}"


def write_active_pointer(dbx: dropbox.Dropbox, base_path: str, dataset_path_lower: str, original_name: str) -> str:
    ptr = {
        "dataset_path_lower": dataset_path_lower,
        "original_name": original_name,
        "updated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return put_json(dbx, active_pointer_path(base_path), ptr)


def read_active_pointer(dbx: dropbox.Dropbox, base_path: str) -> Optional[dict]:
    return get_json(dbx, active_pointer_path(base_path))