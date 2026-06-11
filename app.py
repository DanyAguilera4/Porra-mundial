import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide", page_title="Polla Mundialista")
st.title("⚽ Polla Mundialista - Dashboard Oficial")

# --- CONEXIÓN ---
@st.cache_resource
def get_client():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

client = get_client()
sheet_id = '1-n82WoLSk3b0XE59qIaTrf69R44qAAqu6iJqlDj0RDI' 
sh = client.open_by_key(sheet_id)

# --- FUNCIÓN DE CARGA SEGURA ---
def load_data_safe(sheet_name):
    ws = sh.worksheet(sheet_name)
    data = ws.get_all_values() # Obtiene todo como lista de listas
    if not data: return pd.DataFrame()
    # Convertir a DataFrame usando la primera fila como cabecera
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

# --- CARGA ---
df_apuestas = load_data_safe('Apuestas')
fases_disponibles = [w.title for w in sh.worksheets() if w.title != 'Apuestas']

# --- ZONA ADMIN ---
with st.expander("⚙️ Zona Administrador"):
    fase_admin = st.selectbox("Fase:", fases_disponibles)
    df_admin = load_data_safe(fase_admin)
    st.write(df_admin) # Solo mostrar para ver si carga

# --- RANKING ---
st.header("📊 Clasificación")
if not df_apuestas.empty and 'Puntos' in df_apuestas.columns:
    df_apuestas['Puntos'] = pd.to_numeric(df_apuestas['Puntos'], errors='coerce').fillna(0)
    ranking = df_apuestas.groupby('Usuario')['Puntos'].sum().sort_values(ascending=False)
    st.dataframe(ranking)