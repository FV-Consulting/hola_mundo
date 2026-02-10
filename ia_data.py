# 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
# setx GROQ_API_KEY "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"
import os
import re
import json
import difflib
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from scipy import stats

from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# =========================
# STREAMLIT CONFIG
# =========================
st.set_page_config(page_title="FV Data Analyst (Groq)", page_icon="📊", layout="wide")

DATA_DIR = Path("archivos_subidos/datos")
OUT_DIR = Path("archivos_subidos/salidas")
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTS = {".csv", ".xlsx", ".xls", ".parquet", ".json", ".feather"}

MODEL = os.getenv("OPENAI_MODEL", "lopenai/gpt-oss-120b")  # ✅ Modelo válido de Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")

# =========================
# JSON SAFE (fix Timestamp)
# =========================
def json_safe(obj: Any) -> Any:
    if obj is None:
        return None

    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()

    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()

    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]

    if isinstance(obj, (str, int, float, bool)):
        return obj

    return str(obj)

# =========================
# CLIENT (cache)
# =========================
@st.cache_resource(show_spinner=False)
def get_client() -> OpenAI:
    if not GROQ_API_KEY:
        raise RuntimeError('Falta GROQ_API_KEY. En PowerShell: setx GROQ_API_KEY "gsk_..." y reinicia VS Code/terminal.')
    return OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

try:
    client = get_client()
except Exception as e:
    st.error(str(e))
    st.stop()

# =========================
# FORMATO LATAM
# =========================
LATAM_DECIMAL = ","
LATAM_THOUSANDS = "."

def parse_latam_number(x: Any) -> Any:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    if isinstance(x, (int, float, np.number)):
        return float(x)

    s = str(x).strip()
    if s == "":
        return np.nan

    s = s.replace(" ", "")
    s = re.sub(r"[$€£%]", "", s)

    if LATAM_THOUSANDS in s and LATAM_DECIMAL in s:
        s2 = s.replace(LATAM_THOUSANDS, "").replace(LATAM_DECIMAL, ".")
        try:
            return float(s2)
        except:
            return x

    if LATAM_DECIMAL in s and LATAM_THOUSANDS not in s:
        s2 = s.replace(LATAM_DECIMAL, ".")
        try:
            return float(s2)
        except:
            return x

    try:
        return float(s)
    except:
        return x

def to_numeric_latam(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)
    s = series.map(parse_latam_number)
    return pd.to_numeric(s, errors="coerce")

def set_plotly_latam(fig: go.Figure) -> go.Figure:
    # separators: decimal, miles -> ",."
    fig.update_layout(separators=",.")
    return fig

# =========================
# UNIDADES / ESCALADO
# =========================
UNIT_PRESETS = {
    "unidades": (1.0, "unidades"),
    "miles": (1e-3, "miles"),
    "millones": (1e-6, "millones"),
    "miles de millones": (1e-9, "miles de millones"),
}

def choose_auto_scale(max_abs: float) -> Tuple[float, str]:
    if max_abs <= 0 or np.isnan(max_abs):
        return 1.0, "unidades"
    if max_abs >= 1e9:
        return 1e-9, "miles de millones"
    if max_abs >= 1e6:
        return 1e-6, "millones"
    if max_abs >= 1e3:
        return 1e-3, "miles"
    return 1.0, "unidades"

def apply_axis_units(df: pd.DataFrame, col: str, unit_mode: str, custom_unit_label: Optional[str] = None) -> Tuple[pd.Series, str]:
    s = to_numeric_latam(df[col])
    try:
        max_abs = float(np.nanmax(np.abs(s.values)))
        if not np.isfinite(max_abs):
            max_abs = 0.0
    except Exception:
        max_abs = 0.0

    if unit_mode == "auto":
        factor, unit_lbl = choose_auto_scale(max_abs)
    else:
        factor, unit_lbl = UNIT_PRESETS.get(unit_mode, (1.0, "unidades"))

    scaled = s * factor
    final_unit = custom_unit_label.strip() if (custom_unit_label and custom_unit_label.strip()) else unit_lbl
    return scaled, final_unit

# =========================
# FILES + DATA (cache)
# =========================
@st.cache_data(show_spinner=False)
def list_data_files() -> List[Dict[str, Any]]:
    out = []
    for p in sorted(DATA_DIR.glob("*")):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            out.append({
                "name": p.name,
                "ext": p.suffix.lower(),
                "size_kb": round(p.stat().st_size / 1024, 1),
                "mtime": p.stat().st_mtime,
            })
    return out

@st.cache_data(show_spinner=False)
def load_df_cached(file_name: str, sheet_name: Optional[str]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    p = DATA_DIR / file_name
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo: {p}")

    ext = p.suffix.lower()
    meta: Dict[str, Any] = {"file": file_name, "ext": ext}

    if ext == ".csv":
        df = pd.read_csv(p, sep=None, engine="python")
    elif ext in (".xlsx", ".xls"):
        xl = pd.ExcelFile(p)
        meta["sheets"] = xl.sheet_names
        use_sheet = sheet_name or (xl.sheet_names[0] if xl.sheet_names else None)
        if not use_sheet:
            raise ValueError("El Excel no tiene hojas legibles.")
        meta["sheet_used"] = use_sheet
        df = pd.read_excel(p, sheet_name=use_sheet)
    elif ext == ".parquet":
        df = pd.read_parquet(p)
    elif ext == ".feather":
        df = pd.read_feather(p)
    elif ext == ".json":
        df = pd.read_json(p)
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)
    else:
        raise ValueError(f"Extensión no soportada: {ext}")

    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~pd.Index(df.columns).duplicated()]
    meta["rows"] = int(df.shape[0])
    meta["cols"] = int(df.shape[1])
    return df, meta

@st.cache_data(show_spinner=False)
def df_profile_cached(file_name: str, sheet_name: Optional[str]) -> Dict[str, Any]:
    df, meta = load_df_cached(file_name, sheet_name)
    out: Dict[str, Any] = {"meta": meta, "shape": [int(df.shape[0]), int(df.shape[1])], "columns": []}
    max_levels = 10

    for c in df.columns:
        s = df[c]
        col = {"name": str(c), "dtype": str(s.dtype), "missing": int(s.isna().sum())}
        if pd.api.types.is_numeric_dtype(s):
            sd = s.dropna()
            col.update({
                "min": None if sd.empty else float(sd.min()),
                "max": None if sd.empty else float(sd.max()),
                "mean": None if sd.empty else float(sd.mean()),
                "std": None if sd.empty else (float(sd.std(ddof=1)) if sd.size > 1 else None),
            })
        else:
            vc = s.astype(str).value_counts(dropna=True).head(max_levels)
            col["top_values"] = [{"value": k, "count": int(v)} for k, v in vc.items()]
        out["columns"].append(col)

    return out

def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def save_text(name: str, text: str) -> str:
    p = OUT_DIR / f"{name}_{stamp()}.txt"
    p.write_text(text, encoding="utf-8")
    return str(p)

def save_df(name: str, df: pd.DataFrame) -> str:
    p = OUT_DIR / f"{name}_{stamp()}.csv"
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return str(p)

def get_key(file_name: str, sheet_name: Optional[str]) -> str:
    return f"{file_name}||{sheet_name or ''}"

def get_active_df(file_name: str, sheet_name: Optional[str]) -> Tuple[pd.DataFrame, Dict[str, Any], str]:
    df, meta = load_df_cached(file_name, sheet_name)
    key = get_key(file_name, sheet_name)
    cache = st.session_state.get("cleaned_cache", {})
    if key in cache:
        return cache[key], meta, "cleaned"
    return df, meta, "raw"

# =========================
# SIDEBAR SYNC (FUENTE DE VERDAD)
# =========================
def sync_active_from_sidebar():
    st.session_state.active_file = st.session_state.get("sidebar_file")
    st.session_state.active_sheet = st.session_state.get("sidebar_sheet")

# =========================
# TOOLS
# =========================
def _ok(**kwargs): return {"ok": True, **kwargs}
def _err(msg: str): return {"ok": False, "error": msg}

def tool_list_files(_: Dict[str, Any]) -> Dict[str, Any]:
    return _ok(files=list_data_files())

def tool_set_active_dataset(_: Dict[str, Any]) -> Dict[str, Any]:
    # 🔒 Bloqueado: solo sidebar define dataset
    return _err("Dataset bloqueado: selección solo desde el Sidebar.")

def tool_preview(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        fn = args.get("file_name") or st.session_state.get("active_file")
        sh = args.get("sheet_name") or st.session_state.get("active_sheet")
        n = int(args.get("n", 20))
        if not fn:
            return _err("No hay dataset activo.")
        df, meta, used = get_active_df(fn, sh)
        return _ok(meta=meta, data_used=used, columns=list(df.columns), preview=df.head(n).to_dict("records"))
    except Exception as e:
        return _err(str(e))

def tool_describe_data(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        fn = args.get("file_name") or st.session_state.get("active_file")
        sh = args.get("sheet_name") or st.session_state.get("active_sheet")
        if not fn:
            return _err("No hay dataset activo.")
        prof = df_profile_cached(fn, sh)
        return _ok(profile=prof)
    except Exception as e:
        return _err(str(e))

def tool_clean_latam(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        fn = args.get("file_name") or st.session_state.get("active_file")
        sh = args.get("sheet_name") or st.session_state.get("active_sheet")
        cols = args.get("cols")
        if not fn:
            return _err("No hay dataset activo.")
        df, meta = load_df_cached(fn, sh)

        if not cols:
            cols = []
            for c in df.columns:
                if df[c].dtype == "object":
                    sample = df[c].dropna().astype(str).head(50)
                    if any(re.search(r"\d", x) for x in sample):
                        cols.append(c)

        df2 = df.copy()
        for c in cols:
            if c in df2.columns:
                df2[c] = to_numeric_latam(df2[c])

        st.session_state.cleaned_cache = st.session_state.get("cleaned_cache", {})
        st.session_state.cleaned_cache[get_key(fn, sh)] = df2
        return _ok(meta=meta, cleaned_columns=cols, note="Limpieza aplicada y guardada en sesión.")
    except Exception as e:
        return _err(str(e))

def tool_plot(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        fn = args.get("file_name") or st.session_state.get("active_file")
        sh = args.get("sheet_name") or st.session_state.get("active_sheet")

        kind = (args.get("kind") or "").lower()
        x = args.get("x")
        y = args.get("y")
        color = args.get("color")
        title = args.get("title") or "Gráfico"
        save = bool(args.get("save", False))

        x_label = args.get("x_label")
        y_label = args.get("y_label")
        colors = args.get("color_discrete_sequence")
        template = args.get("template") or "plotly_white"

        x_unit_mode = args.get("x_unit_mode") or "auto"
        y_unit_mode = args.get("y_unit_mode") or "auto"
        x_unit_label = args.get("x_unit_label")
        y_unit_label = args.get("y_unit_label")

        if not fn:
            return _err("No hay dataset activo.")
        if kind not in {"scatter", "line", "hist", "box", "bar"}:
            return _err("kind debe ser: scatter, line, hist, box, bar.")

        df, meta, used = get_active_df(fn, sh)
        plot_df = df.copy()

        if kind in {"scatter", "line", "box", "bar"} and (x is None or y is None):
            return _err("Para scatter/line/box/bar debes indicar x e y.")
        if kind == "hist" and x is None:
            return _err("Para hist debes indicar x.")

        x_plot = x
        y_plot = y
        labels = {}

        # X escalado
        if x and x in plot_df.columns:
            try:
                xs, x_unit_final = apply_axis_units(plot_df, x, x_unit_mode, x_unit_label)
                plot_df["__x_scaled__"] = xs
                x_plot = "__x_scaled__"
                labels[x_plot] = f"{(x_label or x)} (en {x_unit_final})"
            except Exception:
                labels[x_plot] = (x_label or x)

        # Y escalado
        if y and y in plot_df.columns and kind in {"scatter", "line", "box", "bar"}:
            try:
                ys, y_unit_final = apply_axis_units(plot_df, y, y_unit_mode, y_unit_label)
                plot_df["__y_scaled__"] = ys
                y_plot = "__y_scaled__"
                labels[y_plot] = f"{(y_label or y)} (en {y_unit_final})"
            except Exception:
                labels[y_plot] = (y_label or y)

        if kind == "scatter":
            fig = px.scatter(plot_df, x=x_plot, y=y_plot, color=color, title=title,
                             color_discrete_sequence=colors, labels=labels)
        elif kind == "line":
            fig = px.line(plot_df, x=x_plot, y=y_plot, color=color, title=title,
                          color_discrete_sequence=colors, labels=labels)
        elif kind == "hist":
            fig = px.histogram(plot_df, x=x_plot, color=color, title=title,
                               color_discrete_sequence=colors, labels=labels)
        elif kind == "box":
            fig = px.box(plot_df, x=x_plot, y=y_plot, color=color, title=title,
                         color_discrete_sequence=colors, labels=labels)
        else:
            fig = px.bar(plot_df, x=x_plot, y=y_plot, color=color, title=title,
                         color_discrete_sequence=colors, labels=labels)

        fig.update_layout(template=template, margin=dict(l=20, r=20, t=70, b=25))
        fig = set_plotly_latam(fig)
        st.plotly_chart(fig, use_container_width=True)

        saved_path = None
        if save:
            saved_path = str(OUT_DIR / f"plot_{stamp()}.html")
            fig.write_html(saved_path, include_plotlyjs="cdn")

        st.session_state.last_plot_config = {
            "kind": kind, "x": x, "y": y, "color": color, "title": title,
            "x_label": x_label, "y_label": y_label,
            "colors": colors, "template": template,
            "x_unit_mode": x_unit_mode, "y_unit_mode": y_unit_mode,
            "x_unit_label": x_unit_label, "y_unit_label": y_unit_label,
        }

        return _ok(meta=meta, data_used=used, saved_path=saved_path)
    except Exception as e:
        return _err(str(e))

def tool_ols_pro(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        fn = args.get("file_name") or st.session_state.get("active_file")
        sh = args.get("sheet_name") or st.session_state.get("active_sheet")

        y = args.get("y")
        X = args.get("X")
        robust = (args.get("robust") or "hc1").lower()
        title = args.get("title") or "OLS"
        export = bool(args.get("export", False))

        if not fn:
            return _err("No hay dataset activo.")
        if not y or not X or not isinstance(X, list):
            return _err("Debes entregar 'y' (string) y 'X' (lista de strings).")

        df, meta, used = get_active_df(fn, sh)

        cols = [y] + X
        for c in cols:
            if c not in df.columns:
                return _err(f"Columna no encontrada: {c}")

        d = df[cols].copy().dropna()
        d[y] = to_numeric_latam(d[y])
        for c in X:
            d[c] = to_numeric_latam(d[c])
        d = d.dropna()

        if d.shape[0] < 10:
            return _err("Muy pocas observaciones tras limpiar NA/no-numéricos (mínimo ~10).")

        yv = d[y].astype(float)
        Xv = d[X].astype(float)
        Xv = sm.add_constant(Xv, has_constant="add")

        model = sm.OLS(yv, Xv)
        res = model.fit(cov_type=robust) if robust in {"hc0", "hc1", "hc2", "hc3"} else model.fit()

        idx = np.arange(len(yv))
        fig_fit = go.Figure()
        fig_fit.add_trace(go.Scatter(x=idx, y=yv, mode="lines", name="Observado"))
        fig_fit.add_trace(go.Scatter(x=idx, y=res.fittedvalues, mode="lines", name="Ajustado"))
        fig_fit.update_layout(title=f"{title} — Observado vs Ajustado", template="plotly_white",
                              margin=dict(l=20, r=20, t=70, b=25))
        fig_fit = set_plotly_latam(fig_fit)
        st.plotly_chart(fig_fit, use_container_width=True)

        resid = res.resid
        fig_rvf = px.scatter(x=res.fittedvalues, y=resid, title="Residuos vs Ajustados",
                             labels={"x": "Ajustados", "y": "Residuos"})
        fig_rvf.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=70, b=25))
        fig_rvf = set_plotly_latam(fig_rvf)
        st.plotly_chart(fig_rvf, use_container_width=True)

        qq = sm.ProbPlot(resid, dist=stats.norm)
        fig_qq = px.scatter(x=qq.theoretical_quantiles, y=np.sort(resid),
                            title="QQ Plot (Normalidad de residuos)",
                            labels={"x": "Cuantiles teóricos", "y": "Residuos (ordenados)"})
        fig_qq.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=70, b=25))
        fig_qq = set_plotly_latam(fig_qq)
        st.plotly_chart(fig_qq, use_container_width=True)

        jb = stats.jarque_bera(resid)
        bp = sm.stats.diagnostic.het_breuschpagan(resid, res.model.exog)
        dw = sm.stats.stattools.durbin_watson(resid)

        try:
            reset = sm.stats.diagnostic.linear_reset(res, power=2, use_f=True)
            reset_out = {"stat": float(reset.fvalue), "pvalue": float(reset.pvalue)}
        except Exception:
            reset_out = {"stat": None, "pvalue": None}

        try:
            X_no_const = d[X].astype(float)
            vifs = {col: float(variance_inflation_factor(X_no_const.values, i))
                    for i, col in enumerate(X_no_const.columns)}
        except Exception:
            vifs = {}

        result = {
            "ok": True,
            "meta": meta,
            "data_used": used,
            "n": int(res.nobs),
            "dependent": y,
            "regressors": ["const"] + X,
            "r2": float(res.rsquared),
            "adj_r2": float(res.rsquared_adj),
            "aic": float(res.aic),
            "bic": float(res.bic),
            "params": {k: float(v) for k, v in res.params.items()},
            "pvalues": {k: float(v) for k, v in res.pvalues.items()},
            "stderr": {k: float(v) for k, v in res.bse.items()},
            "tests": {
                "jarque_bera": {"stat": float(jb.statistic), "pvalue": float(jb.pvalue)},
                "breusch_pagan": {"lm": float(bp[0]), "pvalue": float(bp[1]), "f": float(bp[2]), "fpvalue": float(bp[3])},
                "durbin_watson": float(dw),
                "reset": reset_out,
                "vif": vifs,
            },
            "notes": f"Covariance: {res.cov_type}",
        }

        with st.expander("Resumen econométrico (texto)"):
            st.text(res.summary().as_text())

        saved = {}
        if export:
            coef_df = pd.DataFrame({"coef": res.params, "std_err": res.bse, "pvalue": res.pvalues}).reset_index().rename(columns={"index": "term"})
            saved["coef_csv"] = save_df("ols_coef", coef_df)
            saved["summary_txt"] = save_text("ols_summary", res.summary().as_text())
            p_json = OUT_DIR / f"ols_result_{stamp()}.json"
            p_json.write_text(json.dumps(json_safe(result), ensure_ascii=False, indent=2), encoding="utf-8")
            saved["result_json"] = str(p_json)
        result["saved"] = saved

        return result
    except Exception as e:
        return _err(str(e))

TOOLS = {
    "list_files": tool_list_files,
    "set_active_dataset": tool_set_active_dataset,
    "preview": tool_preview,
    "describe_data": tool_describe_data,
    "clean_latam": tool_clean_latam,
    "plot": tool_plot,
    "ols_pro": tool_ols_pro,
}

TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "list_files", "description": "Lista archivos en archivos_subidos/datos.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "set_active_dataset", "description": "Bloqueado: el dataset lo define el Sidebar.",
        "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}, "sheet_name": {"type": ["string","null"]}}, "required": ["file_name"]}}},
    {"type": "function", "function": {"name": "preview", "description": "Muestra vista previa del dataset activo.",
        "parameters": {"type": "object", "properties": {"file_name": {"type": ["string","null"]}, "sheet_name": {"type": ["string","null"]}, "n": {"type": "integer", "default": 20}}, "required": []}}},
    {"type": "function", "function": {"name": "describe_data", "description": "Describe columnas, tipos, missing y stats.",
        "parameters": {"type": "object", "properties": {"file_name": {"type": ["string","null"]}, "sheet_name": {"type": ["string","null"]}}, "required": []}}},
    {"type": "function", "function": {"name": "clean_latam", "description": "Convierte números formato LATAM en columnas detectadas o elegidas.",
        "parameters": {"type": "object", "properties": {"file_name": {"type": ["string","null"]}, "sheet_name": {"type": ["string","null"]},
            "cols": {"type": ["array","null"], "items": {"type": "string"}}}, "required": []}}},
    {"type": "function", "function": {"name": "plot", "description": "Crea gráfico Plotly con unidades, colores y etiquetas.",
        "parameters": {"type": "object", "properties": {
            "file_name": {"type": ["string","null"]},
            "sheet_name": {"type": ["string","null"]},
            "kind": {"type": "string", "enum": ["scatter","line","hist","box","bar"]},
            "x": {"type": ["string","null"]},
            "y": {"type": ["string","null"]},
            "color": {"type": ["string","null"]},
            "title": {"type": ["string","null"]},
            "x_label": {"type": ["string","null"]},
            "y_label": {"type": ["string","null"]},
            "color_discrete_sequence": {"type": ["array","null"], "items": {"type": "string"}},
            "template": {"type": ["string","null"]},
            "x_unit_mode": {"type": ["string","null"], "enum": ["auto","unidades","miles","millones","miles de millones"]},
            "y_unit_mode": {"type": ["string","null"], "enum": ["auto","unidades","miles","millones","miles de millones"]},
            "x_unit_label": {"type": ["string","null"]},
            "y_unit_label": {"type": ["string","null"]},
            "save": {"type": "boolean", "default": False}
        }, "required": ["kind"]}}},
    {"type": "function", "function": {"name": "ols_pro", "description": "OLS pro con diagnósticos + gráficos, export opcional.",
        "parameters": {"type": "object", "properties": {
            "file_name": {"type": ["string","null"]},
            "sheet_name": {"type": ["string","null"]},
            "y": {"type": "string"},
            "X": {"type": "array", "items": {"type": "string"}},
            "robust": {"type": "string", "enum": ["hc0","hc1","hc2","hc3","nonrobust"], "default": "hc1"},
            "title": {"type": ["string","null"]},
            "export": {"type": "boolean", "default": False}
        }, "required": ["y","X"]}}},
]

SYSTEM_PROMPT = f"""
Eres un analista de datos, estadístico y econometrista senior.

Reglas:
- No inventes archivos ni columnas.
- El dataset activo lo define SIEMPRE el Sidebar.
- No intentes cambiar dataset con set_active_dataset.
- Para descriptivo: preview + describe_data; si hay números LATAM, sugiere clean_latam.
- Para gráficos: plot. Ofrece opciones para ajustar colores, títulos, ejes y unidades.
- Para econometría: ols_pro con interpretación clara.

Formato:
- Títulos
- Bullets
- Conclusión

Modelo: {MODEL}
"""

def run_agent(user_text: str, history: List[Dict[str, str]]) -> str:
    # 🔒 Forzar que active_file/active_sheet = sidebar, siempre.
    if st.session_state.get("sidebar_file"):
        st.session_state.active_file = st.session_state.get("sidebar_file")
        st.session_state.active_sheet = st.session_state.get("sidebar_sheet")

    active_file = st.session_state.get("active_file")
    active_sheet = st.session_state.get("active_sheet")

    convo = [{"role": "system", "content": SYSTEM_PROMPT}]
    if active_file:
        convo.append({
            "role": "system",
            "content": f"Dataset activo actual (del Sidebar): file_name='{active_file}', sheet_name='{active_sheet}'. Usa este SIEMPRE."
        })

    convo.extend(history)
    convo.append({"role": "user", "content": user_text})

    for _ in range(12):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=convo,
            tools=TOOL_SCHEMAS,
            tool_choice="auto"
        )

        msg = resp.choices[0].message
        text = msg.content or ""
        tool_calls = getattr(msg, "tool_calls", None) or []

        if tool_calls:
            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}

                # 🔒 Nunca permitir cambio de dataset
                if name == "set_active_dataset":
                    tool_out = {"ok": False, "error": "Dataset bloqueado: selección solo desde el Sidebar."}
                else:
                    # ✅ Inyección automática del dataset activo (SIEMPRE el sidebar)
                    if name in {"preview", "describe_data", "clean_latam", "plot", "ols_pro"}:
                        args = args or {}
                        args["file_name"] = st.session_state.get("active_file")
                        args["sheet_name"] = st.session_state.get("active_sheet")

                    fn = TOOLS.get(name)
                    tool_out = fn(args) if fn else {"ok": False, "error": f"Tool no disponible: {name}"}

                convo.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(json_safe(args), ensure_ascii=False)}
                    }]
                })
                convo.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(json_safe(tool_out), ensure_ascii=False)
                })
            continue

        if text.strip():
            return text.strip()

        return "No pude generar una respuesta útil. Prueba pidiendo 'análisis descriptivo' o un gráfico específico."

    return "No logré completar por límites de pasos. Intenta una solicitud más corta o específica."

# =========================
# UI
# =========================
st.markdown("## 📊 FV Data Analyst — Chat (Groq)")
st.caption("🔒 El dataset SIEMPRE se selecciona en el Sidebar (la IA no puede cambiarlo).")

files_meta = list_data_files()
file_names = [f["name"] for f in files_meta]

# Sidebar (fuente de verdad)
with st.sidebar:
    st.markdown("### Dataset activo")
    if file_names:
        # Archivo
        current_file = st.session_state.get("sidebar_file")
        if current_file not in file_names:
            current_file = file_names[0]
            st.session_state.sidebar_file = current_file

        st.selectbox(
            "Archivo",
            options=file_names,
            index=file_names.index(current_file),
            key="sidebar_file",
            on_change=sync_active_from_sidebar
        )

        # Hoja
        chosen_file = st.session_state.get("sidebar_file")
        chosen_sheet = None

        if Path(chosen_file).suffix.lower() in (".xlsx", ".xls"):
            try:
                _, meta = load_df_cached(chosen_file, None)
                sheets = meta.get("sheets", [])
            except Exception:
                sheets = []

            if sheets:
                current_sheet = st.session_state.get("sidebar_sheet")
                if current_sheet not in sheets:
                    current_sheet = sheets[0]
                    st.session_state.sidebar_sheet = current_sheet

                st.selectbox(
                    "Hoja (Excel)",
                    options=sheets,
                    index=sheets.index(st.session_state.sidebar_sheet),
                    key="sidebar_sheet",
                    on_change=sync_active_from_sidebar
                )
                chosen_sheet = st.session_state.sidebar_sheet
            else:
                st.session_state.sidebar_sheet = None
                chosen_sheet = None
        else:
            st.session_state.sidebar_sheet = None
            chosen_sheet = None

        # Asegura sync en el primer render
        if st.session_state.get("active_file") != st.session_state.get("sidebar_file") or st.session_state.get("active_sheet") != st.session_state.get("sidebar_sheet"):
            sync_active_from_sidebar()

        st.divider()
        st.markdown("### Acciones rápidas")
        c1, c2 = st.columns(2)
        if c1.button("Vista previa"):
            result = tool_preview({"file_name": st.session_state.active_file, "sheet_name": st.session_state.active_sheet, "n": 20})
            if result.get("ok"):
                st.success("Vista previa generada")
        if c2.button("Describir"):
            result = tool_describe_data({"file_name": st.session_state.active_file, "sheet_name": st.session_state.active_sheet})
            if result.get("ok"):
                st.success("Descripción generada")

        if st.button("Limpiar formato LATAM (números)"):
            result = tool_clean_latam({"file_name": st.session_state.active_file, "sheet_name": st.session_state.active_sheet})
            if result.get("ok"):
                st.success(f"Limpieza aplicada: {result.get('cleaned_columns', [])}")

        st.divider()
        st.markdown("### Archivos")
        st.dataframe(pd.DataFrame([{k: f[k] for k in ("name", "ext", "size_kb")} for f in files_meta]), use_container_width=True)
    else:
        st.info("No hay archivos en `archivos_subidos/datos`.")

# Vista previa plegable arriba del chat
if st.session_state.get("active_file"):
    st.caption(f"✅ Dataset activo REAL: {st.session_state.get('active_file')} | Hoja: {st.session_state.get('active_sheet')}")
    with st.expander("📂 Dataset activo — vista previa y columnas", expanded=False):
        try:
            df0, meta0, used0 = get_active_df(st.session_state.active_file, st.session_state.get("active_sheet"))
            st.markdown(f"**Archivo:** `{st.session_state.active_file}`  |  **Origen:** `{used0}`")
            st.markdown(f"**Dimensión:** {df0.shape[0]} filas × {df0.shape[1]} columnas")
            st.markdown("**Columnas:**")
            st.write(list(df0.columns))
            st.markdown("**Vista previa (primeras 20 filas):**")
            st.dataframe(df0.head(20), use_container_width=True)
        except Exception as e:
            st.error(f"No se pudo cargar vista previa: {e}")

# Editor rápido del último gráfico
with st.expander("🎨 Editor rápido de gráficos (opcional)", expanded=False):
    cfg = st.session_state.get("last_plot_config")
    if not cfg:
        st.info("Aún no hay un gráfico generado.")
    else:
        cols = st.columns(2)
        title = cols[0].text_input("Título", value=cfg.get("title") or "")
        x_label = cols[0].text_input("Nombre eje X", value=cfg.get("x_label") or "")
        y_label = cols[0].text_input("Nombre eje Y", value=cfg.get("y_label") or "")

        template = cols[1].selectbox(
            "Plantilla",
            ["plotly_white", "plotly", "plotly_dark", "ggplot2", "seaborn", "simple_white"],
            index=["plotly_white", "plotly", "plotly_dark", "ggplot2", "seaborn", "simple_white"].index(cfg.get("template") or "plotly_white"),
        )

        x_unit_mode = cols[1].selectbox(
            "Unidad eje X",
            ["auto", "unidades", "miles", "millones", "miles de millones"],
            index=["auto", "unidades", "miles", "millones", "miles de millones"].index(cfg.get("x_unit_mode") or "auto"),
        )
        y_unit_mode = cols[1].selectbox(
            "Unidad eje Y",
            ["auto", "unidades", "miles", "millones", "miles de millones"],
            index=["auto", "unidades", "miles", "millones", "miles de millones"].index(cfg.get("y_unit_mode") or "auto"),
        )

        x_unit_label = cols[1].text_input("Etiqueta unidad X (opcional: kg, pesos...)", value=cfg.get("x_unit_label") or "")
        y_unit_label = cols[1].text_input("Etiqueta unidad Y (opcional: kg, pesos...)", value=cfg.get("y_unit_label") or "")

        colors_txt = st.text_input("Colores (opcional, separados por coma)", value=",".join(cfg.get("colors") or []))
        colors = [c.strip() for c in colors_txt.split(",") if c.strip()] if colors_txt.strip() else None

        if st.button("🔁 Regenerar último gráfico con estos cambios"):
            tool_plot({
                "kind": cfg["kind"],
                "file_name": st.session_state.get("active_file"),
                "sheet_name": st.session_state.get("active_sheet"),
                "x": cfg.get("x"),
                "y": cfg.get("y"),
                "color": cfg.get("color"),
                "title": title,
                "x_label": x_label or None,
                "y_label": y_label or None,
                "template": template,
                "color_discrete_sequence": colors,
                "x_unit_mode": x_unit_mode,
                "y_unit_mode": y_unit_mode,
                "x_unit_label": x_unit_label or None,
                "y_unit_label": y_unit_label or None,
            })

# Chat
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

user_msg = st.chat_input("Pide lo que necesites (ej: 'análisis descriptivo', 'grafica x vs y en millones', 'OLS y~x1+x2 robusta')")

if user_msg:
    st.session_state.messages.append({"role": "user", "content": user_msg})
    with st.chat_message("user"):
        st.markdown(user_msg)

    with st.chat_message("assistant"):
        with st.spinner("Analizando..."):
            answer = run_agent(user_msg, st.session_state.messages[:-1])
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})