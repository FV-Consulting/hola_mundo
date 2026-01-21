import streamlit as st
import requests

st.title("eje,plo incio de sesion")

def login_screen():
    st.header("esta app es privada")
    st.subheader("por favor incia sesion")
    #crearemos un boton para inciar sesion inicia el flujo gracias al argumento on_click=st.login
    #st.login()es unba funcion nativa de streamlir que redirige al usualo a la pag de google
    # el texto "material/login:" es un atajo para usar los iconos de material design
    st.button(":material/lgin: Iniciar Sesión con Google", on_click=st.login)

#============================================
#LOGICA GENERAL DEL CODIGO 
#======================================

#stexperimental_user es un objeto qeu contine la informacion del usuario autenticado
#el atributo .islogged_in devuelve true si el usuario a iniciado sesion y false en caso contrario.
#este condicional es el nucleo de la aplicacion: decide si mostrar la pantalla de login o el contenido pincipal 
if not st.user.is_authenticated:
    login_screen()
else:
    #si el usuario SI ha iniciado sesion se ejecuta el bloque de codigo
    #usamos with st.sidebar para que todo el contenido indentado a continuacion 
    #aparezca en la barra lateral de la aplicacion
    with st.sidebar:
        #creamos el contenedor para organizar mejor los elementos de la barra lateral 
        with st.container():
            #dividimos el contenedor en dos columnas para alinear la imagen y la informacion del usuario. 
            #el ratio [1,3] significa que la segunda columna sera 3 veces mas ancha qeu la primera

            c1, c2 = st.columns([1,3])
            with c1:
                #verificamos si el objeto de usuario continee una url de imagen de perfil
                if st.user.picture:
                    try:
                        #usamos requests para hacer una peticion get a la url de la imgen
                        response = requests.get(st.user.picture)
                        #si el codifo de estado en la respuesta es 200 (ok) significa que la imagen se obtuvo bien
                        if response.status_code == 200:
                            st.image(response.content,width =100)
                        else:
                            st.warning("no se pudo cargar mg")
                    except Exception as e:
                        st.warning(f"error al cargar img:{e}")
                else:
                    st.info("el usuario no cuenta con img")

            with c2: 
                st.header("información del Usuario")
                st.write(f"**Nombre:**\n{st.user.name}")
                st.write(f"**Correo electronico:**\n{st.user.email}")

        #creamos el boton par cerrar sesion 
        st.button(":material/logout: Cerrar sesión" , on_click=st.logout)


                         