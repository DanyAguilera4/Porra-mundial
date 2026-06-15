import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ─────────────────────────────────────────────
# CONFIGURACIÓN Y ESTILOS (Se mantiene igual)
# ─────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="Porra Mundialista · EIC", page_icon="⚽")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.ranking-table { width: 100%; border-collapse: collapse; }
.ranking-table th {
    background: #1a1a2e; color: #f0f0f0; padding: 10px 14px;
    text-align: left; font-size: 0.82rem; letter-spacing: 0.06em; text-transform: uppercase;
}
.ranking-table td { padding: 10px 14px; border-bottom: 1px solid #e8e8e8; font-size: 0.95rem; }
.ranking-table tr:hover td { background: #f7f7fb; }
.pos-1 td:first-child { color: #c9a227; font-weight: 700; font-size: 1.1rem; }
.pos-2 td:first-child { color: #9e9e9e; font-weight: 700; }
.pos-3 td:first-child { color: #a0522d; font-weight: 700; }
.pts-badge { background: #1a1a2e; color: white; border-radius: 20px; padding: 2px 12px; font-weight: 700; font-size: 0.9rem; }
.pred-card { border: 1px solid #e0e0e0; border-radius: 10px; padding: 12px 16px; margin-bottom: 8px; background: white; }
.pred-card-pending { border-left: 4px solid #9e9e9e; }
.pred-card-correct { border-left: 4px solid #2e7d32; }
.pred-card-partial  { border-left: 4px solid #f57c00; }
.pred-card-wrong    { border-left: 4px solid #c62828; }
.pred-partido { font-weight: 600; font-size: 0.97rem; }
.pred-score { font-size: 0.88rem; color: #555; margin-top: 3px; }
.badge-pleno    { background:#e8f5e9; color:#2e7d32; border-radius:20px; padding:2px 10px; font-size:0.8rem; font-weight:600; }
.badge-parcial  { background:#fff3e0; color:#e65100; border-radius:20px; padding:2px 10px; font-size:0.8rem; font-weight:600; }
.badge-fallo    { background:#ffebee; color:#c62828; border-radius:20px; padding:2px 10px; font-size:0.8rem; font-weight:600; }
.badge-pendiente{ background:#f3f3f3; color:#555;    border-radius:20px; padding:2px 10px; font-size:0.8rem; font-weight:600; }
.user-banner {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white;
    border-radius: 12px; padding: 16px 22px; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between;
}
.user-banner-name { font-size: 1.15rem; font-weight: 700; }
.user-banner-pts  { font-size: 2rem; font-weight: 800; color: #c9a227; }
.user-banner-label{ font-size: 0.75rem; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.07em; }
</style>
""", unsafe_allow_html=True)

st.title("⚽ Porra Mundialista · EIC")

# Botón global para refrescar de forma controlada sin tumbar la API
if st.button("🔄 Refrescar marcadores y clasificación"):
    st.cache_data.clear()
    st.rerun()

# ─────────────────────────────────────────────
# CONEXIÓN Y CARGA DE DATOS (Caché optimizada)
# ─────────────────────────────────────────────
@st.cache_resource
def get_spreadsheet(spreadsheet_id):
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds).open_by_key(spreadsheet_id)

SPREADSHEET_ID = '1-n82WoLSk3b0XE59qIaTrf69R44qAAqu6iJqlDj0RDI'

@st.cache_data(ttl=60) # Subido a 60s para proteger la cuota de la API
def load_sheet_names(spreadsheet_id):
    spreadsheet = get_spreadsheet(spreadsheet_id)
    return [w.title for w in spreadsheet.worksheets() if w.title not in ['Apuestas', 'Usuarios', 'Clasificacion']]

@st.cache_data(ttl=60) # Subido a 60s
def load_data(spreadsheet_id, sheet_name):
    try:
        spreadsheet = get_spreadsheet(spreadsheet_id)
        ws = spreadsheet.worksheet(sheet_name)
        all_values = ws.get_all_values()
        if not all_values or len(all_values) < 2:
            return _empty_df(sheet_name), {}
        df = pd.DataFrame(all_values[1:], columns=all_values[0])
        row_map = {i: i + 2 for i in range(len(df))}
        return df, row_map
    except Exception as e:
        st.error(f"Error cargando '{sheet_name}': {e}")
        return _empty_df(sheet_name), {}

def _empty_df(sheet_name):
    if sheet_name == 'Apuestas':
        return pd.DataFrame(columns=['Usuario', 'Partido', 'Pred_Local', 'Pred_Visita', 'Puntos', 'Jornada'])
    if sheet_name == 'Usuarios':
        return pd.DataFrame(columns=['Usuario', 'Password'])
    return pd.DataFrame(columns=['Jornada', 'Local', 'Visita', 'Goles_Real_Local', 'Goles_Real_Visita'])

def load_df(spreadsheet_id, sheet_name):
    df, _ = load_data(spreadsheet_id, sheet_name)
    return df

# ─────────────────────────────────────────────
# LÓGICA DE PUNTUACIÓN Y AUXILIARES
# ─────────────────────────────────────────────
def calcular_puntos(pred_local, pred_visita, real_local, real_visita):
    try:
        p_l, p_v = int(pred_local), int(pred_visita)
        r_l, r_v = int(real_local), int(real_visita)
        if p_l == r_l and p_v == r_v: return 3
        pred_g = "L" if p_l > p_v else ("V" if p_v > p_l else "E")
        real_g = "L" if r_l > r_v else ("V" if r_v > r_l else "E")
        return 1 if pred_g == real_g else 0
    except (ValueError, TypeError):
        return 0

def badge_puntos(puntos, tiene_resultado):
    if not tiene_resultado: return '<span class="badge-pendiente">⏳ Pendiente</span>'
    if puntos == 3: return '<span class="badge-pleno">🎯 Pleno · 3 pts</span>'
    if puntos == 1: return '<span class="badge-parcial">✅ Ganador · 1 pt</span>'
    return '<span class="badge-fallo">❌ Fallo · 0 pts</span>'

def validar_resultado_existente(val_local, val_visita):
    """Corrige el bug del cero. Detecta si realmente hay un resultado numérico."""
    vl = str(val_local).strip()
    vv = str(val_visita).strip()
    if vl in ['', 'None', 'nan'] or vv in ['', 'None', 'nan']:
        return False
    return vl.isdigit() and vv.isdigit()

# ─────────────────────────────────────────────
# 1. RANKING GENERAL
# ─────────────────────────────────────────────
st.header("🏆 Clasificación General")
df_apuestas = load_df(SPREADSHEET_ID, 'Apuestas')

if not df_apuestas.empty and 'Puntos' in df_apuestas.columns and 'Usuario' in df_apuestas.columns:
    df_apuestas['Puntos'] = pd.to_numeric(df_apuestas['Puntos'], errors='coerce').fillna(0)
    ranking = df_apuestas.groupby('Usuario').agg(Puntos=('Puntos', 'sum'), Apuestas=('Partido', 'count')).sort_values(['Puntos', 'Apuestas'], ascending=[False, False]).reset_index()
    ranking['Pos'] = ranking['Puntos'].rank(method='min', ascending=False).astype(int)

    rows_html = ""
    pos_icons = {1: "🥇", 2: "🥈", 3: "🥉"}
    for _, row in ranking.iterrows():
        pos = row['Pos']
        icon = pos_icons.get(pos, str(pos))
        rows_html += f"""
        <tr class="{"pos-"+str(pos) if pos <= 3 else ""}">
            <td>{icon}</td><td><strong>{row['Usuario']}</strong></td>
            <td><span class="pts-badge">{int(row['Puntos'])} pts</span></td>
            <td style="color:#888;font-size:0.85rem">{int(row['Apuestas'])} apuestas</td>
        </tr>"""
    st.markdown(f'<table class="ranking-table"><thead><tr><th>#</th><th>Jugador</th><th>Puntos</th><th>Apuestas</th></tr></thead><tbody>{rows_html}</tbody></table>', unsafe_allow_html=True)
else:
    st.info("Todavía no hay puntuaciones registradas.")

st.divider()

# ─────────────────────────────────────────────
# 2. ZONA ADMINISTRADOR
# ─────────────────────────────────────────────
hojas = load_sheet_names(SPREADSHEET_ID)

with st.expander("⚙️ Zona Admin: Gestión del Torneo"):
    admin_pass = st.text_input("Contraseña de administrador:", type="password", key="admin_pw")
    ADMIN_PASSWORD = st.secrets.get("admin_password", "Adm1n1str@tor")

    if admin_pass == ADMIN_PASSWORD:
        st.success("Acceso concedido")
        if 'exito_admin' in st.session_state:
            st.success(st.session_state.pop('exito_admin'))

        st.markdown("### 📝 Registrar Resultados de Partidos")
        fase_admin = st.selectbox("Fase:", hojas, key="admin_fase")
        df_admin, row_map_admin = load_data(SPREADSHEET_ID, fase_admin)
        col_jor_admin = 'Jornada' if 'Jornada' in df_admin.columns else ('ID' if 'ID' in df_admin.columns else None)

        if not df_admin.empty and col_jor_admin and all(c in df_admin.columns for c in ['Local', 'Visita']):
            jornada_admin = st.selectbox("Jornada:", sorted(df_admin[col_jor_admin].unique()), key="admin_jor")
            df_admin_filt = df_admin[df_admin[col_jor_admin] == jornada_admin]
            opciones = df_admin_filt['Local'] + " vs " + df_admin_filt['Visita']

            if not opciones.empty:
                partido_sel = st.selectbox("Partido:", opciones)
                idx = df_admin_filt[(df_admin_filt['Local'] + " vs " + df_admin_filt['Visita']) == partido_sel].index[0]
                fila_sheet = row_map_admin[idx]

                col1, col2 = st.columns(2)
                r_l = col1.number_input("Goles Local", 0, step=1, key="admin_rl")
                r_v = col2.number_input("Goles Visita", 0, step=1, key="admin_rv")

                if st.button("💾 Guardar y Recalcular Ranking"):
                    sh = get_spreadsheet(SPREADSHEET_ID)
                    
                    # 1. Actualizar el partido real
                    col_rl = df_admin.columns.get_loc('Goles_Real_Local') + 1
                    col_rv = df_admin.columns.get_loc('Goles_Real_Visita') + 1
                    sh.worksheet(fase_admin).update_cell(fila_sheet, col_rl, r_l)
                    sh.worksheet(fase_admin).update_cell(fila_sheet, col_rv, r_v)

                    # 2. Recalcular apuestas (Seguro mediante coincidencia de texto, no por índice de fila estático)
                    partido_str = f"{df_admin.at[idx, 'Local']} vs {df_admin.at[idx, 'Visita']}"
                    ws_apuestas = sh.worksheet('Apuestas')
                    
                    # Descargamos los datos incluyendo número de fila real mediante rowcol
                    all_apuestas = ws_apuestas.get_all_records()
                    updates = []
                    if all_apuestas:
                        df_fresco = pd.DataFrame(all_apuestas)
                        if 'Partido' in df_fresco.columns and 'Puntos' in df_fresco.columns:
                            col_pts_idx = list(df_fresco.columns).index('Puntos') + 1
                            col_pts_letra = gspread.utils.rowcol_to_a1(1, col_pts_idx)[0]
                            
                            for i, row in df_fresco.iterrows():
                                if str(row['Partido']).strip().lower() == partido_str.strip().lower():
                                    nuevos_pts = calcular_puntos(row['Pred_Local'], row['Pred_Visita'], r_l, r_v)
                                    updates.append({
                                        'range': f"{col_pts_letra}{i + 2}",
                                        'values': [[nuevos_pts]]
                                    })
                            if updates:
                                ws_apuestas.batch_update(updates)

                    st.cache_data.clear()
                    st.session_state['exito_admin'] = f"🏆 Resultado {partido_str} guardado: {r_l}–{r_v}"
                    st.rerun()

        # ── Ajuste Manual de Puntos (Se mantiene igual) ───────────────────
        st.markdown("### ⚖️ Ajuste Manual de Puntos")
        df_apuestas_admin = load_df(SPREADSHEET_ID, 'Apuestas')
        if not df_apuestas_admin.empty and 'Usuario' in df_apuestas_admin.columns:
            usuario_ajuste = st.selectbox("Usuario:", df_apuestas_admin['Usuario'].unique())
            col_pts, col_motivo = st.columns([1, 2])
            puntos_ajuste = col_pts.number_input("Puntos:", value=0, step=1)
            motivo_ajuste = col_motivo.text_input("Motivo:")

            if st.button("Aplicar Ajuste"):
                if puntos_ajuste != 0:
                    get_spreadsheet(SPREADSHEET_ID).worksheet('Apuestas').append_row(
                        [usuario_ajuste, f"AJUSTE ADMIN: {motivo_ajuste}", 0, 0, puntos_ajuste, "AJUSTE"]
                    )
                    st.cache_data.clear()
                    st.session_state['exito_admin'] = f"⚖️ {puntos_ajuste:+d} pts aplicados a {usuario_ajuste}."
                    st.rerun()

# ─────────────────────────────────────────────
# 3. ZONA PRIVADA DE USUARIO
# ─────────────────────────────────────────────
st.divider()
st.subheader("🔐 Acceso de Jugadores")

if 'usuario_autenticado' not in st.session_state:
    st.session_state['usuario_autenticado'] = None

df_usuarios = load_df(SPREADSHEET_ID, 'Usuarios')

if st.session_state['usuario_autenticado'] is None:
    col_u, col_p, col_btn = st.columns([2, 2, 1])
    user_input = col_u.selectbox("Nombre:", [""] + df_usuarios['Usuario'].unique().tolist())
    pass_input = col_p.text_input("Contraseña:", type="password")
    col_btn.markdown("<br>", unsafe_allow_html=True)

    if col_btn.button("Entrar →", use_container_width=True):
        fila_user = df_usuarios[df_usuarios['Usuario'] == user_input]
        if not fila_user.empty and pass_input.strip() == str(fila_user['Password'].values[0]).strip():
            st.session_state['usuario_autenticado'] = user_input
            st.rerun()
        else:
            st.error("Credenciales incorrectas.")
else:
    usuario = st.session_state['usuario_autenticado']
    
    _, col_logout = st.columns([5, 1])
    if col_logout.button("Cerrar sesión 🚪", use_container_width=True):
        st.session_state['usuario_autenticado'] = None
        st.rerun()

    # Cálculo dinámico de puntos del usuario para el Banner
    df_apuestas = load_df(SPREADSHEET_ID, 'Apuestas')
    mis_pts = int(pd.to_numeric(df_apuestas[df_apuestas['Usuario'] == usuario]['Puntos'], errors='coerce').sum()) if not df_apuestas.empty else 0
    
    st.markdown(f'<div class="user-banner"><div><div class="user-banner-label">Jugando como</div><div class="user-banner-name">👤 {usuario}</div></div><div style="text-align:right"><div class="user-banner-label">Puntos totales</div><div class="user-banner-pts">{mis_pts}</div></div></div>', unsafe_allow_html=True)

    # ── FORMULARIO DE PREDICCIONES (Mejorado con st.form) ─────────────────
    st.subheader("📝 Realizar Predicciones")
    fase_user = st.selectbox("Fase:", hojas, key="user_fase")
    df_fase, _ = load_data(SPREADSHEET_ID, fase_user)
    col_jor_user = 'Jornada' if 'Jornada' in df_fase.columns else ('ID' if 'ID' in df_fase.columns else None)

    if not df_fase.empty and col_jor_user:
        jornada_user = st.selectbox("Jornada:", sorted(df_fase[col_jor_user].unique()), key="user_jor")
        df_fase_filt = df_fase[df_fase[col_jor_user] == jornada_user].copy()

        apostados_norm = df_apuestas[df_apuestas['Usuario'] == usuario]['Partido'].str.strip().str.lower().tolist() if not df_apuestas.empty else []
        df_fase_filt['_partido_norm'] = (df_fase_filt['Local'] + " vs " + df_fase_filt['Visita']).str.strip().str.lower()

        df_pendientes = df_fase_filt[~df_fase_filt['_partido_norm'].isin(apostados_norm)]
        df_completados = df_fase_filt[df_fase_filt['_partido_norm'].isin(apostados_norm)]

        if not df_completados.empty:
            with st.expander(f"✅ Ya apostados en {jornada_user} ({len(df_completados)})"):
                for _, row in df_completados.iterrows():
                    tiene_res = validar_resultado_existente(row.get('Goles_Real_Local'), row.get('Goles_Real_Visita'))
                    res_str = f" · Resultado: **{row['Goles_Real_Local']}–{row['Goles_Real_Visita']}**" if tiene_res else ""
                    st.markdown(f"⚽ **{row['Local']} vs {row['Visita']}**{res_str}")

        if df_pendientes.empty:
            st.success(f"🎉 ¡{usuario}, ya has completado todos los partidos de esta jornada!")
        else:
            # Envolver en formulario evita recargas intermedias molestas en el móvil
            with st.form("formulario_apuestas"):
                st.caption(f"Partidos pendientes: **{len(df_pendientes)}**")
                diccionario_inputs = {}
                
                for i, (_, row) in enumerate(df_pendientes.iterrows()):
                    tiene_res = validar_resultado_existente(row.get('Goles_Real_Local'), row.get('Goles_Real_Visita'))
                    if tiene_res:
                        st.markdown(f"⚠️ **{row['Local']} vs {row['Visita']}** _(Ya jugado: {row['Goles_Real_Local']}–{row['Goles_Real_Visita']})_")
                    else:
                        st.markdown(f"**⚽ {row['Local']} vs {row['Visita']}**")

                    col_l, col_sep, col_v = st.columns([2, 1, 2])
                    with col_l:
                        p_l = st.number_input(f"Goles {row['Local']}", min_value=0, step=1, key=f"pl_{jornada_user}_{i}", value=0)
                    col_sep.markdown("<div style='text-align:center;padding-top:28px;font-size:1.2rem'>–</div>", unsafe_allow_html=True)
                    with col_v:
                        p_v = st.number_input(f"Goles {row['Visita']}", min_value=0, step=1, key=f"pv_{jornada_user}_{i}", value=0)
                    
                    diccionario_inputs[i] = {'local': row['Local'], 'visita': row['Visita'], 'p_l': p_l, 'p_v': p_v}
                    st.markdown("---")

                bot_guardar = st.form_submit_button("💾 Guardar todas las predicciones")
                
                if bot_guardar:
                    nuevas_filas = [
                        [usuario, f"{datos['local']} vs {datos['visita']}", int(datos['p_l']), int(datos['p_v']), 0, jornada_user]
                        for datos in diccionario_inputs.values()
                    ]
                    with st.status("Guardando apuestas..."):
                        get_spreadsheet(SPREADSHEET_ID).worksheet('Apuestas').append_rows(nuevas_filas)
                        st.cache_data.clear()
                    st.rerun()

    # ── HISTORIAL PERSONAL (Corregido bug del cero) ───────────────────────
    st.divider()
    st.subheader("📊 Tu Historial de Predicciones")

    if not df_apuestas.empty:
        mis_apuestas = df_apuestas[df_apuestas['Usuario'] == usuario].copy()
        if mis_apuestas.empty:
            st.info("Aún no tienes predicciones.")
        else:
            resultados_reales = {}
            for hoja in hojas:
                df_h = load_df(SPREADSHEET_ID, hoja)
                if not df_h.empty and all(c in df_h.columns for c in ['Local', 'Visita', 'Goles_Real_Local', 'Goles_Real_Visita']):
                    for _, r in df_h.iterrows():
                        key = f"{r['Local']} vs {r['Visita']}".strip().lower()
                        if validar_resultado_existente(r['Goles_Real_Local'], r['Goles_Real_Visita']):
                            resultados_reales[key] = (str(r['Goles_Real_Local']), str(r['Goles_Real_Visita']))

            mis_apuestas = mis_apuestas.iloc[::-1]
            plenos, parciales, fallos, pendientes = 0, 0, 0, 0
            cards_html = ""

            for _, row in mis_apuestas.iterrows():
                partido = str(row.get('Partido', '')).strip()
                if partido.startswith("AJUSTE ADMIN"): continue

                pts = int(pd.to_numeric(row.get('Puntos', 0), errors='coerce') or 0)
                pred_l, pred_v = str(row.get('Pred_Local', '?')), str(row.get('Pred_Visita', '?'))
                key = partido.lower()
                
                tiene_resultado = key in resultados_reales
                real_l, real_v = resultados_reales.get(key, ('?', '?'))

                if tiene_resultado:
                    if pts == 3: plenos += 1
                    elif pts == 1: parciales += 1
                    else: fallos += 1
                else:
                    pendientes += 1

                card_class = "pred-card-pending" if not tiene_resultado else ("pred-card-correct" if pts == 3 else ("pred-card-partial" if pts == 1 else "pred-card-wrong"))
                res_html = f"Resultado real: <strong>{real_l}–{real_v}</strong> · " if tiene_resultado else ""

                cards_html += f"""
                <div class="pred-card {card_class}">
                    <div class="pred-partido">{partido} <span style="font-weight:400;color:#888;font-size:0.82rem;margin-left:8px">{row.get('Jornada', '')}</span></div>
                    <div class="pred-score">Tu predicción: <strong>{pred_l}–{pred_v}</strong> · {res_html}{badge_puntos(pts, tiene_resultado)}</div>
                </div>"""

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🎯 Plenos", plenos)
            c2.metric("✅ Ganador", parciales)
            c3.metric("❌ Fallos", fallos)
            c4.metric("⏳ Pendientes", pendientes)
            st.markdown(cards_html, unsafe_allow_html=True)