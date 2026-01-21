import streamlit as st

import os
import re
import io
import json
import shutil
import zipfile
import base64
from pathlib import Path


# =============================
# CONFIG
# =============================
BLOG_DIR = Path("blog_posts")
INDEX_FILE = BLOG_DIR / "index.json"
BLOG_DIR.mkdir(exist_ok=True)

# Listado (portada)
LIST_IMG_WIDTH = 320
LIST_ROW_MIN_HEIGHT = 150
LIST_POST_GAP_PX = 14

# Detalle (imágenes dentro del post)
DETAIL_MAX_IMG_WIDTH = 760
DETAIL_COVER_MAX_WIDTH = 900


# =============================
# INDEX / POSTS
# =============================
def load_index():
    if not INDEX_FILE.exists():
        return []
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_index(items):
    INDEX_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_post(post_id: str):
    items = [x for x in load_index() if x.get("id") != post_id]
    save_index(items)
    post_dir = BLOG_DIR / post_id
    if post_dir.exists():
        shutil.rmtree(post_dir, ignore_errors=True)


def zip_folder(folder: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(folder):
            for name in files:
                p = Path(root) / name
                arc = p.relative_to(folder).as_posix()
                z.write(p, arcname=arc)
    buf.seek(0)
    return buf.getvalue()


# =============================
# HELPERS: portada embebida
# =============================
def _guess_mime_from_suffix(p: Path) -> str:
    suf = p.suffix.lower().replace(".", "")
    if suf in ["jpg", "jpeg"]:
        return "image/jpeg"
    if suf == "webp":
        return "image/webp"
    if suf == "gif":
        return "image/gif"
    return "image/png"


def _img_to_b64(path: Path) -> str:
    try:
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception:
        return ""


# =============================
# MARKDOWN RENDER (completo)
# =============================
def render_md_with_local_images(md_text: str, base_dir: Path):
    md = md_text or ""
    pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")

    last = 0
    for m in pattern.finditer(md):
        chunk = md[last:m.start()]
        if chunk.strip():
            st.markdown(chunk, unsafe_allow_html=True)

        alt = (m.group(1) or "").strip()
        rel = (m.group(2) or "").strip().strip('"').strip("'")

        img_path = (base_dir / rel).resolve()
        if img_path.exists() and img_path.is_file():
            st.image(
                str(img_path),
                caption=alt if alt else None,
                width=DETAIL_MAX_IMG_WIDTH,
            )
        else:
            st.warning(f"⚠️ No se encuentra la imagen: {rel}")
            st.markdown(md[m.start():m.end()], unsafe_allow_html=True)

        last = m.end()

    tail = md[last:]
    if tail.strip():
        st.markdown(tail, unsafe_allow_html=True)


# =============================
# NAV simple interno (detalle/listado)
# =============================
def goto_page(page_name: str):
    st.session_state["page"] = page_name


# =============================
# CATEGORÍAS
# =============================
def get_post_categories(post):
    categories = []
    title_lower = (post.get("title", "") or "").lower()

    if any(word in title_lower for word in ["análisis", "datos", "visualización", "gráfico", "estadística", "dashboard"]):
        categories.append("Análisis de Datos")

    if any(word in title_lower for word in ["mapa", "mapeo", "geográfico", "geoespacial", "sig", "gis", "cartografía", "ubicación"]):
        categories.append("Cartografía")

    if any(word in title_lower for word in ["python", "r ", "código", "programación", "desarrollo", "software", "api"]):
        categories.append("Tecnología")

    if any(word in title_lower for word in ["investigación", "estudio", "censo", "encuesta", "informe", "reporte"]):
        categories.append("Investigación")

    if any(word in title_lower for word in ["ia", "inteligencia artificial", "machine learning", "ai", "modelo"]):
        categories.append("Inteligencia Artificial")

    if any(word in title_lower for word in ["consultoría", "estrategia", "consulta", "asesoría", "solución"]):
        categories.append("Consultoría")

    if any(word in title_lower for word in ["accesibilidad", "usabilidad", "navegación", "experiencia"]):
        categories.append("Accesibilidad")

    if any(word in title_lower for word in ["abierto", "open data", "transparencia", "público"]):
        categories.append("Datos Abiertos")

    if not categories:
        categories.append("General")

    return categories


# =============================
# CSS (SOLO ESTILOS DEL BLOG)
# ✅ NO oculta sidebar
# ✅ NO crea topbar propia
# ✅ NO cambia padding-top (eso lo maneja app.py)
# =============================
def blog_css():
    st.markdown(
        f"""
        <style>
        /* =========================
           BLOG: colores automáticos
           - Se adapta al tema/fondo
           ========================= */

        .blog-title {{
            font-size: 44px;
            font-weight: 800;
            margin: 8px 0 10px 0;
            color: inherit;
        }}

        .blog-divider {{
            height: 2px;
            background: #0f607a;
            margin: 10px 0 16px 0;
        }}

        .post-sep {{
            height: 2px;
            background: #0f607a;
            margin: {LIST_POST_GAP_PX}px 0;
        }}

        .post-title {{
            font-size: 28px;
            font-weight: 800;
            margin: 0 0 6px 0;
            line-height: 1.15;
            color: inherit; /* ✅ automático */
        }}

        .post-meta {{
            font-size: 13px;
            margin: 4px 0;
            line-height: 1.4;
            color: rgba(127,127,127,0.9); /* ✅ neutro, funciona en ambos fondos */
        }}

        .tag {{
            display: inline-block;
            font-size: 11px;
            padding: 4px 11px;
            border-radius: 6px;
            border: 1px solid rgba(127,127,127,0.35);
            background: rgba(127,127,127,0.08);
            color: inherit; /* ✅ automático */
            width: fit-content;
            margin: 6px 0 8px 0;
        }}

        .post-excerpt {{
            font-size: 14.5px;
            line-height: 1.5;
            max-height: 66px;
            overflow: hidden;
            margin: 8px 0 10px 0;
            color: inherit;       /* ✅ automático */
            opacity: 0.85;        /* ✅ suaviza en ambos fondos */
        }}

        .post-img {{
            width: {LIST_IMG_WIDTH}px;
            height: {LIST_ROW_MIN_HEIGHT}px;
            overflow: hidden;
            background: transparent;
            border: none;
        }}
        .post-img img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
        }}

        /* Inputs: dejamos estilo limpio sin forzar blanco absoluto */
        div[data-baseweb="select"] > div {{
            border-radius: 10px !important;
        }}
        input[type="text"] {{
            border-radius: 10px !important;
        }}

        .cat-title {{
            font-weight: 800;
            font-size: 17px;
            margin-top: 10px;
            margin-bottom: 12px;
            color: inherit; /* ✅ automático */
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# =============================
# FILTRO POR PALABRAS
# =============================
def filter_posts_by_keywords(posts, query):
    if not query:
        return posts
    keywords = query.lower().split()
    filtered = []
    for post in posts:
        title = (post.get("title", "") or "").lower()
        if any(keyword in title for keyword in keywords):
            filtered.append(post)
    return filtered


# =============================
# BLOG (LISTADO)
# =============================
def page_blog():
    blog_css()

    st.session_state.setdefault("confirm_delete_blog_id", None)
    st.session_state.setdefault("blog_selected_cat", "Todos")
    st.session_state.setdefault("blog_order", "Fecha (más reciente)")
    st.session_state.setdefault("blog_filter", "")

    items = load_index()

    col_main, col_side = st.columns([10, 2.5], vertical_alignment="top")

    with col_main:
        st.markdown('<div class="blog-title">Blog</div>', unsafe_allow_html=True)

        a, b = st.columns([1.2, 1.6], vertical_alignment="bottom")
        with a:
            st.write("**Ordar por:**")
            order = st.selectbox(
                "",
                ["Fecha (más reciente)", "Fecha (más antigua)", "Título (A→Z)", "Título (Z→A)"],
                index=["Fecha (más reciente)", "Fecha (más antigua)", "Título (A→Z)", "Título (Z→A)"].index(
                    st.session_state.get("blog_order", "Fecha (más reciente)")
                ),
                label_visibility="collapsed",
                key="order_pick",
            )
            st.session_state["blog_order"] = order

        with b:
            st.write("**Buscar:**")
            q = st.text_input(
                "",
                value=st.session_state.get("blog_filter", ""),
                placeholder="Escribe una palabra...",
                label_visibility="collapsed",
                key="filter_pick",
            )
            st.session_state["blog_filter"] = q

        st.markdown('<div class="blog-divider"></div>', unsafe_allow_html=True)

        if not items:
            st.info("No hay publicaciones aún.")
            return

        selected_cat = st.session_state.get("blog_selected_cat", "Todos")
        filtered = items[:]

        if selected_cat != "Todos":
            filtered = [p for p in filtered if selected_cat in get_post_categories(p)]

        q = (st.session_state.get("blog_filter") or "").strip()
        if q:
            filtered = filter_posts_by_keywords(filtered, q)

        ord_mode = st.session_state.get("blog_order", "Fecha (más reciente)")
        if ord_mode == "Fecha (más antigua)":
            filtered = sorted(filtered, key=lambda x: x.get("created_at", ""))
        elif ord_mode == "Fecha (más reciente)":
            filtered = sorted(filtered, key=lambda x: x.get("created_at", ""), reverse=True)
        elif ord_mode == "Título (A→Z)":
            filtered = sorted(filtered, key=lambda x: (x.get("title", "") or "").lower())
        elif ord_mode == "Título (Z→A)":
            filtered = sorted(filtered, key=lambda x: (x.get("title", "") or "").lower(), reverse=True)

        if not filtered:
            st.info("No hay resultados para tu búsqueda.")
            return

        for post in filtered:
            post_id = post.get("id", "")
            title = post.get("title", "Sin título")
            created = post.get("created_at", "")
            desc = (post.get("description", "") or "")
            if len(desc) > 160:
                desc = desc[:157] + "..."

            left, right = st.columns([1.15, 0.85], vertical_alignment="top")

            with left:
                st.markdown(f'<div class="post-title">{title}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="post-meta">{created}<br>FV Consulting</div>', unsafe_allow_html=True)

                cats = get_post_categories(post)
                if cats:
                    st.markdown(f'<span class="tag">{cats[0]}</span>', unsafe_allow_html=True)

                if desc:
                    st.markdown(f'<div class="post-excerpt">{desc}</div>', unsafe_allow_html=True)

                b1, b2, _ = st.columns([1, 1, 6])
                if b1.button("Ver", key=f"view_{post_id}", use_container_width=True):
                    st.session_state["selected_post_id"] = post_id
                    goto_page("Detalle")
                    st.rerun()

                if b2.button("🗑️", key=f"del_{post_id}", use_container_width=True):
                    st.session_state["confirm_delete_blog_id"] = post_id
                    st.rerun()

                if st.session_state.get("confirm_delete_blog_id") == post_id:
                    st.warning("¿Eliminar?")
                    cA, cB = st.columns(2)
                    if cA.button("✅ Sí", key=f"yes_{post_id}", use_container_width=True):
                        delete_post(post_id)
                        st.session_state["confirm_delete_blog_id"] = None
                        st.rerun()
                    if cB.button("❌ No", key=f"no_{post_id}", use_container_width=True):
                        st.session_state["confirm_delete_blog_id"] = None
                        st.rerun()

            with right:
                cover = (post.get("cover", "") or "").strip()
                if cover:
                    post_dir = BLOG_DIR / post_id
                    p = (post_dir / cover).resolve()
                    if p.exists():
                        b64 = _img_to_b64(p)
                        if b64:
                            mime = _guess_mime_from_suffix(p)
                            st.markdown(
                                f"""
                                <div class="post-img">
                                  <img src="data:{mime};base64,{b64}" />
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

            st.markdown('<div class="post-sep"></div>', unsafe_allow_html=True)

    with col_side:
        st.markdown('<div class="cat-title">Categorías:</div>', unsafe_allow_html=True)

        cat_counts = {}
        for post in items:
            for c in get_post_categories(post):
                cat_counts[c] = cat_counts.get(c, 0) + 1

        if st.button(f"Todos ({len(items)})", use_container_width=True, key="cat_all"):
            st.session_state["blog_selected_cat"] = "Todos"
            st.rerun()

        for cat in sorted(cat_counts.keys(), key=lambda x: x.lower()):
            if st.button(f"{cat} ({cat_counts[cat]})", use_container_width=True, key=f"cat_{cat}"):
                st.session_state["blog_selected_cat"] = cat
                st.rerun()


# =============================
# DETALLE
# =============================
def page_detail():
    blog_css()

    post_id = st.session_state.get("selected_post_id")
    if not post_id:
        st.info("Selecciona una publicación desde el Blog.")
        return

    post = next((x for x in load_index() if x.get("id") == post_id), None)
    if not post:
        st.error("Publicación no encontrada.")
        return

    post_dir = BLOG_DIR / post_id
    md_path = post_dir / "post.md"
    if not md_path.exists():
        st.error("No existe post.md en esta publicación.")
        return

    md_text = md_path.read_text(encoding="utf-8")

    if st.button("← Volver al Blog", use_container_width=False):
        goto_page("Blog")
        st.rerun()

    render_md_with_local_images(md_text, post_dir)


# =============================
# MAIN
# =============================
def boletines_app():
    st.session_state.setdefault("page", "Blog")

    if st.session_state["page"] == "Blog":
        page_blog()
    else:
        page_detail()


if __name__ == "__main__":
    boletines_app()
