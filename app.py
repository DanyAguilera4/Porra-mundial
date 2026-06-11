import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe

# --- CONFIGURACIÓN ---
st.set_page_config(layout="centered", page_title="Porra Mundialista") # Cambiado a 'centered' para móvil
st.title("⚽ Porra Mundialista")

# --- CONEXIÓN ---
@st.cache_resource
def get_connection():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

client = get_connection()
sh = client.open_by_key('1-n82WoLSk3b0XE59qIaTrf69R44qAAqu6iJqlDj0RDI')

@st.cache_data(ttl=10)
def load_data(sheet_name):
    try:
        data = sh.worksheet(sheet_name).get_all_records()
        if not data: return pd.DataFrame(columns=['Usuario', 'Partido', 'Pred_Local', 'Pred_Visita', 'Puntos', 'Jornada'])
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# --- INTERFAZ ---
hojas = [w.title for w in sh.worksheets() if w.title != 'Apuestas']

# 1. RANKING (Minimizado)
with st.expander("🏆 Ver Ranking"):
    df_apuestas = load_data('Apuestas')
    if not df_apuestas.empty and 'Puntos' in df_apuestas.columns:
        df_apuestas['Puntos'] = pd.to_numeric(df_apuestas['Puntos'])
        ranking = df_apuestas.groupby('Usuario')['Puntos'].sum().sort_values(ascending=False).reset_index()
        st.table(ranking)

# 2. ZONA PREDICCIONES
st.subheader("📝 Predicciones")
lista_usuarios = ["Dany", "Dani Veliz", "Raúl", "Andoni", "Endika", "Mikel", "Igor", "Jonathan", "Alberto", "Jon", "Hiago"]
usuario = st.selectbox("¿Quién eres?", lista_usuarios)
fase_user = st.selectbox("Fase:", hojas)
df_fase = load_data(fase_user)
jornada_user = st.selectbox("Jornada:", sorted(df_fase['Jornada'].unique()))
df_fase_filt = df_fase[df_fase['Jornada'] == jornada_user]

# Lógica de filtrado
if 'Usuario' in df_apuestas.columns:
    apuestas_usuario = df_apuestas[df_apuestas['Usuario'] == usuario].copy()
    apuestas_usuario['partido_norm'] = apuestas_usuario['Partido'].str.strip().str.lower()
    df_pendientes = df_fase_filt[~df_fase_filt.apply(lambda x: f"{x['Local']} vs {x['Visita']}".strip().lower() in apuestas_usuario['partido_norm'].tolist(), axis=1)]
else:
    df_pendientes = df_fase_filt

if df_pendientes.empty:
    st.info(f"¡Todo listo para {usuario} en {jornada_user}!")
else:
    st.write(f"Partidos pendientes: **{len(df_pendientes)}**")
    # Configuración de editor amigable para móvil
    df_editor = df_pendientes[['Local', 'Visita']].copy()
    df_editor['Local_Goles'] = 0
    df_editor['Visita_Goles'] = 0
    
    # El editor es mejor usarlo con pocos campos en móvil
    preds = st.data_editor(df_editor, hide_index=True, use_container_width=True)

    if st.button("Guardar Predicciones", type="primary", use_container_width=True):
        pendientes = preds.dropna()
        with st.status("Guardando...", expanded=False) as status:
            nuevas = [[usuario, f"{row['Local']} vs {row['Visita']}", int(row['Local_Goles']), int(row['Visita_Goles']), 0] 
                      for _, row in pendientes.iterrows()]
            sh.worksheet('Apuestas').append_rows(nuevas)
            st.cache_data.clear()
            status.update(label="¡Guardado!", state="complete")
        st.rerun()

# 3. ADMINISTRADOR (Oculto al final)
with st.expander("⚙️ Admin"):
    # (Aquí mantienes tu código anterior de admin, pero dentro de un expander cerrado)
    st.write("Solo para admin...")