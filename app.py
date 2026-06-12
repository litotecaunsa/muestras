import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

import re
import requests   
import streamlit.components.v1 as components   
# --- FUNCIONES DE SOPORTE 3d ---
def obtener_url_embed(url_sketchfab):
    if not url_sketchfab or str(url_sketchfab).strip() == "" or str(url_sketchfab) == "nan":
        return None
    
    url_str = str(url_sketchfab).strip()
    
    # Si es link corto, seguimos la redirección para obtener el link real con el ID
    if "skfb.ly" in url_str:
        try:
            respuesta = requests.get(url_str, allow_redirects=True, timeout=3)
            url_str = respuesta.url
        except Exception:
            pass

    # Extraemos el ID de 32 caracteres
    match = re.search(r"([a-f0-9]{32})", url_str)
    if match:
        id_modelo = match.group(1)
        return f"https://sketchfab.com/models/{id_modelo}/embed"
    
    return None



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

st.title("💎 Litoteca UNSA")

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
ruta_logo = "logolito_unsa.png"

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
    seleccion = df[df["samplebox"] == st.session_state.mapa_punto["nombre"]]
    
    if not seleccion.empty:
        fila = seleccion.iloc[0]
        st.sidebar.markdown("---")
        st.sidebar.subheader(f"📄 Muestra: {fila['samplebox']}")

        col_sb1, col_sb2 = st.sidebar.columns(2)
        with col_sb1:
            st.write(f"**Tipo:** {fila.get('tipo','')}")
            st.write(f"**Roca:** {fila.get('roca','')}")
        with col_sb2:
            st.write(f"**Subtipo:** {fila.get('subtipo','')}")
            st.write(f"**Color:** {fila.get('color','')}")
        
        st.sidebar.write(f"**Observaciones:** {fila.get('observaciones','')}")

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
            st.sidebar.image(fila["img_app"], caption=f"Muestra {fila['samplebox']} (Vista rápida)", use_container_width=True)
            st.sidebar.markdown(f"🔍[ Ver en Alta Resolución]({fila['img_original']})")

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
import io
import os
import requests
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def generar_pdf_ficha(row):
    """Genera un archivo PDF con el diseño institucional y la foto de la muestra."""
    buffer = io.BytesIO()
    
    # 1. Configuración del documento (Márgenes de 1.5 cm)
    margin = 42 # puntos (aprox 1.5cm)
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=margin, leftMargin=margin, 
        topMargin=margin, bottomMargin=margin
    )
    story = []
    styles = getSampleStyleSheet()
    
    # Ancho disponible real para el contenido y la foto
    ancho_disponible = letter[0] - (2 * margin) # 612 - 84 = 528 puntos

    # -------------------------------------------------------------------------
    # ✅ SECCIÓN ENCABEZADO INSTITUCIONAL (Tabla Invisible)
    # -------------------------------------------------------------------------
    logo_path = "logolito.png" # Usamos la misma variable que tienes configurada
    texto_encabezado = """
    <b>REPOSITORIO DE ROCAS</b><br/>
    Litoteca - Geología<br/>
    Facultad de Cs. Naturales - UNSA
    """
    
    style_header = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        alignment=1 # Centrado
    )
    
    # Maquetamos el encabezado en una tabla para alinear logo y texto lateralmente
    p_header = Paragraph(texto_encabezado, style_header)
    
    if os.path.exists(logo_path):
        # Escalamos el logo de manera fija para el membrete superior
        img_logo = RLImage(logo_path, width=50, height=50)
        # Tres columnas: Logo, Texto Centrado, Espacio vacío simétrico para balancear el centro
        tabla_header = Table([[img_logo, p_header, ""]], colWidths=[60, ancho_disponible - 120, 60])
    else:
        tabla_header = Table([[p_header]], colWidths=[ancho_disponible])
        
    tabla_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
    ]))
    story.append(tabla_header)
    story.append(Spacer(1, 15))
    
    # Línea divisoria decorativa institucional
    linea_decorativa = Table([[""]], colWidths=[ancho_disponible], rowHeights=[2])
    linea_decorativa.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), colors.HexColor('#FF4B4B')), # Color acento Streamlit/UNSA
    ]))
    story.append(linea_decorativa)
    story.append(Spacer(1, 15))

    # -------------------------------------------------------------------------
    # ✅ TÍTULO DE LA FICHA
    # -------------------------------------------------------------------------
    style_titulo = ParagraphStyle(
        'TituloStyle',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E1E1E'),
        alignment=0 # Izquierda
    )
    story.append(Paragraph(f"Ficha Técnica Muestra: {row.get('samplebox', 'S/N')}", style_titulo))
    story.append(Spacer(1, 12))

    # -------------------------------------------------------------------------
    # ✅ TABLA DE DATOS GEOLÓGICOS
    # -------------------------------------------------------------------------
    style_celda_negrita = ParagraphStyle('CeldaN', fontName='Helvetica-Bold', fontSize=10, leading=13)
    style_celda_normal = ParagraphStyle('CeldaD', fontName='Helvetica', fontSize=10, leading=13)
    
    # Datos básicos comunes
    datos_tabla = [
        [Paragraph("Código samplebox:", style_celda_negrita), Paragraph(str(row.get('samplebox','—')), style_celda_normal),
         Paragraph("Tipo de Roca:", style_celda_negrita), Paragraph(str(row.get('tipo','—')), style_celda_normal)],
        [Paragraph("Subtipo:", style_celda_negrita), Paragraph(str(row.get('subtipo','—')), style_celda_normal),
         Paragraph("Nombre Roca:", style_celda_negrita), Paragraph(str(row.get('roca','—')), style_celda_normal)],
        [Paragraph("Color característico:", style_celda_negrita), Paragraph(str(row.get('color','—')), style_celda_normal),
         Paragraph("Coordenadas (Lat/Lon):", style_celda_negrita), Paragraph(f"{row.get('latitud','—')}, {row.get('longitud','—')}", style_celda_normal)]
    ]
    
    # Agregar filas extra únicamente si es de tipo Sedimentaria
    if str(row.get('tipo','')).lower() == 'sedimentaria':
        datos_tabla.extend([
            [Paragraph("Textura / Estructura:", style_celda_negrita), Paragraph(f"{row.get('textura','—')} / {row.get('estructura','—')}", style_celda_normal),
             Paragraph("Minerales (Pri/Sec):", style_celda_negrita), Paragraph(f"{row.get('mimeral_pri','—')} / {row.get('mineral_secu','—')}", style_celda_normal)],
            [Paragraph("Fábrica (Clasto/Matriz/Cem):", style_celda_negrita), Paragraph(f"C: {row.get('clasto_sed','—')} | M: {row.get('matriz_sed','—')} | C: {row.get('cemento_sed','—')}", style_celda_normal),
             "", ""]
        ])
        
    # Añadir observaciones ocupando todo el ancho inferior de la tabla
    p_obs_label = Paragraph("Observaciones:", style_celda_negrita)
    p_obs_content = Paragraph(str(row.get('observaciones','Sin observaciones particulares.')), style_celda_normal)
    datos_tabla.append([p_obs_label, p_obs_content, "", ""])
    
    # Construcción formal de la tabla en ReportLab (4 columnas)
    w_col = ancho_disponible / 4.0
    t_datos = Table(datos_tabla, colWidths=[w_col*1.1, w_col*0.9, w_col*1.1, w_col*0.9])
    
    # Estilos visuales de la tabla geológica (Limpia y grisácea)
    estilo_tabla = [
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9F9F9')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CCCCCC')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        # Expansión de celdas para la fila de observaciones (ocupa de columna 1 a la 3)
        ('SPAN', (1, len(datos_tabla)-1), (3, len(datos_tabla)-1)),
    ]
    
    if str(row.get('tipo','')).lower() == 'sedimentaria':
        # Expandir la última celda de fábrica sobrante
        estilo_tabla.append(('SPAN', (1, len(datos_tabla)-2), (3, len(datos_tabla)-2)))
        
    t_datos.setStyle(TableStyle(estilo_tabla))
    story.append(t_datos)
    story.append(Spacer(1, 20))

    # -------------------------------------------------------------------------
    # ✅ SECCIÓN DE FOTOGRAFÍA OPTIMIZADA (CORREGIDA)
    # -------------------------------------------------------------------------
    if isinstance(row.get("img_original"), str) and row["img_original"].startswith("http"):
        try:
            url_foto = row["img_original"]
            
            # 🚀 TRUCO DE CLOUDINARY CORREGIDO: Usamos url_foto correctamente
            if "cloudinary.com" in url_foto and "/image/upload/" in url_foto:
                # Le pedimos a Cloudinary: calidad automática (q_auto), formato óptimo (f_auto)
                # y un ancho máximo de 1000 píxeles (w_1000).
                url_foto = url_foto.replace("/image/upload/", "/image/upload/f_auto,q_auto,w_1000/")
            
            # Descargamos la versión súper liviana
            respuesta = requests.get(url_foto, timeout=10)
            
            if respuesta.status_code == 200:
                imagen_bytes = io.BytesIO(respuesta.content)
                
                # Leemos dimensiones con PIL para respetar el aspect ratio original
                from PIL import Image as PILImage
                con_pil = PILImage.open(imagen_bytes)
                ancho_orig, alto_orig = con_pil.size
                
                # Escalamos calculando la proporción exacta para cubrir el ancho de página (528 ptos)
                proporcion = ancho_disponible / float(ancho_orig)
                alto_escalado = alto_orig * proporcion
                
                img_pdf = RLImage(imagen_bytes, width=ancho_disponible, height=alto_escalado)
                
                story.append(Paragraph("<b>Registro Fotográfico</b>", style_celda_negrita))
                story.append(Spacer(1, 8))
                story.append(img_pdf)
        except Exception as e:
            story.append(Paragraph(f"<i>No se pudo cargar la imagen remota en el PDF. (Error: {e})</i>", style_celda_normal))

    # Construir PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

def renderizar_muestra_catalogo(row, context="catalogo"):
    """Dibuja una muestra en el catálogo/buscador con lógica 'On Demand' y Visor 3D Apaisado."""
    st.markdown("---")
    
    # Creamos las dos columnas principales para los datos y acciones
    col1, col2 = st.columns([2, 1])

    with col1:
        # 🏷️ Cabecera principal con diseño de tarjeta
        st.markdown(f"### 🪨 Muestra: <span style='color:#FF4B4B;'>{row.get('samplebox', context)}</span>", unsafe_allow_html=True)
        
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
                
                # Sección 2: Mineralogía Desglosada
                st.markdown("#### 💎 Composición Mineralógica")
                cm1, cm2 = st.columns(2)
                with cm1:
                    st.markdown(f"**✨ Mineral Primario:**\n{row.get('mimeral_pri','—')}")
                with cm2:
                    st.markdown(f"**✨ Mineral Secundario:**\n{row.get('mineral_secu','—')}")
                
                st.markdown("---")
                
                # Sección 3: Matriz de Soporte
                st.markdown("#### 🔬 Análisis de Componentes")
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

    # Inicializamos las variables que usaremos para el control del 3D antes del bloque de columnas
    current_code = row['samplebox']
    tiene_3d = "3d" in row and isinstance(row["3d"], str) and str(row["3d"]).strip() != "" and str(row["3d"]) != "nan"
    
    if '3d_expandido' not in st.session_state:
        st.session_state['3d_expandido'] = None

    url_embed_3d = None
    is_3d_expanded = False

    with col2:
        st.write("**🎮 Herramientas:**")
        # Botón para geolocalizar (solo si tiene coordenadas)
        if pd.notna(row["latitud"]) and pd.notna(row["longitud"]):
            if st.button(f"📍 Ubicar en Mapa", key=f"map_{context}_{row['samplebox']}"):
                st.session_state.mapa_punto = {
                    "lat": row["latitud"],
                    "lon": row["longitud"],
                    "nombre": row["samplebox"]
                }
                st.session_state.mapa_zoom = None  
                st.session_state.vista = "🗺 Mapa"  
                st.rerun()
        
        # ---------------------------------------------------------
        # ✅ LÓGICA 'ON DEMAND' CLOUDINARY
        # ---------------------------------------------------------
        url_valida = isinstance(row["img_app"], str) and row["img_app"].startswith("http")

        if url_valida:
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
            
        # ---------------------------------------------------------
        # ✅ NUEVA ACCIÓN: BOTÓN INTERACTIVO 3D (SOLO SI TIENE LINK)
        # ---------------------------------------------------------
        if tiene_3d:
            url_embed_3d = obtener_url_embed(row["3d"])
            
            if url_embed_3d:
                is_3d_expanded = (st.session_state['3d_expandido'] == current_code)
                label_3d = "🔼 Ocultar Vista 3D" if is_3d_expanded else "📦 Ver en 3D"
                
                # Al agregar el row.name (índice) blindamos el botón contra cualquier duplicado accidental
                idx_fila = row.name if hasattr(row, 'name') else '0'
                if st.button(label_3d, key=f"btn_3d_{context}_{current_code}_{idx_fila}"):
                    if is_3d_expanded:
                        st.session_state['3d_expandido'] = None  
                    else:
                        st.session_state['3d_expandido'] = current_code  
                    st.rerun()

        # ---------------------------------------------------------
        # ✅ NUEVA ACCIÓN: DESCARGAR FICHA TÉCNICA EN PDF
        # ---------------------------------------------------------
        st.markdown("---")
        with st.spinner("Generando ficha técnica en PDF..."):
            try:
                pdf_datos = generar_pdf_ficha(row)
                st.download_button(
                    label="📄 Descargar Ficha",
                    data=pdf_datos,
                    file_name=f"Ficha_{row['samplebox']}.pdf",
                    mime="application/pdf",
                    key=f"download_{context}_{row['samplebox']}",
                    use_container_width=True
                )
            except Exception as error_pdf:
                st.error(f"Error PDF: {error_pdf}")

    # =============================================================================
    # 🌍 VISOR 3D APAYSADO (¡AFUERA Y ABAJO DE LAS COLUMNAS!)
    # =============================================================================
    # Rompemos el bloque indentado de 'with col2' volviendo a la sangría de la función
    if tiene_3d and url_embed_3d and is_3d_expanded:
        st.write("---")
        st.markdown(f"#### 🌍 Visor Interactivo 3D - Muestra {current_code}")
        
        iframe_html = f"""
        <div style="width: 100%; height: 550px; margin-top: 10px; margin-bottom: 10px;">
            <iframe 
                title="Visor 3D Sketchfab"
                src="{url_embed_3d}"
                width="100%" 
                height="100%" 
                frameborder="0" 
                allowfullscreen 
                mozallowfullscreen="true" 
                webkitallowfullscreen="true" 
                allow="autoplay; fullscreen; xr-spatial-tracking" 
                xr-spatial-tracking>
            </iframe>
        </div>
        """
        components.html(iframe_html, height=560)


                
# --------------------------------
# 🔎 VISTA: CATÁLOGO
# --------------------------------
if vista == "🔎 Catálogo":
    st.header("Repositorio de rocas")

    # 🆕 Función Callback para limpiar el buscador de forma segura
    def limpiar_buscador():
        st.session_state.busqueda_codigo = ""

    # ✅ BUSCADOR
    st.markdown("### 🔎 Buscar por código")
    t1, t2 = st.tabs(["Ingreso Manual", "Ayuda"])
    
    with t1:
        # Mantenemos el key del widget
        codigo_input = st.text_input("Código completo", placeholder="ej: 1IA1", key="busqueda_codigo").upper().strip()
    with t2:
        st.info("Ingresa el código de la roca. El mismo está compuesto por el número de roca, puerta, estante y caja. Ejemplo: 5ID1 o 5id1")

    # Renderizar Buscador
    if codigo_input:
        df_busqueda = df[df["samplebox"].astype(str) == codigo_input]
        
        if df_busqueda.empty:
            st.warning(f"No se encontró ninguna muestra con el código '{codigo_input}'")
            # Usamos el callback si no hay resultados
            st.button("🔄 Volver al catálogo completo", key="btn_volver_vacio", on_click=limpiar_buscador)
        else:
            st.success(f"Se encontró {len(df_busqueda)} coincidencia(s) para: {codigo_input}")
            
            # 🆕 BOTÓN DE RETORNO CON CALLBACK (Evita el StreamlitAPIException)
            st.button("⬅️ Volver al catálogo completo", use_container_width=True, key="btn_volver_exito", on_click=limpiar_buscador)
                
            for _, row in df_busqueda.iterrows():
                renderizar_muestra_catalogo(row, context="search")
            
            st.stop() # Detener renderizado del catálogo general si hay búsqueda

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

    # ✅ RESULTADOS INTELIGENTES (Solo bajo demanda de filtros)
    st.markdown("---")
    
    # Verificamos si el usuario activó algún filtro
    ha_filtrado = (tipo_sel != "Todos") or (subtipo_sel != "Todos") or (roca_sel != "Todos")

    if ha_filtrado:
        total_resultados = len(df_filtrado)
        st.write(f"🔎 Resultados encontrados: **{total_resultados}**")

        if total_resultados == 0:
            st.info("🥪 No se encontraron muestras que coincidan con la combinación de filtros seleccionada.")
        else:
            # Ponemos un límite de cortesía por rendimiento, pero ahora tiene sentido
            MAX_MUESTRAS_CATALOGO = 20 
            if total_resultados > MAX_MUESTRAS_CATALOGO:
                st.warning(f"Mostrando las primeras {MAX_MUESTRAS_CATALOGO} muestras. Refina los filtros para acotar la búsqueda.")
                df_filtrado = df_filtrado.head(MAX_MUESTRAS_CATALOGO)

            # Renderizado del bucle principal
            for _, row in df_filtrado.iterrows():
                renderizar_muestra_catalogo(row, context="cat")
    else:
        # Mensaje amigable cuando la pantalla está limpia
        st.info("💡 Selecciona un **Tipo**, **Subtipo** o **Roca** en los filtros de arriba (o ingresa un código en el buscador) para empezar a explorar las muestras.")

# --------------------------------
# 🗺 VISTA: MAPA GENERAL (FILTRADO INTELIGENTE)
# --------------------------------
elif vista == "🗺 Mapa":
    # Limpiar filas sin coordenadas válidas
    df_mapa = df.dropna(subset=["latitud", "longitud"])
    
    if df_mapa.empty:
        st.warning("No hay muestras georeferenciadas para mostrar en el mapa.")
        st.stop()

    # -------------------------------------------------------------------------
    # ✅ LÓGICA DE FILTRADO PARA ENFOQUE AISLADO
    # -------------------------------------------------------------------------
    # Verificamos si hay un punto seleccionado desde el catálogo
    hay_punto_seleccionado = st.session_state.mapa_punto is not None

    if hay_punto_seleccionado:
        nombre_buscado = st.session_state.mapa_punto["nombre"]
        st.header(f"📍 Ubicación de la Muestra: {nombre_buscado}")
        
        # Botón para salir del modo aislado y ver todo el mapa de nuevo
        if st.button("🌍 Ver mapa con todas las muestras", use_container_width=True):
            st.session_state.mapa_punto = None
            st.rerun()
            
        # Filtramos el dataframe del mapa para que contenga ÚNICAMENTE esta muestra
        df_mapa = df_mapa[df_mapa["samplebox"] == nombre_buscado]
        
        if df_mapa.empty:
            st.warning("La muestra seleccionada no tiene coordenadas válidas de GPS.")
            st.stop()
    else:
        st.header("Mapa de distribución general de muestras (UNSA)")

    # ✅ Gestión de Jitter (pequeña variación para puntos superpuestos)
    df_mapa = df_mapa.copy()
    df_mapa["lat_plot"] = df_mapa["latitud"]
    df_mapa["lon_plot"] = df_mapa["longitud"]

    duplicados = df_mapa.duplicated(subset=["latitud", "longitud"], keep=False)
    if duplicados.any():
        import numpy as np
        df_mapa.loc[duplicados, "lat_plot"] += np.random.uniform(-0.0001, 0.0001, len(df_mapa[duplicados]))
        df_mapa.loc[duplicados, "lon_plot"] += np.random.uniform(-0.0001, 0.0001, len(df_mapa[duplicados]))

    # ✅ Configuración del Centro y Zoom
    if hay_punto_seleccionado:
        # Si está aislada, centramos directo en ella con un zoom bien cercano
        row_punto = df_mapa.iloc[0]
        centro = [row_punto["lat_plot"], row_punto["lon_plot"]]
        zoom_init = 15 
    elif st.session_state.mapa_zoom:
        centro = [st.session_state.mapa_zoom["lat"], st.session_state.mapa_zoom["lon"]]
        zoom_init = st.session_state.mapa_zoom["zoom"]
    else:
        # Vista general (Salta / Campus UNSA)
        centro = [-24.728, -65.412]
        zoom_init = 7 

    # ✅ Crear Mapa Folium
    mapa = folium.Map(location=centro, zoom_start=zoom_init, tiles=None)
    
    # Capas Base (Google y Argenmap)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google", name="Google Satelital", overlay=False, control=True
    ).add_to(mapa)

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
        attr="Google", name="Google Terreno", overlay=False, control=True
    ).add_to(mapa)

    folium.TileLayer(
        tiles="https://wms.ign.gob.ar/geoserver/gwc/service/tms/1.0.0/capabaseargenmap@EPSG%3A3857@png/{z}/{x}/{y}.png",
        attr="Instituto Geográfico Nacional (IGN)", name="Argenmap (IGN)", overlay=False, control=True, tms=True
    ).add_to(mapa)

    # Si hay muchas muestras, usamos clusters. Si es una sola, no hace falta clusterizar
    if len(df_mapa) > 1:
        contenedor_puntos = MarkerCluster(name="Muestras UNSA").add_to(mapa)
    else:
        contenedor_puntos = mapa # Añadir directo al mapa si es el punto aislado

    folium.LayerControl(position="topright", collapsed=False).add_to(mapa)
    
    # ✅ Bucle de Marcadores
    for i, row in df_mapa.iterrows():
        popup_html = f"""
        <div style="font-family: sans-serif; min-width: 200px;">
            <div style="background-color: #f0f0f0; padding: 5px; border-radius: 4px; font-weight: bold; margin-bottom: 5px; color: black;">
                {row['samplebox']}
            </div>
            <span style="color: black;"><b>Tipo:</b> {row.get('tipo','--')}</span><br>
            <span style="color: black;"><b>Roca:</b> {row.get('roca','--')}</span><br>
            <span style="color: black;"><b>Color:</b> {row.get('color','--')}</span><br>
        """

        if row["img_app"]:
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

        # Si es la muestra buscada, cambiamos el icono por uno especial (estrella) para que resalte
        icono_tipo = 'info-sign'
        if hay_punto_seleccionado:
            icono_tipo = 'star' # Ícono de estrella para la destacada

        folium.Marker(
            location=[row["lat_plot"], row["lon_plot"]],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color=color_icon, icon=icono_tipo)
        ).add_to(contenedor_puntos)

    # ✅ Renderizar Mapa en Streamlit
    map_key = "mapa_gral"
    if hay_punto_seleccionado:
        map_key += f"_{st.session_state.mapa_punto['nombre']}"

    st_folium(mapa, width="100%", height=600, key=map_key, returned_objects=[])

    if hay_punto_seleccionado:
        st.info("ℹ️ Estás viendo únicamente la muestra seleccionada. Toda su información detallada está disponible en el panel izquierdo (Sidebar).")
    else:
        st.info("💡 Haz clic en los marcadores o clusters para explorar las muestras georeferenciadas de la UNSA.")
# --------------------------------
# ✅ CRÉDITOS Y PARTICIPANTES (AL FINAL DEL SIDEBAR)
# --------------------------------
st.sidebar.markdown("---")
with st.sidebar.expander("👥 Créditos del Proyecto", expanded=False):
    st.markdown(
        """
        <div style="font-size: 0.9rem;">
            <b>INTEGRANTES LITOTECA</b><br>
            <span style="color: gray; font-size: 0.8rem;">Desarrollo de base de datos y biblioteca de fotografías:</span>
            <ul style="margin-top: 5px; margin-bottom: 10px; padding-left: 20px;">
                <li>Emiliano Romero</li>
                <li>Álvaro Rodríguez</li>
                <li>Camila Leiva</li>
                <li>Sonia Tapia</li>
                <li>Ana Rebuffi</li>
                <li>Martina Contreras</li>
                <li>Julieta Vargas</li>
                <li>Nahuel Díaz</li>
                <li>Ernestina Elena</li>
                <li>Julieta Cancinos</li>
                <li>Gastón Maidana</li>
                <li>Lourdes Isasmendi</li>
                <li>Fabiola Cruz</li>
                <li>Gastón Santillán</li>
                <li>Agustín Beleizán</li>
            </ul>
            <b>Dirección:</b><br>Dr. Rubén Filipovich<br><br>
            <b>Desarrollo de aplicación:</b><br>MSc. Hernán Elena (INTA)
        </div>
        """, 
        unsafe_allow_html=True
    )
