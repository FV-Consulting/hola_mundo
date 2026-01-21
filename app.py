# ============================================================
# app.py — FV Consulting (Navbar azul + Home intacto + SIDEBAR FUNCIONAL)
#
# ✅ Sidebar plegable funcionando en TODAS tus apps
# ✅ Navbar azul fija, texto blanco, SIN subrayado
# ✅ Mantiene tu Home tal cual
# ✅ FIX: el botón ☰ no queda tapado por tu navbar
#
# Nota:
# - Si alguna app interna tiene st.set_page_config(), debes quitarlo
# ============================================================

from pathlib import Path
from urllib.parse import quote

import streamlit as st
from PIL import Image

# ----------------------------
# Imports de tus apps
# ----------------------------
from cargar_documentos import cargar_documentos
from data import data_multiple
from boletines import boletines_app

try:
    from crear_blog import crear_blog_app
except Exception:
    try:
        from crear_blog import main as crear_blog_app
    except Exception:
        crear_blog_app = None

# ----------------------------
# Config
# ----------------------------
try:
    img1 = Image.open("data/logo_fvag.png")
except Exception:
    try:
        img1 = Image.open("image_file/logo_fvag.png")
    except Exception:
        img1 = None

st.set_page_config(
    page_title="FV Consulting",
    page_icon=img1 if img1 else "📊",
    layout="wide",
    initial_sidebar_state="auto",  # ✅ sidebar plegable por defecto
)

# ----------------------------
# Router por query params
# ----------------------------
qp = st.query_params
page = qp.get("page", "Inicio")


def goto(page_name: str):
    st.query_params["page"] = page_name
    st.rerun()


# ============================================================
# CSS: SOLO NAVBAR + padding superior
# ⚠️ CLAVE: NO ocultar el header de Streamlit (si no, no aparece el botón ☰)
# ============================================================
NAVBAR_H = 64
NAVBAR_LEFT_GUTTER = 72  # 👈 espacio reservado para el botón ☰ (prueba 64–84)

st.markdown(
    f"""
    <style>
      /* Puedes ocultar menú y footer sin romper sidebar */
      #MainMenu {{visibility: hidden;}}
      footer {{visibility: hidden;}}

      /* NO ocultar header/toolbar o muere el ☰ */

      /* Empuja el contenido bajo la navbar */
      .main .block-container {{
        padding-top: {NAVBAR_H + 18}px !important;
      }}

      /* ====== GUTTER IZQUIERDO (zona del ☰) ====== */
      .fv-left-gutter {{
        position: fixed;
        top: 0;
        left: 0;
        width: {NAVBAR_LEFT_GUTTER}px;
        height: {NAVBAR_H}px;
        background: transparent;          /* puedes poner white si quieres */
        z-index: 999998;                 /* debajo de la navbar */
        border-bottom: 1px solid rgba(0,0,0,0.06);
        pointer-events: none;            /* no bloquea clicks */
      }}

      /* ====== NAVBAR (empieza DESPUÉS del ☰) ====== */
      .fv-topbar {{
        position: fixed;
        top: 0;
        left: {NAVBAR_LEFT_GUTTER}px;    /* 👈 aquí está la clave */
        right: 0;
        height: {NAVBAR_H}px;
        background: #0f607a;
        z-index: 999999;
        display: flex;
        align-items: center;
        border-bottom: 1px solid rgba(255,255,255,0.15);
      }}

      .fv-topbar-inner {{
        width: 100%;
        max-width: 1400px;
        margin: 0 auto;
        padding: 0 28px;
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 18px;
      }}

      /* Marca FV */
      .fv-brand {{
        color: #ffffff !important;
        font-weight: 800;
        letter-spacing: 0.3px;
        font-size: 22px;
        font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial;
        text-decoration: none !important;
        line-height: 1;
      }}

      .fv-links {{
        display: flex;
        align-items: center;
        gap: 18px;
        flex-wrap: nowrap;
      }}

      /* Links navbar: blancos y SIN subrayado en todos los estados */
      .fv-links a,
      .fv-links a:visited,
      .fv-links a:hover,
      .fv-links a:active {{
        color: #ffffff !important;
        text-decoration: none !important;
      }}

      .fv-link {{
        font-weight: 700;
        font-size: 14px;
        padding: 8px 10px;
        border-radius: 10px;
        transition: background 0.15s ease;
        font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial;
        white-space: nowrap;
      }}

      .fv-link:hover {{
        background: rgba(255,255,255,0.12);
      }}

      .fv-link.active {{
        background: rgba(255,255,255,0.16);
      }}

      @media (max-width: 950px) {{
        .fv-brand {{ font-size: 18px; }}
        .fv-link {{ font-size: 13px; padding: 7px 8px; }}
        .fv-topbar-inner {{ padding: 0 18px; }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)
# ============================================================
# THEME FIX GLOBAL:
# - Dark: se queda como está
# - Light: fuerza texto oscuro legible
# ============================================================
st.markdown("""
<style>

/* ================================
   MODO CLARO (light)
   ================================ */
body[data-theme="light"] {
    --fv-text-main: #0f172a;
    --fv-text-secondary: #1f2933;
}

/* Texto general */
body[data-theme="light"] p,
body[data-theme="light"] span,
body[data-theme="light"] div,
body[data-theme="light"] label,
body[data-theme="light"] li,
body[data-theme="light"] h1,
body[data-theme="light"] h2,
body[data-theme="light"] h3,
body[data-theme="light"] h4,
body[data-theme="light"] h5,
body[data-theme="light"] h6 {
    color: #0f172a !important;
}

/* Markdown */
body[data-theme="light"] .stMarkdown,
body[data-theme="light"] .stMarkdown * {
    color: #0f172a !important;
}

/* Inputs, selects, widgets */
body[data-theme="light"] input,
body[data-theme="light"] textarea,
body[data-theme="light"] select {
    color: #0f172a !important;
}

/* Sidebar en modo claro */
body[data-theme="light"] section[data-testid="stSidebar"] {
    color: #0f172a !important;
}

/* Dataframes */
body[data-theme="light"] .dataframe,
body[data-theme="light"] table {
    color: #0f172a !important;
}

/* ================================
   MODO OSCURO (dark)
   No tocamos nada: usa tu diseño actual
   ================================ */
</style>
""", unsafe_allow_html=True)

# ============================================================
# FIX ROBUSTO: el botón ☰ del sidebar NO queda tapado por tu navbar
# - Lo bajamos justo debajo del navbar
# - Aseguramos z-index alto
# - Ajustamos el panel sidebar para que su contenido no quede oculto arriba
# ============================================================
st.markdown(
    f"""
    <style>
      /* Botón ☰ (toggle del sidebar) */
      [data-testid="stSidebarNavButton"] {{
          position: fixed !important;
          top: {NAVBAR_H + 12}px !important;   /* 👈 debajo de navbar */
          left: 12px !important;
          z-index: 1000001 !important;
      }}

      /* Sidebar: que empiece bajo el navbar */
      section[data-testid="stSidebar"] {{
          top: {NAVBAR_H}px !important;
          height: calc(100vh - {NAVBAR_H}px) !important;
      }}

      /* A veces Streamlit mete padding; lo reforzamos */
      section[data-testid="stSidebar"] > div {{
          padding-top: 10px !important;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


def render_navbar(active: str):
    def cls(name: str) -> str:
        return "fv-link active" if active == name else "fv-link"

    def href(p: str) -> str:
        # Si estás deploy en root, esto funciona.
        # Si tu app está en un subpath, cámbialo a: return f"?page={quote(p)}"
        return f"/?page={quote(p)}"

    st.markdown(
        f"""
        <div class="fv-topbar">
          <div class="fv-topbar-inner">
            <a class="fv-brand" href="{href("Inicio")}">FV Consulting</a>
            <div class="fv-links">
              <a class="{cls("Inicio")}" href="{href("Inicio")}">Inicio</a>
              <a class="{cls("Blog")}" href="{href("Blog")}">Blog</a>
              <a class="{cls("Análisis de Datos")}" href="{href("Análisis de Datos")}">Análisis de Datos</a>
              <a class="{cls("Mapas")}" href="{href("Mapas")}">Mapas</a>
              <a class="{cls("Cargar Data")}" href="{href("Cargar Data")}">Cargar Data</a>
              <a class="{cls("Crear blog")}" href="{href("Crear blog")}">Crear blog</a>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# TU INICIO (Home) — tal cual lo pegaste
# ============================================================
HOME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg-dark: #0a0e1a;
    --bg-card: #151923;
    --text-primary: #ffffff;
    --text-secondary: #94a3b8;
    --accent: #6366f1;
}

/* SOLO HOME */
.home-page {
    background: #0a0e1a;
    color: white;
    min-height: unset !important;
    border-radius: 18px;
    padding: 0.5rem 0 1rem;
}

.hero-left-text { text-align: right; padding-right: 2rem; }
.hero-left-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 1.2;
    color: white;
    margin-bottom: 1rem;
}
.hero-right-text { text-align: left; padding-left: 2rem; }
.hero-right-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.8rem;
    font-weight: 700;
    line-height: 1.3;
    color: white;
    margin-bottom: 1rem;
}

.images-showcase-center { max-width: 600px; margin: 0 auto; perspective: 2000px; }

.img-card {
    position: relative;
    border-radius: 20px;
    overflow: hidden;
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(10px);
    border: 2px solid rgba(100, 116, 139, 0.3);
    aspect-ratio: 16/10;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 1.5rem;
    transform-style: preserve-3d;
    transform: rotateX(10deg) rotateY(-10deg) translateZ(0px);
    transition: all 0.9s cubic-bezier(0.23, 1, 0.32, 1);
    box-shadow:
        0 20px 60px rgba(0, 0, 0, 0.45),
        0 8px 20px rgba(0, 0, 0, 0.25);
}

.img-card:hover {
    transform: rotateX(0deg) rotateY(0deg) translateZ(60px) scale(1.06);
    border-color: rgba(99, 102, 241, 0.7);
    box-shadow:
        0 50px 120px rgba(99, 102, 241, 0.45),
        0 25px 60px rgba(0, 0, 0, 0.4);
    z-index: 10;
}

.img-card img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transform: translateZ(30px);
}

.cards-section {
    padding: 1.5rem 2rem 2.0rem;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
}

.service-card {
    background: rgba(21, 25, 35, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 1.6rem;
    transition: all 0.3s ease;
}
.service-card:hover {
    transform: translateY(-4px);
    border-color: rgba(99, 102, 241, 0.5);
    background: rgba(21, 25, 35, 1);
}

.card-icon {
    width: 48px; height: 48px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 12px;
    font-size: 1.5rem;
    margin-bottom: 1rem;
    background: rgba(99, 102, 241, 0.1);
}
.card-category {
    font-family: 'Inter', sans-serif;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #6366f1;
    margin-bottom: 0.75rem;
}
.card-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.25rem;
    font-weight: 700;
    color: white;
    margin-bottom: 0.75rem;
    line-height: 1.3;
}
.card-description {
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    line-height: 1.6;
    color: #94a3b8;
    margin-bottom: 1.0rem;
}
.card-tags { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1.0rem; }
.tag {
    font-family: 'Inter', sans-serif;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.35rem 0.75rem;
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 50px;
    color: #a5b4fc;
}

@media (max-width: 1024px) {
    .cards-section { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
    .cards-section { grid-template-columns: 1fr; }
    .hero-left-text, .hero-right-text { text-align: center; padding: 0; }
}
</style>
"""


def render_home():
    st.markdown(HOME_CSS, unsafe_allow_html=True)
    st.markdown('<div class="home-page">', unsafe_allow_html=True)

    col_left, col_center, col_right = st.columns([1, 2, 1])

    with col_left:
        st.markdown(
            """
            <div class="hero-left-text">
                <h2 class="hero-left-title">Informacion, datos, economia y simpleza en un mismo sitio.</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

    def img_to_data_uri(path: str) -> str:
        p = Path(path)
        if not p.exists():
            return ""
        ext = p.suffix.lower().replace(".", "")
        if ext == "jpg":
            ext = "jpeg"
        import base64
        return f"data:image/{ext};base64,{base64.b64encode(p.read_bytes()).decode('utf-8')}"

    def render_img(path: str, placeholder: str):
        uri = img_to_data_uri(path)
        if uri:
            st.markdown(f'<div class="img-card"><img src="{uri}"></div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="img-card" style="color:#64748b;font-weight:800;">{placeholder}</div>',
                unsafe_allow_html=True,
            )

    with col_center:
        st.markdown('<div class="images-showcase-center">', unsafe_allow_html=True)
        r1 = st.columns(3)
        with r1[0]:
            render_img("image_file/image_1.png", "1")
        with r1[1]:
            render_img("image_file/image_2.png", "2")
        with r1[2]:
            render_img("image_file/image_3.png", "3")
        r2 = st.columns(3)
        with r2[0]:
            render_img("image_file/image_4.png", "4")
        with r2[1]:
            render_img("image_file/logo_fvag.png", "FV")
        with r2[2]:
            render_img("image_file/image_5.png", "5")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown(
            """
            <div class="hero-right-text">
                <h2 class="hero-right-title">Navega por la innovación en análisis e investigación.</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div style="text-align:center; padding: 2.2rem 2rem 0.5rem;">
            <h2 style="font-family:'Space Grotesk',sans-serif; font-size: 3rem; font-weight: 700; color: white; margin: 0;">
                Bienvenidos a FV Consulting
            </h2>
            <p style="font-family:'Inter',sans-serif; font-size: 1.1rem; color: #94a3b8; margin-top: 0.9rem; line-height:1.7;">
                Una plataforma integral que combina investigación, análisis de datos, visualización avanzada y carga de documentos
                para ofrecer soluciones completas y eficientes.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="cards-section">', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            <div class="service-card">
                <div class="card-icon">📊</div>
                <div class="card-category">REPORTES • VISUALIZACIÓN</div>
                <h3 class="card-title">Blog de Investigación</h3>
                <p class="card-description">Economía, Agricultura, Finanzas, Econometría y Análisis de datos.</p>
                <div class="card-tags">
                    <span class="tag">Dashboards</span>
                    <span class="tag">Analytics</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Explorar →", key="home_blog", use_container_width=True):
            goto("Blog")

    with c2:
        st.markdown(
            """
            <div class="service-card">
                <div class="card-icon">📈</div>
                <div class="card-category">ANALYTICS • ESTADÍSTICA</div>
                <h3 class="card-title">Análisis de Datos</h3>
                <p class="card-description">Herramientas para explorar, modelar y visualizar datos cargados previamente.</p>
                <div class="card-tags">
                    <span class="tag">Machine Learning</span>
                    <span class="tag">Predictivo</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Explorar →", key="home_analisis", use_container_width=True):
            goto("Análisis de Datos")

    with c3:
        st.markdown(
            """
            <div class="service-card">
                <div class="card-icon">🗺️</div>
                <div class="card-category">MAPAS • ESTADÍSTICA</div>
                <h3 class="card-title">Análisis Geoespacial</h3>
                <p class="card-description">Visualización de mapas y análisis territorial con datos geoespaciales.</p>
                <div class="card-tags">
                    <span class="tag">GIS</span>
                    <span class="tag">Territorial</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Explorar →", key="home_mapas", use_container_width=True):
            goto("Mapas")

    c4, c5 = st.columns(2)
    with c4:
        st.markdown(
            """
            <div class="service-card">
                <div class="card-icon">📁</div>
                <div class="card-category">DOCUMENTOS • PROCESAMIENTO</div>
                <h3 class="card-title">Cargar Data</h3>
                <p class="card-description">Pipeline para cargar, depurar y procesar múltiples formatos.</p>
                <div class="card-tags">
                    <span class="tag">Automatización</span>
                    <span class="tag">ETL</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Explorar →", key="home_cargar", use_container_width=True):
            goto("Cargar Data")

    with c5:
        st.markdown(
            """
            <div class="service-card">
                <div class="card-icon">✍️</div>
                <div class="card-category">PUBLICACIÓN • MARKDOWN</div>
                <h3 class="card-title">Crear blog</h3>
                <p class="card-description">Crea y publica entradas en Markdown con imágenes y tablas.</p>
                <div class="card-tags">
                    <span class="tag">Markdown</span>
                    <span class="tag">Editor</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Explorar →", key="home_crear_blog", use_container_width=True):
            goto("Crear blog")

    st.markdown("</div>", unsafe_allow_html=True)  # cards-section
    st.markdown("</div>", unsafe_allow_html=True)  # home-page


# ============================================================
# ROUTER PRINCIPAL
# ============================================================
def main():
    render_navbar(page)

    if page == "Inicio":
        render_home()

    elif page == "Blog":
        boletines_app()

    elif page == "Crear blog":
        if crear_blog_app is None:
            st.error("No pude importar crear_blog.py. Revisa que exista y que tenga crear_blog_app() o main().")
        else:
            crear_blog_app()

    elif page == "Análisis de Datos":
        data_multiple()

    elif page == "Mapas":
        st.title("Mapas")
        st.write("En esta sección podrás crear y visualizar mapas interactivos basados en datos geoespaciales.")

    elif page == "Cargar Data":
        cargar_documentos()

    else:
        st.warning("Página no encontrada. Volviendo a Inicio.")
        goto("Inicio")


if __name__ == "__main__":
    main()
