import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="Polla Mundialista")
st.title("⚽ Polla Mundialista - Dashboard Oficial")

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def get_client():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

client = get_client()
sheet_id = '1-n82WoLSk3b0XE59qIaTrf69R44qAAqu6iJqlDj0RDI' 
sh = client.open_by_key(sheet_id)

def load_data(sheet_name):
    return pd.DataFrame(sh.worksheet(sheet_name).get_all_records())

# --- CARGA DE DATOS ---
df_apuestas = load_data('Apuestas')
fases_disponibles = [w.title for w in sh.worksheets() if w.title != 'Apuestas']

# --- 🏆 RANKING ---
st.header("📊 Clasificación General")
if not df_apuestas.empty and 'Puntos' in df_apuestas.columns:
    ranking = df_apuestas.groupby('Usuario')['Puntos'].sum().sort_values(ascending=False)
    c_r1, c_r2 = st.columns([1, 2])
    with c_r1:
        st.dataframe(ranking, use_container_width=True)
    with c_r2:
        st.bar_chart(ranking)
else:
    st.info("Aún no hay predicciones guardadas.")

st.divider()

# --- ⚙️ ZONA ADMINISTRADOR ---
with st.expander("⚙️ Zona Administrador: Registrar Resultados"):
    fase_admin = st.selectbox("Selecciona la fase:", fases_disponibles)
    df_admin = load_data(fase_admin)
    
    lista_partidos = df_admin['Local'] + " vs " + df_admin['Visita']
    partido_sel = st.selectbox("Partido:", lista_partidos)
    idx = lista_partidos[lista_partidos == partido_sel].index[0]
    
    c1, c2 = st.columns(2)
    r_l = c1.number_input(f"Goles {df_admin.at[idx, 'Local']}", 0)
    r_v = c2.number_input(f"Goles {df_admin.at[idx, 'Visita']}", 0)
    
    if st.button("Guardar y Recalcular"):
        # 1. Actualizar resultados reales en Google Sheets
        df_admin.at[idx, 'Goles_Real_Local'] = r_l
        df_admin.at[idx, 'Goles_Real_Visita'] = r_v
        sh.worksheet(fase_admin).update([df_admin.columns.values.tolist()] + df_admin.values.tolist())
        
        # 2. Recalcular puntos
        partido_str = f"{df_admin.at[idx, 'Local']} vs {df_admin.at[idx, 'Visita']}"
        for i, row in df_apuestas.iterrows():
            if row['Partido'] == partido_str:
                puntos = 3 if row['Pred_Local'] == r_l and row['Pred_Visita'] == r_v else \
                         (1 if (row['Pred_Local'] > row['Pred_Visita'] and r_l > r_v) or \
                               (row['Pred_Local'] < row['Pred_Visita'] and r_l < r_v) or \
                               (row['Pred_Local'] == row['Pred_Visita'] and r_l == r_v) else 0)
                df_apuestas.at[i, 'Puntos'] = puntos
        
        # 3. Guardar puntos en Google Sheets
        sh.worksheet('Apuestas').update([df_apuestas.columns.values.tolist()] + df_apuestas.values.tolist())
        st.success("¡Resultado guardado y Ranking actualizado!")

# --- 📝 ZONA DE PREDICCIONES ---
st.subheader("📝 Realizar Predicciones")
fase_user = st.selectbox("Selecciona la ronda:", fases_disponibles)
df_fase = load_data(fase_user)
    
# Formateo robusto (evita error de fechas)
df_fase['Fecha'] = pd.to_datetime(df_fase['Fecha'], errors='coerce').dt.strftime('%d/%m/%y').fillna("Sin fecha")
df_fase['Hora'] = pd.to_datetime(df_fase['Hora'], format='%H:%M:%S', errors='coerce').dt.strftime('%H:%M').fillna("00:00")
    
usuario = st.text_input("Tu Nombre:")
df_editor = df_fase[['Local', 'Visita', 'Fecha', 'Hora']].copy()
df_editor['Pred_Local'] = 0
df_editor['Pred_Visita'] = 0
    
preds = st.data_editor(df_editor, hide_index=True, use_container_width=True)

if st.button("Guardar Predicciones"):
    if not usuario: st.error("Ingresa tu nombre.")
    else:
        nuevas = [[usuario, f"{row['Local']} vs {row['Visita']}", row['Pred_Local'], row['Pred_Visita'], 0] 
                  for _, row in preds.iterrows()]
        sh.worksheet('Apuestas').append_rows(nuevas)
        st.success("¡Predicciones guardadas en la nube!")