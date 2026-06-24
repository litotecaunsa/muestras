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


# caja de colordef obtener_estilo_badge_fullname(fullname):
def obtener_estilo_badge_fullname(fullname):
    """Devuelve el estilo CSS para el badge según la inicial del fullname (R, V, A)."""
    if not fullname or pd.isna(fullname):
        return None
    
    val = str(fullname).strip().upper()
    
    # Colores estéticos y legibles
    bg_color = "#6c757d"
    if val.startswith("R"):
        bg_color = "#D32F2F"
    elif val.startswith("V"):
        bg_color = "#2E7D32"
    elif val.startswith("A"):
        bg_color = "#1565C0"
        
    return f'<span style="background-color: {bg_color}; color: white; padding: 4px 10px; border-radius: 6px; font-size: 0.9rem; font-weight: bold; margin-left: 10px; white-space: nowrap;">📦 {val}</span>'
    


# --------------------------------
# ✅ SESSION STATE (INICIALIZACIÓN)
# --------------------------------
# Control de selección en mapa
if "mapa_punto" not in st.session_state:
    st.session_state.mapa_punto = None

# Control de zoom en mapa
if "mapa_zoom" not in st.session_state:
    st.session_state.mapa_zoom = None

# ✅ NUEVO: Control para visualización 'On Demand' en el catálogo
# Guarda qué código de muestra tiene la foto expandida actualmente
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
    # 1. Si es nulo de pandas, nativo o vacío, se descarta
    if pd.isna(texto) or texto is None:
        return None
        
    # 2. Convertir a string y limpiar espacios extremos
    texto_str = str(texto).strip()
    
    # 3. Si quedó vacío o es una palabra clave de error/vacío, se descarta
    if texto_str.lower() in ["", "0", "0.0", "nan", "none", "sin foto", "no", "<na>", "null"]:
        return None
        
    # 4. Control definitivo: Debe empezar con el protocolo web correcto
    if texto_str.startswith("http://") or texto_str.startswith("https://"):
        return texto_str
        
    return None

def optimizar_url_cloudinary(url_original):
    """Toma una URL original de Cloudinary e inyecta parámetros de optimización."""
    # Control estricto: si no recibimos un string limpio con contenido, devolvemos None
    if not isinstance(url_original, str) or not url_original:
        return None
        
    if "cloudinary.com" not in url_original:
        return url_original
    
    # Inyectar parámetros antes del nombre del archivo (después de /upload/)
    if "/image/upload/" in url_original:
        return url_original.replace("/image/upload/", "/image/upload/f_auto,q_auto,w_500/")
    return url_original






# --------------------------------
# DATOS
# --------------------------------
# Intentar cargar datos, manejar error de credenciales
try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets. Verifica 'credenciales.json'. Error: {e}")
    st.stop()

# Crear copia para trabajar
df = df_raw.copy()

# ✅ Reparación automática de coordenadas (tu lógica original mejorada)
def fix_coord(valor, tipo="lat"):
    if pd.isna(valor) or valor == "":
        return None
    try:
        texto = str(valor).strip().replace(",", ".")
        # Eliminar cualquier carácter que no sea número, punto o signo menos
        texto_limpio = "".join(c for c in texto if c.isdigit() or c in ".-")
        if not texto_limpio: return None
        numero = float(texto_limpio)
        # Corrección por escala (asumiendo formato incorrecto sin decimales)
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
# 1. Forzamos a que la columna original se trate temporalmente como objeto/string antes de limpiar
df["img_original"] = df["foto_url1"].apply(limpiar_url_imagen)

# 2. Aplicamos la optimización asegurando que reemplace cualquier residuo con None real
df["img_app"] = df["img_original"].apply(optimizar_url_cloudinary)

# 3. PASO EXTRA DE SEGURIDAD: Forzamos a que si img_app es un string vacío o nulo de pandas, sea un None de Python puro
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

# Dejamos una sola línea limpia aquí
 


# --------------------------------
# ✅ CONTROL DE VISTAS EN EL SIDEBAR
# --------------------------------
st.sidebar.markdown("---")

# Definir cuál opción debe estar seleccionada por defecto en base al session_state
indice_actual = 0 if st.session_state.vista == "🔎 Catálogo" else 1

# Primero definimos la variable 'vista' para que Python la conozca
vista = st.sidebar.radio(
    "Seleccionar vista",
    ["🔎 Catálogo", "🗺 Mapa"],
    index=indice_actual
)

# Sincronizamos el estado
st.session_state.vista = vista


# --------------------------------
# ✅ DETALLE EN SIDEBAR (Cuando se selecciona en mapa)
# --------------------------------
if st.session_state.mapa_punto:
    # Buscar la fila por samplebox
    seleccion = df[df["samplebox"] == st.session_state.mapa_punto["nombre"]]
    
    if not seleccion.empty:
        fila = seleccion.iloc[0]
        st.sidebar.markdown("---")
        
        # Badge y Título alineados horizontalmente
        badge_sidebar = obtener_estilo_badge_fullname(fila.get("fullname")) or ""
        st.sidebar.markdown(
            f'<h3 style="margin: 0 0 15px 0; padding: 0; line-height: 1.5; display: block;">'
            f'<span style="vertical-align: middle;">📄 Muestra: </span>'
            f'<span style="vertical-align: middle; font-weight: bold;">{fila["samplebox"]}</span>'
            f'{badge_sidebar}'
            f'</h3>', 
            unsafe_allow_html=True
        )
            
        # Info Básica: Un dato abajo del otro sin columnas
        st.sidebar.write(f"**Tipo:** {fila.get('tipo','')}")
        st.sidebar.write(f"**Subtipo:** {fila.get('subtipo','')}")
        st.sidebar.write(f"**Roca:** {fila.get('roca','')}")
        st.sidebar.write(f"**Color:** {fila.get('color','')}")
        st.sidebar.write(f"**Observaciones:** {fila.get('observaciones','')}")

        # Detalle Sedimentaria
        if fila.get("tipo") == "Sedimentaria":
            with st.sidebar.expander("Ver detalles sedimentarios", expanded=True):
                st.write(f"**Textura:** {fila.get('textura','')}")
                st.write(f"**Estructura:** {fila.get('estructura','')}")
                st.write(f"**Mineral primario:** {fila.get('mimeral_pri','')}")
                st.write(f"**Mineral secundario:** {fila.get('mineral_secu','')}")
                st.write(f"**Clasto:** {fila.get('clasto_sed','')}")
                st.write(f"**Matriz:** {fila.get('matriz_sed','')}")
                st.write(f"**Cemento:** {fila.get('cemento_sed','')}")

        # Imagen (Optimizada para sidebar)
        if fila["img_app"]:
            st.sidebar.image(fila["img_app"], caption=f"Muestra {fila['samplebox']} (Vista rápida)", use_container_width=True)
            st.sidebar.markdown(f"🔍 [Ver en Alta Resolución]({fila['img_original']})")

        if st.sidebar.button("❌ Limpiar selección", use_container_width=True):
            st.session_state.mapa_punto = None
            st.session_state.foto_expandida = None 
            st.rerun()
            
            

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


from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def agregar_pie_pagina(canvas, doc):
    canvas.saveState()

    width, height = doc.pagesize

    # ✅ Línea superior
    canvas.setStrokeColor(colors.HexColor("#CCCCCC"))
    canvas.setLineWidth(0.5)
    canvas.line(40, 50, width - 40, 50)

    # ✅ Fondo gris
    canvas.setFillColor(colors.HexColor("#F5F5F5"))
    canvas.rect(40, 15, width - 80, 30, fill=1, stroke=0)

    # ✅ estilo centrado
    styles = getSampleStyleSheet()
    style_pie = ParagraphStyle(
        name="PieStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        alignment=1,  # 👈 CENTRADO real
        textColor=colors.HexColor("#333333"),
        leading=12
    )

    
    texto_pie = """
    Escuela de Geología, Facultad de Ciencias Naturales, UNSa &nbsp;|&nbsp;
    ✉ litoteca2023@gmail.com &nbsp;|&nbsp;
    <link href="https://sites.google.com/view/litoteca-unsa/p%C3%A1gina-principal">
    <font color="#1565C0"><b> Sitio Web</b></font>
    </link>
    """


    p = Paragraph(texto_pie, style_pie)

    # ✅ centrado real horizontal
    p_width, p_height = p.wrap(width - 80, height)
    p.drawOn(canvas, (width - p_width) / 2, 22)

    canvas.restoreState()
    

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
    # ✅ TÍTULO DE LA FICHA + BADGE COLOR INTERNADO
    # -------------------------------------------------------------------------
    style_titulo = ParagraphStyle(
        'TituloStyle',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=24, # Aumentamos levemente para que el fondo de color no se corte
        textColor=colors.HexColor('#1E1E1E'),
        alignment=0 # Izquierda
    )
    
    # Lógica de color idéntica a la app para el PDF
    fullname_val = str(row.get('fullname', '')).strip().upper()
    bg_color_pdf = "#6c757d" # Gris por defecto
    
    if fullname_val.startswith("R"):
        bg_color_pdf = "#D32F2F" # Rojo
    elif fullname_val.startswith("V"):
        bg_color_pdf = "#2E7D32" # Verde
    elif fullname_val.startswith("A"):
        bg_color_pdf = "#1565C0" # Azul
        
    # Si tiene fullname, armamos el fragmento con fondo de color y texto blanco
    if fullname_val and fullname_val != "NAN" and fullname_val != "":
        badge_pdf = f'  <font color="white" backColor="{bg_color_pdf}"><b>{fullname_val}</b></font>'
    else:
        badge_pdf = ""
        
    # Inyectamos el título y el badge juntos
    texto_titulo = f"Ficha Técnica Muestra: {row.get('samplebox', 'S/N')} / {badge_pdf}"
    story.append(Paragraph(texto_titulo, style_titulo))
    story.append(Spacer(1, 12))

    # -------------------------------------------------------------------------
    # ✅ TABLA DE DATOS GEOLÓGICOS
    # -------------------------------------------------------------------------
    style_celda_negrita = ParagraphStyle('CeldaN', fontName='Helvetica-Bold', fontSize=10, leading=13)
    style_celda_normal = ParagraphStyle('CeldaD', fontName='Helvetica', fontSize=10, leading=13)
    # Preparamos el texto de las coordenadas de forma limpia
    lat = row.get('latitud')
    lon = row.get('longitud')
    
    # Si alguna de las dos coordenadas es nula, vacía o "nan", mostramos el mensaje personalizado
    if pd.isna(lat) or pd.isna(lon) or lat is None or lon is None or str(lat).lower() == 'nan' or str(lon).lower() == 'nan':
        coordenadas_texto = "No georreferenciada"
    else:
        coordenadas_texto = f"{lat}, {lon}"
    # Datos básicos comunes (Actualizado con Fullname)
    datos_tabla = [
        [Paragraph("Código:", style_celda_negrita), Paragraph(str(row.get('samplebox','—')), style_celda_normal),
         Paragraph("Tipo de Roca:", style_celda_negrita), Paragraph(str(row.get('tipo','—')), style_celda_normal)],
        [Paragraph("Subtipo:", style_celda_negrita), Paragraph(str(row.get('subtipo','—')), style_celda_normal),
         Paragraph("Nombre Roca:", style_celda_negrita), Paragraph(str(row.get('roca','—')), style_celda_normal)],
        [Paragraph("Color característico:", style_celda_negrita), Paragraph(str(row.get('color','—')), style_celda_normal),
         Paragraph("Coordenadas (Lat/Lon):", style_celda_negrita), Paragraph(coordenadas_texto, style_celda_normal)]
    ]
    
    # Agregar filas extra únicamente si es de tipo Sedimentaria
    if str(row.get('tipo','')).lower() == 'sedimentaria':
        datos_tabla.extend([
            [Paragraph("Textura / Estructura:", style_celda_negrita), Paragraph(f"{row.get('textura','—')} / {row.get('estructura','—')}", style_celda_normal),
             Paragraph("Minerales (Pri/Sec):", style_celda_negrita), Paragraph(f"{row.get('mimeral_pri','—')} / {row.get('mineral_secu','—')}", style_celda_normal)],
            [Paragraph("Clasto/Matriz/Cemento:", style_celda_negrita), Paragraph(f"C: {row.get('clasto_sed','—')} | M: {row.get('matriz_sed','—')} | C: {row.get('cemento_sed','—')}", style_celda_normal),
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
                
                story.append(Paragraph("<b>Registro Fotográfico:</b>", style_celda_negrita))
                story.append(Spacer(1, 8))
                story.append(img_pdf)
        except Exception as e:
            story.append(Paragraph(f"<i>No se pudo cargar la imagen remota en el PDF. (Error: {e})</i>", style_celda_normal))
    
    
    # Construir PDF
    doc.build(story, onFirstPage=agregar_pie_pagina, onLaterPages=agregar_pie_pagina)
    buffer.seek(0)
    return buffer



    
def renderizar_muestra_catalogo(row, context="catalogo"):
    """Dibuja una muestra en el catálogo/buscador con lógica 'On Demand' y diseño de ancho completo para PDF."""
    st.markdown("---")
    
    # Creamos las dos columnas principales para los datos y acciones rápidas
    col1, col2 = st.columns([2, 1])

    # Inicializamos las variables que usaremos para el control del 3D antes del bloque de columnas
    current_code = row['samplebox']
    tiene_3d = "3d" in row and isinstance(row["3d"], str) and str(row["3d"]).strip() != "" and str(row["3d"]) != "nan"
    
    if '3d_expandido' not in st.session_state:
        st.session_state['3d_expandido'] = None

    url_embed_3d = None
    is_3d_expanded = False
    
    if tiene_3d:
        url_embed_3d = obtener_url_embed(row["3d"])
        if url_embed_3d:
            is_3d_expanded = (st.session_state['3d_expandido'] == current_code)

    with col1:
        # 🏷️ Cabecera principal con diseño de tarjeta + Badge Fullname (Inyección directa limpia)
        badge_html = obtener_estilo_badge_fullname(row.get("fullname")) or ""
        
        # Título h3 donde todo el contenido interno está forzado a ser una sola línea inline
        st.markdown(
            f'<h3 style="margin: 0 0 15px 0; padding: 0; line-height: 1.5; display: block;">'
            f'<span style="vertical-align: middle;">🪨 Muestra: </span>'
            f'<span style="color:#FF4B4B; vertical-align: middle;">{row.get("samplebox", context)}</span>'
            f'{badge_html}'
            f'</h3>', 
            unsafe_allow_html=True
        )
        
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
                
                with cx1:
                    st.markdown("**🧬 Textura**")
                    st.write(row.get('textura','—'))

                with cx2:
                    st.markdown("**🧱 Estructura**")
                    st.write(row.get('estructura','—'))
                                
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

    with col2:
        st.write("**Acciones Rápidas:**")
        # Botón para geolocalizar (solo si tiene coordenadas)
        if pd.notna(row["latitud"]) and pd.notna(row["longitud"]):
            if st.button(f"📍 Ubicar en Mapa", key=f"map_{context}_{row['samplebox']}", use_container_width=True):
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
            
            if st.button(label, key=f"btn_foto_{context}_{current_code}", use_container_width=True):
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
                <div style="text-align: center; color: gray; font-size: 0.8rem;">🔍 Click en la imagen para ampliar</div>
                """, unsafe_allow_html=True)
        else:
            st.warning("⚠️ Muestra sin foto disponible")
            
        # ---------------------------------------------------------
        # ✅ BOTÓN INTERACTIVO 3D (EN LA BOTONERA LATERAL)
        # ---------------------------------------------------------
        if tiene_3d and url_embed_3d:
            label_3d = "🔼 Ocultar Vista 3D" if is_3d_expanded else "📦 Ver en 3D"
            idx_fila = row.name if hasattr(row, 'name') else '0'
            
            if st.button(label_3d, key=f"btn_3d_{context}_{current_code}_{idx_fila}", use_container_width=True):
                if is_3d_expanded:
                    st.session_state['3d_expandido'] = None  
                else:
                    st.session_state['3d_expandido'] = current_code  
                st.rerun()

    # =============================================================================
    # 🌍 SECCIÓN DE ANCHO COMPLETO (FUERA Y ABAJO DE LAS COLUMNAS COL1 Y COL2)
    # =============================================================================
    
    # 1. El Visor 3D si está activo toma todo el ancho disponible de la pantalla de forma apaisada
    if tiene_3d and url_embed_3d and is_3d_expanded:
        st.write("---")
        st.markdown(f"#### 🌍 Visor 3D - Muestra {current_code}")
        
        iframe_html = f"""
        <div style="width: 100%; height: 500px; margin-top: 10px; margin-bottom: 10px;">
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
        components.html(iframe_html, height=510)

    # 2. El botón de Descarga de Ficha técnica pasa al fondo absoluto ocupando todo el ancho horizontal
    st.write("---")
    with st.spinner("Generando ficha técnica en PDF..."):
        try:
            pdf_datos = generar_pdf_ficha(row)
            st.download_button(
                label=f"📄 Descargar Ficha Técnica (Muestra {row['samplebox']})",
                data=pdf_datos,
                file_name=f"Ficha_{row['samplebox']}.pdf",
                mime="application/pdf",
                key=f"download_{context}_{row['samplebox']}",
                use_container_width=True  # 👈 Ocupa el 100% del ancho de la app
            )
        except Exception as error_pdf:
            st.error(f"Error al compilar el PDF de la muestra: {error_pdf}")


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
        st.info("Ingresa el código de la roca. El mismo esta compuesto número de roca, puerta, estante y caja. Todos los caracteres deberán ser escritos en mayúsculas")

    # Renderizar Buscador u Opciones Generales usando un flujo condicional
    if codigo_input:
        df_busqueda = df[df["samplebox"].astype(str) == codigo_input]
        
        if df_busqueda.empty:
            st.warning(f"No se encontró ninguna muestra con el código '{codigo_input}'")
            # Usamos el callback si no hay resultados
            st.button("🔄 Volver al catálogo completo", key="btn_volver_vacio", on_click=limpiar_buscador)
        else:
            st.success(f"Se encontró {len(df_busqueda)} coincidencia(s) para: {codigo_input}")
            
            # 🆕 BOTÓN DE RETORNO CON CALLBACK
            st.button("⬅️ Volver al catálogo completo", use_container_width=True, key="btn_volver_exito", on_click=limpiar_buscador)
                
            for _, row in df_busqueda.iterrows():
                renderizar_muestra_catalogo(row, context="search")
            
            # NOTA: Se removió el st.stop() para permitir que el Sidebar termine de dibujarse de manera prolija.

    else:
        # ✅ FILTROS DEL CATÁLOGO
        st.subheader("Filtrar catálogo completo")
        
        # 🆕 NUEVOS FILTROS INTERACTIVOS: Avanzados / Multimedia
        col_adv1, col_adv2 = st.columns(2)
        with col_adv1:
            filtro_3d = st.checkbox("📦 Mostrar solo muestras con Visor 3D", value=False)
        with col_adv2:
            filtro_geo = st.checkbox("🗺️ Mostrar solo muestras georreferenciadas", value=False)

        # Clonamos el dataframe original para empezar a aplicar la cascada
        df_filtrado = df.copy()

        # 🆕 Aplicar filtros avanzados primero si están activos
        if filtro_3d:
            # Filtra las que tienen contenido válido en la columna '3d'
            df_filtrado = df_filtrado[
                df_filtrado["3d"].notna() & 
                (df_filtrado["3d"].astype(str).str.strip() != "") & 
                (df_filtrado["3d"].astype(str) != "nan")
            ]
            
        if filtro_geo:
            # Filtra las que tienen coordenadas válidas de latitud y longitud
            df_filtrado = df_filtrado.dropna(subset=["latitud", "longitud"])

        # Desplegables en cascada (Tipo -> Subtipo -> Roca)
        col_f1, col_f2, col_f3 = st.columns(3)

        # 1. Filtro por Tipo (ahora dinámico según los filtros anteriores)
        with col_f1:
            tipos_disponibles = sorted(df_filtrado["tipo"].dropna().unique())
            tipo_sel = st.selectbox("1. Filtrar por Tipo", ["Todos"] + tipos_disponibles)

        if tipo_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["tipo"] == tipo_sel]

        # 2. Filtro por Subtipo
        with col_f2:
            subtipos_disponibles = sorted(df_filtrado["subtipo"].dropna().unique())
            subtipo_sel = st.selectbox("2. Filtrar por Subtipo", ["Todos"] + subtipos_disponibles)

        if subtipo_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["subtipo"] == subtipo_sel]

        # 3. Filtro por Roca
        with col_f3:
            rocas_disponibles = sorted(df_filtrado["roca"].dropna().unique())
            roca_sel = st.selectbox("3. Filtrar por Roca", ["Todos"] + rocas_disponibles)

        if roca_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["roca"] == roca_sel]
            

        # ✅ RESULTADOS INTELIGENTES (Se activa si usó filtros de cascada O los nuevos checkboxes)
        st.markdown("---")
        
        # Verificamos si el usuario activó cualquier tipo de filtro
        ha_filtrado = (tipo_sel != "Todos") or (subtipo_sel != "Todos") or (roca_sel != "Todos") or filtro_3d or filtro_geo

        if ha_filtrado:
            total_resultados = len(df_filtrado)
            st.write(f"🔎 Resultados encontrados: **{total_resultados}**")

            if total_resultados == 0:
                st.info("🥪 No se encontraron muestras que coincidan con la combinación de filtros seleccionada.")
            else:
                # Límite de cortesía por rendimiento
                MAX_MUESTRAS_CATALOGO = 20 
                if total_resultados > MAX_MUESTRAS_CATALOGO:
                    st.warning(f"Mostrando las primeras {MAX_MUESTRAS_CATALOGO} muestras. Refina los filtros para acotar la búsqueda.")
                    df_filtrado = df_filtrado.head(MAX_MUESTRAS_CATALOGO)

                # Renderizado del bucle principal
                for _, row in df_filtrado.iterrows():
                    renderizar_muestra_catalogo(row, context="cat")
        else:
            # Mensaje amigable cuando la pantalla está limpia
            st.info("💡 Selecciona alguna opción o marca un filtro arriba para empezar a explorar las muestras.")
        
        
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
        st.header("Muestras georeferenciadas")

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
            <div style="background-color: #e8a7a7; padding: 5px; border-radius: 4px; font-weight: bold; margin-bottom: 5px; color: black;text-align: center;">
                Muestra {row['samplebox']} 
            </div>
            <span style="color: black;"><b>Tipo:</b> {row.get('tipo','--')}</span><br>
            <span style="color: black;"><b>Roca:</b> {row.get('roca','--')}</span><br>
            <span style="color: black;"><b>Color:</b> {row.get('color','--')}</span><br>
            <span style="color: black;"><b>Código:</b> {row.get('fullname','--')}</span><br>
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
# --------------------------------
# ✅ PRESENTACIÓN INSTITUCIONAL (ARRIBA DEL SELECTOR DE VISTAS)
# --------------------------------
with st.sidebar.expander("🏛️ Acerca del Repositorio Digital", expanded=False):
    st.markdown(
        """
        <div style="text-align: justify; font-size: 0.9rem; line-height: 1.4;">
            Esta aplicación interactiva es la extensión digital de 
            <a href="https://sites.google.com/view/litoteca-unsa/p%C3%A1gina-principal" target="_blank" style="text-decoration: none; color: #FF4B4B; font-weight: bold;">
                "La litoteca"
            </a>, el primer repositorio de muestras geológicas de la Argentina desarrollado por la Universidad Nacional de Salta (UNSa).<br><br>
            A través de este sistema, usted puede explorar de manera dinámica la colección de rocas y minerales de la Facultad de Ciencias Naturales. La plataforma permite realizar búsquedas avanzadas por codificación de almacenamiento, filtrar el catálogo por tipo de roca, visualizar mapas de muestras georreferenciadas, interactuar con modelos multimedia en 3D y exportar fichas técnicas institucionales en formato PDF.<br><br>
            El propósito de este entorno digital es consolidar una herramienta científica de consulta, aprendizaje e investigación ágil, diseñada para optimizar los estudios teóricos y facilitar el acceso libre al patrimonio geológico de nuestro país.
        </div>
        """,
        unsafe_allow_html=True
    )
with st.sidebar.expander("👥 Créditos", expanded=False):
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
# ✅ Registro de Versión, Créditos Institucionales y Licencia CC al fondo del Sidebar
st.sidebar.markdown("---") 
st.sidebar.markdown(
    """
    <div style="text-align: center; color: gray; font-size: 0.85rem; line-height: 1.5;">
        <span style="font-size: 0.8rem; color: #888888;">Versión 1.1.0 (2026)</span><br>
        <div style="margin-top: 5px; margin-bottom: 5px;">
            <b>© 2026 Litoteca Digital</b>
        </div>
        <div style="margin-top: 10px;">
            <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/deed.es" target="_blank" style="text-decoration: none; color: #FF4B4B; font-weight: bold;">
                CC BY-NC-SA 4.0
            </a>
        </div>
        <p style="font-size: 0.75rem; color: #666666; margin-top: 4px; padding: 0 5px;">
            Atribución - NoComercial - CompartirIgual<br>
            Material de software y base de datos con fines científicos y educativos.
        </p>
    </div>
    """, 
    unsafe_allow_html=True
)
