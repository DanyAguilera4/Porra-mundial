import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(layout="wide", page_title="Porra Mundialista")
st.title("⚽ Porra Mundialista - Dashboard Oficial ⚽")

# --- CONEXIÓN SEGURA A GOOGLE SHEETS ---
# Utiliza los secretos configurados en Streamlit Cloud
creds_dict = st.secrets["gcp_service_account"]
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# Tu ID de hoja de cálculo
sheet_id = '1743567490' 
sh = client.open_by_key(sheet_id)

# Función para cargar datos desde las hojas de Google
def load_data(sheet_name):
    return pd.DataFrame(sh.worksheet(sheet_name).get_all_records())

# Carga inicial de datos
try:
    df_apuestas = load_data('Apuestas')
    fases_disponibles = [w.title for w in sh.worksheets() if w.title != 'Apuestas']
except Exception as e:
    st.error(f"Error cargando los datos: {e}")
    st.stop()

# --- 🏆 RANKING (Siempre visible) ---
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

# --- 📝 ZONA DE PREDICCIONES ---
st.subheader("📝 Realizar Predicciones")
fase_user = st.selectbox("Selecciona la ronda:", fases_disponibles)
df_fase = load_data(fase_user)

# Formateo de fechas y horas
df_fase['Fecha'] = pd.to_datetime(df_fase['Fecha']).dt.strftime('%d/%m/%y')
df_fase['Hora'] = pd.to_datetime(df_fase['Hora'], format='%H:%M:%S').dt.strftime('%H:%M')

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
        nuevas = []
        for _, row in preds.iterrows():
            # Creamos la fila para la hoja de Apuestas
            nuevas.append([usuario, f"{row['Local']} vs {row['Visita']}", 
                           row['Pred_Local'], row['Pred_Visita'], 0])
        
        # Añadir filas a la hoja de Apuestas en Google Sheets
        worksheet_apuestas = sh.worksheet('Apuestas')
        for fila in nuevas:
            worksheet_apuestas.append_row(fila)
        
        st.success(f"¡Predicciones guardadas en la nube para {usuario}!")
        st.balloons()