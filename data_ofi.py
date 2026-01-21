import os
from io import BytesIO
from datetime import datetime
import re

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# Importaciones opcionales
PLOTLY_AVAILABLE = False
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    pass

# Configuración inicial
DATA_DIR = "archivos_subidos/datos"
os.makedirs(DATA_DIR, exist_ok=True)

st.set_page_config(page_title="Análisis de Datos", layout="wide")

# =========================
# FUNCIONES AUXILIARES
# =========================
def ext_archivo(path: str) -> str:
    return os.path.splitext(path)[1].lower()

def listar_archivos():
    files = []
    for f in os.listdir(DATA_DIR):
        p = os.path.join(DATA_DIR, f)
        if os.path.isfile(p):
            ext = ext_archivo(p)
            if ext in [".csv", ".tsv", ".txt", ".xlsx", ".xls", ".xlsb", ".parquet", ".feather", ".dta"]:
                files.append(f)
    return sorted(files, key=str.lower)

def excel_engine_for_ext(ext: str):
    if ext == ".xlsx":
        return "openpyxl"
    if ext == ".xls":
        return "xlrd"
    if ext == ".xlsb":
        return "pyxlsb"
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
    ext = ext_archivo(path)
    
    if ext == ".csv":
        return pd.read_csv(path)
    if ext == ".tsv":
        return pd.read_csv(path, sep="\t")
    if ext == ".txt":
        return pd.read_csv(path, sep=None, engine="python")
    if ext in [".xlsx", ".xls", ".xlsb"]:
        engine = excel_engine_for_ext(ext)
        if sheet_name is None:
            sheet_name = 0
        if engine:
            return pd.read_excel(path, sheet_name=sheet_name, engine=engine)
        return pd.read_excel(path, sheet_name=sheet_name)
    if ext == ".parquet":
        return pd.read_parquet(path)
    if ext == ".feather":
        return pd.read_feather(path)
    if ext == ".dta":
        return pd.read_stata(path)
    
    raise ValueError(f"Formato no soportado: {ext}")

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

# =========================
# CONVERSIÓN ROBUSTA DE FECHAS
# =========================
def convertir_fecha_robusta(series: pd.Series) -> pd.Series:
    """
    Convierte una serie a fechas probando múltiples formatos comunes.
    Soporta: 11-ene, 11-01-02, 11-01-2002, 2002-01-11, etc.
    """
    # Diccionario de meses en español
    meses_es = {
        'ene': '01', 'enero': '01',
        'feb': '02', 'febrero': '02',
        'mar': '03', 'marzo': '03',
        'abr': '04', 'abril': '04',
        'may': '05', 'mayo': '05',
        'jun': '06', 'junio': '06',
        'jul': '07', 'julio': '07',
        'ago': '08', 'agosto': '08',
        'sep': '09', 'septiembre': '09', 'sept': '09',
        'oct': '10', 'octubre': '10',
        'nov': '11', 'noviembre': '11',
        'dic': '12', 'diciembre': '12'
    }
    
    result = pd.Series([pd.NaT] * len(series), index=series.index)
    
    for idx, val in series.items():
        if pd.isna(val):
            continue
            
        val_str = str(val).strip().lower()
        
        # Reemplazar meses en español por números
        for mes_nombre, mes_num in meses_es.items():
            val_str = re.sub(rf'\b{mes_nombre}\b', mes_num, val_str)
        
        # Intentar múltiples formatos
        formatos = [
            '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y',  # 11-01-2002
            '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',  # 2002-01-11
            '%d-%m-%y', '%d/%m/%y', '%d.%m.%y',  # 11-01-02
            '%m-%d-%Y', '%m/%d/%Y',              # 01-11-2002 (formato US)
            '%d %m %Y', '%d %m %y',              # 11 01 2002
            '%Y%m%d',                            # 20020111
        ]
        
        fecha_convertida = None
        
        # Primero intentar pd.to_datetime (muy flexible)
        try:
            fecha_convertida = pd.to_datetime(val_str, errors='coerce', dayfirst=True)
            if not pd.isna(fecha_convertida):
                result[idx] = fecha_convertida
                continue
        except:
            pass
        
        # Luego intentar formatos específicos
        for fmt in formatos:
            try:
                fecha_convertida = datetime.strptime(val_str, fmt)
                result[idx] = fecha_convertida
                break
            except:
                continue
    
    return result

# =========================
# TIPADO DE COLUMNAS MEJORADO
# =========================
def aplicar_tipo_columna(df: pd.DataFrame, col: str, tipo: str) -> pd.DataFrame:
    out = df.copy()
    if col not in out.columns:
        return out
    
    if tipo == "Texto":
        out[col] = out[col].astype(str)
    
    elif tipo == "Numérica":
        s = out[col].astype(str).str.strip()
        # Eliminar espacios y caracteres especiales
        s = s.str.replace("\u00a0", "", regex=False).str.replace(" ", "", regex=False)
        # Formato latino: 1.234.567,89 -> 1234567.89
        s_lat = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        out[col] = pd.to_numeric(s_lat, errors="coerce")
    
    elif tipo == "Fecha":
        out[col] = convertir_fecha_robusta(out[col])
    
    elif tipo == "Moneda":
        s = out[col].astype(str).str.strip()
        # Eliminar símbolos de moneda
        s = s.str.replace("$", "", regex=False).str.replace("€", "", regex=False)
        s = s.str.replace("£", "", regex=False).str.replace("¥", "", regex=False)
        s = s.str.replace("\u00a0", "", regex=False).str.replace(" ", "", regex=False)
        # Formato latino
        s_lat = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        out[col] = pd.to_numeric(s_lat, errors="coerce")
    
    return out

def panel_tipado(df: pd.DataFrame):
    st.subheader("🧾 Configuración de Tipos de Columnas")
    
    with st.expander("❓ Ayuda", expanded=False):
        st.markdown("""
        **Instrucciones:**
        1. Selecciona una columna
        2. Elige el tipo apropiado
        3. Haz clic en 'Aplicar'
        
        **Tipos soportados:**
        - **Texto**: Convierte todo a cadenas de texto
        - **Numérica**: Detecta números con separadores latinos (1.234,56) o anglosajones (1,234.56)
        - **Fecha**: Detecta múltiples formatos (11-ene, 11-01-2002, 2002-01-11, etc.)
        - **Moneda**: Similar a numérica pero elimina símbolos ($, €, £, ¥)
        
        **Tip:** Si un gráfico no muestra correctamente una variable, ajusta su tipo aquí.
        """)
    
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
        if st.button("✅ Aplicar", key="type_apply_btn"):
            col_types[col] = tipo
            st.success(f"✓ Tipo guardado: {col} → {tipo}")
    
    df2 = df.copy()
    for c, t in col_types.items():
        if c in df2.columns:
            df2 = aplicar_tipo_columna(df2, c, t)
    
    with st.expander("Ver tipos definidos", expanded=False):
        if col_types:
            resumen = pd.DataFrame(
                [{"Columna": k, "Tipo": v} for k, v in col_types.items()]
            ).sort_values("Columna")
            st.dataframe(resumen, use_container_width=True, height=200)
            if st.button("🧽 Limpiar todos los tipos", key="type_reset_btn"):
                st.session_state["col_types"] = {}
                st.rerun()
        else:
            st.info("Aún no has definido tipos manualmente.")
    
    return df2

# =========================
# ESTADÍSTICA DESCRIPTIVA
# =========================
def seccion_estadistica_descriptiva(df: pd.DataFrame):
    st.header("📊 Estadística Descriptiva")
    
    cols = df.columns.tolist()
    if not cols:
        st.info("El dataset no tiene columnas.")
        return
    
    c1, c2 = st.columns([3, 1])
    with c1:
        sel = st.multiselect(
            "Variables a incluir en el análisis",
            cols,
            default=cols[:min(12, len(cols))],
            help="Puedes mezclar variables numéricas y categóricas."
        )
    with c2:
        include_all = st.toggle("Incluir variables categóricas", value=True)
    
    if not sel:
        st.warning("⚠️ Selecciona al menos una variable.")
        return
    
    d = df[sel].copy()
    desc = d.describe(include=("all" if include_all else None))
    
    na = d.isna().sum().sort_values(ascending=False).to_frame("Cantidad NA")
    na["% NA"] = (na["Cantidad NA"] / len(d) * 100).round(2) if len(d) else 0.0
    
    st.subheader("Resumen Estadístico")
    st.dataframe(desc, use_container_width=True, height=360)
    
    st.subheader("Análisis de Valores Faltantes")
    st.dataframe(na, use_container_width=True, height=320)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ Descargar Estadísticas (CSV)",
            df_to_csv_bytes(desc.reset_index().rename(columns={"index": "estadística"})),
            file_name="estadisticas_descriptivas.csv",
            mime="text/csv",
        )
    with col2:
        st.download_button(
            "⬇️ Descargar Faltantes (CSV)",
            df_to_csv_bytes(na.reset_index().rename(columns={"index": "variable"})),
            file_name="valores_faltantes.csv",
            mime="text/csv",
        )

# =========================
# ILUSTRACIONES MEJORADAS
# =========================
def seccion_ilustraciones(df: pd.DataFrame):
    st.header("🎨 Ilustraciones y Visualizaciones")
    
    if not PLOTLY_AVAILABLE:
        st.warning("⚠️ Plotly no está instalado. Instala con: pip install plotly")
        st.info("Usando Matplotlib como alternativa...")
    
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
        render_bar_chart_mejorado(df, cols_num, cols_cat)
    elif tipo_grafico == "Gráfico de Líneas":
        render_line_chart_mejorado(df, cols_num, cols_cat)
    elif tipo_grafico == "Gráfico de Pastel (Pie)":
        render_pie_chart_mejorado(df, cols_cat)
    elif tipo_grafico == "Gráfico de Dispersión":
        render_scatter_chart_plotly(df, cols_num)
    elif tipo_grafico == "Gráfico de Dispersión (Múltiples Variables)":
        render_scatter_multiple(df, cols_num)
    elif tipo_grafico == "Gráfico de Área":
        render_area_chart_mejorado(df, cols_num, cols_cat)
    elif tipo_grafico == "Histograma":
        render_histogram_plotly(df, cols_num)
    elif tipo_grafico == "Box Plot":
        render_boxplot_plotly(df, cols_num, cols_cat)

def render_bar_chart_mejorado(df, cols_num, cols_cat):
    if not cols_cat and not cols_num:
        st.warning("No hay columnas disponibles para graficar.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        cat_col = st.selectbox("Variable Categórica (Eje X)", cols_cat if cols_cat else df.columns.tolist())
    with col2:
        num_cols = st.multiselect(
            "Variables Numéricas (Eje Y) - puedes seleccionar varias",
            cols_num if cols_num else df.columns.tolist(),
            default=[cols_num[0]] if cols_num else []
        )
    
    if not num_cols:
        st.info("Selecciona al menos una variable numérica.")
        return
    
    # Filtro de categorías mejorado
    st.subheader("🔍 Filtro de Categorías")
    
    categorias_unicas = sorted(df[cat_col].dropna().unique().tolist())
    
    col_a, col_b = st.columns(2)
    with col_a:
        min_range = st.number_input("Desde categoría #", 1, len(categorias_unicas), 1, key="bar_min")
    with col_b:
        max_range = st.number_input("Hasta categoría #", min_range, len(categorias_unicas), 
                                    min(min_range + 9, len(categorias_unicas)), key="bar_max")
    
    categorias_seleccionadas = st.multiselect(
        "O selecciona categorías específicas",
        categorias_unicas,
        default=categorias_unicas[min_range-1:max_range],
        key="bar_cat_select"
    )
    
    if not categorias_seleccionadas:
        st.warning("Selecciona al menos una categoría.")
        return
    
    # Filtrar y respetar orden original
    data = df[df[cat_col].isin(categorias_seleccionadas)][[cat_col] + num_cols].dropna()
    
    # Mantener orden original del dataframe
    cat_order = data[cat_col].drop_duplicates().tolist()
    
    if PLOTLY_AVAILABLE:
        fig = go.Figure()
        for num_col in num_cols:
            grouped = data.groupby(cat_col, sort=False)[num_col].mean()
            grouped = grouped.reindex(cat_order)
            fig.add_trace(go.Bar(x=grouped.index, y=grouped.values, name=num_col))
        
        fig.update_layout(
            title=f"Comparación de {', '.join(num_cols)} por {cat_col}",
            xaxis_title=cat_col,
            yaxis_title="Valores",
            barmode='group',
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig, ax = plt.subplots(figsize=(12, 6))
        x = np.arange(len(cat_order))
        width = 0.8 / len(num_cols)
        
        for i, num_col in enumerate(num_cols):
            grouped = data.groupby(cat_col, sort=False)[num_col].mean()
            grouped = grouped.reindex(cat_order)
            ax.bar(x + i * width, grouped.values, width, label=num_col)
        
        ax.set_xlabel(cat_col)
        ax.set_ylabel("Valores")
        ax.set_title(f"Comparación por {cat_col}")
        ax.set_xticks(x + width * (len(num_cols) - 1) / 2)
        ax.set_xticklabels(cat_order, rotation=45, ha='right')
        ax.legend()
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)

def render_line_chart_mejorado(df, cols_num, cols_cat):
    if not cols_num:
        st.warning("No hay columnas numéricas disponibles.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        x_col = st.selectbox("Eje X", df.columns.tolist())
    with col2:
        y_cols = st.multiselect("Eje Y (puedes seleccionar múltiples)", cols_num, 
                                default=cols_num[:min(5, len(cols_num))])
    
    if not y_cols:
        st.info("Selecciona al menos una variable para el eje Y.")
        return
    
    data = df[[x_col] + y_cols].dropna()
    
    # Respetar orden original - NO ordenar
    if not (pd.api.types.is_numeric_dtype(data[x_col]) or pd.api.types.is_datetime64_any_dtype(data[x_col])):
        # Mantener orden de aparición
        data = data.groupby(x_col, sort=False)[y_cols].mean().reset_index()
    
    if PLOTLY_AVAILABLE:
        fig = px.line(data, x=x_col, y=y_cols, title=f"Tendencia de {', '.join(y_cols)}",
                     markers=True)
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig, ax = plt.subplots(figsize=(12, 6))
        for y_col in y_cols:
            ax.plot(data[x_col], data[y_col], marker='o', label=y_col, linewidth=2)
        ax.set_xlabel(x_col, fontsize=12)
        ax.set_ylabel("Valores", fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=30, ha='right')
        plt.tight_layout()
        st.pyplot(fig)

def render_pie_chart_mejorado(df, cols_cat):
    if not cols_cat:
        st.warning("No hay columnas categóricas disponibles.")
        return
    
    cat_col = st.selectbox("Variable Categórica", cols_cat)
    
    st.subheader("🔍 Filtro de Categorías")
    
    categorias_unicas = sorted(df[cat_col].dropna().unique().tolist())
    
    col_a, col_b = st.columns(2)
    with col_a:
        min_range = st.number_input("Desde categoría #", 1, len(categorias_unicas), 1, key="pie_min")
    with col_b:
        max_range = st.number_input("Hasta categoría #", min_range, len(categorias_unicas), 
                                    min(min_range + 9, len(categorias_unicas)), key="pie_max")
    
    categorias_seleccionadas = st.multiselect(
        "O selecciona categorías específicas",
        categorias_unicas,
        default=categorias_unicas[min_range-1:max_range],
        key="pie_cat_select"
    )
    
    if not categorias_seleccionadas:
        st.warning("Selecciona al menos una categoría.")
        return
    
    vc = df[df[cat_col].isin(categorias_seleccionadas)][cat_col].value_counts()
    
    if PLOTLY_AVAILABLE:
        fig = px.pie(values=vc.values, names=vc.index, title=f"Distribución de {cat_col}")
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.pie(vc.values, labels=vc.index, autopct='%1.1f%%', startangle=90)
        ax.set_title(f"Distribución de {cat_col}", fontsize=14)
        st.pyplot(fig)

def render_scatter_multiple(df, cols_num):
    """Gráfico de dispersión con múltiples variables Y"""
    if len(cols_num) < 2:
        st.warning("Se necesitan al menos 2 columnas numéricas.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        x_col = st.selectbox("Eje X", cols_num, key="scatter_multi_x")
    with col2:
        y_cols = st.multiselect("Ejes Y (múltiples)", 
                                [c for c in cols_num if c != x_col],
                                default=[c for c in cols_num if c != x_col][:min(3, len(cols_num)-1)],
                                key="scatter_multi_y")
    
    if not y_cols:
        st.info("Selecciona al menos una variable para el eje Y.")
        return
    
    data = df[[x_col] + y_cols].dropna()
    
    if PLOTLY_AVAILABLE:
        fig = go.Figure()
        for y_col in y_cols:
            fig.add_trace(go.Scatter(
                x=data[x_col], 
                y=data[y_col], 
                mode='markers',
                name=y_col,
                marker=dict(size=8, opacity=0.6)
            ))
        
        fig.update_layout(
            title=f"Dispersión: {', '.join(y_cols)} vs {x_col}",
            xaxis_title=x_col,
            yaxis_title="Valores",
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig, ax = plt.subplots(figsize=(12, 6))
        for y_col in y_cols:
            ax.scatter(data[x_col], data[y_col], label=y_col, alpha=0.6, s=50)
        ax.set_xlabel(x_col, fontsize=12)
        ax.set_ylabel("Valores", fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig)

def render_scatter_chart_plotly(df, cols_num):
    if len(cols_num) < 2:
        st.warning("Se necesitan al menos 2 columnas numéricas.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        x_col = st.selectbox("Eje X", cols_num)
    with col2:
        y_col = st.selectbox("Eje Y", [c for c in cols_num if c != x_col])
    
    data = df[[x_col, y_col]].dropna()
    
    if PLOTLY_AVAILABLE:
        fig = px.scatter(data, x=x_col, y=y_col, title=f"{y_col} vs {x_col}")
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(data[x_col], data[y_col], alpha=0.6, s=50)
        ax.set_xlabel(x_col, fontsize=12)
        ax.set_ylabel(y_col, fontsize=12)
        ax.set_title(f"{y_col} vs {x_col}")
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)

def render_area_chart_mejorado(df, cols_num, cols_cat):
    if not cols_num:
        st.warning("No hay columnas numéricas disponibles.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        x_col = st.selectbox("Eje X", df.columns.tolist())
    with col2:
        y_cols = st.multiselect("Eje Y (múltiples)", cols_num, 
                                default=cols_num[:min(3, len(cols_num))])
    
    if not y_cols:
        st.info("Selecciona al menos una variable para el eje Y.")
        return
    
    data = df[[x_col] + y_cols].dropna()
    
    # Respetar orden original
    if not (pd.api.types.is_numeric_dtype(data[x_col]) or pd.api.types.is_datetime64_any_dtype(data[x_col])):
        data = data.groupby(x_col, sort=False)[y_cols].mean().reset_index()
    
    if PLOTLY_AVAILABLE:
        fig = px.area(data, x=x_col, y=y_cols, title=f"Área: {', '.join(y_cols)}")
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig, ax = plt.subplots(figsize=(12, 6))
        for y_col in y_cols:
            ax.fill_between(range(len(data)), data[y_col], alpha=0.5, label=y_col)
        ax.set_xlabel(x_col, fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig)

def render_histogram_plotly(df, cols_num):
    if not cols_num:
        st.warning("No hay columnas numéricas disponibles.")
        return
    
    col = st.selectbox("Variable Numérica", cols_num)
    bins = st.slider("Número de bins", 10, 100, 30)
    
    data = df[col].dropna()
    
    if PLOTLY_AVAILABLE:
        fig = px.histogram(data, nbins=bins, title=f"Histograma de {col}")
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(data, bins=bins, edgecolor='black')
        ax.set_xlabel(col, fontsize=12)
        ax.set_ylabel("Frecuencia", fontsize=12)
        ax.set_title(f"Histograma de {col}")
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)

def render_boxplot_plotly(df, cols_num, cols_cat):
    if not cols_num:
        st.warning("No hay columnas numéricas disponibles.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        y_col = st.selectbox("Variable Numérica", cols_num)
    with col2:
        if cols_cat:
            x_col = st.selectbox("Agrupar por (opcional)", ["Ninguno"] + cols_cat)
        else:
            x_col = "Ninguno"
    
    if x_col == "Ninguno":
        data = df[[y_col]].dropna()
        if PLOTLY_AVAILABLE:
            fig = px.box(data, y=y_col, title=f"Box Plot de {y_col}")
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
        else:
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.boxplot(data[y_col].values)
            ax.set_ylabel(y_col, fontsize=12)
            ax.set_title(f"Box Plot de {y_col}")
            st.pyplot(fig)
    else:
        data = df[[x_col, y_col]].dropna()
        if PLOTLY_AVAILABLE:
            fig = px.box(data, x=x_col, y=y_col, title=f"Box Plot de {y_col} por {x_col}")
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
        else:
            fig, ax = plt.subplots(figsize=(10, 6))
            data.boxplot(column=y_col, by=x_col, ax=ax)
            plt.suptitle("")
            ax.set_title(f"Box Plot de {y_col} por {x_col}")
            plt.xticks(rotation=45, ha='right')
            st.pyplot(fig)

# =========================
# PROYECCIONES Y ECONOMETRÍA CON TEORÍA
# =========================
def seccion_proyecciones(df: pd.DataFrame):
    st.header("📈 Proyecciones y Econometría")
    
    cols_num = columnas_numericas(df)
    
    if len(cols_num) < 2:
        st.warning("Se necesitan al menos 2 columnas numéricas para realizar regresiones.")
        return
    
    # Explicación teórica
    with st.expander("📚 Teoría: Tipos de Regresión", expanded=False):
        st.markdown("""
        ### 🔵 Regresión Lineal
        
        **¿Qué es?** Ajusta una línea recta que mejor representa la relación entre X e Y.
        
        **Ecuación:** `Y = β₀ + β₁X + ε`
        - `β₀`: Intercepto (valor de Y cuando X=0)
        - `β₁`: Pendiente (cambio en Y por cada unidad de cambio en X)
        - `ε`: Error residual
        
        **Cuándo usarla:** Cuando la relación entre variables es aproximadamente lineal.
        
        **Ejemplo:** Predecir ventas basándose en inversión en publicidad.
        
        ---
        
        ### 🟢 Regresión LOESS (Locally Weighted Scatterplot Smoothing)
        
        **¿Qué es?** Ajusta múltiples regresiones locales, creando una curva suave que se adapta a patrones no lineales.
        
        **Cómo funciona:** 
        1. Para cada punto, considera solo los puntos cercanos
        2. Ajusta una regresión local ponderada
        3. Une todos los ajustes locales
        
        **Cuándo usarla:** Cuando la relación no es lineal y quieres capturar patrones complejos.
        
        **Ventajas:** Muy flexible, no asume forma específica de la relación.
        
        **Desventajas:** Más lenta computacionalmente, puede sobreajustar.
        
        ---
        
        ### 🟣 Regresión Polinomial
        
        **¿Qué es?** Ajusta una curva polinomial de grado n.
        
        **Ecuaciones:**
        - Grado 2: `Y = β₀ + β₁X + β₂X² + ε`
        - Grado 3: `Y = β₀ + β₁X + β₂X² + β₃X³ + ε`
        
        **Cuándo usarla:** Cuando la relación tiene curvaturas específicas (parabólicas, cúbicas).
        
        **Grados comunes:**
        - Grado 2: Curva en forma de U o ∩
        - Grado 3: Curva con punto de inflexión
        - Grados mayores: Curvas más complejas (cuidado con el sobreajuste)
        
        **Ejemplo:** Relación entre edad y salario (puede aumentar y luego estabilizarse).
        """)
    
    st.subheader("Configuración del Modelo")
    
    col1, col2 = st.columns(2)
    with col1:
        x_col = st.selectbox("Variable Predictora (X)", cols_num, key="pred_x")
    with col2:
        y_col = st.selectbox("Variable Objetivo (Y)", [c for c in cols_num if c != x_col], key="pred_y")
    
    col3, col4 = st.columns(2)
    with col3:
        tipo_regresion = st.selectbox(
            "Tipo de Regresión",
            ["Regresión Lineal", "Regresión LOESS", "Regresión Polinomial"]
        )
    with col4:
        sigma_val = st.slider(
            "Intervalo de Confianza (sigma)",
            min_value=0.5,
            max_value=4.0,
            value=2.0,
            step=0.1,
            help="""
            **¿Qué es el intervalo de confianza (sigma)?**
            
            El intervalo de confianza se basa en la desviación estándar (σ) de los residuos.
            
            **Cálculo:**
            1. Se calculan los residuos: `residuo = Y_real - Y_predicho`
            2. Se calcula la desviación estándar de los residuos: `σ`
            3. Los límites se calculan:
               - Límite superior: `Y_predicho + (sigma × σ)`
               - Límite inferior: `Y_predicho - (sigma × σ)`
            
            **Interpretación de valores:**
            - **1σ**: ~68% de los datos dentro del intervalo (rango normal)
            - **2σ**: ~95% de los datos dentro del intervalo (recomendado)
            - **3σ**: ~99.7% de los datos dentro del intervalo (muy estricto)
            
            **Outliers:** Puntos fuera del intervalo se consideran atípicos.
            
            **Ejemplo:** Si σ=2 y tienes 100 observaciones, esperarías ~5 outliers.
            """
        )
    
    if tipo_regresion == "Regresión Polinomial":
        grado = st.slider("Grado del Polinomio", 2, 5, 2,
                         help="Grado 2: parábola, Grado 3: curva con inflexión, Mayor grado: más complejo")
    else:
        grado = 1
    
    # Limpiar datos
    data_clean = df[[x_col, y_col]].dropna()
    
    if len(data_clean) < 10:
        st.warning("Se necesitan al menos 10 observaciones válidas.")
        return
    
    x = data_clean[x_col].values
    y = data_clean[y_col].values
    
    # Realizar regresión
    if tipo_regresion == "Regresión Lineal":
        coeffs = np.polyfit(x, y, 1)
        poly = np.poly1d(coeffs)
        predictions = poly(x)
        
        st.info(f"**Ecuación:** Y = {coeffs[0]:.4f}·X + {coeffs[1]:.4f}")
        
    elif tipo_regresion == "Regresión Polinomial":
        coeffs = np.polyfit(x, y, grado)
        poly = np.poly1d(coeffs)
        predictions = poly(x)
        
        ecuacion = " + ".join([f"{coeffs[i]:.4f}·X^{grado-i}" for i in range(len(coeffs))])
        st.info(f"**Ecuación:** Y = {ecuacion}")
        
    else:  # LOESS
        try:
            import statsmodels.api as sm
            lowess = sm.nonparametric.lowess
            result = lowess(y, x, frac=0.66)
            sorted_indices = np.argsort(x)
            x = x[sorted_indices]
            y = y[sorted_indices]
            predictions = result[:, 1][sorted_indices]
            
            st.info("**LOESS:** Ajuste local ponderado (no tiene ecuación explícita)")
        except ImportError:
            st.error("Para usar LOESS, instala: pip install statsmodels")
            return
    
    # Calcular intervalos
    residuals = y - predictions
    std_dev = np.std(residuals)
    upper_bound = predictions + (sigma_val * std_dev)
    lower_bound = predictions - (sigma_val * std_dev)
    
    # Identificar outliers
    outliers_mask = (y > upper_bound) | (y < lower_bound)
    
    # Visualización
    st.subheader(f"Resultados: {y_col} vs {x_col}")
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Puntos normales
    ax.scatter(x[~outliers_mask], y[~outliers_mask], alpha=0.5, label="Datos normales", s=50, color='steelblue')
    
    # Outliers
    ax.scatter(x[outliers_mask], y[outliers_mask], alpha=0.7, label="Outliers", 
               marker='x', s=100, color='red', linewidths=2)
    
    # Línea de regresión
    sorted_indices = np.argsort(x)
    ax.plot(x[sorted_indices], predictions[sorted_indices], 'b-', linewidth=2, label="Predicción")
    
    # Intervalo de confianza
    ax.fill_between(x[sorted_indices], lower_bound[sorted_indices], upper_bound[sorted_indices], 
                     alpha=0.2, color='blue', label=f"IC {sigma_val}σ")
    
    ax.set_xlabel(x_col, fontsize=12)
    ax.set_ylabel(y_col, fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    st.pyplot(fig)
    
    # Métricas
    col1, col2, col3 = st.columns(3)
    
    with col1:
        r_squared = 1 - (np.sum(residuals**2) / np.sum((y - np.mean(y))**2))
        st.metric("R² (Coeficiente de Determinación)", f"{r_squared:.4f}",
                 help="R² cercano a 1 indica buen ajuste. R² cercano a 0 indica mal ajuste.")
    
    with col2:
        num_outliers = np.sum(outliers_mask)
        pct_outliers = (num_outliers / len(y)) * 100
        st.metric("Número de Outliers", f"{num_outliers} ({pct_outliers:.1f}%)")
    
    with col3:
        rmse = np.sqrt(np.mean(residuals**2))
        st.metric("RMSE (Error Cuadrático Medio)", f"{rmse:.4f}",
                 help="RMSE más bajo indica mejor ajuste. Mismas unidades que Y.")
    
    # Tabla de outliers
    if num_outliers > 0:
        st.subheader("Outliers Detectados")
        outliers_df = data_clean[outliers_mask].copy()
        outliers_df["Predicción"] = predictions[outliers_mask]
        outliers_df["Residuo"] = residuals[outliers_mask]
        outliers_df["Desviaciones σ"] = (residuals[outliers_mask] / std_dev).round(2)
        st.dataframe(outliers_df, use_container_width=True, height=300)
        
        st.download_button(
            "⬇️ Descargar Outliers (CSV)",
            df_to_csv_bytes(outliers_df),
            file_name="outliers.csv",
            mime="text/csv",
        )
    
    # Regresión OLS completa
    st.divider()
    st.subheader("Análisis de Regresión Completo (OLS)")
    
    with st.expander("🔧 Configuración Avanzada de OLS", expanded=False):
        st.markdown("""
        **Regresión de Mínimos Cuadrados Ordinarios (OLS)**
        
        Estima la relación entre una variable dependiente Y y múltiples variables independientes X.
        
        **Errores Robustos (HC1):** Corrigen la heterocedasticidad (varianza no constante de los errores).
        """)
        
        y_ols = st.selectbox("Variable Dependiente (Y)", cols_num, key="ols_y_adv")
        x_candidates = [c for c in cols_num if c != y_ols]
        xs_ols = st.multiselect(
            "Variables Independientes (X)", 
            x_candidates, 
            default=x_candidates[:min(3, len(x_candidates))],
            key="ols_xs_adv"
        )
        robust = st.toggle("Errores Estándar Robustos (HC1)", value=True, key="ols_robust")
    
    if xs_ols:
        try:
            import statsmodels.api as sm
            
            ols_data = df[[y_ols] + xs_ols].dropna()
            
            if len(ols_data) < 10:
                st.warning("Se necesitan al menos 10 observaciones para OLS.")
            else:
                Y = ols_data[y_ols]
                X = sm.add_constant(ols_data[xs_ols])
                
                model_ols = sm.OLS(Y, X).fit()
                
                if robust:
                    model_ols = model_ols.get_robustcov_results(cov_type="HC1")
                
                summary_text = model_ols.summary().as_text()
                
                st.text(summary_text)
                
                # Interpretación simplificada
                with st.expander("📊 Interpretación de Resultados", expanded=False):
                    st.markdown(f"""
                    ### Interpretación del Modelo OLS
                    
                    **R-squared: {model_ols.rsquared:.4f}**
                    - {model_ols.rsquared*100:.1f}% de la variabilidad en {y_ols} es explicada por las variables X.
                    
                    **Coeficientes:**
                    """)
                    
                    for i, var in enumerate(X.columns):
                        coef = model_ols.params[i]
                        pval = model_ols.pvalues[i]
                        sig = "✓ Significativo" if pval < 0.05 else "✗ No significativo"
                        
                        st.markdown(f"""
                        - **{var}**: {coef:.4f} (p-value: {pval:.4f}) {sig}
                          - Por cada unidad de aumento en {var}, {y_ols} cambia en {coef:.4f} unidades.
                        """)
                
                st.download_button(
                    "⬇️ Descargar Resumen OLS (TXT)",
                    summary_text.encode("utf-8"),
                    file_name="resumen_ols.txt",
                    mime="text/plain"
                )
        except ImportError:
            st.error("Para usar OLS avanzado, instala: pip install statsmodels")
        except Exception as e:
            st.error(f"Error al ajustar el modelo: {e}")

# =========================
# MAIN APPLICATION
# =========================
def data_analysis():
    st.title("🎯 Sistema Integral de Análisis de Datos")
    st.caption("Análisis completo: Estadística · Visualizaciones · Proyecciones")
    
    # Sidebar
    st.sidebar.header("📁 Selección de Dataset")
    
    files = listar_archivos()
    if not files:
        st.warning(f"⚠️ No hay archivos en: {DATA_DIR}")
        st.info("Por favor, carga archivos en la carpeta 'Cargar Documentos'")
        st.stop()
    
    archivo = st.sidebar.selectbox("Archivo", files, key="file_selector")
    path = os.path.join(DATA_DIR, archivo)
    ext = ext_archivo(path)
    
    # Selección de hoja para Excel
    sheet = None
    if ext in [".xlsx", ".xls", ".xlsb"]:
        sheets = obtener_sheets_excel(path)
        if not sheets:
            st.sidebar.error("No se pudieron listar las hojas de Excel.")
            st.stop()
        sheet = st.sidebar.selectbox("Hoja de Excel", sheets, key="sheet_selector")
    
    # Opciones de limpieza
    st.sidebar.header("🧹 Opciones de Limpieza")
    drop_blank = st.sidebar.toggle("Eliminar filas/columnas en blanco", value=True)
    auto_numeric = st.sidebar.toggle("Convertir numéricos automáticamente", value=True)
    
    if auto_numeric:
        umbral = st.sidebar.slider("Umbral de conversión", 0.40, 0.95, 0.70, 0.05)
    else:
        umbral = 0.70
    
    # Cargar datos
    with st.spinner("📥 Cargando dataset..."):
        try:
            df = leer_archivo(path, sheet_name=sheet)
        except Exception as e:
            st.error(f"❌ Error al leer el archivo: {e}")
            st.info("💡 Tip: Asegúrate de tener instaladas las librerías necesarias.")
            st.stop()
    
    # Limpieza
    df = limpiar_df(df, drop_blank=drop_blank)
    if auto_numeric and not df.empty:
        df = intentar_convertir_numericos(df, umbral=umbral)
    
    # Información del dataset
    st.info(
        f"📊 **Dataset:** {archivo}"
        + (f" | **Hoja:** {sheet}" if sheet else "")
        + f" | **Filas:** {len(df):,} | **Columnas:** {df.shape[1]}"
    )
    
    # Panel de configuración de tipos
    st.divider()
    df_typed = panel_tipado(df)
    
    # Vista previa
    with st.expander("👀 Vista Previa del Dataset", expanded=False):
        st.dataframe(df_typed.head(100), use_container_width=True, height=400)
    
    st.divider()
    
    # Botones de secciones
    st.subheader("🎯 Selecciona una Sección de Análisis")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Estadística Descriptiva", use_container_width=True, type="primary"):
            st.session_state["seccion_activa"] = "estadistica"
    
    with col2:
        if st.button("🎨 Ilustraciones", use_container_width=True, type="primary"):
            st.session_state["seccion_activa"] = "ilustraciones"
    
    with col3:
        if st.button("📈 Proyecciones y Econometría", use_container_width=True, type="primary"):
            st.session_state["seccion_activa"] = "proyecciones"
    
    if "seccion_activa" not in st.session_state:
        st.session_state["seccion_activa"] = None
    
    st.divider()
    
    # Renderizar sección activa
    if st.session_state["seccion_activa"] == "estadistica":
        seccion_estadistica_descriptiva(df_typed)
    elif st.session_state["seccion_activa"] == "ilustraciones":
        seccion_ilustraciones(df_typed)
    elif st.session_state["seccion_activa"] == "proyecciones":
        seccion_proyecciones(df_typed)
    else:
        st.info("👆 Selecciona una sección de análisis usando los botones superiores.")
    
    # Vista completa del dataset
    st.divider()
    st.header("📋 Dataset Completo")
    st.dataframe(df_typed, use_container_width=True, height=500)
    
    # Botón de descarga
    st.download_button(
        "⬇️ Descargar Dataset Procesado (CSV)",
        df_to_csv_bytes(df_typed),
        file_name=f"{archivo.split('.')[0]}_procesado.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    data_analysis()