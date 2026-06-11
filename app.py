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

# ID de tu hoja de cálculo convertido a Google Sheets
sheet_id = '1-n82WoLSk3b0XE59qIaTrf69R44qAAqu6iJqlDj0RDI' 
sh = client.open_by_key(sheet_id)

# Función para cargar datos
def load_data(sheet_name):
    worksheet = sh.worksheet(sheet_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

# --- PANEL DE ADMINISTRADOR (Sidebar) ---
with st.sidebar:
    st.header("⚙️ Panel de Control")
    admin_pass = st.text_input("Contraseña Administrador", type="password")
    
    if admin_pass == "1234":
        st.success("Acceso Admin concedido")
        st.divider()
        st.subheader("Registrar Resultados Oficiales")
        
        # Selección de fase para actualizar resultados
        todas_las_fases = [w.title for w in sh.worksheets() if w.title != 'Apuestas']
        fase_admin = st.selectbox("Selecciona fase para añadir resultados:", todas_las_fases)
        
        df_admin = load_data(fase_admin)
        
        # Editor para que el admin ponga los goles reales
        st.write(f"Introduce los goles reales para {fase_admin}:")
        admin_editor = st.data_editor(
            df_admin,
            hide_index=True,
            use_container_width=True,
            disabled=("Local", "Visita", "Fecha", "Hora") # El admin solo edita goles
        )
        
        if st.button("Actualizar Resultados Oficiales"):
            try:
                ws_actualizar = sh.worksheet(fase_admin)
                # Convertimos el dataframe editado a lista de listas para subirlo
                # Incluimos los encabezados
                datos_nuevos = [admin_editor.columns.values.tolist()] + admin_editor.values.tolist()
                
                # Limpiar y actualizar la hoja completa
                ws_actualizar.clear()
                ws_actualizar.update('A1', datos_nuevos)
                
                st.success(f"¡Resultados de {fase_admin} actualizados correctamente!")
                st.balloons()
            except Exception as e:
                st.error(f"Error al actualizar: {e}")
    else:
        st.info("Introduce la contraseña para gestionar resultados oficiales.")

# --- CARGA DE DATOS PARA USUARIOS ---
try:
    df_apuestas = load_data('Apuestas')
    fases_disponibles = [w.title for w in sh.worksheets() if w.title != 'Apuestas']
except Exception as e:
    st.error(f"Error cargando los datos: {e}")
    st.stop()

# --- 🏆 RANKING ---
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

# --- 📝 ZONA DE PREDICCIONES (USUARIOS) ---
st.subheader("📝 Realizar Predicciones")
fase_user = st.selectbox("Selecciona la ronda para apostar:", fases_disponibles, key="user_fase")
df_fase = load_data(fase_user)

# --- FORMATEO ROBUSTO DE FECHAS ---
df_fase['Fecha_dt'] = pd.to_datetime(df_fase['Fecha'], errors='coerce')
df_fase['Hora_dt'] = pd.to_datetime(df_fase['Hora'], format='%H:%M:%S', errors='coerce')
df_fase = df_fase.sort_values(by=['Fecha_dt', 'Hora_dt'])

df_fase['Fecha_Show'] = df_fase['Fecha_dt'].dt.strftime('%d/%m/%y').fillna("Sin fecha")
df_fase['Hora_Show'] = df_fase['Hora_dt'].dt.strftime('%H:%M').fillna("00:00")

usuario = st.text_input("Tu Nombre:")

# Preparar tabla para el usuario
df_user_editor = pd.DataFrame({
    'Local': df_fase['Local'],
    'Visita': df_fase['Visita'],
    'Fecha': df_fase['Fecha_Show'],
    'Hora': df_fase['Hora_Show'],
    'Pred_Local': 0,
    'Pred_Visita': 0
})

preds = st.data_editor(
    df_user_editor, 
    hide_index=True, 
    use_container_width=True,
    column_config={
        "Pred_Local": st.column_config.NumberColumn("Goles Local", min_value=0),
        "Pred_Visita": st.column_config.NumberColumn("Goles Visita", min_value=0),
    }
)

if st.button("Guardar Mis Predicciones"):
    if not usuario: 
        st.error("Por favor, ingresa tu nombre.")
    else:
        worksheet_apuestas = sh.worksheet('Apuestas')
        filas_nuevas = []
        for _, row in preds.iterrows():
            filas_nuevas.append([
                usuario, 
                f"{row['Local']} vs {row['Visita']}", 
                row['Pred_Local'], 
                row['Pred_Visita'], 
                0 # Puntos iniciales
            ])
        
        # Subir todas las filas nuevas
        worksheet_apuestas.append_rows(filas_nuevas)
        st.success(f"¡Predicciones guardadas correctamente para {usuario}!")
        st.balloons()