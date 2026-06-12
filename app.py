import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

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

# OPTIMIZACIÓN: Función con caché para abrir el documento evitando bloqueos de cuota (Rate Limits)
@st.cache_resource
def get_spreadsheet(spreadsheet_id):
    client = get_connection()
    return client.open_by_key(spreadsheet_id)

# ID de tu documento de Google Sheets
SPREADSHEET_ID = '1-n82WoLSk3b0XE59qIaTrf69R44qAAqu6iJqlDj0RDI'

# Cargamos el archivo usando la nueva función optimizada
sh = get_spreadsheet(SPREADSHEET_ID)

@st.cache_data(ttl=10)
def load_data(sheet_name):
    try:
        data = sh.worksheet(sheet_name).get_all_records()
        if not data: 
            if sheet_name == 'Apuestas':
                return pd.DataFrame(columns=['Usuario', 'Partido', 'Pred_Local', 'Pred_Visita', 'Puntos', 'Jornada'])
            return pd.DataFrame(columns=['Jornada', 'Local', 'Visita', 'Goles_Real_Local', 'Goles_Real_Visita'])
        return pd.DataFrame(data)
    except Exception as e:
        print(f"Error cargando {sheet_name}: {e}")
        if sheet_name == 'Apuestas':
            return pd.DataFrame(columns=['Usuario', 'Partido', 'Pred_Local', 'Pred_Visita', 'Puntos', 'Jornada'])
        return pd.DataFrame(columns=['Jornada', 'Local', 'Visita', 'Goles_Real_Local', 'Goles_Real_Visita'])

# --- LÓGICA DE PUNTUACIÓN ---
def calcular_puntos(pred_local, pred_visita, real_local, real_visita):
    try:
        p_l, p_v, r_l, r_v = int(pred_local), int(pred_visita), int(real_local), int(real_visita)
        if p_l == r_l and p_v == r_v: 
            return 3  # Pleno
        pred_g = "L" if p_l > p_v else ("V" if p_v > p_l else "E")
        real_g = "L" if r_l > r_v else ("V" if r_v > r_l else "E")
        return 1 if pred_g == real_g else 0  # Acierto de ganador/empate
    except (ValueError, TypeError):
        return 0

# --- INTERFAZ ---
hojas = [w.title for w in sh.worksheets() if w.title not in ['Apuestas', 'Usuarios']]

# 1. RANKING
st.header("🏆 Clasificación General 🏆")
df_apuestas = load_data('Apuestas')
if not df_apuestas.empty and 'Puntos' in df_apuestas.columns:
    df_apuestas['Puntos'] = pd.to_numeric(df_apuestas['Puntos'], errors='coerce').fillna(0)
    ranking = df_apuestas.groupby('Usuario')['Puntos'].sum().sort_values(ascending=False).reset_index()
    ranking.index = ranking.index + 1
    st.table(ranking)

st.divider()

# 2. ZONA ADMINISTRADOR
with st.expander("⚙️ Zona Admin: Gestión del Torneo"):
    # CAMBIO 1: Sistema de contraseña
    admin_pass = st.text_input("Contraseña de administrador:", type="password")
    
    if admin_pass == "Adm1n1str@tor":  # Cambia "admin123" por la contraseña que quieras usar
        st.success("Acceso concedido")
        
        # --- NUEVA FUNCIÓN: AÑADIR PARTIDOS MANUALMENTE ---
        st.markdown("### 🆕 Añadir Nuevos Partidos Manualmente")
        st.write("Usa esta sección para añadir partidos de eliminación directa a medida que se definan.")
        
        fase_nueva = st.selectbox("Selecciona la Fase para añadir el partido:", hojas, key="add_fase")
        
        col_jor, col_loc, col_vis = st.columns(3)
        jornada_nueva = col_jor.text_input("Jornada/Ronda (Ej: 16avos, Octavos 1):", value="16avos")
        equipo_local = col_loc.text_input("Equipo Local:")
        equipo_visita = col_vis.text_input("Equipo Visitante:")
        
        if st.button("➕ Insertar Partido"):
            if equipo_local.strip() == "" or equipo_visita.strip() == "":
                st.error("Por favor, introduce el nombre de ambos equipos.")
            else:
                try:
                    ws_fase = sh.worksheet(fase_nueva)
                    # Insertamos la nueva fila: Jornada, Local, Visita, Goles_Real_Local, Goles_Real_Visita
                    # Dejamos los goles vacíos ("") para que el admin los rellene después en el registrador de resultados
                    ws_fase.append_row([jornada_nueva.strip(), equipo_local.strip(), equipo_visita.strip(), "", ""])
                    st.cache_data.clear()
                    st.success(f"¡Partido '{equipo_local} vs {equipo_visita}' añadido correctamente a la fase {fase_nueva}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar el partido: {e}")
                    
        st.divider()
        
        # --- REGISTRAR RESULTADOS ---
        st.markdown("### 📝 Registrar Resultados de Partidos")
        
        fase_admin = st.selectbox("Selecciona Fase:", hojas, key="admin_fase")
        df_admin = load_data(fase_admin)
        
        if not df_admin.empty and all(col in df_admin.columns for col in ['Jornada', 'Local', 'Visita']):
            jornada_admin = st.selectbox("Selecciona Jornada:", sorted(df_admin['Jornada'].unique()), key="admin_jor")
            df_admin_filt = df_admin[df_admin['Jornada'] == jornada_admin]
            
            opciones_partidos = df_admin_filt['Local'] + " vs " + df_admin_filt['Visita']
            
            if not opciones_partidos.empty:
                partio_sel = st.selectbox("Partido:", opciones_partidos)
                filtro_idx = df_admin_filt[df_admin_filt['Local'] + " vs " + df_admin_filt['Visita'] == partio_sel].index
                
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
                        
                        # ACTUALIZACIÓN EN BATCH
                        ws_apuestas = sh.worksheet('Apuestas')
                        datos_frescos = ws_apuestas.get_all_records()
                        
                        if datos_frescos:
                            df_fresco = pd.DataFrame(datos_frescos)
                            if 'Partido' in df_fresco.columns and 'Puntos' in df_fresco.columns:
                                col_puntos_letra = gspread.utils.rowcol_to_a1(1, list(df_fresco.columns).index('Puntos') + 1)[0]
                                
                                updates = []
                                for i, row in df_fresco.iterrows():
                                    if str(row['Partido']).strip().lower() == partido_str.strip().lower():
                                        nuevos_puntos = calcular_puntos(row['Pred_Local'], row['Pred_Visita'], r_l, r_v)
                                        fila_sheet = i + 2
                                        updates.append({
                                            'range': f"{col_puntos_letra}{fila_sheet}",
                                            'values': [[nuevos_puntos]]
                                        })
                                
                                if updates:
                                    ws_apuestas.batch_update(updates)
                        
                        st.cache_data.clear()
                        st.success("¡Resultados y puntos asignados de golpe!")
                        st.rerun()
                else:
                    st.error("No se pudo encontrar el índice del partido seleccionado.")
            else:
                st.warning("No hay partidos registrados para la jornada seleccionada.")
        else:
            st.warning("La hoja está vacía o le faltan columnas básicas.")
            
        st.divider()
        
        # CAMBIO 2: Dar/Quitar puntos manualmente
        st.markdown("### ⚖️ Ajuste Manual de Puntos")
        st.write("Usa esta zona para dar puntos extra (bonus) o quitar puntos (penalizaciones).")
        if not df_apuestas.empty and 'Usuario' in df_apuestas.columns:
            usuario_ajuste = st.selectbox("Selecciona al usuario:", df_apuestas['Usuario'].unique())
            col_pts, col_motivo = st.columns([1, 2])
            puntos_ajuste = col_pts.number_input("Puntos (usa negativos para restar):", value=0, step=1)
            motivo_ajuste = col_motivo.text_input("Motivo (ej: Bonus por acertar el campeón):")
            
            if st.button("Aplicar Ajuste de Puntos"):
                if puntos_ajuste != 0:
                    ws_apuestas = sh.worksheet('Apuestas')
                    # Añadimos una fila simulando una apuesta pero que solo suma puntos a ese usuario
                    ws_apuestas.append_row([usuario_ajuste, f"AJUSTE ADMIN: {motivo_ajuste}", 0, 0, puntos_ajuste, "AJUSTE"])
                    st.cache_data.clear()
                    st.success(f"Se ha aplicado el ajuste de {puntos_ajuste} puntos a {usuario_ajuste}.")
                    st.rerun()
                else:
                    st.warning("El ajuste de puntos no puede ser 0.")
                    
    elif admin_pass != "":
        st.error("Contraseña incorrecta.")

# 3. ZONA PREDICCIONES
st.subheader("📝 Realizar Predicciones")

df_usuarios = load_data('Usuarios')
if not df_usuarios.empty and 'Usuario' in df_usuarios.columns:
    lista_usuarios = df_usuarios['Usuario'].astype(str).str.strip().unique().tolist()
else:
    lista_usuarios = ["Dany", "Dani Veliz", "Raúl", "Andoni", "Endika", "Mikel", "Igor", "Jonathan", "Alberto", "Jon", "Hiago"]

usuario = st.selectbox("Selecciona tu nombre:", lista_usuarios)
fase_user = st.selectbox("Selecciona Fase:", hojas, key="user_fase")
df_fase = load_data(fase_user)

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
                    nuevas = [[usuario, f"{row['Local']} vs {row['Visita']}", int(row['Pred_Local']), int(row['Pred_Visita']), 0, jornada_user] 
                              for _, row in pendientes_de_guardar.iterrows()]
                    sh.worksheet('Apuestas').append_rows(nuevas)
                    st.cache_data.clear()
                    status.update(label="¡Predicciones guardadas con éxito!", state="complete")
                st.rerun()
else:
    st.warning("No hay jornadas configuradas para la fase seleccionada.")