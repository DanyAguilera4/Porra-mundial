import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(layout="wide", page_title="Porra Mundialista")
st.title("⚽ Porra Mundialista - Dashboard Oficial ⚽")

# Configuración de Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
client = gspread.authorize(creds)
# REEMPLAZA ESTO CON TU ID DE LA HOJA
sheet_id = '17hH1ixuvI16PCtYsbInV2iluF33w1Bg5' 
sh = client.open_by_key(sheet_id)

# Función para cargar datos
def load_data(sheet_name):
    return pd.DataFrame(sh.worksheet(sheet_name).get_all_records())

# Carga inicial
df_apuestas = load_data('Apuestas')
fases_disponibles = [w.title for w in sh.worksheets() if w.title != 'Apuestas']

# --- 🏆 RANKING ---
st.header("🏆 Clasificación General 🏆")
if not df_apuestas.empty and 'Puntos' in df_apuestas.columns:
    ranking = df_apuestas.groupby('Usuario')['Puntos'].sum().sort_values(ascending=False)
    st.bar_chart(ranking)

st.divider()

# --- 📝 ZONA DE PREDICCIONES ---
st.subheader("📝 Realizar Predicciones")
fase_user = st.selectbox("Selecciona la ronda:", fases_disponibles)
df_fase = load_data(fase_user)

# Formateo
df_fase['Fecha'] = pd.to_datetime(df_fase['Fecha']).dt.strftime('%d/%m/%y')
df_fase['Hora'] = pd.to_datetime(df_fase['Hora'], format='%H:%M:%S').dt.strftime('%H:%M')

usuario = st.text_input("Tu Nombre:")
columnas_ordenadas = ['Local', 'Visita', 'Fecha', 'Hora']
df_editor = df_fase[columnas_ordenadas].copy()
df_editor['Pred_Local'] = 0
df_editor['Pred_Visita'] = 0

preds = st.data_editor(df_editor, hide_index=True, use_container_width=True)

if st.button("Guardar Predicciones"):
    if not usuario: st.error("Ingresa tu nombre.")
    else:
        nuevas = []
        for _, row in preds.iterrows():
            nuevas.append({'Usuario': usuario, 'Partido': f"{row['Local']} vs {row['Visita']}", 
                           'Pred_Local': row['Pred_Local'], 'Pred_Visita': row['Pred_Visita'], 'Puntos': 0})
        
        # Añadir filas a la hoja de Apuestas
        worksheet_apuestas = sh.worksheet('Apuestas')
        for n in nuevas:
            worksheet_apuestas.append_row(list(n.values()))
        st.success("¡Guardado en la nube!")