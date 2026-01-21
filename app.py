# ============================================================
# app.py — FV Consulting (Navbar fija + sidebar plegable)
# ✅ NO aparecen botones blancos debajo (sin st.button "invisibles")
# ✅ Navbar azul navega con query params (?page=...)
# ✅ Sidebar plegable NO queda roto (NO ocultamos header)
# ✅ Mantiene tu router y tus apps
# ============================================================

import streamlit as st
import logging as login 
from PIL import Image
from urllib.parse import quote

from cargar_documentos import cargar_documentos
from data import data_multiple
from boletines import boletines_app

# ---- Import creador de blog ----
try:
    from crear_blog import crear_blog_app
except Exception:
    try:
        from crear_blog import main as crear_blog_app
    except Exception:
        crear_blog_app = None

#--------------------------------------------------
# 0) Inicio de sesion
#-----------------------------------------------------

# ------------------------------------------------------------
# 1) CONFIG
# ------------------------------------------------------------
try:
    img1 = Image.open("data/logo_fvag.png")
except Exception:
    img1 = None

st.set_page_config(
    page_title="FV Consulting",
    page_icon=img1 if img1 else "📊",
    layout="wide",
    initial_sidebar_state="collapsed"  # puedes dejar "auto" si quieres
)

# ------------------------------------------------------------
# 2) Router por query params (FUENTE DE VERDAD)
# ------------------------------------------------------------
qp = st.query_params
page = qp.get("page", "Inicio")

def goto(page_name: str):
    st.query_params["page"] = page_name
    st.rerun()

# ------------------------------------------------------------
# 3) CSS GLOBAL: NAVBAR FIJA + NO TAPAR CONTENIDO
# ------------------------------------------------------------
NAVBAR_H = 66

def inject_global_css():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700;800&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap');

        html, body, [class*="css"] {{
          font-family: "Open Sans", Helvetica, sans-serif;
        }}

        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}

        /* ❌ NO ocultar header, si no desaparece/rompe el ☰ del sidebar */
        /* header {{visibility: hidden;}} */

        /* Espacio para navbar fija */
        .main .block-container {{
          padding-top: {NAVBAR_H + 26}px !important;
          padding-left: 28px;
          padding-right: 28px;
          max-width: 1400px;
        }}

        /* Navbar fija */
        .fv-navbar {{
          position: fixed;
          top: 0; left: 0; right: 0;
          height: {NAVBAR_H}px;
          background: #0f607a;
          color: white;
          z-index: 999999;
          display: flex;
          align-items: center;
          border-bottom: 1px solid rgba(255,255,255,0.12);
          box-shadow: 0 2px 8px rgba(0,0,0,0.10);
        }}

        .fv-navbar-inner {{
          width: 100%;
          max-width: 1400px;
          margin: 0 auto;
          padding: 0 28px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 24px;
        }}

        .fv-brand {{
          display: flex;
          align-items: center;
          gap: 12px;
          color: white !important;
          text-decoration: none !important;
        }}

        .fv-brand-title {{
          font-family: Raleway, sans-serif;
          font-weight: 800;
          letter-spacing: 0.2px;
          font-size: 30px;
          line-height: 1;
          color: white !important;
          text-decoration: none !important;
        }}

        /* Links navbar */
        .fv-nav-buttons {{
          display: flex;
          align-items: center;
          gap: 8px;
        }}

        .fv-nav-link,
        .fv-nav-link:visited,
        .fv-nav-link:hover,
        .fv-nav-link:active {{
          color: white !important;
          text-decoration: none !important;
        }}

        .fv-nav-btn {{
          display: inline-block;
          background: transparent;
          color: white;
          border: none;
          padding: 8px 16px;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          border-radius: 8px;
          transition: all 0.2s ease;
          white-space: nowrap;
          font-family: "Open Sans", sans-serif;
        }}

        .fv-nav-btn:hover {{
          background: rgba(255,255,255,0.15);
        }}

        .fv-nav-btn.active {{
          background: rgba(255,255,255,0.25);
        }}

        /* Responsive */
        @media (max-width: 1200px) {{
          .fv-nav-buttons {{ gap: 4px; }}
          .fv-nav-btn {{ padding: 6px 12px; font-size: 14px; }}
        }}

        @media (max-width: 900px) {{
          .fv-brand-title {{ font-size: 22px; }}
          .main .block-container {{ padding-left: 16px; padding-right: 16px; }}
          .fv-nav-buttons {{ display: none; }} /* en móvil, usar sidebar */
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------
# 4) NAVBAR (SOLO HTML LINKS, SIN BOTONES STREAMLIT)
# ------------------------------------------------------------
def render_navbar(active_page: str):
    pages = [
        ("Inicio", "Inicio"),
        ("Blog", "Blog"),
        ("Crear blog", "Crear blog"),
        ("Analizar datos", "Análisis"),
        ("Mapas", "Mapas"),
        ("Cargar data", "Cargar documentos"),
    ]

    def href(p: str) -> str:
        return f"/?page={quote(p)}"

    buttons_html = ""
    for label, page_name in pages:
        active_class = "active" if active_page == page_name else ""
        buttons_html += (
            f'<a class="fv-nav-link" href="{href(page_name)}">'
            f'  <span class="fv-nav-btn {active_class}">{label}</span>'
            f"</a>"
        )

    st.markdown(
        f"""
        <div class="fv-navbar">
          <div class="fv-navbar-inner">
            <a class="fv-brand" href="{href("Inicio")}">
              <div class="fv-brand-title">FV Consulting</div>
            </a>
            <div class="fv-nav-buttons">
              {buttons_html}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------
# 5) MAIN ROUTER
# ------------------------------------------------------------
def main():
    page = st.query_params.get("page", "Inicio")

    inject_global_css()
    render_navbar(page)

    if page == "Inicio":
        st.title("FV Consulting")
        st.write("Bienvenido a FV Consulting. Aquí encontrarás información sobre servicios y proyectos.")

    elif page == "Blog":
        boletines_app()

    elif page == "Crear blog":
        if crear_blog_app is None:
            st.error("No pude importar crear_blog.py. Revisa que exista y que tenga crear_blog_app() o main().")
            st.info("Ejemplo recomendado en crear_blog.py: def crear_blog_app(): ...")
        else:
            crear_blog_app()

    elif page == "Análisis":
        data_multiple()

    elif page == "Mapas":
        st.title("Mapas")
        st.write("En esta sección podrás crear y visualizar mapas interactivos basados en datos geoespaciales.")

    elif page == "Cargar documentos":
        cargar_documentos()

    else:
        st.warning("Página no reconocida. Volviendo a Inicio...")
        st.query_params["page"] = "Inicio"
        st.rerun()

if __name__ == "__main__":
    main()
