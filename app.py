import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

import json
from streamlit import secrets


# --------------------------------
# ✅ SESSION STATE
# --------------------------------
if "mapa_punto" not in st.session_state:
    st.session_state.mapa_punto = None

# 👉 ✅ 
if "mapa_zoom" not in st.session_state:
    st.session_state.mapa_zoom = None


# --------------------------------
# CONFIG
# --------------------------------
st.set_page_config(layout="wide")
st.title("🪨 Litoteca UNSA")

# --------------------------------
# GOOGLE SHEETS
# --------------------------------
@st.cache_data
def load_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds_dict = json.loads(secrets["gcp_service_account"])
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict, scope
    )

    
    client = gspread.authorize(creds)
    sheet = client.open("db_litoteca_unsa").sheet1
    return pd.DataFrame(sheet.get_all_records())

# --------------------------------
# IMÁGENES
# --------------------------------
def drive_to_img(texto):
    if not texto:
        return None

    texto = str(texto).strip()

    if texto in ["0", "", "nan", "None", "sin foto"]:
        return None

    match = re.search(r"/d/([a-zA-Z0-9_-]+)", texto)

    if match:
        file_id = match.group(1)
        return f"https://lh3.googleusercontent.com/d/{file_id}"

    return None

# --------------------------------
# DATOS
# --------------------------------
df = load_data()

def fix_coord(valor, tipo="lat"):
    if pd.isna(valor):
        return None

    try:
        texto = str(valor).strip().replace(",", ".")
        numero = float(texto)

        # --------------------------------
        # ✅ CORRECCIÓN POR ESCALA
        # --------------------------------
        if tipo == "lat":
            while abs(numero) > 90:
                numero = numero / 10

        if tipo == "lon":
            while abs(numero) > 180:
                numero = numero / 10

        return numero

    except:
        return None

df["latitud"] = df["latitud"].apply(lambda x: fix_coord(x, "lat"))
df["longitud"] = df["longitud"].apply(lambda x: fix_coord(x, "lon"))
df["img"] = df["foto_url1"].apply(drive_to_img)

# --------------------------------
# ✅ CONTROL DE VISTA (PRO)
# --------------------------------
if "vista" not in st.session_state:
    st.session_state.vista = "🔎 Catálogo"

st.sidebar.title("Menú")
# --------------------------------
# ✅ DETALLE EN SIDEBAR
# --------------------------------
if st.session_state.mapa_punto:

    fila = df[df["fullname"] == st.session_state.mapa_punto["nombre"]].iloc[0]

    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Muestra seleccionada")

    st.sidebar.write(f"Código: {fila['fullname']}")
    st.sidebar.write(f"Tipo: {fila.get('tipo','')}")
    st.sidebar.write(f"Subtipo: {fila.get('subtipo','')}")
    st.sidebar.write(f"Roca: {fila.get('roca','')}")
    st.sidebar.write(f"Color: {fila.get('color','')}")
    st.sidebar.write(f"Observaciones: {fila.get('observaciones','')}")

    if fila.get("tipo") == "Sedimentaria":
        st.sidebar.markdown("**Sedimentaria:**")
        st.sidebar.write(f"Textura: {fila.get('textura','')}")
        st.sidebar.write(f"Estructura: {fila.get('estructura','')}")
        st.sidebar.write(f"Mineral primario: {fila.get('mimeral_pri','')}")
        st.sidebar.write(f"Mineral secundario: {fila.get('mineral_secu','')}")
        st.sidebar.write(f"Clasto: {fila.get('clasto_sed','')}")
        st.sidebar.write(f"Matriz: {fila.get('matriz_sed','')}")
        st.sidebar.write(f"Cemento: {fila.get('cemento_sed','')}")

    if fila["img"]:
        st.sidebar.image(fila["img"], use_container_width=True)

    if st.sidebar.button("❌ Limpiar selección"):
        st.session_state.mapa_punto = None
        st.rerun()



vista = st.sidebar.radio(
    "Seleccionar vista",
    ["🔎 Catálogo", "🗺 Mapa"],
    index=0 if st.session_state.vista == "🔎 Catálogo" else 1
)

# mantener estado
st.session_state.vista = vista

# --------------------------------
# 🔎 CATÁLOGO
# --------------------------------
if vista == "🔎 Catálogo":

    st.header("Catálogo de muestras")

    # --------------------------------
    # ✅ MAPA ARRIBA
    # --------------------------------
    if st.session_state.mapa_punto:

        import folium
        from streamlit_folium import st_folium

        p = st.session_state.mapa_punto

        row = df[df["fullname"] == p["nombre"]].iloc[0]

        mapa = folium.Map(
            location=[row["latitud"], row["longitud"]],
            zoom_start=12
        )


        html = f"<b>{row['fullname']}</b><br>{row['roca']}"

        if row["img"]:
            html += f'<br><img src="{row["img"]}" width="200">'


        folium.Marker(
            location=[row["latitud"], row["longitud"]],
            popup=folium.Popup(html, max_width=250)
        ).add_to(mapa)

        st_folium(mapa, width=900, height=500)

        # ------------------------------
        # BUSCAR FILA ORIGINAL
        # ------------------------------
        row = df[df["fullname"] == p["nombre"]].iloc[0]

        st.markdown("### 📄 Información de la muestra")

        col1, col2 = st.columns([1, 2])

        # INFO COMPLETA
        with col1:
            st.write(f"Tipo: {row.get('tipo','')}")
            st.write(f"Subtipo: {row.get('subtipo','')}")
            st.write(f"Roca: {row.get('roca','')}")
            st.write(f"Color: {row.get('color','')}")
            st.write(f"Observaciones: {row.get('observaciones','')}")

            # ✅ SEDIMENTARIAS
            if row.get("tipo") == "Sedimentaria":
                st.markdown("**Características sedimentarias:**")

                st.write(f"Textura: {row.get('textura','')}")
                st.write(f"Estructura: {row.get('estructura','')}")
                st.write(f"Mineral primario: {row.get('mimeral_pri','')}")
                st.write(f"Mineral secundario: {row.get('mineral_secu','')}")
                st.write(f"Clasto: {row.get('clasto_sed','')}")
                st.write(f"Matriz: {row.get('matriz_sed','')}")
                st.write(f"Cemento: {row.get('cemento_sed','')}")

        # IMAGEN GRANDE
        with col2:
            if row["img"]:
                st.markdown(f"""
                <a href="{row['img']}" target="_blank">
                    <img src="{row['img']}" style="width:100%; border-radius:8px;">
                </a>
                """, unsafe_allow_html=True)

                st.caption("🔍 Click en la imagen para ampliar")

        
        if st.button("🌍 Abrir en mapa general"):

            st.session_state.mapa_zoom = {
                "lat": p["lat"],
                "lon": p["lon"]
            }

            st.session_state.mapa_punto = None
            st.session_state.vista = "🗺 Mapa"

            st.rerun()
        
        
        # ------------------------------
        # BOTÓN VOLVER
        # ------------------------------
        if st.button("🔙 Volver al catálogo"):
            st.session_state.mapa_punto = None
            st.rerun()

        # 💥 CLAVE
        st.stop()

    # --------------------------------
    # 🔎 BUSCADOR
    # --------------------------------
    st.subheader("Buscar por código")

    codigo = st.text_input("Ingresar código (ej: A-1IA1)").upper().strip()

    if codigo:

        df_busqueda = df[df["fullname"].astype(str) == codigo]

        if len(df_busqueda) == 0:
            st.warning("No se encontró ese código")
        else:
            st.success(f"Resultado para: {codigo}")

            for _, row in df_busqueda.iterrows():

                st.markdown("---")
                col1, col2 = st.columns([1, 2])

                with col1:
                    st.subheader(row.get("fullname", ""))

                    st.write(f"Tipo: {row.get('tipo','')}")
                    st.write(f"Subtipo: {row.get('subtipo','')}")
                    st.write(f"Roca: {row.get('roca','')}")
                    st.write(f"Color: {row.get('color','')}")
                    st.write(f"Observaciones: {row.get('observaciones','')}")

                    if row.get("tipo") == "Sedimentaria":
                        st.markdown("**Características sedimentarias:**")
                        st.write(f"Textura: {row.get('textura','')}")
                        st.write(f"Estructura: {row.get('estructura','')}")
                        st.write(f"Mineral primario: {row.get('mimeral_pri','')}")
                        st.write(f"Mineral secundario: {row.get('mineral_secu','')}")
                        st.write(f"Clasto: {row.get('clasto_sed','')}")
                        st.write(f"Matriz: {row.get('matriz_sed','')}")
                        st.write(f"Cemento: {row.get('cemento_sed','')}")

                with col2:
                    if row["img"]:
                        st.markdown(f"""
                        <a href="{row['img']}" target="_blank">
                            <img src="{row['img']}" style="width:100%; border-radius:8px;">
                        </a>
                        """, unsafe_allow_html=True)

                        st.caption("🔍 Click en la imagen para ampliar")

                    if pd.notna(row["latitud"]) and pd.notna(row["longitud"]):
                        if st.button(f"📍 Ver en mapa {row['fullname']}"):

                            st.session_state.mapa_punto = {
                                "lat": row["latitud"],
                                "lon": row["longitud"],
                                "nombre": row["fullname"],
                                "roca": row["roca"],
                                "img": row["img"]
                            }

                            st.rerun()

        st.stop()

    # --------------------------------
    # FILTROS
    # --------------------------------
    tipos = ["Seleccionar"] + sorted(df["tipo"].dropna().unique())
    tipo_sel = st.selectbox("Tipo", tipos)

    if tipo_sel == "Seleccionar":
        st.info("Seleccioná un tipo para comenzar")
        st.stop()

    df_filtrado = df[df["tipo"] == tipo_sel]

    if tipo_sel != "Metamórfica":
        subtipos = ["Todos"] + sorted(df_filtrado["subtipo"].dropna().unique())
        subtipo_sel = st.selectbox("Subtipo", subtipos)

        if subtipo_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["subtipo"] == subtipo_sel]

    st.write(f"🔎 Resultados: {len(df_filtrado)}")

    for _, row in df_filtrado.iterrows():

        st.markdown("---")
        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader(row.get("fullname",""))

            st.write(f"Tipo: {row.get('tipo','')}")
            st.write(f"Subtipo: {row.get('subtipo','')}")
            st.write(f"Roca: {row.get('roca','')}")
            st.write(f"Color: {row.get('color','')}")
            st.write(f"Observaciones: {row.get('observaciones','')}")

            if row.get("tipo") == "Sedimentaria":
                st.markdown("**Características sedimentarias:**")
                st.write(f"Textura: {row.get('textura','')}")
                st.write(f"Estructura: {row.get('estructura','')}")
                st.write(f"Mineral primario: {row.get('mimeral_pri','')}")
                st.write(f"Mineral secundario: {row.get('mineral_secu','')}")
                st.write(f"Clasto: {row.get('clasto_sed','')}")
                st.write(f"Matriz: {row.get('matriz_sed','')}")
                st.write(f"Cemento: {row.get('cemento_sed','')}")

        with col2:
            if row["img"]:
                st.markdown(f"""
                <a href="{row['img']}" target="_blank">
                    <img src="{row['img']}" style="width:100%; border-radius:8px;">
                </a>
                """, unsafe_allow_html=True)

                st.caption("🔍 Click en la imagen para ampliar")

            if pd.notna(row["latitud"]) and pd.notna(row["longitud"]):
                if st.button(f"📍 Ver en mapa {row['fullname']}"):

                    st.session_state.mapa_punto = {
                        "lat": row["latitud"],
                        "lon": row["longitud"],
                        "nombre": row["fullname"],
                        "roca": row["roca"],
                        "img": row["img"]
                    }

                    st.rerun()

# --------------------------------
# 🗺 MAPA GENERAL
# --------------------------------
elif vista == "🗺 Mapa":

    import folium
    from streamlit_folium import st_folium
    from folium.plugins import MarkerCluster

    st.header("Mapa general")

    df_mapa = df.dropna(subset=["latitud", "longitud"])
    
    if not df_mapa.empty:
        centro = [
            df_mapa["latitud"].mean(),
            df_mapa["longitud"].mean()
        ]
        zoom = 8
    # --------------------------------
    # ✅ JITTER PARA EVITAR SUPERPOSICIÓN
    # --------------------------------
    df_mapa = df_mapa.copy()

    df_mapa["lat_plot"] = df_mapa["latitud"]
    df_mapa["lon_plot"] = df_mapa["longitud"]

    # aplicar pequeña variación si hay duplicados
    duplicados = df_mapa.duplicated(subset=["latitud", "longitud"], keep=False)

    df_mapa.loc[duplicados, "lat_plot"] += (
        df_mapa.loc[duplicados].groupby(["latitud", "longitud"]).cumcount() * 0.0001
    )

    # ✅ si viene de una muestra → centrarse ahí
    if st.session_state.mapa_zoom:
        centro = [
            st.session_state.mapa_zoom["lat"],
            st.session_state.mapa_zoom["lon"]
        ]
        zoom = 12
    else:
        centro = [-25.5, -66]
        zoom = 9

    mapa = folium.Map(location=centro, zoom_start=zoom)
    cluster = MarkerCluster().add_to(mapa)
    
    for i, row in df_mapa.iterrows():

        html = f"<b>{row['fullname']}</b><br>{row['roca']}"

        if row["img"]:
            html += f'<br><img src="{row["img"]}" width="200">'

        # --------------------------------
        # ✅ POPUP PRO
        # --------------------------------
        # ID real (clave)
        id_text = f"{row['fullname']}|{i}"

        # HTML visible
        html_visible = f"""
        <b>{row['fullname']}</b><br>
        <b>Tipo:</b> {row.get('tipo','')}<br>
        <b>Subtipo:</b> {row.get('subtipo','')}<br>
        <b>Roca:</b> {row.get('roca','')}<br>
        """

        if row["img"]:
            html_visible += f'<br><img src="{row["img"]}" width="150" style="border-radius:6px;">'

        # ✅ combinación: TEXTO + HTML
        
        popup_text = f"""
        <div style="display:none">{id_text}</div>
        {html_visible}
        """


        folium.Marker(
            location=[row["lat_plot"], row["lon_plot"]],
            popup=folium.Popup(popup_text, max_width=250)
        ).add_to(cluster)
                
        
        
        

    map_data = st_folium(mapa, width=1000, height=600)

    # --------------------------------
    # ✅ CLICK EN MAPA
    # --------------------------------
    import re

    if map_data and map_data.get("last_object_clicked_popup"):

        texto = map_data["last_object_clicked_popup"]

        # --------------------------------
        # ✅ DETECTAR POR CÓDIGO (ROBUSTO)
        # --------------------------------
        lineas = texto.split("\n")

        if len(lineas) > 0:
            codigo = lineas[0].strip()

            fila = df[df["fullname"] == codigo]

            if not fila.empty:
                fila = fila.iloc[0]

                st.session_state.mapa_punto = {
                    "nombre": fila["fullname"]
                }

                st.rerun()
