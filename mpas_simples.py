# mpas_simples.py
from __future__ import annotations

from pathlib import Path
import json
import re

import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


# ============================================================
# RUTAS (AUTO: LOCAL + STREAMLIT CLOUD)
# - Capas: mapas/capas/capas_generales/...
# - Datos descriptivos: mapas/datos_descriptivos_chile/socioeconomicos/descriptivos/...
# ============================================================

def _find_repo_root(start: Path) -> Path:
    start = start.resolve()
    for p in [start] + list(start.parents):
        if (p / "mapas").exists():
            return p
    return start

REPO_ROOT = _find_repo_root(Path(__file__).resolve().parent)
BASE_DIR = REPO_ROOT / "mapas"

# --- Capas (según tu GitHub) ---
SHP_COMUNAS = BASE_DIR / "capas" / "capas_generales" / "comunas" / "comunas.shp"
SHP_PROVINCIAS = BASE_DIR / "capas" / "capas_generales" / "provincias" / "Provincias.shp"
SHP_REGIONES = BASE_DIR / "capas" / "capas_generales" / "regiones" / "Regional.shp"

SHP_RED_HIDRO = BASE_DIR / "capas" / "capas_generales" / "red_hidrografica" / "Red_Hidrografica.shp"
SHP_RED_FERRO = BASE_DIR / "capas" / "capas_generales" / "red_ferroviaria" / "Red_ferroviaria.shp"
SHP_MASA_HIDRICA = BASE_DIR / "capas" / "capas_generales" / "masa_hidrica" / "masas_lacustres.shp"

# --- Descriptivos (según tu GitHub) ---
DESCRIPTIVOS_DIR = BASE_DIR / "datos_descriptivos_chile" / "socioeconomicos" / "descriptivos"

XLSX_DEMO = DESCRIPTIVOS_DIR / "Indicadores_Demograficos_Anual_2024.xlsx"
SHEET_DEMO = "Hoja1"

XLSX_IA = DESCRIPTIVOS_DIR / "Estimacion_Inseguridad_Alimentaria_Comunal_2022.xlsx"
SHEET_IA = "IA Mod-Sev 2022"

XLSX_EDU = DESCRIPTIVOS_DIR / "Indicadores_Educacion_Anual_2024.xlsx"
SHEET_EDU = "Hoja1"

# ✅ Migración eliminada (ya no existe ese indicador)
# XLSX_MIG = ...
# SHEET_MIG = ...

# Pobreza (si existe en tu repo). Si no existe, se ignora.
RUTA_POBREZA = BASE_DIR / "pobreza.xlsx"
POB_SKIPROWS = range(0, 2)

CHILE_BOUNDS = [[-56.0, -76.0], [-17.0, -66.0]]


# ============================================================
# FUNCIONES: LIMPIAR/FORMATEAR SOLO PARA VISTA (NO CAMBIA TIPOS)
# ============================================================

def clean_number_view(x):
    """
    Intenta convertir x a número SOLO para uso temporal (colores/tooltip).
    - NO modifica el DataFrame.
    - Si no puede interpretar, devuelve None.
    Acepta: int/float/str.
    """
    if x is None:
        return None

    # NaN
    try:
        if isinstance(x, float) and np.isnan(x):
            return None
    except Exception:
        pass

    # ya es numérico
    if isinstance(x, (int, float, np.integer, np.floating)):
        try:
            return float(x)
        except Exception:
            return None

    # texto
    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return None

        s = s.replace("\u00a0", "").replace(" ", "")

        # Caso ES: "1.234.567,89"
        if "," in s:
            s2 = s.replace(".", "").replace(",", ".")
            try:
                return float(s2)
            except Exception:
                return None

        # Caso con puntos: miles "1.234.567" o decimal "12.34"
        if "." in s:
            if s.count(".") > 1:
                s2 = s.replace(".", "")
                try:
                    return float(s2)
                except Exception:
                    return None
            try:
                return float(s)
            except Exception:
                return None

        # entero sin separadores
        try:
            return float(s)
        except Exception:
            return None

    # otros tipos
    try:
        return float(x)
    except Exception:
        return None


def format_number_view(x, decimals=None):
    """
    Formatea SOLO para mostrar (string):
    - miles con '.'
    - decimales con ','
    - Si x no es numérico, devuelve x tal cual (string).
    - NO modifica tipos del DataFrame.
    """
    n = clean_number_view(x)
    if n is None:
        return "" if x is None else str(x)

    if decimals is None:
        decimals = 0 if float(n).is_integer() else 2

    s = f"{n:,.{decimals}f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s


# ============================================================
# HELPERS
# ============================================================

def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf is None or gdf.empty:
        return gdf
    if gdf.crs is None:
        return gdf.set_crs("EPSG:4326")
    return gdf.to_crs("EPSG:4326")


def simplify_gdf(gdf: gpd.GeoDataFrame, tol: float) -> gpd.GeoDataFrame:
    if gdf is None or gdf.empty:
        return gdf
    gdf = gdf.copy()
    try:
        gdf["geometry"] = gdf["geometry"].simplify(tol, preserve_topology=True)
    except Exception:
        pass
    return gdf


def geojson_clean(gdf: gpd.GeoDataFrame) -> dict:
    gdf = gdf[gdf.geometry.notna()].copy()
    try:
        gdf = gdf[~gdf.geometry.is_empty].copy()
    except Exception:
        pass

    js = json.loads(gdf.to_json())
    features = []
    for ft in js.get("features", []):
        geom = ft.get("geometry") or {}
        if "coordinates" not in geom or geom.get("coordinates") in (None, [], [None]):
            continue
        features.append(ft)
    js["features"] = features
    return js


def fixed_folium_map(center=(-33.45, -70.66), zoom_start=4, tiles="CartoDB positron", zoom_control=False):
    m = folium.Map(
        location=list(center),
        zoom_start=zoom_start,
        tiles=None,
        zoom_control=zoom_control,
        control_scale=False,
        dragging=False,
        scrollWheelZoom=False,
        doubleClickZoom=False,
        touchZoom=False,
        prefer_canvas=True,
    )
    folium.TileLayer(tiles, control=False).add_to(m)
    m.fit_bounds(CHILE_BOUNDS)
    m.options["maxBounds"] = CHILE_BOUNDS
    m.options["maxBoundsViscosity"] = 1.0
    m.options["minZoom"] = 4
    m.options["maxZoom"] = 10
    return m


def norm_col(c) -> str:
    c = str(c).replace("\n", " ").replace("\r", " ")
    c = re.sub(r"\s+", " ", c).strip().lower()
    return c


def parse_cut_com(x) -> pd.Series:
    s = x.astype(str).str.strip()
    s = s.str.replace(r"[^\d]", "", regex=True)
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def safe_clip(layer_gdf: gpd.GeoDataFrame, clip_poly: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if layer_gdf is None or clip_poly is None or len(clip_poly) == 0:
        return layer_gdf
    try:
        return gpd.clip(layer_gdf, clip_poly)
    except Exception:
        return layer_gdf


def _require_shp_minimum(shp_path: Path, label: str):
    """
    Para evitar pyogrio DataSourceError redacted:
    valida que exista el .shp y que al menos existan .dbf y .shx si el nombre base coincide.
    """
    if not shp_path.exists():
        st.error(f"❌ No existe shapefile de {label}: {shp_path}")
        st.stop()

    base = shp_path.with_suffix("")
    needed = [base.with_suffix(".shp"), base.with_suffix(".shx"), base.with_suffix(".dbf")]
    missing = [p.name for p in needed if not p.exists()]
    if missing:
        st.error(
            f"❌ Shapefile incompleto para {label}.\n\n"
            f"Faltan: {missing}\n\n"
            "Asegúrate de subir .shp + .shx + .dbf (y recomendado .prj/.cpg) a la misma carpeta."
        )
        st.stop()


def safe_read_shp_optional(path: Path, label: str):
    """
    Lee capas opcionales sin botar la app.
    Si falta o falla, devuelve GeoDataFrame vacío WGS84.
    """
    empty = gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326")
    if not path.exists():
        return empty
    try:
        _require_shp_minimum(path, label)
        return ensure_wgs84(gpd.read_file(path))
    except Exception as e:
        st.warning(f"⚠️ No pude cargar {label}: {e}")
        return empty


# ============================================================
# PALETAS
# ============================================================

PALETTES = {
    "residentes": ["#e8f5e9", "#66bb6a", "#1b5e20"],
    "pobreza_n_personas_2020": ["#fff3e0", "#fb8c00", "#4e342e"],
    "ia_modsev_2022": ["#e3f2fd", "#1e88e5", "#0d47a1"],
    "tasa_matricula_2024": ["#f3e5f5", "#ab47bc", "#4a148c"],
}

REGION_GRADIENT = ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]


# ============================================================
# LOAD SHAPES (CACHE)
# ============================================================

@st.cache_resource(show_spinner=False)
def load_shapes():
    _require_shp_minimum(SHP_COMUNAS, "COMUNAS")
    _require_shp_minimum(SHP_PROVINCIAS, "PROVINCIAS")
    _require_shp_minimum(SHP_REGIONES, "REGIONES")

    comunas = ensure_wgs84(gpd.read_file(SHP_COMUNAS))
    provincias = ensure_wgs84(gpd.read_file(SHP_PROVINCIAS))
    regiones = ensure_wgs84(gpd.read_file(SHP_REGIONES))

    # Normalización ligera (NO cambia tipos de indicadores, solo nombres de columnas geográficas)
    if "cod_comuna" in comunas.columns and "CUT_COM" not in comunas.columns:
        comunas = comunas.rename(columns={"cod_comuna": "CUT_COM"})
    if "Comuna" in comunas.columns and "Nombre comuna" not in comunas.columns:
        comunas = comunas.rename(columns={"Comuna": "Nombre comuna"})

    if "CUT_COM" in comunas.columns:
        comunas["CUT_COM"] = pd.to_numeric(comunas["CUT_COM"], errors="coerce").astype("Int64")

    # Simplificación (geom)
    comunas = simplify_gdf(comunas, 0.01)
    provincias = simplify_gdf(provincias, 0.02)
    regiones = simplify_gdf(regiones, 0.03)

    # Opcionales
    red_hidro = simplify_gdf(safe_read_shp_optional(SHP_RED_HIDRO, "RED HIDROGRÁFICA"), 0.005)
    red_ferro = simplify_gdf(safe_read_shp_optional(SHP_RED_FERRO, "RED FERROVIARIA"), 0.005)
    masa_hidrica = simplify_gdf(safe_read_shp_optional(SHP_MASA_HIDRICA, "MASA HÍDRICA"), 0.01)

    return comunas, provincias, regiones, red_hidro, red_ferro, masa_hidrica


# ============================================================
# LOAD INDICATORS (CACHE)
# - NO fuerza conversiones
# - si Excel falta, no revienta
# ============================================================

@st.cache_data(show_spinner=False, ttl=3600)
def load_indicators(_comunas: gpd.GeoDataFrame) -> pd.DataFrame:
    base_cols = ["CUT_COM", "Region", "Provincia", "Nombre comuna"]
    base = _comunas[[c for c in base_cols if c in _comunas.columns]].drop_duplicates().copy()

    # Helpers: leer excel seguro sin romper
    def _read_excel_safe(path: Path, sheet_name=None, header=0, skiprows=None):
        if not path.exists():
            st.warning(f"⚠️ No existe: {path.name} (se omite)")
            return None
        try:
            return pd.read_excel(path, sheet_name=sheet_name, header=header, skiprows=skiprows)
        except Exception as e:
            st.warning(f"⚠️ No pude leer {path.name}: {e}")
            return None

    # DEMO: intentamos mapear columnas sin convertir
    demo = pd.DataFrame({"CUT_COM": pd.Series(dtype="Int64"), "residentes": pd.Series(dtype="object")})
    df_demo = _read_excel_safe(XLSX_DEMO, sheet_name=SHEET_DEMO)
    if df_demo is not None:
        cols = {norm_col(c): c for c in df_demo.columns}
        c_cut = cols.get("cutcomuna") or cols.get("cut_com") or cols.get("cut com") or cols.get("cutcom")
        c_res = cols.get("residentes")
        if c_cut and c_res:
            tmp = df_demo[[c_cut, c_res]].copy()
            tmp = tmp.rename(columns={c_cut: "CUT_COM", c_res: "residentes"})
            tmp["CUT_COM"] = pd.to_numeric(tmp["CUT_COM"], errors="coerce").astype("Int64")
            # NO sumar ni convertir: tomamos primer valor no-nulo por comuna
            demo = tmp.sort_values("CUT_COM").dropna(subset=["CUT_COM"]).groupby("CUT_COM", as_index=False).agg(
                residentes=("residentes", "first")
            )

    # IA: busca header dinámico, luego toma columna indicador sin convertir
    ia = pd.DataFrame({"CUT_COM": pd.Series(dtype="Int64"), "ia_modsev_2022": pd.Series(dtype="object")})
    df_ia_raw = _read_excel_safe(XLSX_IA, sheet_name=SHEET_IA, header=None)
    if df_ia_raw is not None:
        header_row = None
        for i in range(min(40, len(df_ia_raw))):
            row = df_ia_raw.iloc[i].astype(str).str.lower().tolist()
            if any(("código" in x) or ("codigo" in x) for x in row):
                header_row = i
                break
        df_ia = _read_excel_safe(XLSX_IA, sheet_name=SHEET_IA, header=header_row if header_row is not None else 0)
        if df_ia is not None:
            df_ia.columns = [str(c).strip() for c in df_ia.columns]
            col_codigo = next((c for c in df_ia.columns if norm_col(c) in ("código", "codigo")), None)

            col_ind = None
            for c in df_ia.columns:
                nc = norm_col(c)
                # tu criterio original: inseguridad alimentaria moderada (mod-sev)
                if ("inseguridad alimentaria" in nc) and ("moderada" in nc):
                    col_ind = c
                    break

            if col_codigo and col_ind:
                tmp = df_ia[[col_codigo, col_ind]].copy()
                tmp = tmp.rename(columns={col_codigo: "CUT_COM", col_ind: "ia_modsev_2022"})
                tmp["CUT_COM"] = pd.to_numeric(tmp["CUT_COM"], errors="coerce").astype("Int64")
                ia = tmp.dropna(subset=["CUT_COM"]).groupby("CUT_COM", as_index=False).agg(
                    ia_modsev_2022=("ia_modsev_2022", "first")
                )

    # EDU: tasa matrícula, sin convertir
    edu = pd.DataFrame(columns=["Nombre comuna", "tasa_matricula_2024"])
    df_edu = _read_excel_safe(XLSX_EDU, sheet_name=SHEET_EDU)
    if df_edu is not None:
        df_edu.columns = [str(c).strip() for c in df_edu.columns]
        c_nom = next((c for c in df_edu.columns if norm_col(c) in ("nom_com", "nombre comuna", "nom com")), None)
        c_tasa = next((c for c in df_edu.columns if ("tasa" in norm_col(c) and "matricula" in norm_col(c))), None)
        if c_nom and c_tasa:
            tmp = df_edu[[c_nom, c_tasa]].copy()
            tmp = tmp.rename(columns={c_nom: "Nombre comuna", c_tasa: "tasa_matricula_2024"})
            edu = tmp.groupby("Nombre comuna", as_index=False).agg(tasa_matricula_2024=("tasa_matricula_2024", "first"))

    # POBREZA: si existe, sin convertir
    pob = pd.DataFrame({"CUT_COM": pd.Series(dtype="Int64"), "pobreza_n_personas_2020": pd.Series(dtype="object")})
    df_pob = _read_excel_safe(RUTA_POBREZA, sheet_name=0, skiprows=POB_SKIPROWS) if RUTA_POBREZA.exists() else None
    if df_pob is not None:
        df_pob.columns = [str(c).strip() for c in df_pob.columns]
        col_codigo = next((c for c in df_pob.columns if norm_col(c) in ("código", "codigo")), None)

        col_red = None
        for c in df_pob.columns:
            nc = norm_col(c)
            if ("numero de personas" in nc or "número de personas" in nc) and ("pobreza" in nc) and ("ingresos" in nc):
                col_red = c
                break

        if col_codigo and col_red:
            tmp = df_pob[[col_codigo, col_red]].copy()
            tmp["CUT_COM"] = parse_cut_com(tmp[col_codigo])
            tmp = tmp.rename(columns={col_red: "pobreza_n_personas_2020"})
            pob = tmp[["CUT_COM", "pobreza_n_personas_2020"]].dropna(subset=["CUT_COM"]).groupby("CUT_COM", as_index=False).agg(
                pobreza_n_personas_2020=("pobreza_n_personas_2020", "first")
            )

    # Merge final (sin migración)
    out = base.merge(demo, on="CUT_COM", how="left")
    out = out.merge(ia, on="CUT_COM", how="left")
    out = out.merge(pob, on="CUT_COM", how="left")
    if "Nombre comuna" in out.columns and "Nombre comuna" in edu.columns:
        out = out.merge(edu, on="Nombre comuna", how="left")
    else:
        out["tasa_matricula_2024"] = np.nan

    return out


# ============================================================
# MAPA ESTÁTICO (GeoPandas) por indicador (sin cambiar tipos)
# ============================================================

def plot_static_indicator(gdf: gpd.GeoDataFrame, col: str, title: str, palette: list[str]):
    df = gdf.copy()
    if col not in df.columns:
        st.info("Este indicador no está disponible.")
        return

    # Para rangos solo necesitamos valores numéricos, pero NO tocamos la base:
    values = df[col].map(clean_number_view)
    v = values.dropna()
    if v.empty:
        st.warning("Sin datos numéricos para este indicador en esta selección.")
        return

    q = v.quantile([0.25, 0.50, 0.75]).tolist()
    bins = [-np.inf, q[0], q[1], q[2], np.inf]
    labels = ["Muy bajo", "Bajo", "Medio", "Alto"]
    df["_val_num"] = values
    df["Rango"] = pd.cut(df["_val_num"], bins=bins, labels=labels, include_lowest=True)

    cmap = mcolors.ListedColormap([palette[0], palette[0], palette[1], palette[2]])

    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    df.plot(
        column="Rango",
        categorical=True,
        legend=True,
        cmap=cmap,
        ax=ax,
        edgecolor="#0f172a",
        linewidth=0.35,
    )
    ax.set_title(title)
    ax.axis("off")
    st.pyplot(fig, use_container_width=True)

    # Tabla vista (sin tocar datos)
    cols = [c for c in ["Nombre comuna", "Provincia", "Region", col, "Rango"] if c in df.columns]
    t = df.drop(columns=["geometry"], errors="ignore")[cols].copy()
    if col in t.columns:
        t[col] = t[col].map(lambda x: format_number_view(x, 2 if ("tasa" in col or "ia_" in col) else 0))
    st.dataframe(t.head(15), use_container_width=True)


# ============================================================
# APP PRINCIPAL (MISMA FIRMA)
# ============================================================

def mapas_app():
    if st.button("Volver al inicio"):
        st.query_params["page"] = "Inicio"
        st.rerun()

    comunas, provincias, regiones, red_hidro, red_ferro, masa_hidrica = load_shapes()
    ind_df = load_indicators(comunas)

    # selector región
    REGION_LIST = sorted(comunas["Region"].dropna().unique().tolist()) if "Region" in comunas.columns else []
    region_sel = st.selectbox("Selecciona la región", REGION_LIST if REGION_LIST else ["(sin Región en SHP)"])

    layer_options = ["Regiones", "Provincias", "Comunas", "Masas lacustres", "Red ferroviaria", "Red hidrográfica"]
    layers_sel = st.multiselect(
        "Selector de capas",
        options=layer_options,
        default=["Provincias", "Comunas"],
    )

    INDICATORS = [
        ("residentes", "Población (residentes)"),
        ("pobreza_n_personas_2020", "Pobreza 2020: Nº personas (SAE)"),
        ("ia_modsev_2022", "IA Mod-Sev 2022 (%)"),
        ("tasa_matricula_2024", "Tasa matrícula 2024"),
    ]

    indicator_key = st.selectbox(
        "Selector de indicadores",
        options=[k for k, _ in INDICATORS],
        format_func=lambda k: dict(INDICATORS)[k],
    )

    col_left, col_right = st.columns([1, 2], vertical_alignment="top")

    # ========================================================
    # MAPA 1 (Chile)
    # ========================================================
    with col_left:
        st.markdown("### Mapa de Chile")
        m1 = fixed_folium_map(center=(-33.45, -70.66), zoom_start=4, zoom_control=False)

        region_names = regiones["Region"].dropna().unique().tolist() if "Region" in regiones.columns else []
        palette = [
            "#e11d48", "#f97316", "#eab308", "#22c55e", "#06b6d4",
            "#3b82f6", "#8b5cf6", "#db2777", "#84cc16", "#0ea5e9",
            "#f43f5e", "#a855f7", "#10b981", "#fb7185", "#f59e0b",
        ]
        color_by_region = {r: palette[i % len(palette)] for i, r in enumerate(sorted(region_names))}
        gj_reg = geojson_clean(regiones[[c for c in ["Region", "codregion", "geometry"] if c in regiones.columns]])

        folium.GeoJson(
            data=gj_reg,
            name="Regiones",
            show=True,
            style_function=lambda f: {
                "fillColor": color_by_region.get(f["properties"].get("Region"), "#94a3b8"),
                "color": "#0f172a",
                "weight": 1.1,
                "fillOpacity": 0.65,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[c for c in ["Region", "codregion"] if gj_reg["features"] and c in gj_reg["features"][0]["properties"]],
                aliases=["Reg:", "Cod:"],
                sticky=True,
                localize=True,
            ),
        ).add_to(m1)

        st_folium(m1, width=None, height=520, key="mapa_1")

    # ========================================================
    # MAPA 2 (Región + indicador)
    # ========================================================
    with col_right:
        st.markdown("### Mapa de Región y sus indicadores")

        rg_poly = regiones[regiones["Region"] == region_sel] if "Region" in regiones.columns else regiones.iloc[0:0]

        g_reg = comunas.copy()
        if "Region" in g_reg.columns and region_sel in REGION_LIST:
            g_reg = g_reg[g_reg["Region"] == region_sel].copy()

        merge_keys = [c for c in ["CUT_COM", "Region", "Provincia", "Nombre comuna"] if c in g_reg.columns and c in ind_df.columns]
        if merge_keys:
            g_reg = g_reg.merge(ind_df, on=merge_keys, how="left")

        # ✅ columnas formato SOLO PARA VISTA (no toca original)
        def make_fmt_cols(df):
            out = df.copy()
            if "residentes" in out.columns:
                out["pop_fmt"] = out["residentes"].map(lambda v: format_number_view(v, 0))
            else:
                out["pop_fmt"] = ""
            if "pobreza_n_personas_2020" in out.columns:
                out["pob_fmt"] = out["pobreza_n_personas_2020"].map(lambda v: format_number_view(v, 0))
            else:
                out["pob_fmt"] = ""
            if "ia_modsev_2022" in out.columns:
                out["ia_fmt"] = out["ia_modsev_2022"].map(lambda v: format_number_view(v, 2))
            else:
                out["ia_fmt"] = ""
            if "tasa_matricula_2024" in out.columns:
                out["mat_fmt"] = out["tasa_matricula_2024"].map(lambda v: format_number_view(v, 2))
            else:
                out["mat_fmt"] = ""
            return out

        g_reg = make_fmt_cols(g_reg)

        # rango para colormap usando conversión solo de vista
        vals = g_reg.get(indicator_key, pd.Series([], dtype="object")).map(clean_number_view).dropna()
        vmin = float(vals.min()) if len(vals) else 0.0
        vmax = float(vals.max()) if len(vals) else 1.0
        if vmin == vmax:
            vmax = vmin + 1.0

        m2 = fixed_folium_map(center=(-33.45, -70.66), zoom_start=4, zoom_control=False)
        try:
            if len(rg_poly):
                b = rg_poly.total_bounds
                m2.fit_bounds([[b[1], b[0]], [b[3], b[2]]])
        except Exception:
            pass

        if "Regiones" in layers_sel:
            folium.GeoJson(
                data=geojson_clean(regiones[[c for c in ["Region", "geometry"] if c in regiones.columns]]),
                name="Regiones",
                show=True,
                style_function=lambda f: {"color": "#111827", "weight": 2.0, "fillOpacity": 0.0},
            ).add_to(m2)

        if "Provincias" in layers_sel and provincias is not None and len(provincias):
            prov_clip = safe_clip(provincias, rg_poly)
            folium.GeoJson(
                data=geojson_clean(prov_clip[[c for c in ["Provincia", "Region", "geometry"] if c in prov_clip.columns]]),
                name="Provincias",
                show=True,
                style_function=lambda f: {"color": "#f97316", "weight": 1.8, "fillOpacity": 0.0},
            ).add_to(m2)

        if "Comunas" in layers_sel and g_reg is not None and len(g_reg):
            needed = [
                "Nombre comuna", "Provincia", "Region",
                "pop_fmt", "pob_fmt", "ia_fmt", "mat_fmt",
                indicator_key,
                "geometry",
            ]
            gj_com = geojson_clean(g_reg[[c for c in needed if c in g_reg.columns]])

            pal = folium.LinearColormap(
                REGION_GRADIENT,
                vmin=vmin,
                vmax=vmax,
                caption=dict(INDICATORS)[indicator_key],
            )

            tooltip_fields = [f for f in [
                "Nombre comuna", "Provincia", "Region",
                "pop_fmt", "pob_fmt", "ia_fmt", "mat_fmt",
            ] if gj_com["features"] and f in gj_com["features"][0]["properties"]]

            alias_map = {
                "Nombre comuna": "Com:",
                "Provincia": "Prov:",
                "Region": "Reg:",
                "pop_fmt": "Pob:",
                "pob_fmt": "Pobrez:",
                "ia_fmt": "IA%:",
                "mat_fmt": "Mat%:",
            }
            tooltip_aliases = [alias_map.get(f, f"{f}:") for f in tooltip_fields]

            def style_fn(feat):
                v_raw = feat["properties"].get(indicator_key)
                v = clean_number_view(v_raw)  # ✅ solo para color, no modifica datos
                return {
                    "fillColor": pal(v) if v is not None else "#00000000",
                    "color": "#ffffff",
                    "weight": 0.55,
                    "fillOpacity": 0.85,
                }

            folium.GeoJson(
                data=gj_com,
                name=f"Indicador: {dict(INDICATORS)[indicator_key]}",
                show=True,
                style_function=style_fn,
                tooltip=folium.GeoJsonTooltip(fields=tooltip_fields, aliases=tooltip_aliases, sticky=True),
            ).add_to(m2)

            pal.add_to(m2)

        if "Masas lacustres" in layers_sel and masa_hidrica is not None and len(masa_hidrica):
            mh = safe_clip(masa_hidrica, rg_poly)
            folium.GeoJson(
                data=geojson_clean(mh[[c for c in ["Nombre", "Tipo", "geometry"] if c in mh.columns]]),
                name="Masas lacustres",
                show=True,
                style_function=lambda f: {"color": "#0ea5e9", "weight": 1.2, "fillOpacity": 0.35},
            ).add_to(m2)

        if "Red ferroviaria" in layers_sel and red_ferro is not None and len(red_ferro):
            rf = safe_clip(red_ferro, rg_poly)
            folium.GeoJson(
                data=geojson_clean(rf[[c for c in ["Activ_2016", "Largo_Km", "geometry"] if c in rf.columns]]),
                name="Red ferroviaria",
                show=True,
                style_function=lambda f: {"color": "#e11d48", "weight": 2.4, "opacity": 0.85},
            ).add_to(m2)

        if "Red hidrográfica" in layers_sel and red_hidro is not None and len(red_hidro):
            rh = safe_clip(red_hidro, rg_poly)
            folium.GeoJson(
                data=geojson_clean(rh[[c for c in ["Nombre", "Dren_Tipo", "geometry"] if c in rh.columns]]),
                name="Red hidrográfica",
                show=True,
                style_function=lambda f: {"color": "#22c55e", "weight": 2.2, "opacity": 0.85},
            ).add_to(m2)

        folium.LayerControl(collapsed=False).add_to(m2)
        st_folium(m2, width=None, height=520, key="mapa_2")

    # ========================================================
    # TABLAS + MAPAS FIJOS
    # ========================================================
    st.markdown("## Tablas y mapas por indicador")

    view = ind_df.copy()
    if "Region" in view.columns and region_sel in REGION_LIST:
        view = view[view["Region"] == region_sel].copy()

    g_reg_static = comunas.copy()
    if "Region" in g_reg_static.columns and region_sel in REGION_LIST:
        g_reg_static = g_reg_static[g_reg_static["Region"] == region_sel].copy()

    merge_keys = [c for c in ["CUT_COM", "Region", "Provincia", "Nombre comuna"] if c in g_reg_static.columns and c in view.columns]
    if merge_keys:
        g_reg_static = g_reg_static.merge(view, on=merge_keys, how="left")

    st.markdown("### Tabla resumen (Top 15) — indicador seleccionado")

    cols_base = [c for c in ["Region", "Provincia", "Nombre comuna"] if c in view.columns]
    cols_ind = [k for k, _ in INDICATORS if k in view.columns]
    show_cols = cols_base + cols_ind

    tmp = view.copy()

    # ✅ no convertimos columnas; si quieres ordenar "numéricamente" sin tocar data:
    sort_key = tmp.get(indicator_key, pd.Series([], dtype="object")).map(clean_number_view)
    tmp["_sortnum"] = sort_key
    tmp = tmp.sort_values("_sortnum", ascending=False, na_position="last")
    tmp = tmp.drop(columns=["_sortnum"], errors="ignore")

    tmp_show = tmp[show_cols].copy()

    # ✅ solo para vista (no modifica original): formateamos con format_number_view
    for k, _label in INDICATORS:
        if k in tmp_show.columns:
            dec = 2 if ("tasa" in k or "ia_" in k) else 0
            tmp_show[k] = tmp_show[k].map(lambda v: format_number_view(v, dec))

    st.dataframe(tmp_show.head(15), use_container_width=True)

    for k, label in INDICATORS:
        with st.expander(f"{label} — tabla + mapa fijo", expanded=False):
            sub = view[cols_base + [k]].copy() if k in view.columns else view[cols_base].copy()

            q = st.text_input(f"Buscar (com/prov/reg) — {label}", key=f"search_{k}")
            if q.strip():
                qq = q.strip().lower()
                for c in cols_base:
                    sub[c] = sub[c].astype(str)
                mask = False
                for c in cols_base:
                    mask = mask | sub[c].str.lower().str.contains(qq, na=False)
                sub = sub[mask].copy()

            if k in sub.columns:
                # ordenar numéricamente sin tocar data
                sub["_sortnum"] = sub[k].map(clean_number_view)
                sub = sub.sort_values("_sortnum", ascending=False, na_position="last").drop(columns=["_sortnum"], errors="ignore")

                sub_fmt = sub.copy()
                dec = 2 if ("tasa" in k or "ia_" in k) else 0
                sub_fmt[k] = sub_fmt[k].map(lambda v: format_number_view(v, dec))
                st.dataframe(sub_fmt.head(200), use_container_width=True)
            else:
                st.info("Este indicador no está disponible.")
                continue

            pal = PALETTES.get(k, ["#e5e7eb", "#6b7280", "#111827"])
            plot_static_indicator(
                gdf=g_reg_static,
                col=k,
                title=f"{label} — Rangos (cuantiles) — {region_sel}",
                palette=pal,
            )

    st.markdown("## Descripción de los indicadores")
    st.info("Aquí puedes agregar texto fuente/unidad por indicador si quieres.")


# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================
if __name__ == "__main__":
    st.set_page_config(page_title="Chile | Dashboard mapas", layout="wide")
    mapas_app()