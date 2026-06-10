import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

# --------------------------------
# ✅ SESSION STATE (INICIALIZACIÓN)
# --------------------------------
if "mapa_punto" not in st.session_state:
    st.session_state.mapa_punto = None

if "mapa_zoom" not in st.session_state:
    st.session_state.mapa_zoom = None

if "foto_expandida" not in st.session_state:
    st.session_state.foto_expandida = None

# --------------------------------
# CONFIG
# --------------------------------
# Pasamos "logolito.png" al parámetro page_icon
st.set_page_config(
    layout="wide", 
    page_title="Litoteca UNSA",
    page_icon="logolito.png"
)

st.title("🪨 Litoteca UNSA")

# --------------------------------
# GOOGLE SHEETS
# --------------------------------
@st.cache_data(ttl=600)
def load_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open("db_litoteca_unsa").worksheet("MUESTRAS")
    return pd.DataFrame(sheet.get_all_records())

# --------------------------------
# ✅ GESTIÓN DE IMÁGENES (CLOUDINARY DIRECTO)
# --------------------------------
def limpiar_url_imagen(texto):
    """Limpia el texto de la columna foto_url1 para obtener la URL base de forma ultra-estricta."""
    if pd.isna(texto) or texto is None:
        return None
        
    texto_str = str(texto).strip()
    
    if texto_str.lower() in ["", "0", "0.0", "nan", "none", "sin foto", "no", "<na>", "null"]:
        return None
        
    if texto_str.startswith("http://") or texto_str.startswith("https://"):
        return texto_str
        
    return None

def optimizar_url_cloudinary(url_original):
    """Toma una URL original de Cloudinary e inyecta parámetros de optimización."""
    if not isinstance(url_original, str) or not url_original:
        return None
        
    if "cloudinary.com" not in url_original:
        return url_original
    
    if "/image/upload/" in url_original:
        return url_original.replace("/image/upload/", "/image/upload/f_auto,q_auto,w_500/")
    return url_original

# --------------------------------
# DATOS
# --------------------------------
try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets. Verifica 'credenciales.json'. Error: {e}")
    st.stop()

df = df_raw.copy()

# ✅ Reparación automática de coordenadas
def fix_coord(valor, tipo="lat"):
    if pd.isna(valor) or valor == "":
        return None
    try:
        texto = str(valor).strip().replace(",", ".")
        texto_limpio = "".join(c for c in texto if c.isdigit() or c in ".-")
        if not texto_limpio: return None
        numero = float(texto_limpio)
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

# ✅ Procesamiento de Imágenes Cloudinary Ultra-Seguro
df["img_original"] = df["foto_url1"].apply(limpiar_url_imagen)
df["img_app"] = df["img_original"].apply(optimizar_url_cloudinary)
df["img_app"] = df["img_app"].where(df["img_app"].notna(), None)

# --------------------------------
# ✅ CONTROL DE VISTA Y LOGO (ESTILO INTA - ADAPTATIVO)
# --------------------------------
if "vista" not in st.session_state:
    st.session_state.vista = "🔎 Catálogo"

import os
ruta_logo = "logolito.png"

# Contenedor del encabezado del Sidebar
with st.sidebar.container():
    st.markdown(
        """
        <style>
        .sidebar-header {
            text-align: center;
            padding: 10px 0px;
        }
        .sidebar-title {
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            /* Eliminamos el color fijo para que sea adaptativo (blanco en Dark Mode) */
            margin-top: 15px;
            margin-bottom: 0px;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
    
    if os.path.exists(ruta_logo):
        st.image(ruta_logo, use_container_width=True)
    
    st.markdown('<p class="sidebar-title">Panel de Control</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)



# --------------------------------
# ✅ DETALLE EN SIDEBAR (Cuando se selecciona en mapa)
# --------------------------------
if st.session_state.mapa_punto:
    seleccion = df[df["fullname"] == st.session_state.mapa_punto["nombre"]]
    
    if not seleccion.empty:
        fila = seleccion.iloc[0]
        st.sidebar.markdown("---")
        st.sidebar.subheader(f"📄 Muestra: {fila['fullname']}")

        col_sb1, col_sb2 = st.sidebar.columns(2)
        with col_sb1:
            st.write(f"**Tipo:** {fila.get('tipo','')}")
            st.write(f"**Roca:** {fila.get('roca','')}")
        with col_sb2:
            st.write(f"**Subtipo:** {fila.get('subtipo','')}")
            st.write(f"**Color:** {fila.get('color','')}")
        
        st.write(f"**Observaciones:** {fila.get('observaciones','')}")

        if fila.get("tipo") == "Sedimentaria":
            with st.sidebar.expander("Ver detalles sedimentarios", expanded=True):
                st.write(f"**Textura:** {fila.get('textura','')}")
                st.write(f"**Estructura:** {fila.get('estructura','')}")
                st.write(f"**Mineral primario:** {fila.get('mimeral_pri','')}")
                st.write(f"**Mineral secundario:** {fila.get('mineral_secu','')}")
                st.write(f"**Clasto:** {fila.get('clasto_sed','')}")
                st.write(f"**Matriz:** {fila.get('matriz_sed','')}")
                st.write(f"**Cemento:** {fila.get('cemento_sed','')}")

        # 📄 FIX DEL ERROR: Forzamos validación estricta de string con http en la barra lateral
        sb_url_valida = isinstance(fila["img_app"], str) and fila["img_app"].startswith("http")
        if sb_url_valida:
            st.sidebar.image(fila["img_app"], caption=f"Muestra {fila['fullname']} (Vista rápida)", use_container_width=True)
            st.sidebar.markdown(f"[🔍 Ver en Alta Resolución]({fila['img_original']})")

        if st.sidebar.button("❌ Limpiar selección", use_container_width=True):
            st.session_state.mapa_punto = None
            st.session_state.foto_expandida = None
            st.rerun()

st.sidebar.markdown("---")
indice_actual = 0 if st.session_state.vista == "🔎 Catálogo" else 1

vista = st.sidebar.radio(
    "Seleccionar vista",
    ["🔎 Catálogo", "🗺 Mapa"],
    index=indice_actual
)

st.session_state.vista = vista

# --------------------------------
# FUNCIONES AUXILIARES DE RENDERIZADO
# --------------------------------
def renderizar_muestra_catalogo(row, context="catalogo"):
    """Dibuja una muestra en el catálogo/buscador con lógica 'On Demand'."""
    st.markdown("---")
    col1, col2 = st.columns([2, 1])

    with col1:
        # 🏷️ Cabecera principal con diseño de tarjeta
        st.markdown(f"### 🪨 Muestra: <span style='color:#FF4B4B;'>{row.get('fullname', context)}</span>", unsafe_allow_html=True)
        
        # 🗂️ Ficha de Datos Básicos en columnas limpias
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**📁 Tipo:**\n{row.get('tipo','—')}")
            st.markdown(f"**🎨 Color:**\n{row.get('color','—')}")
        with c2:
            st.markdown(f"**🌿 Subtipo:**\n{row.get('subtipo','—')}")
        with c3:
            st.markdown(f"**💎 Roca:**\n`{row.get('roca','—')}`")
            
        st.markdown(f"**📝 Observaciones:**\n*{row.get('observaciones','Sin observaciones particulares.')}*")

        # 🔬 Características Sedimentarias Avanzadas (Diseño Ficha Premium)
        if row.get("tipo") == "Sedimentaria":
            with st.expander("🔍 Ver Características Sedimentarias Detalladas", expanded=False):
                
                # Sección 1: Textura y Estructura
                st.markdown("#### 📐 Textura y Estructura")
                cx1, cx2 = st.columns(2)
                cx1.metric(label="🧬 Textura", value=str(row.get('textura','—')).capitalize())
                cx2.metric(label="🧱 Estructura", value=str(row.get('estructura','—')).capitalize())
                
                st.markdown("---")
                
                # Sección 2: Mineralogía Desglosada (Sin abreviaturas raras)
                st.markdown("#### 💎 Composición Mineralógica")
                cm1, cm2 = st.columns(2)
                with cm1:
                    st.markdown(f"**✨ Mineral Primario:**\n{row.get('mimeral_pri','—')}")
                with cm2:
                    st.markdown(f"**✨ Mineral Secundario:**\n{row.get('mineral_secu','—')}")
                
                st.markdown("---")
                
                
                # Sección 3: Matriz de Soporte (Clasto, Matriz, Cemento) adaptativa
                st.markdown("#### 🔬 Análisis de Componentes (Fábrica)")
                cc1, cc2, cc3 = st.columns(3)

                with cc1:
                    with st.container(border=True):
                        st.markdown("<div style='text-align:center;'><b>🔴 Clasto</b></div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align:center;'>{row.get('clasto_sed','—')}</div>", unsafe_allow_html=True)
                        
                with cc2:
                    with st.container(border=True):
                        st.markdown("<div style='text-align:center;'><b>🟡 Matriz</b></div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align:center;'>{row.get('matriz_sed','—')}</div>", unsafe_allow_html=True)
                        
                with cc3:
                    with st.container(border=True):
                        st.markdown("<div style='text-align:center;'><b>🟤 Cemento</b></div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align:center;'>{row.get('cemento_sed','—')}</div>", unsafe_allow_html=True)


    with col2:
        st.write("**Acciones:**")
        if pd.notna(row["latitud"]) and pd.notna(row["longitud"]):
            if st.button(f"📍 Ubicar en Mapa", key=f"map_{context}_{row['fullname']}"):
                st.session_state.mapa_punto = {
                    "lat": row["latitud"],
                    "lon": row["longitud"],
                    "nombre": row["fullname"]
                }
                st.session_state.mapa_zoom = None
                st.session_state.vista = "🗺 Mapa"
                st.rerun()
        
        # ---------------------------------------------------------
        # ✅ LÓGICA 'ON DEMAND' CLOUDINARY
        # ---------------------------------------------------------
        url_valida = isinstance(row["img_app"], str) and row["img_app"].startswith("http")

        if url_valida:
            current_code = row['fullname']
            is_expanded = (st.session_state.foto_expandida == current_code)
            label = "🔼 Ocultar Foto" if is_expanded else "📷 Ver Foto"
            
            if st.button(label, key=f"btn_foto_{context}_{current_code}"):
                if is_expanded:
                    st.session_state.foto_expandida = None
                else:
                    st.session_state.foto_expandida = current_code
                st.rerun()

            if is_expanded:
                st.markdown("---")
                st.markdown(f"""
                <a href="{row['img_original']}" target="_blank">
                    <img src="{row['img_app']}" style="width:100%; border-radius:8px; border: 2px solid #ddd; cursor: zoom-in;" title="Click para ver original en alta resolución">
                </a>
                <div style="text-align: center; color: gray; font-size: 0.8rem;">🔍 Click en la imagen para ampliar (Muestra {current_code})</div>
                """, unsafe_allow_html=True)
        else:
            st.warning("⚠️ Muestra sin foto disponible")

# --------------------------------
# 🔎 VISTA: CATÁLOGO
# --------------------------------
if vista == "🔎 Catálogo":
    st.header("Catálogo de muestras")

    st.markdown("### 🔎 Buscar por código")
    t1, t2 = st.tabs(["Ingreso Manual", "Ayuda"])
    
    with t1:
        codigo_input = st.text_input("Código completo", placeholder="ej: A-1IA1").upper().strip()
    with t2:
        st.info("Ingresa el código 'fullname' exacto que figura en el Sheet.")

    if codigo_input:
        df_busqueda = df[df["fullname"].astype(str) == codigo_input]
        
        if df_busqueda.empty:
            st.warning(f"No se encontró ninguna muestra con el código '{codigo_input}'")
        else:
            st.success(f"Se encontró {len(df_busqueda)} coincidencia(s) para: {codigo_input}")
            for _, row in df_busqueda.iterrows():
                renderizar_muestra_catalogo(row, context="search")
            st.stop()

    st.markdown("---")
    
    # ✅ NUEVOS FILTROS EN CASCADA COMPLETA (TIPO -> SUBTIPO -> ROCA)
    st.subheader("Filtrar catálogo completo")
    col_f1, col_f2, col_f3 = st.columns(3)
    
    df_filtrado = df.copy()

    with col_f1:
        tipos_disponibles = sorted(df["tipo"].dropna().unique())
        tipo_sel = st.selectbox("1. Filtrar por Tipo", ["Todos"] + tipos_disponibles)

    if tipo_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["tipo"] == tipo_sel]

    with col_f2:
        subtipos_disponibles = sorted(df_filtrado["subtipo"].dropna().unique())
        subtipo_sel = st.selectbox("2. Filtrar por Subtipo (opcional)", ["Todos"] + subtipos_disponibles)

    if subtipo_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["subtipo"] == subtipo_sel]

    with col_f3:
        rocas_disponibles = sorted(df_filtrado["roca"].dropna().unique())
        roca_sel = st.selectbox("3. Filtrar por Roca (opcional)", ["Todos"] + rocas_disponibles)

    if roca_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["roca"] == roca_sel]

    # ✅ RESULTADOS
    MAX_MUESTRAS_CATALOGO = 50
    total_resultados = len(df_filtrado)
    st.write(f"🔎 Resultados encontrados: **{total_resultados}**")

    if total_resultados > MAX_MUESTRAS_CATALOGO:
        st.warning(f"Mostrando solo las primeras {MAX_MUESTRAS_CATALOGO} muestras para optimizar carga. Usa los filtros o el buscador para refinar.")
        df_filtrado = df_filtrado.head(MAX_MUESTRAS_CATALOGO)

    for _, row in df_filtrado.iterrows():
        renderizar_muestra_catalogo(row, context="cat")

# --------------------------------
# 🗺 VISTA: MAPA GENERAL
# --------------------------------
elif vista == "🗺 Mapa":
    st.header("Mapa de distribución de muestras (UNSA)")

    df_mapa = df.dropna(subset=["latitud", "longitud"])
    
    if df_mapa.empty:
        st.warning("No hay muestras georeferenciadas para mostrar en el mapa.")
        st.stop()

    df_mapa = df_mapa.copy()
    df_mapa["lat_plot"] = df_mapa["latitud"]
    df_mapa["lon_plot"] = df_mapa["longitud"]

    duplicados = df_mapa.duplicated(subset=["latitud", "longitud"], keep=False)
    if duplicados.any():
        import numpy as np
        df_mapa.loc[duplicados, "lat_plot"] += np.random.uniform(-0.0001, 0.0001, len(df_mapa[duplicados]))
        df_mapa.loc[duplicados, "lon_plot"] += np.random.uniform(-0.0001, 0.0001, len(df_mapa[duplicados]))

    if st.session_state.mapa_zoom and st.session_state.mapa_punto:
        centro = [st.session_state.mapa_zoom["lat"], st.session_state.mapa_zoom["lon"]]
        zoom_init = st.session_state.mapa_zoom["zoom"]
    elif st.session_state.mapa_punto:
        p = st.session_state.mapa_punto
        centro = [p["lat"], p["lon"]]
        zoom_init = 14
    else:
        centro = [-24.8, -65.4]
        zoom_init = 6

    mapa = folium.Map(location=centro, zoom_start=zoom_init, tiles="OpenStreetMap")
    cluster = MarkerCluster(name="Muestras UNSA").add_to(mapa)
    
    folium.TileLayer('Stamen Terrain', name="Terreno", attr="Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under ODbL.").add_to(mapa)
    folium.LayerControl().add_to(mapa)
    
    for i, row in df_mapa.iterrows():
        popup_html = f"""
        <div style="font-family: sans-serif; min-width: 200px;">
            <div style="background-color: #f0f0f0; padding: 5px; border-radius: 4px; font-weight: bold; margin-bottom: 5px;">
                {row['fullname']}
            </div>
            <b>Tipo:</b> {row.get('tipo','--')}<br>
            <b>Roca:</b> {row.get('roca','--')}<br>
            <b>Color:</b> {row.get('color','--')}<br>
        """

        if isinstance(row["img_app"], str) and row["img_app"].startswith("http"):
            popup_html += f"""
            <div style="margin-top: 8px; text-align: center;">
                <img src="{row['img_app']}" width="180" style="border-radius:6px; border: 1px solid #ccc;"><br>
                <a href="{row['img_original']}" target="_blank" style="font-size: 0.8rem; text-decoration: none; color: #007bff;">🔍 Ver original/ampliar</a>
            </div>
            """
        else:
            popup_html += """<div style="color: gray; margin-top:5px; font-style: italic;">(Sin foto)</div>"""
        
        popup_html += "</div>"

        color_icon = 'blue'
        tipo_lower = str(row.get('tipo','')).lower()
        if 'sedimentaria' in tipo_lower: color_icon = 'green'
        elif 'ígnea' in tipo_lower or 'ignea' in tipo_lower: color_icon = 'red'
        elif 'metamórfica' in tipo_lower or 'metamorfica' in tipo_lower: color_icon = 'purple'

        folium.Marker(
            location=[row["lat_plot"], row["lon_plot"]],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color=color_icon, icon='info-sign')
        ).add_to(cluster)

    map_key = "mapa_gral"
    if st.session_state.mapa_punto:
        map_key += f"_{st.session_state.mapa_punto['nombre']}"

    st_folium(mapa, width="100%", height=600, key=map_key, returned_objects=[])

    st.info("💡 Haz clic en los marcadores (o números de cluster) para ver la info de la muestra y su foto optimizada. Usa el Catálogo para buscar muestras específicas y ubicarlas aquí.")
