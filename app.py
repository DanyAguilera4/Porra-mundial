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
    try:
        data = sh.worksheet(sheet_name).get_all_records()
        if not data: 
            if sheet_name == 'Apuestas':
                return pd.DataFrame(columns=['Usuario', 'Partido', 'Pred_Local', 'Pred_Visita', 'Puntos', 'Jornada'])
            return pd.DataFrame(columns=['Jornada', 'Local', 'Visita', 'Goles_Real_Local', 'Goles_Real_Visita'])
        return pd.DataFrame(data)
    except:
        # BLINDADO: Si falla la conexión o la hoja no existe, devuelve columnas por defecto para evitar KeyErrors
        if sheet_name == 'Apuestas':
            return pd.DataFrame(columns=['Usuario', 'Partido', 'Pred_Local', 'Pred_Visita', 'Puntos', 'Jornada'])
        return pd.DataFrame(columns=['Jornada', 'Local', 'Visita', 'Goles_Real_Local', 'Goles_Real_Visita'])

# --- LÓGICA DE PUNTUACIÓN ---
def calcular_puntos(pred_local, pred_visita, real_local, real_visita):
    try:
        p_l, p_v, r_l, r_v = int(pred_local), int(pred_visita), int(real_local), int(real_visita)
        if p_l == r_l and p_v == r_v: return 3
        pred_g = "L" if p_l > p_v else ("V" if p_v > p_l else "E")
        real_g = "L" if r_l > r_v else ("V" if r_v > r_l else "E")
        return 1 if pred_g == real_g else 0
    except:
        return 0

# --- INTERFAZ ---
hojas = [w.title for w in sh.worksheets() if w.title != 'Apuestas']

# 1. RANKING
st.header("🏆 Clasificación General 🏆")
df_apuestas = load_data('Apuestas')
if not df_apuestas.empty and 'Puntos' in df_apuestas.columns:
    # BLINDADO: Convierte a numérico de forma segura ignorando textos extraños o celdas vacías vacías
    df_apuestas['Puntos'] = pd.to_numeric(df_apuestas['Puntos'], errors='coerce').fillna(0)
    ranking = df_apuestas.groupby('Usuario')['Puntos'].sum().sort_values(ascending=False).reset_index()
    st.table(ranking)

st.divider()

# 2. ZONA ADMINISTRADOR
with st.expander("⚙️ Zona Administrador: Registrar Resultados"):
    fase_admin = st.selectbox("Selecciona Fase:", hojas, key="admin_fase")
    df_admin = load_data(fase_admin)
    
    # BLINDADO: Validar que la hoja de la fase tiene datos y la estructura correcta antes de operar
    if not df_admin.empty and 'Jornada' in df_admin.columns and 'Local' in df_admin.columns and 'Visita' in df_admin.columns:
        jornada_admin = st.selectbox("Selecciona Jornada:", sorted(df_admin['Jornada'].unique()), key="admin_jor")
        df_admin_filt = df_admin[df_admin['Jornada'] == jornada_admin]
        
        opciones_partidos = df_admin_filt['Local'] + " vs " + df_admin_filt['Visita']
        
        # BLINDADO: Evita romper la app si la jornada elegida no tiene partidos listados
        if not opciones_partidos.empty:
            partido_sel = st.selectbox("Partido:", opciones_partidos)
            filtro_idx = df_admin_filt[df_admin_filt['Local'] + " vs " + df_admin_filt['Visita'] == partido_sel].index
            
            if len(filtro_idx) > 0:
                idx = filtro_idx[0]
                
                col1, col2 = st.columns(2)
                r_l = col1.number_input("Goles Local", 0, step=1)
                r_v = col2.number_input("Goles Visita", 0, step=1)
                
                if st.button("Guardar y Recalcular Ranking"):
                    ws = sh.worksheet(fase_admin)
                    ws.update_cell(idx + 2, df_admin.columns.get_loc('Goles_Real_Local') + 1, r_l)
                    ws.update_cell(idx + 2, df_admin.columns.get_loc('Goles_Real_Visita') + 1, r_v)
                    
                    partido_str = f"{df_admin.at[idx, 'Local']} vs {df_admin.at[idx, 'Visita']}"
                    for i, row in df_apuestas.iterrows():
                        if row['Partido'] == partido_str:
                            df_apuestas.at[i, 'Puntos'] = calcular_puntos(row['Pred_Local'], row['Pred_Visita'], r_l, r_v)
                    set_with_dataframe(sh.worksheet('Apuestas'), df_apuestas)
                    st.cache_data.clear()
                    st.success("¡Ranking actualizado!")
                    st.rerun()
            else:
                st.error("No se pudo encontrar el índice del partido seleccionado.")
        else:
            st.warning("No hay partidos registrados para la jornada seleccionada.")
    else:
        st.warning("La hoja de esta fase está vacía o le faltan las columnas básicas ('Jornada', 'Local', 'Visita').")

# 3. ZONA PREDICCIONES
st.subheader("📝 Realizar Predicciones")
lista_usuarios = ["Dany", "Dani Veliz", "Raúl", "Andoni", "Endika", "Mikel", "Igor", "Jonathan", "Alberto", "Jon", "Hiago"]
usuario = st.selectbox("Selecciona tu nombre:", lista_usuarios)
fase_user = st.selectbox("Selecciona Fase:", hojas, key="user_fase")
df_fase = load_data(fase_user)

# BLINDADO: Validar existencia de la columna Jornada en la fase del usuario
if not df_fase.empty and 'Jornada' in df_fase.columns:
    jornada_user = st.selectbox("Selecciona Jornada:", sorted(df_fase['Jornada'].unique()), key="user_jor")
    df_fase_filt = df_fase[df_fase['Jornada'] == jornada_user]

    if 'Usuario' in df_apuestas.columns and not df_apuestas.empty:
        apuestas_usuario = df_apuestas[df_apuestas['Usuario'] == usuario].copy()
        apuestas_usuario['partido_norm'] = apuestas_usuario['Partido'].str.strip().str.lower()
        df_pendientes = df_fase_filt[~df_fase_filt.apply(lambda x: f"{x['Local']} vs {x['Visita']}".strip().lower() in apuestas_usuario['partido_norm'].tolist(), axis=1)]
    else:
        df_pendientes = df_fase_filt

    if df_pendientes.empty:
        st.info(f"¡{usuario}, ya has completado todos tus partidos en esta jornada!")
    else:
        st.write(f"Partidos pendientes para **{usuario}** en {jornada_user}: {len(df_pendientes)}")
        df_editor = df_pendientes[['Local', 'Visita']].copy()
        df_editor['Pred_Local'] = None
        df_editor['Pred_Visita'] = None
        
        # BLINDADO: Configuración estricta del editor para impedir que escriban texto, decimales o números negativos
        preds = st.data_editor(
            df_editor, 
            hide_index=True,
            column_config={
                "Local": st.column_config.TextColumn("Local", disabled=True),
                "Visita": st.column_config.TextColumn("Visita", disabled=True),
                "Pred_Local": st.column_config.NumberColumn("Pred. Local", min_value=0, step=1, required=True),
                "Pred_Visita": st.column_config.NumberColumn("Pred. Visita", min_value=0, step=1, required=True)
            }
        )

        if st.button("Guardar Predicciones"):
            pendientes_de_guardar = preds.dropna(subset=['Pred_Local', 'Pred_Visita'])
            if pendientes_de_guardar.empty:
                st.warning("Por favor, rellena resultados antes de guardar.")
            else:
                with st.status("Guardando en la nube...", expanded=True) as status:
                    # Incluye 'jornada_user' para rellenar las 6 columnas completas de la hoja
                    nuevas = [[usuario, f"{row['Local']} vs {row['Visita']}", int(row['Pred_Local']), int(row['Pred_Visita']), 0, jornada_user] 
                              for _, row in pendientes_de_guardar.iterrows()]
                    sh.worksheet('Apuestas').append_rows(nuevas)
                    st.cache_data.clear()
                    status.update(label="¡Predicciones guardadas con éxito!", state="complete")
                st.rerun()
else:
    st.warning("No hay jornadas configuradas para la fase seleccionada.")