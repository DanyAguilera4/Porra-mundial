import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe

# --- CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Porra Mundialista")
st.title("⚽ Porra Mundialista - EIC")

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
    return pd.DataFrame(sh.worksheet(sheet_name).get_all_records())

# --- LÓGICA DE PUNTUACIÓN ---
def calcular_puntos(pred_local, pred_visita, real_local, real_visita):
    if pred_local == real_local and pred_visita == real_visita:
        return 3
    pred_g = "L" if pred_local > pred_visita else ("V" if pred_visita > pred_local else "E")
    real_g = "L" if real_local > real_visita else ("V" if real_visita > real_local else "E")
    return 1 if pred_g == real_g else 0

# --- INTERFAZ ---
fases_disponibles = [w.title for w in sh.worksheets() if w.title != 'Apuestas']

# 1. RANKING
st.header("🏆 Clasificación General 🏆")
df_apuestas = load_data('Apuestas')

if not df_apuestas.empty and 'Puntos' in df_apuestas.columns:
    ranking = df_apuestas.groupby('Usuario')['Puntos'].sum().sort_values(ascending=False).reset_index()
    st.table(ranking)

st.divider()

# 2. ZONA ADMINISTRADOR
with st.expander("⚙️ Zona Administrador: Registrar Resultados"):
    fase_admin = st.selectbox("Fase:", fases_disponibles)
    df_admin = load_data(fase_admin)
    partido_sel = st.selectbox("Partido:", df_admin['Local'] + " vs " + df_admin['Visita'])
    idx = df_admin[df_admin['Local'] + " vs " + df_admin['Visita'] == partido_sel].index[0]
    
    col1, col2 = st.columns(2)
    r_l = col1.number_input("Goles Local", 0, step=1)
    r_v = col2.number_input("Goles Visita", 0, step=1)
    
    if st.button("Guardar y Recalcular Ranking"):
        ws = sh.worksheet(fase_admin)
        ws.update_cell(idx + 2, df_admin.columns.get_loc('Goles_Real_Local') + 1, r_l)
        ws.update_cell(idx + 2, df_admin.columns.get_loc('Goles_Real_Visita') + 1, r_v)
        
        # Recalcular puntos
        partido_str = f"{df_admin.at[idx, 'Local']} vs {df_admin.at[idx, 'Visita']}"
        for i, row in df_apuestas.iterrows():
            if row['Partido'] == partido_str:
                df_apuestas.at[i, 'Puntos'] = calcular_puntos(row['Pred_Local'], row['Pred_Visita'], r_l, r_v)
        set_with_dataframe(sh.worksheet('Apuestas'), df_apuestas)
        st.success("¡Ranking actualizado!")
        st.rerun()

# 3. ZONA PREDICCIONES
st.subheader("📝 Realizar Predicciones")

lista_usuarios = ["Dany", "Dani Veliz", "Raúl", "Andoni", "Endika", "Mikel", "Igor", "Jonathan", "Alberto", "Jon", "Hiago"]
usuario = st.selectbox("Selecciona tu nombre:", lista_usuarios)
fase_user = st.selectbox("Selecciona ronda:", fases_disponibles, key="fase_user")

df_fase = load_data(fase_user)

# Aseguramos que df_apuestas tenga la columna 'Usuario' antes de filtrar
if 'Usuario' in df_apuestas.columns:
    apuestas_usuario = df_apuestas[df_apuestas['Usuario'] == usuario]
    partidos_ya_apostados = apuestas_usuario['Partido'].tolist()
    
    # Filtrar: Mostrar solo lo que falta por apostar
    df_pendientes = df_fase[~df_fase.apply(lambda x: f"{x['Local']} vs {x['Visita']}" in partidos_ya_apostados, axis=1)]
else:
    df_pendientes = df_fase
    st.warning("La hoja de Apuestas está vacía o no tiene la columna 'Usuario'.")

if df_pendientes.empty:
    st.info(f"¡{usuario}, ya has completado todos tus partidos en esta fase!")
else:
    st.write(f"Partidos pendientes para **{usuario}**: {len(df_pendientes)}")
    df_editor = df_pendientes[['Local', 'Visita']].copy()
    df_editor['Pred_Local'] = 0
    df_editor['Pred_Visita'] = 0
    preds = st.data_editor(df_editor, hide_index=True)

    if st.button("Guardar Predicciones"):
        nuevas = [[usuario, f"{row['Local']} vs {row['Visita']}", row['Pred_Local'], row['Pred_Visita'], 0] 
                  for _, row in preds.iterrows()]
        sh.worksheet('Apuestas').append_rows(nuevas)
        st.success("¡Guardado! Tus predicciones han sido registradas.")
        st.rerun()