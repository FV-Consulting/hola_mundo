import streamlit as st

st.title("Login test")

if not st.user.is_logged_in:
    st.button("Login con Google", on_click=st.login)
    st.stop()

st.success(f"Hola {st.user.name} — {st.user.email}")
st.button("Logout", on_click=st.logout)
