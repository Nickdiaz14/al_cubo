import cv2
from pyzbar.pyzbar import decode
import numpy as np
from dotenv import load_dotenv
import psycopg2
import os
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk

load_dotenv()

# --- CONFIGURACIÓN DE PANTALLA ---
# Usamos tkinter para obtener el ancho y alto real del monitor
root = tk.Tk()
ANCHO_PANTALLA = root.winfo_screenwidth()
ALTO_PANTALLA = root.winfo_screenheight()
root.destroy() # Cerramos la instancia de tkinter, solo queríamos los datos

# Variables globales de estado
estado_app = {
    "escaneando": True,
    "datos_usuario": None,
    "acceso_valido": False,
    "acceso_activo": False
}

boton_rect = (0, 0, 0, 0)

# --- PARTE 1: BASE DE DATOS ---
def connect_db():
    try:
        connection = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port="5432"
        )
        return connection
    except Exception as e:
        print(f"Error conectando a DB: {e}")
        return None

# --- PARTE 2: VALIDACIÓN ---
def verificar_acceso(codigo_leido, conn):
    if not conn: return False, None, None
    
    cursor = conn.cursor()
    try:
        # Primero revisamos si el QR existe
        cursor.execute("SELECT name, document, used, active FROM entradas_qr_al_cubo WHERE qr_info = %s", (codigo_leido,))
        resultado = cursor.fetchone()
        
        if resultado:
            nombre, documento, usado, activo = resultado
            if not usado and activo:
                # Si no se ha usado, permitimos acceso y lo marcamos como usado
                cursor.execute("UPDATE entradas_qr_al_cubo SET used = TRUE WHERE qr_info = %s", (codigo_leido,))
                conn.commit()
                return True, True, nombre, documento
            elif not activo:
                # Existe pero está inactivo
                return False, False, nombre, documento
            else:
                # Existe pero ya fue usado
                return False, True, nombre, documento
        else:
            # No existe
            return False, False, None, None
            
    except Exception as e:
        print(f"Error SQL: {e}")
        return False, False, None, None
    
# --- PARTE 3: VISUALIZACIÓN ---
def poner_texto_utf8(imagen_cv, texto, posicion, tamano_fuente, color_bgr):
    imagen_pil = Image.fromarray(cv2.cvtColor(imagen_cv, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(imagen_pil)

    try:
        font = ImageFont.truetype("arial.ttf", tamano_fuente)
    except IOError:
        font = ImageFont.load_default()

    color_rgb = (color_bgr[2], color_bgr[1], color_bgr[0]) 
    draw.text(posicion, texto, font=font, fill=color_rgb)

    return cv2.cvtColor(np.array(imagen_pil), cv2.COLOR_RGB2BGR)

def dibujar_resultado():
    global boton_rect
    
    # IMPORTANTE: Creamos el lienzo del tamaño del MONITOR, no de la cámara
    lienzo = np.ones((ALTO_PANTALLA, ANCHO_PANTALLA, 3), dtype="uint8") * 255
    centro_x, centro_y = ANCHO_PANTALLA // 2, ALTO_PANTALLA // 2
    
    nombre, doc = estado_app["datos_usuario"] if estado_app["datos_usuario"] else (None, None)
    
    if estado_app["acceso_valido"]:
        # --- VERDE ---
        color = (0, 200, 0)
        lienzo = poner_texto_utf8(lienzo, "ACCESO PERMITIDO", (centro_x - 200, centro_y - 50), 40, color)
        lienzo = poner_texto_utf8(lienzo, f"Nombre: {nombre}", (centro_x - 190, centro_y + 10), 25, (0,0,0))
        lienzo = poner_texto_utf8(lienzo, f"Doc: {doc}", (centro_x - 190, centro_y + 50), 25, (0,0,0))

    elif nombre and doc and not estado_app["acceso_activo"]:
        # --- MORADO ---
        color = (164, 73, 163)
        lienzo = poner_texto_utf8(lienzo, "ACCESO DENEGADO", (centro_x - 200, centro_y - 50), 40, color)
        lienzo = poner_texto_utf8(lienzo, f"Usuario: {nombre}", (centro_x - 190, centro_y + 10), 25, (0,0,0))
        lienzo = poner_texto_utf8(lienzo, f"Doc: {doc}", (centro_x - 190, centro_y + 50), 25, (0,0,0))
        lienzo = poner_texto_utf8(lienzo, "Usuario inactivo", (centro_x - 120, centro_y + 90), 20, (0,0,0))
    else:
        if nombre and doc:
            # --- AMARILLO ---
            color = (0, 65, 255)
            lienzo = poner_texto_utf8(lienzo, "ACCESO DENEGADO", (centro_x - 200, centro_y - 50), 40, color)
            lienzo = poner_texto_utf8(lienzo, f"Usuario: {nombre}", (centro_x - 190, centro_y + 10), 25, (0,0,0))
            lienzo = poner_texto_utf8(lienzo, f"Doc: {doc}", (centro_x - 190, centro_y + 50), 25, (0,0,0))
            lienzo = poner_texto_utf8(lienzo, "Acceso ya utilizado", (centro_x - 120, centro_y + 90), 20, (0,0,0))
        else:
            # --- ROJO ---
            color = (0, 0, 255)
            lienzo = poner_texto_utf8(lienzo, "ACCESO DENEGADO", (centro_x - 200, centro_y - 50), 40, color)
            lienzo = poner_texto_utf8(lienzo, "QR no registrado en el sistema", (centro_x - 150, centro_y), 20, (0,0,0))

    # --- BOTÓN ---
    boton_ancho, boton_alto = 300, 80
    x1_btn = centro_x - (boton_ancho // 2)
    y1_btn = ALTO_PANTALLA - 200 # Más abajo en pantallas grandes
    x2_btn = x1_btn + boton_ancho
    y2_btn = y1_btn + boton_alto
    
    boton_rect = (x1_btn, y1_btn, x2_btn, y2_btn)
    
    cv2.rectangle(lienzo, (x1_btn, y1_btn), (x2_btn, y2_btn), (200, 100, 0), -1)
    lienzo = poner_texto_utf8(lienzo, "LEER SIGUIENTE", (x1_btn + 35, y1_btn + 20), 30, (255,255,255))
    
    return lienzo

# --- PARTE 4: CLIC ---
def click_raton(event, x, y, flags, param):
    global estado_app
    if event == cv2.EVENT_LBUTTONDOWN:
        if not estado_app["escaneando"]:
            bx1, by1, bx2, by2 = boton_rect
            if bx1 <= x <= bx2 and by1 <= y <= by2:
                print("🔄 Reactivando...")
                estado_app["escaneando"] = True
                estado_app["datos_usuario"] = None
                estado_app["acceso_valido"] = False

# --- PARTE 5: MAIN ---
def iniciar_lector():
    conn = connect_db()
    cap = cv2.VideoCapture(0)
    
    nombre_ventana = 'Control de Acceso QR'
    
    # 1. Crear ventana NORMAL (permite cambios)
    cv2.namedWindow(nombre_ventana, cv2.WINDOW_NORMAL)
    
    # 2. Configurar FULLSCREEN
    cv2.setWindowProperty(nombre_ventana, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    cv2.setMouseCallback(nombre_ventana, click_raton)

    print(f"🎥 Sistema iniciado en Pantalla Completa ({ANCHO_PANTALLA}x{ALTO_PANTALLA})")

    while True:
        if estado_app["escaneando"]:
            ret, frame = cap.read()
            if not ret: break
            
            codigos = decode(frame)
            if len(codigos) > 0:
                qr = codigos[0]
                contenido = qr.data.decode('utf-8')
                
                es_valido, es_activo, nombre, doc = verificar_acceso(contenido, conn)
                
                estado_app["acceso_valido"] = es_valido
                estado_app["acceso_activo"] = es_activo
                estado_app["datos_usuario"] = (nombre, doc)
                estado_app["escaneando"] = False
            
            # La cámara se estirará para llenar la pantalla completa
            cv2.imshow(nombre_ventana, frame)
            
        else:
            # Dibujamos el resultado usando la resolución nativa del monitor
            imagen_resultado = dibujar_resultado()
            cv2.imshow(nombre_ventana, imagen_resultado)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    if conn: conn.close()

if __name__ == "__main__":
    iniciar_lector()