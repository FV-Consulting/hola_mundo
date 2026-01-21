import os
import re
import time
import json
import tempfile
from io import BytesIO
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

DATA_DIR = "archivos_subidos/datos"
os.makedirs(DATA_DIR, exist_ok=True)

ACTIVE_POINTER = os.path.join(DATA_DIR, "dataset_activo.json")

SUPPORTED_TYPES = [
    "csv", "tsv", "txt", "json",
    "parquet", "feather",
    "dta",
    "sav", "sas7bdat",
    "rds", "rda", "rdata", "RData"
]

# -----------------------------
# Sidebar control (sb=1/0)
# -----------------------------
def sb_is_open() -> bool:
    qp = st.query_params
    return str(qp.get("sb", "1")) != "0"

# -----------------------------
# Helpers
# -----------------------------
def ext_from_name(name: str) -> str:
    return os.path.splitext(name)[1].lower()

def make_unique_columns(cols):
    seen = {}
    out = []
    for i, c in enumerate(cols, start=1):
        name = "" if c is None else str(c).strip()
        if name == "" or name.lower() in ["nan", "none"]:
            name = f"col_{i}"
        if name not in seen:
            seen[name] = 1
            out.append(name)
        else:
            seen[name] += 1
            out.append(f"{name}_{seen[name]}")
    return out

def limpiar_df(df: pd.DataFrame, drop_blank=True) -> pd.DataFrame:
    df2 = df.copy()
    if drop_blank:
        df2 = df2.dropna(axis=0, how="all")
        df2 = df2.dropna(axis=1, how="all")
    df2.columns = make_unique_columns(df2.columns)
    return df2.reset_index(drop=True)

def intentar_convertir_numericos_neutral(df: pd.DataFrame, umbral=0.70) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if out[c].dtype == "object":
            conv = pd.to_numeric(out[c], errors="coerce")
            if float(conv.notna().mean()) >= umbral:
                out[c] = conv
    return out

def safe_slug(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-zA-Z0-9_\-]+", "", s)
    return s or "archivo"

def build_timestamp_name_from_original(original_name: str) -> str:
    base = safe_slug(os.path.splitext(original_name)[0])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"dataset_{base}_{ts}.parquet"

def _cleanup_prev_temp():
    prev = st.session_state.get("_tmp_path")
    if prev and os.path.exists(prev):
        try:
            os.remove(prev)
        except Exception:
            pass
    st.session_state["_tmp_path"] = None

def ensure_temp_file(uploaded_file) -> str:
    sig = f"{uploaded_file.name}:{uploaded_file.size}"
    if (
        st.session_state.get("_tmp_sig") == sig
        and st.session_state.get("_tmp_path")
        and os.path.exists(st.session_state["_tmp_path"])
    ):
        return st.session_state["_tmp_path"]

    _cleanup_prev_temp()

    ext = ext_from_name(uploaded_file.name)
    fd, path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.session_state["_tmp_sig"] = sig
    st.session_state["_tmp_path"] = path
    return path

def persist_tabulado_parquet(df: pd.DataFrame, original_name: str, meta: dict | None = None) -> dict:
    os.makedirs(DATA_DIR, exist_ok=True)

    filename = build_timestamp_name_from_original(original_name)
    save_path = os.path.join(DATA_DIR, filename)

    df.to_parquet(save_path, index=False)

    pointer = {
        "last_file": filename,
        "last_path": save_path,
        "original_name": original_name,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "format": "parquet",
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "meta": meta or {}
    }
    with open(ACTIVE_POINTER, "w", encoding="utf-8") as fp:
        json.dump(pointer, fp, ensure_ascii=False, indent=2)

    return {"saved_path": save_path, "filename": filename, "pointer_path": ACTIVE_POINTER}

def load_last_uploaded_dataset():
    if not os.path.exists(ACTIVE_POINTER):
        return None
    try:
        with open(ACTIVE_POINTER, "r", encoding="utf-8") as fp:
            meta = json.load(fp)
        path = meta.get("last_path")
        if not path or not os.path.exists(path):
            return None
    except Exception:
        return None

    try:
        return pd.read_parquet(path)
    except Exception:
        return None

def read_json_to_df(uploaded_file):
    raw = uploaded_file.getbuffer().tobytes()
    txt = raw.decode("utf-8", errors="replace").strip()
    try:
        return pd.read_json(BytesIO(raw), lines=True)
    except Exception:
        pass
    try:
        return pd.read_json(BytesIO(raw))
    except Exception:
        pass

    obj = json.loads(txt)
    if isinstance(obj, list):
        if len(obj) == 0:
            return pd.DataFrame()
        if all(isinstance(x, dict) for x in obj):
            return pd.json_normalize(obj)
        return pd.DataFrame({"value": obj})
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, list) and len(v) > 0 and all(isinstance(x, dict) for x in v):
                df = pd.json_normalize(v)
                df.insert(0, "_source_key", k)
                return df
        return pd.json_normalize(obj)
    return pd.DataFrame({"value": [obj]})

def read_r_any(temp_path: str):
    try:
        import pyreadr
    except Exception as e:
        raise RuntimeError("Para leer .rds/.rda/.RData instala: pip install pyreadr") from e

    res = pyreadr.read_r(temp_path)
    if not res:
        return None, []
    keys = list(res.keys())
    return res, keys

def _decode_bytes(raw: bytes) -> str:
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")

def _sniff_sep(sample_text: str):
    candidates = [";", ",", "\t", "|"]
    lines = [l for l in sample_text.splitlines() if l.strip()][:30]
    if not lines:
        return None

    scores = {}
    for sep in candidates:
        counts = [l.count(sep) for l in lines]
        if max(counts) == 0:
            scores[sep] = -1
            continue
        scores[sep] = float(np.mean(counts)) - float(np.std(counts))

    best = max(scores, key=scores.get)
    return best if scores.get(best, -1) > 0 else None

def _parse_text_table(raw_bytes: bytes, default_sep=None) -> pd.DataFrame:
    text = _decode_bytes(raw_bytes)
    sample = "\n".join(text.splitlines()[:80])
    sep = default_sep or _sniff_sep(sample)

    try:
        if sep is None:
            df = pd.read_csv(BytesIO(raw_bytes), sep=None, engine="python")
        else:
            df = pd.read_csv(BytesIO(raw_bytes), sep=sep, engine="python")
    except Exception:
        df = pd.read_csv(BytesIO(raw_bytes), sep=None, engine="python")

    if df.shape[1] == 1:
        probe = ""
        try:
            probe = str(df.iloc[0, 0])
        except Exception:
            probe = ""

        alt_seps = [";", ",", "\t", "|"]
        alt_seps = sorted(alt_seps, key=lambda s: probe.count(s), reverse=True)

        for s in alt_seps:
            if s and (probe.count(s) >= 1 or (sep is None and sample.count(s) > 0)):
                try:
                    df2 = pd.read_csv(BytesIO(raw_bytes), sep=s, engine="python")
                    if df2.shape[1] > 1:
                        df = df2
                        break
                except Exception:
                    continue

    return df

def read_dataset(uploaded_file):
    ext = ext_from_name(uploaded_file.name)
    temp_path = ensure_temp_file(uploaded_file)
    raw_bytes = uploaded_file.getbuffer().tobytes()

    if ext == ".csv":
        df = _parse_text_table(raw_bytes, default_sep=None)
        return df, {"ext": ext}

    if ext == ".tsv":
        df = _parse_text_table(raw_bytes, default_sep="\t")
        return df, {"ext": ext}

    if ext == ".txt":
        df = _parse_text_table(raw_bytes, default_sep=None)
        return df, {"ext": ext}

    if ext == ".json":
        df = read_json_to_df(uploaded_file)
        return df, {"ext": ext}

    if ext == ".parquet":
        df = pd.read_parquet(BytesIO(raw_bytes))
        return df, {"ext": ext}

    if ext == ".feather":
        df = pd.read_feather(BytesIO(raw_bytes))
        return df, {"ext": ext}

    if ext == ".dta":
        df = pd.read_stata(BytesIO(raw_bytes))
        return df, {"ext": ext}

    if ext == ".sav":
        df = pd.read_spss(temp_path)
        return df, {"ext": ext}

    if ext == ".sas7bdat":
        df = pd.read_sas(temp_path)
        return df, {"ext": ext}

    if ext in [".rds", ".rda", ".rdata", ".rdata".lower()]:
        r_res, keys = read_r_any(temp_path)
        if r_res is None or not keys:
            return pd.DataFrame(), {"ext": ext, "r_objects": []}
        return r_res[keys[0]], {"ext": ext, "r_objects": keys, "r_selected": keys[0]}

    raise RuntimeError(f"Formato no soportado: {ext}")

def mostrar_info_dataset(df: pd.DataFrame):
    st.markdown("### Información del dataset")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Filas", f"{df.shape[0]:,}")
    with col2:
        st.metric("Columnas", f"{df.shape[1]:,}")
    with col3:
        st.metric("Memoria (MB)", f"{df.memory_usage(deep=True).sum() / 1024**2:.2f}")
    with col4:
        st.metric("Nulos", f"{int(df.isna().sum().sum()):,}")

    with st.expander("Tipos de datos por columna", expanded=False):
        tipos_df = pd.DataFrame({
            "Columna": df.columns,
            "Tipo": [str(dtype) for dtype in df.dtypes],
            "No nulos": [int(df[col].notna().sum()) for col in df.columns],
            "Nulos": [int(df[col].isna().sum()) for col in df.columns],
            "% nulos": [f"{(df[col].isna().sum() / len(df) * 100):.1f}%" if len(df) else "0.0%" for col in df.columns]
        })
        st.dataframe(tipos_df, use_container_width=True, height=320)

    with st.expander("Estadísticas descriptivas", expanded=False):
        try:
            st.dataframe(df.describe(include="all").T, use_container_width=True)
        except Exception:
            st.write("No fue posible calcular describe() para este dataset.")

    st.markdown("### Vista previa")
    n_max = min(500, len(df)) if len(df) else 20
    n_filas = st.slider("Filas a mostrar", 5, max(5, n_max), min(20, max(5, n_max)))
    st.dataframe(df.head(n_filas), use_container_width=True, height=420)

# ============================================================
# APP
# ============================================================
def cargar_documentos():
    st.title("Cargar y visualizar datos")
    st.caption("Guarda el dataset TABULADO (procesado) como Parquet en archivos_subidos/datos/ para usarlo en otras apps.")

    st.session_state.setdefault("dataset_cargado", None)
    st.session_state.setdefault("dataset_activo", None)

    if st.session_state["dataset_activo"] is None:
        persisted = load_last_uploaded_dataset()
        if persisted is not None:
            st.session_state["dataset_activo"] = persisted

    # Sidebar solo si sb=1
    if sb_is_open():
        with st.sidebar:
            st.markdown("## Guía rápida")
            st.markdown("---")
            st.markdown(
                f"""
                - Sube un archivo (CSV/JSON/Stata/SPSS/SAS/R).
                - Se tabula y procesa.
                - Se guarda **como Parquet** en `{DATA_DIR}` con fecha/hora.
                - Se actualiza `{ACTIVE_POINTER}` para que otras apps carguen el último.
                """
            )

            if os.path.exists(ACTIVE_POINTER):
                with st.expander("Último dataset guardado (puntero)", expanded=False):
                    try:
                        with open(ACTIVE_POINTER, "r", encoding="utf-8") as fp:
                            st.json(json.load(fp))
                    except Exception:
                        st.write("No se pudo leer el puntero.")
    else:
        st.info("☰ **Filtros ocultos**. Usa el botón '☰ Mostrar filtros' bajo el navbar para ver el sidebar.")

    st.markdown("## Cargar archivo")
    uploaded = st.file_uploader(
        "Selecciona un archivo",
        type=SUPPORTED_TYPES,
        help="CSV, JSON, RDS, DTA, SAV..."
    )

    if uploaded is None:
        if st.session_state["dataset_activo"] is not None:
            st.markdown("---")
            st.markdown("## Último dataset tabulado (desde disco)")
            mostrar_info_dataset(st.session_state["dataset_activo"])
        else:
            st.info("Sube un archivo para comenzar.")
        st.stop()

    with st.expander("Opciones de procesamiento", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            drop_blank = st.checkbox("Eliminar filas y columnas vacías", value=True)
            auto_numeric = st.checkbox("Convertir numéricos automáticamente (neutral)", value=True)
        with col2:
            usar_header = st.checkbox("Usar primera fila como nombres de columnas", value=False)
            umbral_numeric = st.slider("Umbral de conversión numérica", 0.50, 0.95, 0.70, 0.05)

    try:
        with st.spinner("Leyendo y tabulando..."):
            df_raw, meta = read_dataset(uploaded)

        if "r_objects" in meta and len(meta["r_objects"]) > 1:
            st.info(f"El archivo contiene {len(meta['r_objects'])} objeto(s).")
            chosen = st.selectbox("Selecciona objeto", meta["r_objects"], index=0)
            temp_path = ensure_temp_file(uploaded)
            r_res, _ = read_r_any(temp_path)
            df_raw = r_res[chosen]
            meta["r_selected"] = chosen

        df = limpiar_df(df_raw, drop_blank=drop_blank)

        if usar_header and len(df) >= 2:
            df.columns = make_unique_columns(df.iloc[0].tolist())
            df = df.iloc[1:].reset_index(drop=True)

        if auto_numeric:
            df = intentar_convertir_numericos_neutral(df, umbral=float(umbral_numeric))

        st.session_state["dataset_cargado"] = df.copy()
        st.success(f"Archivo cargado: {uploaded.name}")

        if df.shape[1] == 1 and ext_from_name(uploaded.name) in [".csv", ".tsv", ".txt"]:
            st.warning(
                "El archivo se cargó con una sola columna. "
                "Probablemente el separador no se detectó bien (por ejemplo, ';')."
            )

    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        st.stop()

    st.markdown("---")
    mostrar_info_dataset(df)

    st.markdown("---")
    st.markdown("## Acciones")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Guardar TABULADO (Parquet) para otras apps", use_container_width=True, type="primary"):
            info = persist_tabulado_parquet(df, original_name=uploaded.name, meta={"read_meta": meta})
            st.session_state["dataset_activo"] = df.copy()

            st.success("Dataset tabulado guardado como Parquet (y puntero actualizado).")
            with st.expander("Detalles de guardado", expanded=True):
                st.write("Archivo:", info["filename"])
                st.write("Ruta:", info["saved_path"])
                st.write("Puntero:", info["pointer_path"])

    with col2:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Descargar CSV (procesado)",
            data=csv_bytes,
            file_name=f"datos_procesados_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col3:
        try:
            bio = BytesIO()
            with pd.ExcelWriter(bio, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="data")
            xlsx_bytes = bio.getvalue()

            st.download_button(
                label="Descargar Excel (procesado)",
                data=xlsx_bytes,
                file_name=f"datos_procesados_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"No fue posible generar Excel: {e}")

    if st.session_state.get("dataset_activo") is not None:
        st.markdown("---")
        st.markdown("## Dataset activo (en memoria)")

        df_activo = st.session_state["dataset_activo"]
        st.write(f"Filas: {df_activo.shape[0]:,} | Columnas: {df_activo.shape[1]:,}")
        st.dataframe(df_activo.head(20), use_container_width=True, height=350)


if __name__ == "__main__":
    cargar_documentos()
