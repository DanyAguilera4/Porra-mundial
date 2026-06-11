import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Polla Mundialista")
st.title("⚽ Polla Mundialista")

# --- CONEXIÓN ---
@st.cache_resource
def get_connection():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

client = get_connection()
sh = client.open_by_key('1-n82WoLSk3b0XE59qIaTrf69R44qAAqu6iJqlDj0RDI')

# Función con caché para los datos (usar st.cache_data)
@st.cache_data(ttl=60) # Refresca datos cada 60 segundos
def load_data(sheet_name):
    return pd.DataFrame(sh.worksheet(sheet_name).get_all_records())

# --- LÓGICA ---
df_apuestas = load_data('Apuestas')
fases_disponibles = [w.title for w in sh.worksheets() if w.title != 'Apuestas']

# --- ZONA ADMINISTRADOR ---
with st.expander("⚙️ Zona Administrador"):
    fase_admin = st.selectbox("Fase:", fases_disponibles)
    df_admin = load_data(fase_admin)
    
    partido_sel = st.selectbox("Partido:", df_admin['Local'] + " vs " + df_admin['Visita'])
    idx = df_admin[df_admin['Local'] + " vs " + df_admin['Visita'] == partido_sel].index[0]
    
    r_l = st.number_input("Goles Local", 0)
    r_v = st.number_input("Goles Visita", 0)
    
    if st.button("Guardar Resultados"):
        # Actualizar hoja de resultados
        ws = sh.worksheet(fase_admin)
        ws.update_cell(idx + 2, df_admin.columns.get_loc('Goles_Real_Local') + 1, r_l)
        ws.update_cell(idx + 2, df_admin.columns.get_loc('Goles_Real_Visita') + 1, r_v)
        st.success("Resultados guardados")
        st.rerun()

# --- ZONA DE PREDICCIONES ---
st.subheader("📝 Tus Predicciones")
usuario = st.text_input("Nombre de usuario:")
fase_user = st.selectbox("Selecciona ronda:", fases_disponibles)
df_fase = load_data(fase_user)

# Editor de datos optimizado
preds = st.data_editor(df_fase[['Local', 'Visita']], num_rows="dynamic")

if st.button("Enviar Predicciones"):
    if not usuario:
        st.error("Ingresa tu nombre")
    else:
        # Aquí deberías implementar una lógica para buscar si el usuario ya apostó
        # y usar ws.update() en lugar de append_rows para evitar duplicados.
        st.info("Funcionalidad de guardado lista para implementar con ws.update()")