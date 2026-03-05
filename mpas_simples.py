# mpas_simples.py  (o el nombre que uses)
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
# CONFIG (IMPORTANTE)
# - Al integrarlo en una app principal, NO llames st.set_page_config aquí.
# ============================================================

# BASE_DIR (deja tu ruta si estás en local)
BASE_DIR = Path(r"C:\Users\manue\Fvagconsulting Dropbox\Manuel Rojas\mapas")

# --- SHP (rutas locales) ---
SHP_COMUNAS = BASE_DIR / "capas" / "capas_generales" / "comunas" / "comunas.shp"
SHP_PROVINCIAS = BASE_DIR / "capas" / "capas_generales" / "provincias" / "Provincias.shp"
SHP_REGIONES = BASE_DIR / "capas" / "capas_generales" / "regiones" / "Regional.shp"

# --- capas opcionales ---
SHP_RED_HIDRO = BASE_DIR / "capas" / "capas_generales" / "red_hidrografica" / "Red_Hidrografica.shp"
SHP_RED_FERRO = BASE_DIR / "capas" / "capas_generales" / "red_ferroviaria" / "Red_ferroviaria.shp"
SHP_MASA_HIDRICA = BASE_DIR / "capas" / "capas_generales" / "masa_hidrica" / "masas_lacustres.shp"

# --- EXCEL descriptivos ---
XLSX_DEMO = BASE_DIR / "datos_descriptivos_chile" / "socioeconomicos" / "descriptivos" / "Indicadores_Demograficos_Anual_2024.xlsx"
SHEET_DEMO = "Hoja1"

XLSX_IA = BASE_DIR / "datos_descriptivos_chile" / "socioeconomicos" / "descriptivos" / "Estimacion_Inseguridad_Alimentaria_Comunal_2022.xlsx"
SHEET_IA = "IA Mod-Sev 2022"

XLSX_EDU = BASE_DIR / "datos_descriptivos_chile" / "socioeconomicos" / "descriptivos" / "Indicadores_Educacion_Anual_2024.xlsx"
SHEET_EDU = "Hoja1"

XLSX_MIG = BASE_DIR / "datos_descriptivos_chile" / "socioeconomicos" / "descriptivos" / "Indicadores_Migracion_Interna_Anual_2024.xlsx"
SHEET_MIG = "1"

# --- POBREZA (tu ruta) ---
RUTA_POBREZA = Path(r"C:\Users\manue\Fvagconsulting Dropbox\Manuel Rojas\MAPAS\pobreza.xlsx")
POB_SKIPROWS = range(0, 2)

# bounds Chile
CHILE_BOUNDS = [[-56.0, -76.0], [-17.0, -66.0]]

# ============================================================
# HELPERS
# ============================================================
def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        return gdf.set_crs("EPSG:4326")
    return gdf.to_crs("EPSG:4326")


def to_numeric_clean(series: pd.Series) -> pd.Series:
    """
    Interpreta:
      '.' como separador de miles
      ',' como separador decimal
    """
    s = series.astype(str).str.strip()
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def format_es_number(x, decimals=0):
    """
    Formato ES: miles '.' y decimales ','
    """
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    try:
        x = float(x)
    except Exception:
        return str(x)

    if decimals <= 0:
        s = f"{x:,.0f}"
    else:
        s = f"{x:,.{decimals}f}"

    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def simplify_gdf(gdf: gpd.GeoDataFrame, tol: float) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].simplify(tol, preserve_topology=True)
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


def safe_read_shp(path: Path):
    try:
        if path.exists():
            return ensure_wgs84(gpd.read_file(path))
    except Exception:
        return None
    return None


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
    c = str(c)
    c = c.replace("\n", " ").replace("\r", " ")
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


# ============================================================
# PALETAS
# ============================================================
PALETTES = {
    "residentes": ["#e8f5e9", "#66bb6a", "#1b5e20"],
    "pobreza_n_personas_2020": ["#fff3e0", "#fb8c00", "#4e342e"],
    "ia_modsev_2022": ["#e3f2fd", "#1e88e5", "#0d47a1"],
    "tasa_matricula_2024": ["#f3e5f5", "#ab47bc", "#4a148c"],
    "mig_neto": ["#e0f7fa", "#26c6da", "#004d40"],
    "mig_in_2024": ["#fce4ec", "#ec407a", "#880e4f"],
    "mig_out_2018": ["#ede7f6", "#7e57c2", "#311b92"],
}

REGION_GRADIENT = ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]


# ============================================================
# LOAD SHAPES (CACHE)
# ============================================================
@st.cache_resource(show_spinner=False)
def load_shapes():
    comunas = ensure_wgs84(gpd.read_file(SHP_COMUNAS))
    provincias = ensure_wgs84(gpd.read_file(SHP_PROVINCIAS))
    regiones = ensure_wgs84(gpd.read_file(SHP_REGIONES))

    if "cod_comuna" in comunas.columns:
        comunas = comunas.rename(columns={"cod_comuna": "CUT_COM"})
    if "Comuna" in comunas.columns:
        comunas = comunas.rename(columns={"Comuna": "Nombre comuna"})

    comunas["CUT_COM"] = pd.to_numeric(comunas["CUT_COM"], errors="coerce").astype("Int64")

    comunas = simplify_gdf(comunas, 0.01)
    provincias = simplify_gdf(provincias, 0.02)
    regiones = simplify_gdf(regiones, 0.03)

    red_hidro = safe_read_shp(SHP_RED_HIDRO)
    red_ferro = safe_read_shp(SHP_RED_FERRO)
    masa_hidrica = safe_read_shp(SHP_MASA_HIDRICA)

    if red_hidro is not None:
        red_hidro = simplify_gdf(red_hidro, 0.005)
    if red_ferro is not None:
        red_ferro = simplify_gdf(red_ferro, 0.005)
    if masa_hidrica is not None:
        masa_hidrica = simplify_gdf(masa_hidrica, 0.01)

    return comunas, provincias, regiones, red_hidro, red_ferro, masa_hidrica


# ============================================================
# LOAD INDICATORS (CACHE)
# ============================================================
@st.cache_data(show_spinner=False, ttl=3600)
def load_indicators(_comunas: gpd.GeoDataFrame) -> pd.DataFrame:
    base_cols = ["CUT_COM", "Region", "Provincia", "Nombre comuna"]
    base = _comunas[[c for c in base_cols if c in _comunas.columns]].drop_duplicates().copy()

    df_demo = pd.read_excel(XLSX_DEMO, sheet_name=SHEET_DEMO)
    df_demo["cutcomuna"] = pd.to_numeric(df_demo["cutcomuna"], errors="coerce").astype("Int64")
    df_demo["residentes"] = to_numeric_clean(df_demo["residentes"])
    demo = (
        df_demo.groupby("cutcomuna", as_index=False)
        .agg(residentes=("residentes", "sum"))
        .rename(columns={"cutcomuna": "CUT_COM"})
    )

    df_ia_raw = pd.read_excel(XLSX_IA, sheet_name=SHEET_IA, header=None)
    header_row = None
    for i in range(min(40, len(df_ia_raw))):
        row = df_ia_raw.iloc[i].astype(str).str.lower().tolist()
        if any("código" in x or "codigo" in x for x in row):
            header_row = i
            break
    df_ia = (
        pd.read_excel(XLSX_IA, sheet_name=SHEET_IA, header=header_row)
        if header_row is not None
        else pd.read_excel(XLSX_IA, sheet_name=SHEET_IA)
    )

    df_ia.columns = [str(c).strip() for c in df_ia.columns]
    col_codigo = next((c for c in df_ia.columns if norm_col(c) in ("código", "codigo")), None)

    col_ind = None
    for c in df_ia.columns:
        nc = norm_col(c)
        if "inseguridad alimentaria" in nc and "moderada" in nc:
            col_ind = c
            break

    if col_codigo and col_ind:
        ia = df_ia[[col_codigo, col_ind]].copy()
        ia = ia.rename(columns={col_codigo: "CUT_COM", col_ind: "ia_modsev_2022"})
        ia["CUT_COM"] = pd.to_numeric(ia["CUT_COM"], errors="coerce").astype("Int64")
        ia["ia_modsev_2022"] = to_numeric_clean(ia["ia_modsev_2022"])
    else:
        ia = pd.DataFrame({"CUT_COM": pd.Series(dtype="Int64"), "ia_modsev_2022": pd.Series(dtype="float")})

    df_edu = pd.read_excel(XLSX_EDU, sheet_name=SHEET_EDU)
    df_edu.columns = [str(c).strip() for c in df_edu.columns]
    c_nom = next((c for c in df_edu.columns if norm_col(c) in ("nom_com", "nombre comuna", "nom com")), None)
    c_tasa = next((c for c in df_edu.columns if "tasa" in norm_col(c) and "matricula" in norm_col(c)), None)

    edu = pd.DataFrame(columns=["Nombre comuna", "tasa_matricula_2024"])
    if c_nom and c_tasa:
        edu = df_edu[[c_nom, c_tasa]].copy()
        edu = edu.rename(columns={c_nom: "Nombre comuna", c_tasa: "tasa_matricula_2024"})
        edu["tasa_matricula_2024"] = to_numeric_clean(edu["tasa_matricula_2024"])
        edu = edu.groupby("Nombre comuna", as_index=False).agg(
            tasa_matricula_2024=("tasa_matricula_2024", "mean")
        )

    df_mig = pd.read_excel(XLSX_MIG, sheet_name=SHEET_MIG)
    df_mig.columns = [str(c).strip() for c in df_mig.columns]
    c_dest = next((c for c in df_mig.columns if norm_col(c) == "comuna_2024"), None)
    c_orig = next((c for c in df_mig.columns if norm_col(c) == "comuna_2018"), None)
    c_w = next((c for c in df_mig.columns if norm_col(c) == "inm_2024"), None)

    mig = pd.DataFrame(columns=["CUT_COM", "mig_in_2024", "mig_out_2018", "mig_neto"])
    if c_dest and c_orig:
        if c_w:
            df_mig[c_w] = to_numeric_clean(df_mig[c_w]).fillna(1.0)
            inflow = df_mig.groupby(c_dest, as_index=False).agg(mig_in_2024=(c_w, "sum"))
            outflow = df_mig.groupby(c_orig, as_index=False).agg(mig_out_2018=(c_w, "sum"))
        else:
            inflow = df_mig.groupby(c_dest, as_index=False).size().rename(columns={"size": "mig_in_2024"})
            outflow = df_mig.groupby(c_orig, as_index=False).size().rename(columns={"size": "mig_out_2018"})

        inflow = inflow.rename(columns={c_dest: "CUT_COM"})
        outflow = outflow.rename(columns={c_orig: "CUT_COM"})
        inflow["CUT_COM"] = pd.to_numeric(inflow["CUT_COM"], errors="coerce").astype("Int64")
        outflow["CUT_COM"] = pd.to_numeric(outflow["CUT_COM"], errors="coerce").astype("Int64")

        mig = inflow.merge(outflow, on="CUT_COM", how="outer")
        mig["mig_in_2024"] = mig["mig_in_2024"].fillna(0.0)
        mig["mig_out_2018"] = mig["mig_out_2018"].fillna(0.0)
        mig["mig_neto"] = mig["mig_in_2024"] - mig["mig_out_2018"]

    pob = pd.DataFrame({"CUT_COM": pd.Series(dtype="Int64"), "pobreza_n_personas_2020": pd.Series(dtype="float")})
    if RUTA_POBREZA.exists():
        df_pob = pd.read_excel(RUTA_POBREZA, engine="openpyxl", skiprows=POB_SKIPROWS)
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
            tmp["pobreza_n_personas_2020"] = to_numeric_clean(tmp[col_red])
            pob = tmp[["CUT_COM", "pobreza_n_personas_2020"]].dropna(subset=["CUT_COM"])

    out = base.merge(demo, on="CUT_COM", how="left")
    out = out.merge(ia, on="CUT_COM", how="left")
    out = out.merge(mig, on="CUT_COM", how="left")
    out = out.merge(pob, on="CUT_COM", how="left")
    if "Nombre comuna" in out.columns and "Nombre comuna" in edu.columns:
        out = out.merge(edu, on="Nombre comuna", how="left")

    return out


# ============================================================
# MAPA ESTÁTICO (GeoPandas) por indicador
# ============================================================
def plot_static_indicator(gdf: gpd.GeoDataFrame, col: str, title: str, palette: list[str]):
    df = gdf.copy()
    df[col] = pd.to_numeric(df[col], errors="coerce")

    v = df[col].dropna()
    if v.empty:
        st.warning("Sin datos para este indicador en esta selección.")
        return

    q = v.quantile([0.25, 0.50, 0.75]).tolist()
    bins = [-np.inf, q[0], q[1], q[2], np.inf]
    labels = ["Muy bajo", "Bajo", "Medio", "Alto"]
    df["Rango"] = pd.cut(df[col], bins=bins, labels=labels, include_lowest=True)

    cmap = mcolors.ListedColormap([
        palette[0],
        mcolors.to_hex(mcolors.to_rgb(palette[0])),
        palette[1],
        palette[2],
    ])

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

    cols = [c for c in ["Nombre comuna", "Provincia", "Region", col, "Rango"] if c in df.columns]
    t = df.drop(columns=["geometry"], errors="ignore")[cols].copy()
    if col in t.columns:
        dec = 2 if "tasa" in col or "ia_" in col else 0
        t[col] = t[col].apply(lambda x: format_es_number(x, decimals=dec))
    st.dataframe(t.head(15), use_container_width=True)


# ============================================================
# MAIN APP (para llamar desde app.py)
# ============================================================
def mapas_app():
    # (Opcional) CSS oscuro sobrio SOLO para esta sección
    st.markdown(
        """
        <style>
          .stApp { background: #0b1220; }
          html, body, [class*="css"] { color: #e5e7eb; }
          h1,h2,h3,h4,h5,h6 { color: #f3f4f6 !important; }
          .stMarkdown, .stMarkdown * { color: #e5e7eb !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Botón volver (usa tu router por query params)
    if st.button("Volver al inicio"):
        st.query_params["page"] = "Inicio"
        st.rerun()

    comunas, provincias, regiones, red_hidro, red_ferro, masa_hidrica = load_shapes()
    ind_df = load_indicators(comunas)

    REGION_LIST = sorted([r for r in comunas["Region"].dropna().unique().tolist()]) if "Region" in comunas.columns else []
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
        ("mig_neto", "Migración neta"),
        ("mig_in_2024", "Migración 2024 (in)"),
        ("mig_out_2018", "Migración 2018 (out)"),
    ]
    indicator_key = st.selectbox(
        "Selector de indicadores",
        options=[k for k, _ in INDICATORS],
        format_func=lambda k: dict(INDICATORS)[k],
    )

    col_left, col_right = st.columns([1, 2], vertical_alignment="top")

    # -----------------
    # MAPA 1
    # -----------------
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

    # -----------------
    # MAPA 2
    # -----------------
    with col_right:
        st.markdown("### Mapa de Región y sus indicadores")

        rg_poly = regiones[regiones["Region"] == region_sel] if "Region" in regiones.columns else regiones.iloc[0:0]

        g_reg = comunas.copy()
        if "Region" in g_reg.columns and region_sel in REGION_LIST:
            g_reg = g_reg[g_reg["Region"] == region_sel].copy()

        merge_keys = [c for c in ["CUT_COM", "Region", "Provincia", "Nombre comuna"] if c in g_reg.columns and c in ind_df.columns]
        g_reg = g_reg.merge(ind_df, on=merge_keys, how="left")

        def make_fmt_cols(df):
            out = df.copy()
            out["pop_fmt"] = out.get("residentes").apply(lambda x: format_es_number(x, 0))
            out["pob_fmt"] = out.get("pobreza_n_personas_2020").apply(lambda x: format_es_number(x, 0))
            out["ia_fmt"] = out.get("ia_modsev_2022").apply(lambda x: format_es_number(x, 2))
            out["mat_fmt"] = out.get("tasa_matricula_2024").apply(lambda x: format_es_number(x, 2))
            out["mnet_fmt"] = out.get("mig_neto").apply(lambda x: format_es_number(x, 0))
            out["min_fmt"] = out.get("mig_in_2024").apply(lambda x: format_es_number(x, 0))
            out["mout_fmt"] = out.get("mig_out_2018").apply(lambda x: format_es_number(x, 0))
            return out

        g_reg = make_fmt_cols(g_reg)

        vals = pd.to_numeric(g_reg.get(indicator_key, pd.Series([], dtype=float)), errors="coerce")
        vals = vals[vals.notna()]
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

        if "Provincias" in layers_sel:
            prov_clip = safe_clip(provincias, rg_poly)
            folium.GeoJson(
                data=geojson_clean(prov_clip[[c for c in ["Provincia", "Region", "geometry"] if c in prov_clip.columns]]),
                name="Provincias",
                show=True,
                style_function=lambda f: {"color": "#f97316", "weight": 1.8, "fillOpacity": 0.0},
            ).add_to(m2)

        if "Comunas" in layers_sel:
            needed = [
                "Nombre comuna", "Provincia", "Region",
                "pop_fmt", "pob_fmt", "ia_fmt", "mat_fmt", "mnet_fmt", "min_fmt", "mout_fmt",
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
                "mnet_fmt", "min_fmt", "mout_fmt",
            ] if gj_com["features"] and f in gj_com["features"][0]["properties"]]

            alias_map = {
                "Nombre comuna": "Com:",
                "Provincia": "Prov:",
                "Region": "Reg:",
                "pop_fmt": "Pob:",
                "pob_fmt": "Pobrez:",
                "ia_fmt": "IA%:",
                "mat_fmt": "Mat%:",
                "mnet_fmt": "MigN:",
                "min_fmt": "MigIn:",
                "mout_fmt": "MigOut:",
            }
            tooltip_aliases = [alias_map.get(f, f"{f}:") for f in tooltip_fields]

            def style_fn(feat):
                v = feat["properties"].get(indicator_key)
                return {
                    "fillColor": pal(v) if v is not None and v == v else "#00000000",
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

        if "Masas lacustres" in layers_sel and masa_hidrica is not None:
            mh = safe_clip(masa_hidrica, rg_poly)
            folium.GeoJson(
                data=geojson_clean(mh[[c for c in ["Nombre", "Tipo", "geometry"] if c in mh.columns]]),
                name="Masas lacustres",
                show=True,
                style_function=lambda f: {"color": "#0ea5e9", "weight": 1.2, "fillOpacity": 0.35},
                tooltip=folium.GeoJsonTooltip(
                    fields=[c for c in ["Nombre", "Tipo"] if mh.columns.isin([c]).any()],
                    aliases=["Nom:", "Tipo:"],
                    sticky=True,
                ),
            ).add_to(m2)

        if "Red ferroviaria" in layers_sel and red_ferro is not None:
            rf = safe_clip(red_ferro, rg_poly)
            folium.GeoJson(
                data=geojson_clean(rf[[c for c in ["Activ_2016", "Largo_Km", "geometry"] if c in rf.columns]]),
                name="Red ferroviaria",
                show=True,
                style_function=lambda f: {"color": "#e11d48", "weight": 2.4, "opacity": 0.85},
            ).add_to(m2)

        if "Red hidrográfica" in layers_sel and red_hidro is not None:
            rh = safe_clip(red_hidro, rg_poly)
            folium.GeoJson(
                data=geojson_clean(rh[[c for c in ["Nombre", "Dren_Tipo", "geometry"] if c in rh.columns]]),
                name="Red hidrográfica",
                show=True,
                style_function=lambda f: {"color": "#22c55e", "weight": 2.2, "opacity": 0.85},
            ).add_to(m2)

        folium.LayerControl(collapsed=False).add_to(m2)
        st_folium(m2, width=None, height=520, key="mapa_2")

    # -----------------
    # TABLAS + MAPAS FIJOS
    # -----------------
    st.markdown("## Tablas y mapas por indicador")

    view = ind_df.copy()
    if "Region" in view.columns and region_sel in REGION_LIST:
        view = view[view["Region"] == region_sel].copy()

    g_reg_static = comunas.copy()
    if "Region" in g_reg_static.columns and region_sel in REGION_LIST:
        g_reg_static = g_reg_static[g_reg_static["Region"] == region_sel].copy()

    merge_keys = [c for c in ["CUT_COM", "Region", "Provincia", "Nombre comuna"] if c in g_reg_static.columns and c in view.columns]
    g_reg_static = g_reg_static.merge(view, on=merge_keys, how="left")

    st.markdown("### Tabla resumen (Top 15) — indicador seleccionado")
    cols_base = [c for c in ["Region", "Provincia", "Nombre comuna"] if c in view.columns]
    cols_ind = [k for k, _ in INDICATORS if k in view.columns]
    show_cols = cols_base + cols_ind

    tmp = view.copy()
    tmp[indicator_key] = pd.to_numeric(tmp.get(indicator_key), errors="coerce")
    tmp = tmp.sort_values(indicator_key, ascending=False, na_position="last")

    tmp_fmt = tmp[show_cols].copy()
    for k, _ in INDICATORS:
        if k in tmp_fmt.columns:
            dec = 2 if ("tasa" in k or "ia_" in k) else 0
            tmp_fmt[k] = tmp_fmt[k].apply(lambda x: format_es_number(x, decimals=dec))

    st.dataframe(tmp_fmt.head(15), use_container_width=True)

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
                dec = 2 if ("tasa" in k or "ia_" in k) else 0
                sub[k] = pd.to_numeric(sub[k], errors="coerce")
                sub = sub.sort_values(k, ascending=False, na_position="last")
                sub_fmt = sub.copy()
                sub_fmt[k] = sub_fmt[k].apply(lambda x: format_es_number(x, decimals=dec))
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
    st.info("Luego lo dejamos automático por indicador (fuente, unidad, nota metodológica).")


# ============================================================
# EJECUCIÓN DIRECTA (solo si corres ESTE archivo)
# ============================================================
if __name__ == "__main__":
    # Si lo corres solo: streamlit run mpas_simples.py
    st.set_page_config(page_title="Chile | Dashboard mapas", layout="wide")
    mapas_app()
