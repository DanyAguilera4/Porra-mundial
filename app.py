import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(layout="wide", page_title="Porra Mundialista")
st.title("⚽ Porra Mundialista - Dashboard Oficial ⚽")

# --- CONEXIÓN SEGURA A GOOGLE SHEETS ---
creds_dict = st.secrets["gcp_service_account"]
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# ID de la hoja de cálculo (formato Google Sheets nativo)
sheet_id = '1-n82WoLSk3b0XE59qIaTrf69R44qAAqu6iJqlDj0RDI' 
sh = client.open_by_key(sheet_id)

def load_data(sheet_name):
    return pd.DataFrame(sh.worksheet(sheet_name).get_all_records())

# --- ZONA DE ADMINISTRADOR ---
with st.sidebar:
    st.header("⚙️ Panel Admin")
    admin_pass = st.text_input("Contraseña Admin", type="password")
    if admin_pass == "1234": # Cambia "1234" por tu contraseña real
        st.success("Acceso Admin concedido")
        if st.button("Recargar datos"):
            st.cache_data.clear()
        st.subheader("Datos de Apuestas")
        st.dataframe(load_data('Apuestas'))
    else:
        st.info("Introduce contraseña para ver panel admin")

# --- CARGA INICIAL ---
try:
    df_apuestas = load_data('Apuestas')
    fases_disponibles = [w.title for w in sh.worksheets() if w.title != 'Apuestas']
except Exception as e:
    st.error(f"Error cargando los datos: {e}")
    st.stop()

# --- RANKING ---
st.header("🏆 Clasificación General 🏆")
if not df_apuestas.empty and 'Puntos' in df_apuestas.columns:
    ranking = df_apuestas.groupby('Usuario')['Puntos'].sum().sort_values(ascending=False)
    col1, col2 = st.columns([1, 2])
    with col1:
        st.dataframe(ranking, use_container_width=True)
    with col2:
        st.bar_chart(ranking)
else:
    st.info("Aún no hay predicciones guardadas o puntos registrados.")

st.divider()

# --- ZONA DE PREDICCIONES ---
st.subheader("📝 Realizar Predicciones")
fase_user = st.selectbox("Selecciona la ronda:", fases_disponibles)
df_fase = load_data(fase_user)

# --- CORRECCIÓN ORDEN Y FORMATO DE FECHAS ---
# Convertimos a fechas reales para ordenar cronológicamente
df_fase['Fecha_dt'] = pd.to_datetime(df_fase['Fecha'], errors='coerce')
df_fase['Hora_dt'] = pd.to_datetime(df_fase['Hora'], format='%H:%M:%S', errors='coerce')
df_fase = df_fase.sort_values(by=['Fecha_dt', 'Hora_dt'])

# Formateamos para mostrar al usuario
df_fase['Fecha'] = df_fase['Fecha_dt'].dt.strftime('%d/%m/%y').fillna("Sin fecha")
df_fase['Hora'] = df_fase['Hora_dt'].dt.strftime('%H:%M').fillna("00:00")
df_fase = df_fase.drop(columns=['Fecha_dt', 'Hora_dt'])

usuario = st.text_input("Tu Nombre:")

# Preparar tabla para el editor
columnas_ordenadas = ['Local', 'Visita', 'Fecha', 'Hora']
df_editor = df_fase[columnas_ordenadas].copy()
df_editor['Pred_Local'] = 0
df_editor['Pred_Visita'] = 0

preds = st.data_editor(
    df_editor, 
    hide_index=True, 
    use_container_width=True,
    column_config={
        "Pred_Local": st.column_config.NumberColumn("Goles Local", min_value=0),
        "Pred_Visita": st.column_config.NumberColumn("Goles Visita", min_value=0),
    }
)

if st.button("Guardar Predicciones"):
    if not usuario: 
        st.error("Por favor, ingresa tu nombre.")
    else:
        worksheet_apuestas = sh.worksheet('Apuestas')
        for _, row in preds.iterrows():
            worksheet_apuestas.append_row([usuario, f"{row['Local']} vs {row['Visita']}", 
                                           row['Pred_Local'], row['Pred_Visita'], 0])
        st.success(f"¡Predicciones guardadas para {usuario}!")
        st.balloons()