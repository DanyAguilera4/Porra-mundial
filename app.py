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
    # Asegúrate de tener los secretos configurados en Streamlit Cloud o en .streamlit/secrets.toml
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
        if not data: 
            return pd.DataFrame(columns=['Usuario', 'Partido', 'Pred_Local', 'Pred_Visita', 'Puntos'])
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error cargando {sheet_name}: {e}")
        return pd.DataFrame()

# --- LÓGICA ---
def calcular_puntos(p_l, p_v, r_l, r_v):
    if int(p_l) == int(r_l) and int(p_v) == int(r_v): return 3
    pred_g = "L" if int(p_l) > int(p_v) else ("V" if int(p_v) > int(p_l) else "E")
    real_g = "L" if int(r_l) > int(r_v) else ("V" if int(r_v) > int(r_l) else "E")
    return 1 if pred_g == real_g else 0

# --- INTERFAZ ---
fases_disponibles = [w.title for w in sh.worksheets() if w.title != 'Apuestas']

# 1. RANKING
st.header("🏆 Clasificación General 🏆")
df_apuestas = load_data('Apuestas')
if not df_apuestas.empty and 'Puntos' in df_apuestas.columns:
    df_apuestas['Puntos'] = pd.to_numeric(df_apuestas['Puntos'])
    ranking = df_apuestas.groupby('Usuario')['Puntos'].sum().sort_values(ascending=False).reset_index()
    st.table(ranking)

st.divider()

# 2. ZONA ADMINISTRADOR
with st.expander("⚙️ Zona Administrador"):
    fase_admin = st.selectbox("Selecciona Jornada:", fases_disponibles)
    df_admin = load_data(fase_admin)
    partido_sel = st.selectbox("Partido:", df_admin['Local'] + " vs " + df_admin['Visita'])
    idx = df_admin[df_admin['Local'] + " vs " + df_admin['Visita'] == partido_sel].index[0]
    
    r_l = st.number_input("Goles Local", 0, step=1)
    r_v = st.number_input("Goles Visita", 0, step=1)
    
    if st.button("Guardar y Recalcular"):
        ws = sh.worksheet(fase_admin)
        ws.update_cell(idx + 2, df_admin.columns.get_loc('Goles_Real_Local') + 1, r_l)
        ws.update_cell(idx + 2, df_admin.columns.get_loc('Goles_Real_Visita') + 1, r_v)
        st.cache_data.clear()
        st.success("¡Resultados guardados!")
        st.rerun()

# 3. ZONA PREDICCIONES
st.subheader("📝 Realizar Predicciones")
lista_usuarios = ["Dany", "Dani Veliz", "Raúl", "Andoni", "Endika", "Mikel", "Igor", "Jonathan", "Alberto", "Jon", "Hiago"]
usuario = st.selectbox("Selecciona tu nombre:", lista_usuarios)
fase_user = st.selectbox("Selecciona Jornada:", fases_disponibles)

df_fase = load_data(fase_user)
if 'Usuario' in df_apuestas.columns:
    apuestas_usuario = df_apuestas[df_apuestas['Usuario'] == usuario].copy()
    apuestas_usuario['partido_norm'] = apuestas_usuario['Partido'].str.strip().str.lower()
    df_pendientes = df_fase[~df_fase.apply(lambda x: f"{x['Local']} vs {x['Visita']}".strip().lower() in apuestas_usuario['partido_norm'].tolist(), axis=1)]
else:
    df_pendientes = df_fase

if df_pendientes.empty:
    st.info(f"¡{usuario}, ya has completado todos los partidos de {fase_user}!")
else:
    df_editor = df_pendientes[['Local', 'Visita']].copy()
    df_editor['Pred_Local'] = None
    df_editor['Pred_Visita'] = None
    preds = st.data_editor(df_editor, hide_index=True)

    if st.button("Guardar Predicciones"):
        pendientes = preds.dropna(subset=['Pred_Local', 'Pred_Visita'])
        if not pendientes.empty:
            with st.status("Guardando...", expanded=True) as status:
                nuevas = [[usuario, f"{row['Local']} vs {row['Visita']}", int(row['Pred_Local']), int(row['Pred_Visita']), 0] 
                          for _, row in pendientes.iterrows()]
                sh.worksheet('Apuestas').append_rows(nuevas)
                st.cache_data.clear()
                status.update(label="¡Guardado!", state="complete")
            st.rerun()