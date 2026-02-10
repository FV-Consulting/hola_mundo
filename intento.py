import os
from io import BytesIO
from datetime import datetime
import re

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Importaciones opcionales
PLOTLY_AVAILABLE = False
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    pass

STATSMODELS_AVAILABLE = False
try:
    import statsmodels.api as sm
    from statsmodels.stats.diagnostic import het_breuschpagan
    from statsmodels.stats.stattools import durbin_watson
    STATSMODELS_AVAILABLE = True
except ImportError:
    pass

# =========================
# Configuración inicial
# =========================
DATA_DIR = "archivos_subidos/datos"
os.makedirs(DATA_DIR, exist_ok=True)

def sb_is_open() -> bool:
    qp = st.query_params
    return str(qp.get("sb", "1")) != "0"

# =========================
# FORMATO LATINO + ESCALADO
# =========================
PLOTLY_CONFIG = {"locale": "pt-BR"}


def format_lat_number(x, decimals=2):
    """
    Formatea números con:
    - '.' miles
    - ',' decimales
    """
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return ""
        s = f"{float(x):,.{decimals}f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s
    except Exception:
        return str(x)


def mpl_lat_formatter(decimals=0):
    def _fmt(x, pos=None):
        return format_lat_number(x, decimals=decimals)
    return FuncFormatter(_fmt)


def style_latino(df: pd.DataFrame, decimals=2):
    """
    Styler para que st.dataframe muestre:
    - '.' miles
    - ',' decimales
    SOLO para columnas numéricas.
    """
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if not num_cols:
        return df

    fmt_map = {c: (lambda v, d=decimals: format_lat_number(v, decimals=d)) for c in num_cols}
    return df.style.format(fmt_map, na_rep="")


def get_scale_factor_and_label(mode: str, series_max_abs: float):
    if mode == "Unidades":
        return 1.0, "unidades"
    if mode == "Cientos":
        return 100.0, "cientos"
    if mode == "Miles":
        return 1_000.0, "miles"
    if mode == "Millones":
        return 1_000_000.0, "millones"

    m = float(series_max_abs) if series_max_abs is not None else 0.0
    m = abs(m)

    if m >= 1_000_000:
        return 1_000_000.0, "millones"
    if m >= 1_000:
        return 1_000.0, "miles"
    if m >= 100:
        return 100.0, "cientos"
    return 1.0, "unidades"


def scale_values(arr, factor: float):
    try:
        return np.asarray(arr, dtype="float64") / float(factor)
    except Exception:
        return arr


def set_title_with_unit_matplotlib(ax, title: str, unit_label: str):
    ax.set_title(f"{title}\nUnidad: {unit_label}", fontsize=14)


def set_title_with_unit_plotly(fig, title: str, unit_label: str):
    fig.update_layout(
        title=dict(
            text=f"{title}<br><sup>Unidad: {unit_label}</sup>",
            x=0.0,
            xanchor="left"
        )
    )
    return fig


def _nice_ticks(vmin: float, vmax: float, n: int = 6):
    """
    Genera ticks "bonitos" (aprox. n ticks) para un rango numérico.
    """
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        return [vmin] if np.isfinite(vmin) else [0.0]

    span = vmax - vmin
    vmin2 = vmin - 0.02 * span
    vmax2 = vmax + 0.02 * span

    raw = np.linspace(vmin2, vmax2, n)

    mag = max(abs(vmin2), abs(vmax2), 1e-9)
    if mag >= 1_000_000:
        step = 100_000
    elif mag >= 100_000:
        step = 10_000
    elif mag >= 10_000:
        step = 1_000
    elif mag >= 1_000:
        step = 100
    elif mag >= 100:
        step = 10
    elif mag >= 10:
        step = 1
    elif mag >= 1:
        step = 0.1
    else:
        step = 0.01

    ticks = np.unique(np.round(raw / step) * step)
    return ticks.tolist()


def apply_plotly_latino_format(fig, decimals=0):
    fig.update_layout(separators=".,")

    # ---- EJE Y ----
    y_all = []
    for tr in fig.data:
        if hasattr(tr, "y") and tr.y is not None:
            try:
                y_arr = np.asarray(tr.y, dtype="float64")
                y_arr = y_arr[np.isfinite(y_arr)]
                if y_arr.size:
                    y_all.append(y_arr)
            except Exception:
                pass

    if y_all:
        y_concat = np.concatenate(y_all)
        y_min, y_max = float(np.min(y_concat)), float(np.max(y_concat))
        y_ticks = _nice_ticks(y_min, y_max, n=6)
        y_text = [format_lat_number(v, decimals=decimals) for v in y_ticks]

        fig.update_yaxes(
            tickmode="array",
            tickvals=y_ticks,
            ticktext=y_text
        )

    # ---- EJE X numérico ----
    x_all = []
    x_is_numeric = True
    for tr in fig.data:
        if hasattr(tr, "x") and tr.x is not None:
            try:
                x_arr = np.asarray(tr.x)
                if x_arr.dtype.kind in ("U", "S", "O"):
                    x_is_numeric = False
                    break
                x_num = np.asarray(tr.x, dtype="float64")
                x_num = x_num[np.isfinite(x_num)]
                if x_num.size:
                    x_all.append(x_num)
            except Exception:
                x_is_numeric = False
                break

    if x_is_numeric and x_all:
        x_concat = np.concatenate(x_all)
        x_min, x_max = float(np.min(x_concat)), float(np.max(x_concat))
        x_ticks = _nice_ticks(x_min, x_max, n=6)
        x_text = [format_lat_number(v, decimals=decimals) for v in x_ticks]

        fig.update_xaxes(
            tickmode="array",
            tickvals=x_ticks,
            ticktext=x_text
        )

    # ---- HOVER ----
    for tr in fig.data:
        if hasattr(tr, "y") and tr.y is not None:
            try:
                y_vals = np.asarray(tr.y, dtype="float64")
                tr.customdata = [format_lat_number(v, decimals=decimals) for v in y_vals]
                tr.hovertemplate = "%{customdata}<extra></extra>"
            except Exception:
                pass

    return fig


# =========================
# LECTURA ROBUSTA DE ARCHIVOS
# =========================
def ext_archivo(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def listar_archivos():
    """Lista todos los archivos de datos soportados"""
    files = []
    extensiones_soportadas = [
        ".csv", ".tsv", ".txt", 
        ".xlsx", ".xls", ".xlsb", ".xlsm",
        ".parquet", ".feather", ".dta",
        ".json", ".jsonl",
        ".sav", ".sas7bdat",
        ".h5", ".hdf5", ".rdata"
    ]
    
    for f in os.listdir(DATA_DIR):
        p = os.path.join(DATA_DIR, f)
        if os.path.isfile(p):
            ext = ext_archivo(p)
            if ext in extensiones_soportadas:
                files.append(f)
    return sorted(files, key=str.lower)


def detectar_delimitador(path: str, n_lines: int = 5) -> str:
    """Detecta automáticamente el delimitador de un archivo de texto"""
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            sample = ''.join([f.readline() for _ in range(n_lines)])
        
        delimitadores = [',', ';', '\t', '|', ':']
        conteos = {d: sample.count(d) for d in delimitadores}
        delim = max(conteos, key=conteos.get)
        
        if conteos[delim] > 0:
            return delim
        return ','
    except Exception:
        return ','


def detectar_encoding(path: str) -> str:
    """Detecta el encoding del archivo"""
    encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']
    
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc) as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    return 'utf-8'


def excel_engine_for_ext(ext: str):
    if ext == ".xlsx":
        return "openpyxl"
    if ext == ".xls":
        return "xlrd"
    if ext == ".xlsb":
        return "pyxlsb"
    if ext == ".xlsm":
        return "openpyxl"
    return None


def obtener_sheets_excel(path: str):
    ext = ext_archivo(path)
    engine = excel_engine_for_ext(ext)
    try:
        xls = pd.ExcelFile(path, engine=engine)
        return xls.sheet_names
    except Exception:
        try:
            xls = pd.ExcelFile(path)
            return xls.sheet_names
        except Exception:
            return []


@st.cache_data(show_spinner=False)
def leer_archivo(path: str, sheet_name=None):
    """Lectura robusta y automática de múltiples formatos"""
    ext = ext_archivo(path)
    
    try:
        # Archivos CSV y de texto
        if ext in [".csv", ".txt"]:
            encoding = detectar_encoding(path)
            delim = detectar_delimitador(path)
            
            try:
                return pd.read_csv(path, sep=delim, encoding=encoding)
            except Exception:
                return pd.read_csv(path, sep=None, engine="python", encoding=encoding)
        
        # TSV
        elif ext == ".tsv":
            encoding = detectar_encoding(path)
            return pd.read_csv(path, sep="\t", encoding=encoding)
        
        # Excel
        elif ext in [".xlsx", ".xls", ".xlsb", ".xlsm"]:
            engine = excel_engine_for_ext(ext)
            if sheet_name is None:
                sheet_name = 0
            if engine:
                return pd.read_excel(path, sheet_name=sheet_name, engine=engine)
            return pd.read_excel(path, sheet_name=sheet_name)
        
        # Parquet
        elif ext == ".parquet":
            return pd.read_parquet(path)
        
        # Feather
        elif ext == ".feather":
            return pd.read_feather(path)
        
        # Stata
        elif ext == ".dta":
            return pd.read_stata(path)
        
        # JSON
        elif ext in [".json", ".jsonl"]:
            try:
                return pd.read_json(path)
            except ValueError:
                return pd.read_json(path, lines=True)
        
        # SPSS
        elif ext == ".sav":
            try:
                import pyreadstat
                df, meta = pyreadstat.read_sav(path)
                return df
            except ImportError:
                st.warning("Para leer archivos .sav, instala: pip install pyreadstat")
                return pd.DataFrame()
        
        # SAS
        elif ext == ".sas7bdat":
            return pd.read_sas(path)
        
        # HDF5
        elif ext in [".h5", ".hdf5"]:
            return pd.read_hdf(path)
        
        else:
            raise ValueError(f"Formato no soportado: {ext}")
    
    except Exception as e:
        st.error(f"Error al leer archivo {os.path.basename(path)}: {str(e)}")
        st.info("Intentando lectura alternativa...")
        
        # Intento de lectura genérica
        try:
            encoding = detectar_encoding(path)
            return pd.read_csv(path, sep=None, engine="python", encoding=encoding)
        except Exception as e2:
            st.error(f"No se pudo leer el archivo: {str(e2)}")
            return pd.DataFrame()


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
    """Limpieza robusta del DataFrame"""
    if df.empty:
        return df
    
    df2 = df.copy()
    
    # Eliminar filas/columnas completamente vacías
    if drop_blank:
        df2 = df2.dropna(axis=0, how="all")
        df2 = df2.dropna(axis=1, how="all")
    
    # Hacer nombres de columnas únicos
    df2.columns = make_unique_columns(df2.columns)
    
    # Eliminar columnas sin nombre o inválidas
    df2 = df2.loc[:, ~df2.columns.str.contains('^Unnamed')]
    
    return df2.reset_index(drop=True)


def intentar_convertir_numericos(df: pd.DataFrame, umbral=0.70) -> pd.DataFrame:
    """Conversión inteligente de columnas a numéricas"""
    out = df.copy()
    for c in out.columns:
        if out[c].dtype == "object":
            s = out[c].astype(str).str.strip()
            s = s.str.replace("\u00a0", "", regex=False).str.replace(" ", "", regex=False)
            s_lat = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
            conv = pd.to_numeric(s_lat, errors="coerce")
            if float(conv.notna().mean()) >= umbral:
                out[c] = conv
    return out


def columnas_numericas(df):
    return df.select_dtypes(include="number").columns.tolist()


def columnas_no_numericas(df):
    nums = set(columnas_numericas(df))
    return [c for c in df.columns if c not in nums]


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


# =========================
# CONVERSIÓN ROBUSTA DE FECHAS
# =========================
def convertir_fecha_robusta(series: pd.Series) -> pd.Series:
    meses_es = {
        "ene": "01", "enero": "01",
        "feb": "02", "febrero": "02",
        "mar": "03", "marzo": "03",
        "abr": "04", "abril": "04",
        "may": "05", "mayo": "05",
        "jun": "06", "junio": "06",
        "jul": "07", "julio": "07",
        "ago": "08", "agosto": "08",
        "sep": "09", "septiembre": "09", "sept": "09",
        "oct": "10", "octubre": "10",
        "nov": "11", "noviembre": "11",
        "dic": "12", "diciembre": "12",
    }

    result = pd.Series([pd.NaT] * len(series), index=series.index)
    formatos = [
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
        "%m-%d-%Y", "%m/%d/%Y",
        "%d %m %Y", "%d %m %y",
        "%Y%m%d",
    ]

    for idx, val in series.items():
        if pd.isna(val):
            continue

        val_str = str(val).strip().lower()

        for mes_nombre, mes_num in meses_es.items():
            val_str = re.sub(rf"\b{mes_nombre}\b", mes_num, val_str)

        try:
            fecha_convertida = pd.to_datetime(val_str, errors="coerce", dayfirst=True)
            if not pd.isna(fecha_convertida):
                result[idx] = fecha_convertida
                continue
        except Exception:
            pass

        for fmt in formatos:
            try:
                result[idx] = datetime.strptime(val_str, fmt)
                break
            except Exception:
                continue

    return result


# =========================
# TIPADO DE COLUMNAS
# =========================
def aplicar_tipo_columna(df: pd.DataFrame, col: str, tipo: str) -> pd.DataFrame:
    out = df.copy()
    if col not in out.columns:
        return out

    if tipo == "Texto":
        out[col] = out[col].astype(str)

    elif tipo == "Numérica":
        s = out[col].astype(str).str.strip()
        s = s.str.replace("\u00a0", "", regex=False).str.replace(" ", "", regex=False)
        s_lat = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        out[col] = pd.to_numeric(s_lat, errors="coerce")

    elif tipo == "Fecha":
        out[col] = convertir_fecha_robusta(out[col])

    elif tipo == "Moneda":
        s = out[col].astype(str).str.strip()
        s = s.str.replace("$", "", regex=False).str.replace("€", "", regex=False)
        s = s.str.replace("£", "", regex=False).str.replace("¥", "", regex=False)
        s = s.str.replace("\u00a0", "", regex=False).str.replace(" ", "", regex=False)
        s_lat = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        out[col] = pd.to_numeric(s_lat, errors="coerce")

    return out


def panel_tipado(df: pd.DataFrame):
    st.subheader("Configuración de Tipos de Columnas")

    with st.expander("❓ Ayuda", expanded=False):
        st.markdown(
            """
            **Regla numérica (formato latino)**
            - **','** separador decimal
            - **'.'** separador de miles
            - Ejemplo: `1.234.567,89` → `1234567.89`
            """
        )

    if "col_types" not in st.session_state:
        st.session_state["col_types"] = {}

    col_types = st.session_state["col_types"]

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        col = st.selectbox("Columna", df.columns.tolist(), key="type_col_pick")
    with c2:
        tipo = st.selectbox("Tipo", ["Texto", "Numérica", "Fecha", "Moneda"], key="type_kind_pick")
    with c3:
        st.write("")
        st.write("")
        if st.button("Aplicar", key="type_apply_btn"):
            col_types[col] = tipo
            st.success(f"✓ Tipo guardado: {col} → {tipo}")

    df2 = df.copy()
    for c, t in col_types.items():
        if c in df2.columns:
            df2 = aplicar_tipo_columna(df2, c, t)

    with st.expander("Ver tipos definidos", expanded=False):
        if col_types:
            resumen = pd.DataFrame([{"Columna": k, "Tipo": v} for k, v in col_types.items()]).sort_values("Columna")
            st.dataframe(resumen, use_container_width=True, height=200)
            if st.button("Limpiar todos los tipos", key="type_reset_btn"):
                st.session_state["col_types"] = {}
                st.rerun()
        else:
            st.info("Aún no has definido tipos manualmente.")

    return df2


# =========================
# ESTADÍSTICA DESCRIPTIVA
# =========================
def seccion_estadistica_descriptiva(df: pd.DataFrame):
    st.header("Estadística Descriptiva")

    cols = df.columns.tolist()
    if not cols:
        st.info("El dataset no tiene columnas.")
        return

    c1, c2 = st.columns([3, 1])
    with c1:
        sel = st.multiselect(
            "Variables a incluir en el análisis",
            cols,
            default=cols[: min(12, len(cols))],
            help="Puedes mezclar variables numéricas y categóricas."
        )
    with c2:
        include_all = st.toggle("Incluir variables categóricas", value=True)

    if not sel:
        st.warning("⚠️ Selecciona al menos una variable.")
        return

    d = df[sel].copy()
    desc = d.describe(include=("all" if include_all else None))

    na = d.isna().sum().sort_values(ascending=False).to_frame("Cantidad de NA")
    na["% de NA"] = (na["Cantidad de NA"] / len(d) * 100).round(2) if len(d) else 0.0

    st.subheader("Resumen Estadístico")
    st.dataframe(style_latino(desc, decimals=2), use_container_width=True, height=360)

    st.subheader("Análisis de Valores Faltantes")
    st.dataframe(style_latino(na, decimals=2), use_container_width=True, height=320)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ Descargar estadísticas (CSV)",
            df_to_csv_bytes(desc.reset_index().rename(columns={"index": "estadística"})),
            file_name="estadisticas_descriptivas.csv",
            mime="text/csv",
        )
    with col2:
        st.download_button(
            "⬇️ Descargar faltantes (CSV)",
            df_to_csv_bytes(na.reset_index().rename(columns={"index": "variable"})),
            file_name="valores_faltantes.csv",
            mime="text/csv",
        )


# =========================
# ILUSTRACIONES (MANTENIDO)
# =========================
def seccion_ilustraciones(df: pd.DataFrame, scale_mode: str):
    st.header("Ilustraciones y Visualizaciones")

    if not PLOTLY_AVAILABLE:
        st.warning("⚠️ Plotly no está instalado. Instala con: pip install plotly")
        st.info("Se usará Matplotlib como alternativa.")

    cols_num = columnas_numericas(df)
    cols_cat = columnas_no_numericas(df)

    if df.empty:
        st.info("Dataset vacío.")
        return

    tipo_grafico = st.selectbox(
        "Selecciona el tipo de gráfico",
        [
            "Gráfico de Barras",
            "Gráfico de Líneas",
            "Gráfico de Pastel (Pie)",
            "Gráfico de Dispersión",
            "Gráfico de Dispersión (Múltiples Variables)",
            "Gráfico de Área",
            "Histograma",
            "Box Plot",
        ]
    )

    st.divider()

    if tipo_grafico == "Gráfico de Barras":
        render_bar_chart_mejorado(df, cols_num, cols_cat, scale_mode)
    elif tipo_grafico == "Gráfico de Líneas":
        render_line_chart_mejorado(df, cols_num, cols_cat, scale_mode)
    elif tipo_grafico == "Gráfico de Pastel (Pie)":
        render_pie_chart_mejorado(df, cols_cat)
    elif tipo_grafico == "Gráfico de Dispersión":
        render_scatter_chart_plotly(df, cols_num, scale_mode)
    elif tipo_grafico == "Gráfico de Dispersión (Múltiples Variables)":
        render_scatter_multiple(df, cols_num, scale_mode)
    elif tipo_grafico == "Gráfico de Área":
        render_area_chart_mejorado(df, cols_num, cols_cat, scale_mode)
    elif tipo_grafico == "Histograma":
        render_histogram_plotly(df, cols_num, scale_mode)
    elif tipo_grafico == "Box Plot":
        render_boxplot_plotly(df, cols_num, cols_cat, scale_mode)


def _scale_info_for_ycols(df, y_cols, scale_mode: str):
    mx = 0.0
    for c in y_cols:
        try:
            mx = max(mx, float(np.nanmax(np.abs(df[c].values.astype("float64")))))
        except Exception:
            continue
    factor, label = get_scale_factor_and_label(scale_mode, mx)
    return factor, label


def render_bar_chart_mejorado(df, cols_num, cols_cat, scale_mode: str):
    if not cols_cat and not cols_num:
        st.warning("No hay columnas disponibles para graficar.")
        return

    col1, col2 = st.columns(2)
    with col1:
        cat_col = st.selectbox("Variable categórica (Eje X)", cols_cat if cols_cat else df.columns.tolist())
    with col2:
        num_cols = st.multiselect(
            "Variables numéricas (Eje Y) - puedes seleccionar varias",
            cols_num if cols_num else df.columns.tolist(),
            default=[cols_num[0]] if cols_num else []
        )

    if not num_cols:
        st.info("Selecciona al menos una variable numérica.")
        return

    factor, unit_label = _scale_info_for_ycols(df, num_cols, scale_mode)

    st.subheader("Filtro de Categorías")
    categorias_unicas = sorted(df[cat_col].dropna().unique().tolist())

    col_a, col_b = st.columns(2)
    with col_a:
        min_range = st.number_input("Desde categoría #", 1, len(categorias_unicas), 1, key="bar_min")
    with col_b:
        max_range = st.number_input(
            "Hasta categoría #",
            min_range,
            len(categorias_unicas),
            min(min_range + 9, len(categorias_unicas)),
            key="bar_max"
        )

    categorias_seleccionadas = st.multiselect(
        "O selecciona categorías específicas",
        categorias_unicas,
        default=categorias_unicas[min_range - 1:max_range],
        key="bar_cat_select"
    )

    if not categorias_seleccionadas:
        st.warning("Selecciona al menos una categoría.")
        return

    data = df[df[cat_col].isin(categorias_seleccionadas)][[cat_col] + num_cols].dropna()
    cat_order = data[cat_col].drop_duplicates().tolist()

    if PLOTLY_AVAILABLE:
        fig = go.Figure()
        for num_col in num_cols:
            grouped = data.groupby(cat_col, sort=False)[num_col].mean().reindex(cat_order)
            y_scaled = scale_values(grouped.values, factor)
            fig.add_trace(go.Bar(x=grouped.index, y=y_scaled, name=num_col))

        fig.update_layout(
            xaxis_title=cat_col,
            yaxis_title=f"Valores (en {unit_label})",
            barmode="group",
            height=500
        )
        fig = set_title_with_unit_plotly(fig, f"Comparación de {', '.join(num_cols)} por {cat_col}", unit_label)
        fig = apply_plotly_latino_format(fig, decimals=0)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    else:
        fig, ax = plt.subplots(figsize=(12, 6))
        x = np.arange(len(cat_order))
        width = 0.8 / len(num_cols)

        for i, num_col in enumerate(num_cols):
            grouped = data.groupby(cat_col, sort=False)[num_col].mean().reindex(cat_order)
            y_scaled = scale_values(grouped.values, factor)
            ax.bar(x + i * width, y_scaled, width, label=num_col)

        ax.set_xlabel(cat_col)
        ax.set_ylabel(f"Valores (en {unit_label})")
        set_title_with_unit_matplotlib(ax, f"Comparación por {cat_col}", unit_label)

        ax.set_xticks(x + width * (len(num_cols) - 1) / 2)
        ax.set_xticklabels(cat_order, rotation=45, ha="right")
        ax.legend()
        ax.grid(True, alpha=0.3)

        ax.yaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
        st.pyplot(fig)


def render_line_chart_mejorado(df, cols_num, cols_cat, scale_mode: str):
    if not cols_num:
        st.warning("No hay columnas numéricas disponibles.")
        return

    col1, col2 = st.columns(2)
    with col1:
        x_col = st.selectbox("Eje X", df.columns.tolist())
    with col2:
        y_cols = st.multiselect(
            "Eje Y (puedes seleccionar múltiples)",
            cols_num,
            default=cols_num[: min(5, len(cols_num))]
        )

    if not y_cols:
        st.info("Selecciona al menos una variable para el eje Y.")
        return

    factor, unit_label = _scale_info_for_ycols(df, y_cols, scale_mode)

    data = df[[x_col] + y_cols].dropna()
    if not (pd.api.types.is_numeric_dtype(data[x_col]) or pd.api.types.is_datetime64_any_dtype(data[x_col])):
        data = data.groupby(x_col, sort=False)[y_cols].mean().reset_index()

    if PLOTLY_AVAILABLE:
        data_plot = data.copy()
        for y in y_cols:
            data_plot[y] = scale_values(data_plot[y].values, factor)

        fig = px.line(data_plot, x=x_col, y=y_cols, markers=True)
        fig.update_layout(height=500, yaxis_title=f"Valores (en {unit_label})")
        fig = set_title_with_unit_plotly(fig, f"Tendencia de {', '.join(y_cols)}", unit_label)
        fig = apply_plotly_latino_format(fig, decimals=0)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    else:
        fig, ax = plt.subplots(figsize=(12, 6))
        for y_col in y_cols:
            ax.plot(
                data[x_col],
                scale_values(data[y_col].values, factor),
                marker="o",
                label=y_col,
                linewidth=2
            )
        ax.set_xlabel(x_col, fontsize=12)
        ax.set_ylabel(f"Valores (en {unit_label})", fontsize=12)
        set_title_with_unit_matplotlib(ax, f"Tendencia de {', '.join(y_cols)}", unit_label)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()

        ax.yaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
        st.pyplot(fig)


def render_pie_chart_mejorado(df, cols_cat):
    if not cols_cat:
        st.warning("No hay columnas categóricas disponibles.")
        return

    cat_col = st.selectbox("Variable categórica", cols_cat)

    st.subheader("Filtro de Categorías")
    categorias_unicas = sorted(df[cat_col].dropna().unique().tolist())

    col_a, col_b = st.columns(2)
    with col_a:
        min_range = st.number_input("Desde categoría #", 1, len(categorias_unicas), 1, key="pie_min")
    with col_b:
        max_range = st.number_input(
            "Hasta categoría #",
            min_range,
            len(categorias_unicas),
            min(min_range + 9, len(categorias_unicas)),
            key="pie_max"
        )

    categorias_seleccionadas = st.multiselect(
        "O selecciona categorías específicas",
        categorias_unicas,
        default=categorias_unicas[min_range - 1:max_range],
        key="pie_cat_select"
    )

    if not categorias_seleccionadas:
        st.warning("Selecciona al menos una categoría.")
        return

    vc = df[df[cat_col].isin(categorias_seleccionadas)][cat_col].value_counts()

    if PLOTLY_AVAILABLE:
        fig = px.pie(values=vc.values, names=vc.index)
        fig.update_layout(height=500)
        fig.update_layout(separators=".,")
        fig = set_title_with_unit_plotly(fig, f"Distribución de {cat_col}", "conteos")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    else:
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.pie(vc.values, labels=vc.index, autopct="%1.1f%%", startangle=90)
        ax.set_title(f"Distribución de {cat_col}", fontsize=14)
        st.pyplot(fig)


def render_scatter_multiple(df, cols_num, scale_mode: str):
    if len(cols_num) < 2:
        st.warning("Se necesitan al menos 2 columnas numéricas.")
        return

    col1, col2 = st.columns(2)
    with col1:
        x_col = st.selectbox("Eje X", cols_num, key="scatter_multi_x")
    with col2:
        y_cols = st.multiselect(
            "Ejes Y (múltiples)",
            [c for c in cols_num if c != x_col],
            default=[c for c in cols_num if c != x_col][: min(3, len(cols_num) - 1)],
            key="scatter_multi_y"
        )

    if not y_cols:
        st.info("Selecciona al menos una variable para el eje Y.")
        return

    factor, unit_label = _scale_info_for_ycols(df, y_cols, scale_mode)
    data = df[[x_col] + y_cols].dropna()

    if PLOTLY_AVAILABLE:
        fig = go.Figure()
        for y_col in y_cols:
            fig.add_trace(go.Scatter(
                x=data[x_col],
                y=scale_values(data[y_col].values, factor),
                mode="markers",
                name=y_col,
                marker=dict(size=8, opacity=0.6)
            ))
        fig.update_layout(
            xaxis_title=x_col,
            yaxis_title=f"Valores (en {unit_label})",
            height=500
        )
        fig = set_title_with_unit_plotly(fig, f"Dispersión: {', '.join(y_cols)} vs {x_col}", unit_label)
        fig = apply_plotly_latino_format(fig, decimals=0)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    else:
        fig, ax = plt.subplots(figsize=(12, 6))
        for y_col in y_cols:
            ax.scatter(
                data[x_col],
                scale_values(data[y_col].values, factor),
                label=y_col,
                alpha=0.6,
                s=50
            )
        ax.set_xlabel(x_col, fontsize=12)
        ax.set_ylabel(f"Valores (en {unit_label})", fontsize=12)
        set_title_with_unit_matplotlib(ax, f"Dispersión: {', '.join(y_cols)} vs {x_col}", unit_label)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        ax.yaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
        st.pyplot(fig)


def render_scatter_chart_plotly(df, cols_num, scale_mode: str):
    if len(cols_num) < 2:
        st.warning("Se necesitan al menos 2 columnas numéricas.")
        return

    col1, col2 = st.columns(2)
    with col1:
        x_col = st.selectbox("Eje X", cols_num)
    with col2:
        y_col = st.selectbox("Eje Y", [c for c in cols_num if c != x_col])

    factor, unit_label = _scale_info_for_ycols(df, [y_col], scale_mode)
    data = df[[x_col, y_col]].dropna()

    if PLOTLY_AVAILABLE:
        data_plot = data.copy()
        data_plot[y_col] = scale_values(data_plot[y_col].values, factor)
        fig = px.scatter(data_plot, x=x_col, y=y_col)
        fig.update_layout(height=500, yaxis_title=f"{y_col} (en {unit_label})")
        fig = set_title_with_unit_plotly(fig, f"{y_col} vs {x_col}", unit_label)
        fig = apply_plotly_latino_format(fig, decimals=0)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(data[x_col], scale_values(data[y_col].values, factor), alpha=0.6, s=50)
        ax.set_xlabel(x_col, fontsize=12)
        ax.set_ylabel(f"{y_col} (en {unit_label})", fontsize=12)
        set_title_with_unit_matplotlib(ax, f"{y_col} vs {x_col}", unit_label)
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
        st.pyplot(fig)


def render_area_chart_mejorado(df, cols_num, cols_cat, scale_mode: str):
    if not cols_num:
        st.warning("No hay columnas numéricas disponibles.")
        return

    col1, col2 = st.columns(2)
    with col1:
        x_col = st.selectbox("Eje X", df.columns.tolist())
    with col2:
        y_cols = st.multiselect("Eje Y (múltiples)", cols_num, default=cols_num[: min(3, len(cols_num))])

    if not y_cols:
        st.info("Selecciona al menos una variable para el eje Y.")
        return

    factor, unit_label = _scale_info_for_ycols(df, y_cols, scale_mode)
    data = df[[x_col] + y_cols].dropna()

    if not (pd.api.types.is_numeric_dtype(data[x_col]) or pd.api.types.is_datetime64_any_dtype(data[x_col])):
        data = data.groupby(x_col, sort=False)[y_cols].mean().reset_index()

    if PLOTLY_AVAILABLE:
        data_plot = data.copy()
        for y in y_cols:
            data_plot[y] = scale_values(data_plot[y].values, factor)
        fig = px.area(data_plot, x=x_col, y=y_cols)
        fig.update_layout(height=500, yaxis_title=f"Valores (en {unit_label})")
        fig = set_title_with_unit_plotly(fig, f"Área: {', '.join(y_cols)}", unit_label)
        fig = apply_plotly_latino_format(fig, decimals=0)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    else:
        fig, ax = plt.subplots(figsize=(12, 6))
        xs = np.arange(len(data))
        for y_col in y_cols:
            ax.fill_between(xs, scale_values(data[y_col].values, factor), alpha=0.5, label=y_col)
        ax.set_xlabel(x_col, fontsize=12)
        ax.set_ylabel(f"Valores (en {unit_label})", fontsize=12)
        set_title_with_unit_matplotlib(ax, f"Área: {', '.join(y_cols)}", unit_label)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        ax.yaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
        st.pyplot(fig)


def render_histogram_plotly(df, cols_num, scale_mode: str):
    if not cols_num:
        st.warning("No hay columnas numéricas disponibles.")
        return

    col = st.selectbox("Variable numérica", cols_num)
    bins = st.slider("Número de bins", 10, 100, 30)

    factor, unit_label = _scale_info_for_ycols(df, [col], scale_mode)
    data = df[col].dropna()
    data_scaled = scale_values(data.values, factor)

    if PLOTLY_AVAILABLE:
        fig = px.histogram(data_scaled, nbins=bins)
        fig.update_layout(height=500, xaxis_title=f"{col} (en {unit_label})")
        fig = set_title_with_unit_plotly(fig, f"Histograma de {col}", unit_label)
        fig.update_layout(separators=".,")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(data_scaled, bins=bins, edgecolor="black")
        ax.set_xlabel(f"{col} (en {unit_label})", fontsize=12)
        ax.set_ylabel("Frecuencia", fontsize=12)
        set_title_with_unit_matplotlib(ax, f"Histograma de {col}", unit_label)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
        st.pyplot(fig)


def render_boxplot_plotly(df, cols_num, cols_cat, scale_mode: str):
    if not cols_num:
        st.warning("No hay columnas numéricas disponibles.")
        return

    col1, col2 = st.columns(2)
    with col1:
        y_col = st.selectbox("Variable numérica", cols_num)
    with col2:
        if cols_cat:
            x_col = st.selectbox("Agrupar por (opcional)", ["Ninguno"] + cols_cat)
        else:
            x_col = "Ninguno"

    factor, unit_label = _scale_info_for_ycols(df, [y_col], scale_mode)

    if x_col == "Ninguno":
        data = df[[y_col]].dropna()
        data_plot = data.copy()
        data_plot[y_col] = scale_values(data_plot[y_col].values, factor)

        if PLOTLY_AVAILABLE:
            fig = px.box(data_plot, y=y_col)
            fig.update_layout(height=500, yaxis_title=f"{y_col} (en {unit_label})")
            fig = set_title_with_unit_plotly(fig, f"Box Plot de {y_col}", unit_label)
            fig = apply_plotly_latino_format(fig, decimals=0)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.boxplot(data_plot[y_col].values)
            ax.set_ylabel(f"{y_col} (en {unit_label})", fontsize=12)
            set_title_with_unit_matplotlib(ax, f"Box Plot de {y_col}", unit_label)
            ax.yaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
            st.pyplot(fig)

    else:
        data = df[[x_col, y_col]].dropna()
        data_plot = data.copy()
        data_plot[y_col] = scale_values(data_plot[y_col].values, factor)

        if PLOTLY_AVAILABLE:
            fig = px.box(data_plot, x=x_col, y=y_col)
            fig.update_layout(height=500, yaxis_title=f"{y_col} (en {unit_label})")
            fig = set_title_with_unit_plotly(fig, f"Box Plot de {y_col} por {x_col}", unit_label)
            fig = apply_plotly_latino_format(fig, decimals=0)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            fig, ax = plt.subplots(figsize=(10, 6))
            data_plot.boxplot(column=y_col, by=x_col, ax=ax)
            plt.suptitle("")
            set_title_with_unit_matplotlib(ax, f"Box Plot de {y_col} por {x_col}", unit_label)
            plt.xticks(rotation=45, ha="right")
            ax.yaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
            st.pyplot(fig)


# =========================
# REGRESIONES LINEALES
# =========================
def seccion_regresiones(df: pd.DataFrame, scale_mode: str):
    """
    Sección de regresiones lineales simples y múltiples con tests estadísticos
    """
    st.header("Regresiones Lineales y Tests Econométricos")
    
    if not STATSMODELS_AVAILABLE:
        st.error("⚠️ Se requiere statsmodels para análisis econométrico. Instala con: pip install statsmodels")
        return
    
    cols_num = columnas_numericas(df)
    if len(cols_num) < 2:
        st.warning("Se necesitan al menos 2 columnas numéricas para realizar regresiones.")
        return
    
    # Tipo de regresión
    tipo_regresion = st.radio(
        "Tipo de Regresión",
        ["Regresión Lineal Simple", "Regresión Lineal Múltiple"],
        horizontal=True
    )
    
    st.divider()
    
    if tipo_regresion == "Regresión Lineal Simple":
        regresion_simple(df, cols_num, scale_mode)
    else:
        regresion_multiple(df, cols_num, scale_mode)


def regresion_simple(df: pd.DataFrame, cols_num: list, scale_mode: str):
    """Regresión lineal simple Y = β0 + β1*X + ε"""
    
    st.subheader("Regresión Lineal Simple")
    st.markdown("**Modelo:** Y = β₀ + β₁·X + ε")
    
    col1, col2 = st.columns(2)
    with col1:
        x_col = st.selectbox("Variable independiente (X)", cols_num, key="reg_simple_x")
    with col2:
        y_col = st.selectbox(
            "Variable dependiente (Y)", 
            [c for c in cols_num if c != x_col], 
            key="reg_simple_y"
        )
    
    # Preparar datos
    data_clean = df[[x_col, y_col]].dropna()
    
    if len(data_clean) < 3:
        st.warning("Se necesitan al menos 3 observaciones válidas.")
        return
    
    st.info(f"📊 Observaciones utilizadas: **{format_lat_number(len(data_clean), decimals=0)}**")
    
    # Ajustar modelo
    X = sm.add_constant(data_clean[x_col])
    y = data_clean[y_col]
    
    modelo = sm.OLS(y, X).fit()
    
    # ====================
    # RESULTADOS
    # ====================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Resumen del Modelo", 
        "📈 Gráficos", 
        "🔬 Tests Estadísticos",
        "📋 Tabla Completa"
    ])
    
    with tab1:
        mostrar_resumen_regresion(modelo, x_col, y_col)
    
    with tab2:
        graficar_regresion_simple(data_clean, x_col, y_col, modelo, scale_mode)
    
    with tab3:
        realizar_tests_diagnostico(modelo, data_clean, x_col)
    
    with tab4:
        st.subheader("Tabla Completa de Resultados")
        st.text(modelo.summary())
        
        # Descargar resultados
        st.download_button(
            "⬇️ Descargar resultados (TXT)",
            str(modelo.summary()),
            file_name=f"regresion_simple_{y_col}_vs_{x_col}.txt",
            mime="text/plain"
        )


def regresion_multiple(df: pd.DataFrame, cols_num: list, scale_mode: str):
    """Regresión lineal múltiple Y = β0 + β1*X1 + β2*X2 + ... + ε"""
    
    st.subheader("Regresión Lineal Múltiple")
    st.markdown("**Modelo:** Y = β₀ + β₁·X₁ + β₂·X₂ + ... + βₖ·Xₖ + ε")
    
    col1, col2 = st.columns(2)
    with col1:
        y_col = st.selectbox("Variable dependiente (Y)", cols_num, key="reg_mult_y")
    with col2:
        x_cols = st.multiselect(
            "Variables independientes (X₁, X₂, ...)",
            [c for c in cols_num if c != y_col],
            default=[c for c in cols_num if c != y_col][:min(3, len(cols_num)-1)],
            key="reg_mult_x"
        )
    
    if not x_cols:
        st.info("Selecciona al menos una variable independiente.")
        return
    
    # Preparar datos
    data_clean = df[[y_col] + x_cols].dropna()
    
    if len(data_clean) < len(x_cols) + 2:
        st.warning(f"Se necesitan al menos {len(x_cols) + 2} observaciones para este modelo.")
        return
    
    st.info(f"📊 Observaciones utilizadas: **{format_lat_number(len(data_clean), decimals=0)}**")
    st.info(f"🔢 Variables independientes: **{len(x_cols)}**")
    
    # Ajustar modelo
    X = sm.add_constant(data_clean[x_cols])
    y = data_clean[y_col]
    
    modelo = sm.OLS(y, X).fit()
    
    # ====================
    # RESULTADOS
    # ====================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Resumen del Modelo", 
        "📈 Gráficos", 
        "🔬 Tests Estadísticos",
        "📋 Tabla Completa"
    ])
    
    with tab1:
        mostrar_resumen_regresion_multiple(modelo, x_cols, y_col)
    
    with tab2:
        graficar_regresion_multiple(data_clean, x_cols, y_col, modelo, scale_mode)
    
    with tab3:
        realizar_tests_diagnostico(modelo, data_clean, x_cols)
    
    with tab4:
        st.subheader("Tabla Completa de Resultados")
        st.text(modelo.summary())
        
        # Descargar resultados
        st.download_button(
            "⬇️ Descargar resultados (TXT)",
            str(modelo.summary()),
            file_name=f"regresion_multiple_{y_col}.txt",
            mime="text/plain"
        )


def mostrar_resumen_regresion(modelo, x_col: str, y_col: str):
    """Muestra resumen visual de la regresión simple"""
    
    st.markdown("### 📋 Ecuación del Modelo")
    
    beta_0 = modelo.params['const']
    beta_1 = modelo.params[x_col]
    
    signo = '+' if beta_1 >= 0 else ''
    st.latex(f"\\hat{{Y}} = {beta_0:.4f} {signo} {beta_1:.4f} \\cdot X")
    
    st.markdown(f"**{y_col} = {format_lat_number(beta_0, 4)} {signo} {format_lat_number(beta_1, 4)} · {x_col}**")
    
    st.divider()
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("R² (Ajustado)", f"{modelo.rsquared_adj:.4f}")
        st.caption("Bondad de ajuste")
    
    with col2:
        st.metric("R²", f"{modelo.rsquared:.4f}")
        st.caption("Coef. determinación")
    
    with col3:
        st.metric("F-statistic", f"{format_lat_number(modelo.fvalue, 2)}")
        st.caption(f"p-value: {modelo.f_pvalue:.4e}")
    
    with col4:
        st.metric("N° observaciones", format_lat_number(int(modelo.nobs), 0))
    
    st.divider()
    
    # Tabla de coeficientes
    st.markdown("### 📊 Coeficientes y Significancia")
    
    resultados = pd.DataFrame({
        'Coeficiente': modelo.params,
        'Error Estándar': modelo.bse,
        'Estadístico t': modelo.tvalues,
        'P-value': modelo.pvalues,
        'IC 95% Inferior': modelo.conf_int()[0],
        'IC 95% Superior': modelo.conf_int()[1]
    })
    
    resultados.index = ['Intercepto (β₀)', f'{x_col} (β₁)']
    
    # Agregar significancia
    def significancia(p):
        if p < 0.001:
            return "***"
        elif p < 0.01:
            return "**"
        elif p < 0.05:
            return "*"
        elif p < 0.1:
            return "."
        return ""
    
    resultados['Significancia'] = resultados['P-value'].apply(significancia)
    
    st.dataframe(style_latino(resultados, decimals=4), use_container_width=True)
    
    st.caption("Significancia: *** p<0.001, ** p<0.01, * p<0.05, . p<0.1")


def mostrar_resumen_regresion_multiple(modelo, x_cols: list, y_col: str):
    """Muestra resumen visual de la regresión múltiple"""
    
    st.markdown("### 📋 Ecuación del Modelo")
    
    ecuacion_parts = [f"{modelo.params['const']:.4f}"]
    for x in x_cols:
        coef = modelo.params[x]
        signo = '+' if coef >= 0 else ''
        ecuacion_parts.append(f"{signo} {coef:.4f}·{x}")
    
    ecuacion = " ".join(ecuacion_parts)
    st.markdown(f"**{y_col} = {ecuacion}**")
    
    st.divider()
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("R² (Ajustado)", f"{modelo.rsquared_adj:.4f}")
        st.caption("Bondad de ajuste")
    
    with col2:
        st.metric("R²", f"{modelo.rsquared:.4f}")
        st.caption("Coef. determinación")
    
    with col3:
        st.metric("F-statistic", f"{format_lat_number(modelo.fvalue, 2)}")
        st.caption(f"p-value: {modelo.f_pvalue:.4e}")
    
    with col4:
        st.metric("N° observaciones", format_lat_number(int(modelo.nobs), 0))
    
    st.divider()
    
    # Tabla de coeficientes
    st.markdown("### 📊 Coeficientes y Significancia")
    
    resultados = pd.DataFrame({
        'Coeficiente': modelo.params,
        'Error Estándar': modelo.bse,
        'Estadístico t': modelo.tvalues,
        'P-value': modelo.pvalues,
        'IC 95% Inferior': modelo.conf_int()[0],
        'IC 95% Superior': modelo.conf_int()[1]
    })
    
    # Renombrar índice
    nuevos_nombres = ['Intercepto (β₀)'] + [f'{x} (β{i+1})' for i, x in enumerate(x_cols)]
    resultados.index = nuevos_nombres
    
    # Agregar significancia
    def significancia(p):
        if p < 0.001:
            return "***"
        elif p < 0.01:
            return "**"
        elif p < 0.05:
            return "*"
        elif p < 0.1:
            return "."
        return ""
    
    resultados['Significancia'] = resultados['P-value'].apply(significancia)
    
    st.dataframe(style_latino(resultados, decimals=4), use_container_width=True)
    
    st.caption("Significancia: *** p<0.001, ** p<0.01, * p<0.05, . p<0.1")


def graficar_regresion_simple(data, x_col: str, y_col: str, modelo, scale_mode: str):
    """Genera gráficos para regresión simple"""
    
    factor, unit_label = get_scale_factor_and_label(
        scale_mode, 
        np.nanmax(np.abs(data[y_col].values))
    )
    
    x = data[x_col].values
    y = data[y_col].values
    y_pred = modelo.fittedvalues.values
    residuos = modelo.resid.values
    
    # Escalar para visualización
    y_scaled = scale_values(y, factor)
    y_pred_scaled = scale_values(y_pred, factor)
    residuos_scaled = scale_values(residuos, factor)
    
    # GRÁFICO 1: Dispersión con línea de regresión
    st.markdown("#### 1️⃣ Dispersión y Línea de Regresión")
    
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    
    # Puntos observados
    ax1.scatter(x, y_scaled, alpha=0.6, s=50, label='Datos observados', color='steelblue')
    
    # Línea de regresión
    sorted_idx = np.argsort(x)
    ax1.plot(x[sorted_idx], y_pred_scaled[sorted_idx], 
             color='red', linewidth=2, label='Línea de regresión')
    
    # Intervalos de confianza (95%)
    from scipy import stats
    predict = modelo.get_prediction()
    predict_summary = predict.summary_frame(alpha=0.05)
    
    lower = scale_values(predict_summary['obs_ci_lower'].values, factor)
    upper = scale_values(predict_summary['obs_ci_upper'].values, factor)
    
    ax1.fill_between(x[sorted_idx], lower[sorted_idx], upper[sorted_idx], 
                     alpha=0.2, color='red', label='IC 95%')
    
    ax1.set_xlabel(x_col, fontsize=12)
    ax1.set_ylabel(f"{y_col} (en {unit_label})", fontsize=12)
    ax1.set_title(f"Regresión: {y_col} vs {x_col}\nR² = {modelo.rsquared:.4f}", fontsize=14)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
    
    st.pyplot(fig1)
    
    # GRÁFICO 2: Residuos vs Valores Ajustados
    st.markdown("#### 2️⃣ Residuos vs Valores Ajustados")
    
    fig2, ax2 = plt.subplots(figsize=(12, 5))
    
    ax2.scatter(y_pred_scaled, residuos_scaled, alpha=0.6, s=50, color='steelblue')
    ax2.axhline(y=0, color='red', linestyle='--', linewidth=2)
    ax2.set_xlabel(f"Valores Ajustados (en {unit_label})", fontsize=12)
    ax2.set_ylabel(f"Residuos (en {unit_label})", fontsize=12)
    ax2.set_title("Gráfico de Residuos", fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
    ax2.yaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
    
    st.pyplot(fig2)
    
    # GRÁFICO 3: Q-Q Plot (Normalidad de residuos)
    st.markdown("#### 3️⃣ Q-Q Plot (Normalidad de Residuos)")
    
    fig3, ax3 = plt.subplots(figsize=(8, 8))
    sm.qqplot(residuos, line='s', ax=ax3)
    ax3.set_title("Q-Q Plot", fontsize=14)
    ax3.grid(True, alpha=0.3)
    
    st.pyplot(fig3)
    
    st.caption("💡 **Interpretación:** Si los puntos siguen la línea diagonal, los residuos son normales.")


def graficar_regresion_multiple(data, x_cols: list, y_col: str, modelo, scale_mode: str):
    """Genera gráficos para regresión múltiple"""
    
    factor, unit_label = get_scale_factor_and_label(
        scale_mode, 
        np.nanmax(np.abs(data[y_col].values))
    )
    
    y = data[y_col].values
    y_pred = modelo.fittedvalues.values
    residuos = modelo.resid.values
    
    # Escalar
    y_scaled = scale_values(y, factor)
    y_pred_scaled = scale_values(y_pred, factor)
    residuos_scaled = scale_values(residuos, factor)
    
    # GRÁFICO 1: Valores Observados vs Predichos
    st.markdown("#### 1️⃣ Valores Observados vs Predichos")
    
    fig1, ax1 = plt.subplots(figsize=(10, 10))
    
    ax1.scatter(y_scaled, y_pred_scaled, alpha=0.6, s=50, color='steelblue')
    
    # Línea de 45 grados (predicción perfecta)
    min_val = min(y_scaled.min(), y_pred_scaled.min())
    max_val = max(y_scaled.max(), y_pred_scaled.max())
    ax1.plot([min_val, max_val], [min_val, max_val], 
             'r--', linewidth=2, label='Predicción perfecta')
    
    ax1.set_xlabel(f"Valores Observados (en {unit_label})", fontsize=12)
    ax1.set_ylabel(f"Valores Predichos (en {unit_label})", fontsize=12)
    ax1.set_title(f"Observados vs Predichos\nR² = {modelo.rsquared:.4f}", fontsize=14)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
    ax1.yaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
    
    st.pyplot(fig1)
    
    # GRÁFICO 2: Residuos vs Valores Ajustados
    st.markdown("#### 2️⃣ Residuos vs Valores Ajustados")
    
    fig2, ax2 = plt.subplots(figsize=(12, 5))
    
    ax2.scatter(y_pred_scaled, residuos_scaled, alpha=0.6, s=50, color='steelblue')
    ax2.axhline(y=0, color='red', linestyle='--', linewidth=2)
    ax2.set_xlabel(f"Valores Ajustados (en {unit_label})", fontsize=12)
    ax2.set_ylabel(f"Residuos (en {unit_label})", fontsize=12)
    ax2.set_title("Gráfico de Residuos", fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
    ax2.yaxis.set_major_formatter(mpl_lat_formatter(decimals=0))
    
    st.pyplot(fig2)
    
    # GRÁFICO 3: Q-Q Plot
    st.markdown("#### 3️⃣ Q-Q Plot (Normalidad de Residuos)")
    
    fig3, ax3 = plt.subplots(figsize=(8, 8))
    sm.qqplot(residuos, line='s', ax=ax3)
    ax3.set_title("Q-Q Plot", fontsize=14)
    ax3.grid(True, alpha=0.3)
    
    st.pyplot(fig3)
    
    # GRÁFICO 4: Coeficientes con intervalos de confianza
    st.markdown("#### 4️⃣ Coeficientes e Intervalos de Confianza")
    
    params = modelo.params[1:]  # Excluir intercepto
    conf_int = modelo.conf_int()[1:]
    
    fig4, ax4 = plt.subplots(figsize=(10, max(6, len(x_cols) * 0.8)))
    
    y_pos = np.arange(len(x_cols))
    
    ax4.errorbar(params, y_pos, 
                xerr=[params - conf_int[0], conf_int[1] - params],
                fmt='o', markersize=8, capsize=5, capthick=2)
    
    ax4.axvline(x=0, color='red', linestyle='--', linewidth=1, alpha=0.5)
    ax4.set_yticks(y_pos)
    ax4.set_yticklabels(x_cols)
    ax4.set_xlabel('Valor del Coeficiente', fontsize=12)
    ax4.set_title('Coeficientes con IC 95%', fontsize=14)
    ax4.grid(True, alpha=0.3, axis='x')
    
    st.pyplot(fig4)


def realizar_tests_diagnostico(modelo, data, x_cols):
    """Realiza tests estadísticos de diagnóstico"""
    
    st.markdown("### 🔬 Tests de Diagnóstico Econométrico")
    
    # TEST 1: Normalidad de Residuos (Jarque-Bera)
    st.markdown("#### 1️⃣ Test de Normalidad (Jarque-Bera)")
    
    from statsmodels.stats.stattools import jarque_bera
    
    jb_stat, jb_pvalue, skew, kurtosis = jarque_bera(modelo.resid)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Estadístico JB", f"{jb_stat:.4f}")
        st.metric("P-value", f"{jb_pvalue:.4e}")
    with col2:
        st.metric("Asimetría (Skewness)", f"{skew:.4f}")
        st.metric("Curtosis (Kurtosis)", f"{kurtosis:.4f}")
    
    if jb_pvalue > 0.05:
        st.success("✅ Los residuos parecen seguir una distribución normal (p > 0.05)")
    else:
        st.warning("⚠️ Los residuos NO siguen una distribución normal (p < 0.05)")
    
    st.caption("**H₀:** Los residuos siguen una distribución normal")
    
    st.divider()
    
    # TEST 2: Heterocedasticidad (Breusch-Pagan)
    st.markdown("#### 2️⃣ Test de Heterocedasticidad (Breusch-Pagan)")
    
    bp_stat, bp_pvalue, _, _ = het_breuschpagan(modelo.resid, modelo.model.exog)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Estadístico LM", f"{bp_stat:.4f}")
    with col2:
        st.metric("P-value", f"{bp_pvalue:.4e}")
    
    if bp_pvalue > 0.05:
        st.success("✅ No hay evidencia de heterocedasticidad (p > 0.05)")
    else:
        st.warning("⚠️ Hay evidencia de heterocedasticidad (p < 0.05)")
    
    st.caption("**H₀:** Homocedasticidad (varianza constante de los residuos)")
    
    st.divider()
    
    # TEST 3: Autocorrelación (Durbin-Watson)
    st.markdown("#### 3️⃣ Test de Autocorrelación (Durbin-Watson)")
    
    dw_stat = durbin_watson(modelo.resid)
    
    st.metric("Estadístico Durbin-Watson", f"{dw_stat:.4f}")
    
    if 1.5 < dw_stat < 2.5:
        st.success(f"✅ No hay autocorrelación significativa (DW ≈ 2)")
    elif dw_stat < 1.5:
        st.warning(f"⚠️ Posible autocorrelación positiva (DW < 1.5)")
    else:
        st.warning(f"⚠️ Posible autocorrelación negativa (DW > 2.5)")
    
    st.caption("**Interpretación:** DW ≈ 2 indica ausencia de autocorrelación")
    
    st.divider()
    
    # TEST 4: Multicolinealidad (VIF) - Solo para regresión múltiple
    if isinstance(x_cols, list) and len(x_cols) > 1:
        st.markdown("#### 4️⃣ Test de Multicolinealidad (VIF)")
        
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        
        X = modelo.model.exog[:, 1:]  # Excluir intercepto
        
        vif_data = pd.DataFrame()
        vif_data["Variable"] = x_cols
        vif_data["VIF"] = [variance_inflation_factor(X, i) for i in range(X.shape[1])]
        
        st.dataframe(style_latino(vif_data, decimals=2), use_container_width=True)
        
        max_vif = vif_data["VIF"].max()
        
        if max_vif < 5:
            st.success("✅ No hay multicolinealidad problemática (VIF < 5)")
        elif max_vif < 10:
            st.warning("⚠️ Multicolinealidad moderada detectada (5 ≤ VIF < 10)")
        else:
            st.error("❌ Multicolinealidad severa detectada (VIF ≥ 10)")
        
        st.caption("**Interpretación:** VIF < 5: sin problema | 5-10: moderado | >10: severo")


# =========================
# MAIN APPLICATION
# =========================
def data_multiple():
    st.title("Sistema Integral de Análisis de Datos")
    st.caption("Análisis completo: Estadística · Visualizaciones · Regresiones")

    with st.sidebar:
        st.markdown("<div style='height:72px;'></div>", unsafe_allow_html=True)

    st.sidebar.header("Selección de Dataset")

    files = listar_archivos()
    if not files:
        st.warning(f"No hay archivos en: {DATA_DIR}")
        st.info("Por favor, carga archivos en la sección 'Cargar Documentos'.")
        st.stop()

    archivo = st.sidebar.selectbox("Archivo", files, key="file_selector")
    path = os.path.join(DATA_DIR, archivo)
    ext = ext_archivo(path)

    sheet = None
    if ext in [".xlsx", ".xls", ".xlsb", ".xlsm"]:
        sheets = obtener_sheets_excel(path)
        if not sheets:
            st.sidebar.error("No se pudieron listar las hojas de Excel.")
            st.stop()
        sheet = st.sidebar.selectbox("Hoja de Excel", sheets, key="sheet_selector")

    st.sidebar.header("Opciones de Limpieza")
    drop_blank = st.sidebar.toggle("Eliminar filas/columnas en blanco", value=True)
    auto_numeric = st.sidebar.toggle("Convertir numéricos automáticamente", value=True)
    umbral = st.sidebar.slider("Umbral de conversión", 0.40, 0.95, 0.70, 0.05) if auto_numeric else 0.70

    st.sidebar.header("Formato de Gráficos")
    scale_mode = st.sidebar.selectbox(
        "Unidad de los gráficos (eje Y)",
        ["Auto", "Unidades", "Cientos", "Miles", "Millones"],
        index=0
    )

    with st.spinner("📥 Cargando dataset..."):
        try:
            df = leer_archivo(path, sheet_name=sheet)
        except Exception as e:
            st.error(f"❌ Error al leer el archivo: {e}")
            st.stop()

    if df.empty:
        st.error("❌ El archivo está vacío o no se pudo leer correctamente.")
        st.stop()

    df = limpiar_df(df, drop_blank=drop_blank)
    if auto_numeric and not df.empty:
        df = intentar_convertir_numericos(df, umbral=umbral)

    st.info(
        f"**Dataset:** {archivo}"
        + (f" | **Hoja:** {sheet}" if sheet else "")
        + f" | **Filas:** {format_lat_number(len(df), decimals=0)}"
        + f" | **Columnas:** {format_lat_number(df.shape[1], decimals=0)}"
    )

    st.divider()
    df_typed = panel_tipado(df)

    with st.expander("Vista Previa del Dataset", expanded=False):
        st.dataframe(style_latino(df_typed.head(100), decimals=2), use_container_width=True, height=400)

    st.divider()

    st.subheader("Selecciona una Sección de Análisis")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📊 Estadística Descriptiva", use_container_width=True, type="primary"):
            st.session_state["seccion_activa"] = "estadistica"
    with col2:
        if st.button("📈 Ilustraciones", use_container_width=True, type="primary"):
            st.session_state["seccion_activa"] = "ilustraciones"
    with col3:
        if st.button("📉 Regresiones Lineales", use_container_width=True, type="primary"):
            st.session_state["seccion_activa"] = "regresiones"

    if "seccion_activa" not in st.session_state:
        st.session_state["seccion_activa"] = None

    st.divider()

    if st.session_state["seccion_activa"] == "estadistica":
        seccion_estadistica_descriptiva(df_typed)
    elif st.session_state["seccion_activa"] == "ilustraciones":
        seccion_ilustraciones(df_typed, scale_mode)
    elif st.session_state["seccion_activa"] == "regresiones":
        seccion_regresiones(df_typed, scale_mode)
    else:
        st.info("Selecciona una sección de análisis usando los botones superiores.")

    st.divider()
    st.header("Dataset Completo")
    st.dataframe(style_latino(df_typed, decimals=2), use_container_width=True, height=500)

    st.download_button(
        "⬇️ Descargar Dataset Procesado (CSV)",
        df_to_csv_bytes(df_typed),
        file_name=f"{archivo.split('.')[0]}_procesado.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    data_multiple()