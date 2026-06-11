import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Porra Mundialista")
st.title("⚽ Porra Mundialista - Mantenedores Básicos ⚽")

file_path = 'quiniela.xlsx'

try:
    xls = pd.ExcelFile(file_path)
    df_apuestas = pd.read_excel(file_path, sheet_name='Apuestas')
    fases_disponibles = [s for s in xls.sheet_names if s != 'Apuestas']

    # --- 🏆 RANKING (Siempre visible) ---
    st.header("🏆 Clasificación General 🏆")
    if not df_apuestas.empty and 'Puntos' in df_apuestas.columns:
        # Agrupamos por usuario y sumamos puntos
        ranking = df_apuestas.groupby('Usuario')['Puntos'].sum().sort_values(ascending=False)
        
        c_r1, c_r2 = st.columns([1, 2])
        with c_r1:
            st.write("Tabla de posiciones:")
            st.dataframe(ranking, use_container_width=True)
        with c_r2:
            st.bar_chart(ranking)
    else:
        st.info("Aún no hay predicciones guardadas o puntos registrados.")

    st.divider() # Línea divisoria visual

    # --- ⚙️ ZONA ADMINISTRADOR ---
    with st.expander("⚙️ Zona Administrador: Registrar Resultados"):
        fase_admin = st.selectbox("Selecciona la fase:", fases_disponibles)
        df_admin = pd.read_excel(file_path, sheet_name=fase_admin)
        
        lista_partidos = df_admin['Local'] + " vs " + df_admin['Visita']
        partido_sel = st.selectbox("Partido:", lista_partidos)
        idx = lista_partidos[lista_partidos == partido_sel].index[0]
        
        c1, c2 = st.columns(2)
        r_l = c1.number_input(f"Goles {df_admin.at[idx, 'Local']}", 0)
        r_v = c2.number_input(f"Goles {df_admin.at[idx, 'Visita']}", 0)
        
        if st.button("Guardar y Recalcular"):
            df_admin.at[idx, 'Goles_Real_Local'] = r_l
            df_admin.at[idx, 'Goles_Real_Visita'] = r_v
            
            # Recalcular puntos para TODOS los usuarios
            partido_str = f"{df_admin.at[idx, 'Local']} vs {df_admin.at[idx, 'Visita']}"
            for i, row in df_apuestas.iterrows():
                if row['Partido'] == partido_str:
                    puntos = 0
                    if row['Pred_Local'] == r_l and row['Pred_Visita'] == r_v: puntos = 3
                    elif (row['Pred_Local'] > row['Pred_Visita'] and r_l > r_v) or \
                         (row['Pred_Local'] < row['Pred_Visita'] and r_l < r_v) or \
                         (row['Pred_Local'] == row['Pred_Visita'] and r_l == r_v): puntos = 1
                    df_apuestas.at[i, 'Puntos'] = puntos
            
            with pd.ExcelWriter(file_path, engine='openpyxl', mode='w') as writer:
                for sheet in xls.sheet_names:
                    if sheet == fase_admin: df_admin.to_excel(writer, sheet_name=sheet, index=False)
                    else: pd.read_excel(file_path, sheet_name=sheet).to_excel(writer, sheet_name=sheet, index=False)
                df_apuestas.to_excel(writer, sheet_name='Apuestas', index=False)
            st.success("¡Resultado guardado y Ranking actualizado!")

    # --- 📝 ZONA DE PREDICCIONES ---
    st.subheader("📝 Realizar Predicciones")
    fase_user = st.selectbox("Selecciona la ronda:", fases_disponibles)
    df_fase = pd.read_excel(file_path, sheet_name=fase_user)
    
    # Formateo visual
    df_fase['Fecha'] = pd.to_datetime(df_fase['Fecha']).dt.strftime('%d/%m/%y')
    df_fase['Hora'] = pd.to_datetime(df_fase['Hora'], format='%H:%M:%S').dt.strftime('%H:%M')
    
    usuario = st.text_input("Tu Nombre:")
    
    columnas_ordenadas = ['Local', 'Visita', 'Fecha', 'Hora']
    df_editor = df_fase[columnas_ordenadas].copy()
    df_editor['Pred_Local'] = 0
    df_editor['Pred_Visita'] = 0
    
    preds = st.data_editor(
        df_editor, 
        column_config={
            "Local": st.column_config.TextColumn("Local", width="medium", disabled=True),
            "Visita": st.column_config.TextColumn("Visita", width="medium", disabled=True),
            "Fecha": st.column_config.TextColumn("Fecha", width="small", disabled=True),
            "Hora": st.column_config.TextColumn("Hora", width="small", disabled=True),
            "Pred_Local": st.column_config.NumberColumn("Goles Local", width="small", min_value=0),
            "Pred_Visita": st.column_config.NumberColumn("Goles Visita", width="small", min_value=0),
        },
        hide_index=True,
        use_container_width=True
    )

    if st.button("Guardar Predicciones"):
        if not usuario: st.error("Ingresa tu nombre.")
        else:
            nuevas = []
            for _, row in preds.iterrows():
                nuevas.append({'Usuario': usuario, 'Partido': f"{row['Local']} vs {row['Visita']}", 
                               'Pred_Local': row['Pred_Local'], 'Pred_Visita': row['Pred_Visita'], 'Puntos': 0})
            pd.concat([df_apuestas, pd.DataFrame(nuevas)]).to_excel(file_path, sheet_name='Apuestas', index=False)
            st.success("¡Predicciones guardadas!")

except Exception as e:
    st.error(f"Error técnico: {e}. Asegúrate de cerrar el Excel.")