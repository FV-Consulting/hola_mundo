import streamlit as st
import requests

st.title("Ejemplo inicio de sesión")

def login_screen():
    st.header("Esta app es privada")
    st.subheader("Por favor inicia sesión")
    st.button(":material/login: Iniciar Sesión con Google", on_click=st.login)

if not st.user.is_logged_in:
    login_screen()
else:
    with st.sidebar:
        c1, c2 = st.columns([1, 3])

        with c1:
            if st.user.picture:
                try:
                    r = requests.get(st.user.picture, timeout=10)
                    if r.status_code == 200:
                        st.image(r.content, width=90)
                    else:
                        st.warning("No se pudo cargar la imagen")
                except Exception as e:
                    st.warning(f"Error al cargar imagen: {e}")
            else:
                st.info("El usuario no tiene imagen")

        with c2:
            st.markdown("### Información del usuario")
            st.write(f"**Nombre:** {st.user.name}")
            st.write(f"**Correo:** {st.user.email}")

        st.button(":material/logout: Cerrar sesión", on_click=st.logout)

    st.success("✅ Sesión iniciada")
