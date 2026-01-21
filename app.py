# ============================================================
# app.py — FV Consulting (Navbar azul + Home intacto + SIDEBAR FUNCIONAL)
# + Login Google en el HOME (zona verde) + Roles por dominio
#
# ✅ Botón de login en el HOME (zona verde)
# ✅ Botones "Explorar →" se habilitan SOLO tras iniciar sesión
# ✅ Router bloquea todas las páginas (excepto Inicio) si no hay sesión
# ✅ SOLO @fvagconsulting.com puede "Crear blog" (admin usa TODO)
# ✅ Sidebar plegable muestra foto + correo + logout al iniciar sesión
# ✅ FIX: elimina el </div> suelto (wrappers HTML incompatibles con Streamlit)
# ============================================================

from pathlib import Path
from urllib.parse import quote
import base64

import streamlit as st
from PIL import Image
import requests

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
    initial_sidebar_state="auto",
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
# AUTH HELPERS (Streamlit Cloud)
# ============================================================
def auth_state():
    """
    Devuelve:
      logged_in: bool
      email: str
      name: str
      picture: str
      is_admin: bool  (solo dominio fvagconsulting.com)
    """
    if not hasattr(st, "user") or not hasattr(st.user, "is_logged_in"):
        return False, "", "", "", False

    logged_in = bool(st.user.is_logged_in)
    if not logged_in:
        return False, "", "", "", False

    email = st.user.email or ""
    name = st.user.name or ""
    picture = st.user.picture or ""
    is_admin = email.lower().endswith("@fvagconsulting.com") if email else False
    return logged_in, email, name, picture, is_admin


def render_user_sidebar(logged_in: bool, email: str, name: str, picture: str, is_admin: bool):
    if not logged_in:
        return

    with st.sidebar:
        st.markdown("### 👤 Sesión")
        c1, c2 = st.columns([1, 3])

        with c1:
            if picture:
                try:
                    r = requests.get(picture, timeout=10)
                    if r.status_code == 200:
                        st.image(r.content, width=60)
                    else:
                        st.write(" ")
                except Exception:
                    st.write(" ")
            else:
                st.write(" ")

        with c2:
            st.write(f"**{name or 'Usuario'}**")
            st.caption(email)

        st.caption("✅ Admin (acceso total)" if is_admin else "👀 Usuario (sin Crear blog)")
        st.button(":material/logout: Cerrar sesión", on_click=st.logout, use_container_width=True)


# ============================================================
# CSS: NAVBAR + padding superior
# ============================================================
NAVBAR_H = 64
NAVBAR_LEFT_GUTTER = 72  # espacio reservado para el ☰

st.markdown(
    f"""
    <style>
      #MainMenu {{visibility: hidden;}}
      footer {{visibility: hidden;}}

      .main .block-container {{
        padding-top: {NAVBAR_H + 18}px !important;
      }}

      .fv-left-gutter {{
        position: fixed;
        top: 0;
        left: 0;
        width: {NAVBAR_LEFT_GUTTER}px;
        height: {NAVBAR_H}px;
        background: transparent;
        z-index: 999998;
        border-bottom: 1px solid rgba(0,0,0,0.06);
        pointer-events: none;
      }}

      .fv-topbar {{
        position: fixed;
        top: 0;
        left: {NAVBAR_LEFT_GUTTER}px;
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

      .fv-link:hover {{ background: rgba(255,255,255,0.12); }}
      .fv-link.active {{ background: rgba(255,255,255,0.16); }}

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
# THEME FIX GLOBAL (modo claro)
# ============================================================
st.markdown("""
<style>
body[data-theme="light"] {
    --fv-text-main: #0f172a;
    --fv-text-secondary: #1f2933;
}
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
body[data-theme="light"] .stMarkdown,
body[data-theme="light"] .stMarkdown * {
    color: #0f172a !important;
}
body[data-theme="light"] input,
body[data-theme="light"] textarea,
body[data-theme="light"] select {
    color: #0f172a !important;
}
body[data-theme="light"] section[data-testid="stSidebar"] {
    color: #0f172a !important;
}
body[data-theme="light"] .dataframe,
body[data-theme="light"] table {
    color: #0f172a !important;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# FIX: botón ☰ del sidebar NO queda tapado por navbar
# ============================================================
st.markdown(
    f"""
    <style>
      [data-testid="stSidebarNavButton"] {{
          position: fixed !important;
          top: {NAVBAR_H + 12}px !important;
          left: 12px !important;
          z-index: 1000001 !important;
      }}
      section[data-testid="stSidebar"] {{
          top: {NAVBAR_H}px !important;
          height: calc(100vh - {NAVBAR_H}px) !important;
      }}
      section[data-testid="stSidebar"] > div {{
          padding-top: 10px !important;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# RESPONSIVE FIX (igual que tu estilo)
# ============================================================
st.markdown("""
<style>
html, body { max-width: 100%; overflow-x: hidden; }
.main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
.fv-link { padding: 8px 10px; }

@media (max-width: 1024px) {
  .fv-topbar-inner { padding: 0 16px !important; }
  .fv-links { gap: 10px !important; }
  .fv-link { font-size: 13px !important; padding: 7px 8px !important; }
  .hero-left-title { font-size: 2.0rem !important; }
  .hero-right-title { font-size: 1.5rem !important; }
}

@media (max-width: 768px) {
  .fv-topbar { height: 56px !important; }
  .fv-topbar-inner { padding: 0 12px !important; gap: 10px !important; grid-template-columns: 1fr !important; }
  .fv-brand { display: block; text-align: center; font-size: 18px !important; margin-top: 6px; }
  .fv-links { justify-content: center !important; flex-wrap: wrap !important; gap: 8px !important; padding-bottom: 8px; }
  .fv-link { font-size: 12px !important; padding: 6px 8px !important; border-radius: 10px !important; }
  .main .block-container { padding-top: 86px !important; }
  [data-testid="stSidebarNavButton"] { top: 68px !important; left: 10px !important; transform: scale(0.95); }
  .hero-left-text, .hero-right-text { text-align: center !important; padding: 0 !important; }
  .hero-left-title { font-size: 1.6rem !important; }
  .hero-right-title { font-size: 1.25rem !important; }
  .images-showcase-center { max-width: 100% !important; }
  .img-card { border-radius: 16px !important; }
}

@media (max-width: 420px) {
  .fv-link { font-size: 11px !important; padding: 6px 7px !important; }
  .hero-left-title { font-size: 1.35rem !important; }
  .hero-right-title { font-size: 1.1rem !important; }
}
</style>
""", unsafe_allow_html=True)


def render_navbar(active: str, show_crear_blog: bool):
    def cls(name: str) -> str:
        return "fv-link active" if active == name else "fv-link"

    def href(p: str) -> str:
        return f"/?page={quote(p)}"

    crear_blog_link = ""
    if show_crear_blog:
        crear_blog_link = f'<a class="{cls("Crear blog")}" href="{href("Crear blog")}">Crear blog</a>'

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
              {crear_blog_link}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# HOME (misma estética) + CTA Login en zona verde
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

/* ===== HOME WRAPPER (sin div abierto/cerrado) ===== */
div[data-testid="stVerticalBlock"]:has(#fv-home-anchor) {
    background: #0a0e1a;
    color: white;
    border-radius: 18px;
    padding: 0.5rem 0 1rem;
}
#fv-home-anchor { display: none; }

/* ===== Imagenes centro: aplicamos estilo al bloque que contiene el ancla ===== */
div[data-testid="stVerticalBlock"]:has(#fv-images-anchor) {
    max-width: 600px;
    margin: 0 auto;
    perspective: 2000px;
}
#fv-images-anchor { display:none; }

/* ===== Cards section: aplicamos padding sin div wrapper ===== */
div[data-testid="stVerticalBlock"]:has(#fv-cards-anchor) {
    padding: 1.5rem 2rem 2.0rem;
}
#fv-cards-anchor { display:none; }

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

/* Tarjetas de imágenes */
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

/* Service cards */
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

@media (max-width: 768px) {
    .hero-left-text, .hero-right-text { text-align: center; padding: 0; }
}

/* ===== BLOQUE LOGIN (zona verde) ===== */
.fv-login-cta {
  max-width: 920px;
  margin: 0.4rem auto 0.9rem;
  padding: 1.1rem 1.2rem;
  border-radius: 16px;
  background: rgba(21, 25, 35, 0.70);
  border: 1px solid rgba(99, 102, 241, 0.28);
  backdrop-filter: blur(10px);
  box-shadow: 0 18px 60px rgba(0,0,0,0.35);
}
.fv-login-cta p{
  margin: 0;
  font-family:'Inter',sans-serif;
  font-size: 1.02rem;
  color: #94a3b8;
  line-height: 1.7;
  text-align: center;
}
.fv-login-cta strong{ color: #ffffff; }
</style>
"""


def render_home(logged_in: bool, email: str, name: str, is_admin: bool):
    st.markdown(HOME_CSS, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div id="fv-home-anchor"></div>', unsafe_allow_html=True)

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
            # ✅ ancla para el bloque de imágenes (sin abrir/cerrar div HTML)
            st.markdown('<div id="fv-images-anchor"></div>', unsafe_allow_html=True)

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

        with col_right:
            st.markdown(
                """
                <div class="hero-right-text">
                    <h2 class="hero-right-title">Navega por la innovación en análisis e investigación.</h2>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Título central
        st.markdown(
            """
            <div style="text-align:center; padding: 2.2rem 2rem 0.35rem;">
                <h2 style="font-family:'Space Grotesk',sans-serif; font-size: 3rem; font-weight: 700; color: white; margin: 0;">
                    Bienvenidos a FV Consulting
                </h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # CTA Login (zona verde)
        if not logged_in:
            st.markdown(
                """
                <div class="fv-login-cta">
                  <p>
                    <strong>Inicia sesión</strong> para usar las aplicaciones de <strong>FV Consulting</strong>.<br/>
                    Si tu correo es <strong>@fvagconsulting.com</strong>, tendrás acceso total, incluyendo <strong>Crear blog</strong>.
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            b1, b2, b3 = st.columns([2, 1.3, 2])
            with b2:
                st.button(
                    ":material/login: Iniciar sesión con Google",
                    on_click=st.login,
                    use_container_width=True,
                    key="home_login_btn",
                )
        else:
            st.markdown(
                f"""
                <div class="fv-login-cta">
                  <p>
                    ✅ Sesión iniciada como <strong>{name or "Usuario"}</strong> (<strong>{email}</strong>).<br/>
                    {"🟢 Eres <strong>Admin</strong>: acceso total." if is_admin else "🔒 Acceso a todas las apps, excepto <strong>Crear blog</strong>."}
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ✅ ancla cards-section (sin wrapper HTML)
        st.markdown('<div id="fv-cards-anchor"></div>', unsafe_allow_html=True)

        explore_disabled = not logged_in

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
            if st.button("Explorar →", key="home_blog", use_container_width=True, disabled=explore_disabled):
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
            if st.button("Explorar →", key="home_analisis", use_container_width=True, disabled=explore_disabled):
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
            if st.button("Explorar →", key="home_mapas", use_container_width=True, disabled=explore_disabled):
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
            if st.button("Explorar →", key="home_cargar", use_container_width=True, disabled=explore_disabled):
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
            if st.button(
                "Explorar →",
                key="home_crear_blog",
                use_container_width=True,
                disabled=(not logged_in) or (logged_in and not is_admin),
            ):
                goto("Crear blog")


# ============================================================
# ROUTER PRINCIPAL
# ============================================================
def main():
    logged_in, email, name, picture, is_admin = auth_state()

    # Navbar: ocultar "Crear blog" si no es admin
    render_navbar(page, show_crear_blog=is_admin)

    # Sidebar: si hay sesión, mostrar usuario + logout
    render_user_sidebar(logged_in, email, name, picture, is_admin)

    # 🔒 GATE GLOBAL:
    # Todas las páginas (excepto Inicio) requieren iniciar sesión.
    if page != "Inicio" and not logged_in:
        st.warning("Debes iniciar sesión para usar las aplicaciones.")
        c1, c2, c3 = st.columns([2, 1.3, 2])
        with c2:
            st.button(":material/login: Iniciar sesión con Google", on_click=st.login, use_container_width=True)
        st.stop()

    if page == "Inicio":
        render_home(logged_in, email, name, is_admin)

    elif page == "Blog":
        boletines_app()

    elif page == "Crear blog":
        # Admin usa TODO; otros NO
        if not is_admin:
            st.error("Acceso denegado: solo cuentas @fvagconsulting.com pueden crear publicaciones.")
            st.stop()

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
