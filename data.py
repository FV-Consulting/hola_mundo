import os
import io
import re
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# ✅ CONFIGURAR LÍMITE DE PANDAS STYLER
pd.set_option("styler.render.max_elements", 10_000_000)

# ✅ CONEXIÓN A NEON (POSTGRESQL)
# Se asume que la URL está en st.secrets["connections"]["postgresql"]["url"]
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Error de configuración de base de datos: {e}")
    st.stop()

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

# ============================================================
# FUNCIONES DE LECTURA SQL
# ============================================================

def listar_tablas_sql():
    """Lista las tablas del usuario en el esquema public"""
    try:
        query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;"
        df_tablas = conn.query(query)
        return df_tablas['table_name'].tolist()
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return []

@st.cache_data(ttl=600)
def leer_tabla_sql(nombre_tabla):
    """Lee una tabla completa desde Neon"""
    try:
        # Usamos comillas dobles para manejar nombres de tablas con caracteres especiales
        query = f'SELECT * FROM "{nombre_tabla}";'
        return conn.query(query)
    except Exception as e:
        st.error(f"Error al leer la tabla {nombre_tabla}: {e}")
        return pd.DataFrame()

# ============================================================
# FORMATO LATINO + UTILIDADES
# ============================================================

def format_lat_number(x, decimals=2):
    try:
        if x is None or (isinstance(x, (float, np.floating)) and np.isnan(x)):
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

def style_latino(df: pd.DataFrame, decimals=2, max_cells=262144):
    total_cells = df.shape[0] * df.shape[1]
    if total_cells > max_cells:
        return df
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if not num_cols:
        return df
    fmt_map = {c: (lambda v, d=decimals: format_lat_number(v, decimals=d)) for c in num_cols}
    return df.style.format(fmt_map, na_rep="")

def get_scale_factor_and_label(mode: str, series_max_abs: float):
    if mode == "Unidades": return 1.0, "unidades"
    if mode == "Cientos": return 100.0, "cientos"
    if mode == "Miles": return 1_000.0, "miles"
    if mode == "Millones": return 1_000_000.0, "millones"

    m = abs(float(series_max_abs)) if series_max_abs is not None else 0.0
    if m >= 1_000_000: return 1_000_000.0, "millones"
    if m >= 1_000: return 1_000.0, "miles"
    if m >= 100: return 100.0, "cientos"
    return 1.0, "unidades"

def scale_values(arr, factor: float):
    try:
        return np.asarray(arr, dtype="float64") / float(factor)
    except Exception:
        return arr

def set_title_with_unit_matplotlib(ax, title: str, unit_label: str):
    ax.set_title(f"{title}\nUnidad: {unit_label}", fontsize=14)

def set_title_with_unit_plotly(fig, title: str, unit_label: str):
    fig.update_layout(title=dict(text=f"{title}<br><sup>Unidad: {unit_label}</sup>", x=0.0, xanchor="left"))
    return fig

def apply_plotly_latino_format(fig, decimals=0):
    fig.update_layout(separators=".,")
    return fig

# ============================================================
# LIMPIEZA Y PROCESAMIENTO
# ============================================================

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
    if df.empty: return df
    df2 = df.copy()
    if drop_blank:
        df2 = df2.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df2.columns = make_unique_columns(df2.columns)
    df2 = df2.loc[:, ~df2.columns.str.contains('^Unnamed')]
    return df2.reset_index(drop=True)

def intentar_convertir_numericos(df: pd.DataFrame, umbral=0.70) -> pd.DataFrame:
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

# ============================================================
# TIPADO DE COLUMNAS
# ============================================================

def convertir_fecha_robusta(series: pd.Series) -> pd.Series:
    meses_es = {"ene": "01", "feb": "02", "mar": "03", "abr": "04", "may": "05", "jun": "06", "jul": "07", "ago": "08", "sep": "09", "oct": "10", "nov": "11", "dic": "12"}
    result = pd.Series([pd.NaT] * len(series), index=series.index)
    formatos = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y"]
    for idx, val in series.items():
        if pd.isna(val): continue
        val_str = str(val).strip().lower()
        try:
            fecha = pd.to_datetime(val_str, errors="coerce", dayfirst=True)
            if not pd.isna(fecha):
                result[idx] = fecha
                continue
        except: pass
    return result

def aplicar_tipo_columna(df: pd.DataFrame, col: str, tipo: str) -> pd.DataFrame:
    out = df.copy()
    if col not in out.columns: return out
    if tipo == "Texto": out[col] = out[col].astype(str)
    elif tipo == "Numérica" or tipo == "Moneda":
        s = out[col].astype(str).str.strip().str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        out[col] = pd.to_numeric(s, errors="coerce")
    elif tipo == "Fecha": out[col] = convertir_fecha_robusta(out[col])
    return out

def panel_tipado(df: pd.DataFrame):
    st.subheader("Configuración de Tipos de Columnas")
    if "col_types" not in st.session_state: st.session_state["col_types"] = {}
    col_types = st.session_state["col_types"]
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: col = st.selectbox("Columna", df.columns.tolist(), key="type_col_pick")
    with c2: tipo = st.selectbox("Tipo", ["Texto", "Numérica", "Fecha", "Moneda"], key="type_kind_pick")
    with c3:
        st.write("")
        if st.button("Aplicar", key="type_apply_btn"):
            col_types[col] = tipo
            st.success("✓ Tipo guardado")
    df2 = df.copy()
    for c, t in col_types.items():
        if c in df2.columns: df2 = aplicar_tipo_columna(df2, c, t)
    return df2

# ============================================================
# SECCIONES DE ANÁLISIS (ESTADÍSTICA / ILUSTRACIONES / REGRESIÓN)
# ============================================================

def seccion_estadistica_descriptiva(df: pd.DataFrame):
    st.header("Estadística Descriptiva")
    cols = df.columns.tolist()
    sel = st.multiselect("Variables", cols, default=cols[: min(8, len(cols))])
    if not sel: return
    d = df[sel].copy()
    st.dataframe(style_latino(d.describe(include="all")), use_container_width=True)

def render_bar_chart_mejorado(df, cols_num, cols_cat, scale_mode: str):
    cat_col = st.selectbox("Eje X (Categoría)", cols_cat if cols_cat else df.columns.tolist())
    num_cols = st.multiselect("Eje Y (Numéricas)", cols_num, default=[cols_num[0]] if cols_num else [])
    if not num_cols: return
    factor, unit_label = get_scale_factor_and_label(scale_mode, df[num_cols].max().max())
    data = df.groupby(cat_col)[num_cols].mean().reset_index()
    for c in num_cols: data[c] = data[c] / factor
    if PLOTLY_AVAILABLE:
        fig = px.bar(data, x=cat_col, y=num_cols, barmode="group", title=f"Promedio por {cat_col}")
        st.plotly_chart(fig, use_container_width=True)

def seccion_ilustraciones(df: pd.DataFrame, scale_mode: str):
    st.header("Ilustraciones y Visualizaciones")
    tipo = st.selectbox("Tipo de gráfico", ["Gráfico de Barras", "Histograma", "Box Plot"])
    cols_num = columnas_numericas(df)
    cols_cat = columnas_no_numericas(df)
    if tipo == "Gráfico de Barras": render_bar_chart_mejorado(df, cols_num, cols_cat, scale_mode)
    elif tipo == "Histograma":
        col = st.selectbox("Variable", cols_num)
        fig = px.histogram(df, x=col)
        st.plotly_chart(fig, use_container_width=True)
    elif tipo == "Box Plot":
        col = st.selectbox("Variable", cols_num)
        fig = px.box(df, y=col)
        st.plotly_chart(fig, use_container_width=True)

def seccion_regresiones(df: pd.DataFrame, scale_mode: str):
    st.header("Regresiones Lineales")
    if not STATSMODELS_AVAILABLE: return
    cols_num = columnas_numericas(df)
    if len(cols_num) < 2: return
    y_col = st.selectbox("Dependiente (Y)", cols_num)
    x_col = st.selectbox("Independiente (X)", [c for c in cols_num if c != y_col])
    data = df[[x_col, y_col]].dropna()
    X = sm.add_constant(data[x_col])
    model = sm.OLS(data[y_col], X).fit()
    st.text(model.summary())

# ============================================================
# MAIN APPLICATION
# ============================================================

def data_multiple():
    st.title("Sistema Integral de Análisis de Datos")
    st.caption("☁️ Datos servidos desde Neon PostgreSQL")

    tablas = listar_tablas_sql()
    if not tablas:
        st.warning("No hay tablas en la base de datos.")
        st.stop()

    with st.sidebar:
        st.header("Selección de Dataset")
        tabla_sel = st.selectbox("Tabla SQL", tablas, key="table_selector")
        st.header("Opciones de Limpieza")
        auto_numeric = st.toggle("Convertir numéricos automáticamente", value=True)
        scale_mode = st.selectbox("Unidad de gráficos", ["Auto", "Unidades", "Miles", "Millones"], index=0)

    with st.spinner(f"Cargando tabla {tabla_sel}..."):
        df = leer_tabla_sql(tabla_sel)

    if df.empty:
        st.error("La tabla seleccionada no contiene datos.")
        st.stop()

    df = limpiar_df(df)
    if auto_numeric:
        df = intentar_convertir_numericos(df)

    st.info(f"**Tabla:** {tabla_sel} | **Filas:** {len(df):,} | **Columnas:** {df.shape[1]}")
    st.divider()
    
    df_typed = panel_tipado(df)

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

    seccion = st.session_state.get("seccion_activa")
    if seccion == "estadistica": seccion_estadistica_descriptiva(df_typed)
    elif seccion == "ilustraciones": seccion_ilustraciones(df_typed, scale_mode)
    elif seccion == "regresiones": seccion_regresiones(df_typed, scale_mode)

    st.divider()
    st.header("Dataset Completo")
    st.dataframe(style_latino(df_typed), use_container_width=True, height=500)

    st.download_button("⬇️ Descargar Dataset Procesado (CSV)", df_to_csv_bytes(df_typed), file_name=f"{tabla_sel}_procesado.csv", mime="text/csv")

if __name__ == "__main__":
    data_multiple()