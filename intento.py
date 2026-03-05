import pandas as pd
from sqlalchemy import create_engine
import os
import re

# ============================================================
# ⚙️ CONFIGURACIÓN
# ============================================================
DATABASE_URL = "postgresql://neondb_owner:npg_nXQZR2tolkI1@ep-muddy-dew-ai8xuib9-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
CARPETA_DATOS = "mis_daC:/Users/manue/Fvagconsulting Dropbox/Projects/datos_app.streamlit" # Nombre de la carpeta en tu PC donde están los archivos

def limpiar_nombre_tabla(nombre):
    """Limpia el nombre del archivo para que sea una tabla SQL válida"""
    nombre = nombre.lower()
    nombre = re.sub(r'[^a-z0-9_]', '', nombre.replace(' ', '_'))
    return nombre

def cargar_todo_a_neon():
    if not os.path.exists(CARPETA_DATOS):
        print(f"❌ La carpeta '{CARPETA_DATOS}' no existe. Créala y pon tus archivos allí.")
        return

    engine = create_engine(DATABASE_URL)
    archivos = os.listdir(CARPETA_DATOS)
    
    print(f"🔎 Se encontraron {len(archivos)} archivos. Iniciando subida...\n")

    for archivo in archivos:
        ruta_completa = os.path.join(CARPETA_DATOS, archivo)
        nombre_base, ext = os.path.splitext(archivo)
        ext = ext.lower()
        
        # Saltarse carpetas o archivos ocultos
        if os.path.isdir(ruta_completa) or archivo.startswith('.'):
            continue

        try:
            # --- DETECCIÓN Y LECTURA ---
            if ext == '.csv':
                df = pd.read_csv(ruta_completa)
            elif ext in ['.xlsx', '.xls', '.xlsm', '.xlsb']:
                engine_ex = 'pyxlsb' if ext == '.xlsb' else 'openpyxl'
                df = pd.read_excel(ruta_completa, engine=engine_ex)
            elif ext == '.parquet':
                df = pd.read_parquet(ruta_completa)
            elif ext == '.json':
                df = pd.read_json(ruta_completa)
            elif ext == '.sav':
                df = pd.read_spss(ruta_completa)
            else:
                print(f"⚠️ Saltando {archivo}: formato no compatible.")
                continue

            # --- LIMPIEZA DE COLUMNAS ---
            df.columns = [re.sub(r'[^a-z0-9_]', '', c.lower().replace(' ', '_')) for c in df.columns]

            # --- CARGA ---
            nombre_tabla = limpiar_nombre_tabla(nombre_base)
            print(f"🚀 Subiendo '{archivo}' como tabla '{nombre_tabla}'...")
            
            df.to_sql(nombre_tabla, engine, if_exists='replace', index=False)
            print(f"✅ {archivo} cargado correctamente.")

        except Exception as e:
            print(f"❌ Error cargando {archivo}: {e}")

    print("\n✨ Proceso terminado. Todos los datos están en Neon.")

if __name__ == "__main__":
    cargar_todo_a_neon()