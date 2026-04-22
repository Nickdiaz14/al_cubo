from flask import Flask, render_template, request, jsonify, redirect, url_for
import psycopg2
import os
from dotenv import load_dotenv
import threading
import random
load_dotenv()

app = Flask(__name__)

# --- MEMORIA RAM ---
BASE_DATOS_LOCAL = {}

# --- CONEXIÓN DB ---
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port="5432"
        )
        return conn
    except Exception as e:
        print(f"Error Conexión DB: {e}")
        return None

# --- FUNCIÓN DE CARGA (Ahora devuelve la cantidad) ---
def cargar_datos_en_memoria():
    print("⏳ Actualizando memoria local...")
    conn = get_db_connection()
    if not conn:
        return 0 # Error

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT qr_info, name, document, used, active FROM entradas_qr_al_cubo")
        filas = cursor.fetchall()
        
        # Usamos una variable temporal para no dejar el sistema vacío mientras carga
        nueva_db = {}
        
        count = 0
        for fila in filas:
            qr_code, nombre, doc, usado, activo = fila
            nueva_db[qr_code] = {
                "name": nombre,
                "doc": doc,
                "used": usado,
                "active": activo
            }
            count += 1
        
        # Reemplazo atómico (Thread-safe en Python para lecturas)
        global BASE_DATOS_LOCAL
        BASE_DATOS_LOCAL = nueva_db
        
        print(f"✅ ¡Base de datos recargada! {count} usuarios en memoria.")
        return count
        
    except Exception as e:
        print(f"Error cargando datos: {e}")
        return 0
    finally:
        if conn: conn.close()

# --- HILO BACKGROUND ---
def actualizar_db_segundo_plano(qr_code):
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE entradas_qr_al_cubo SET used = TRUE WHERE qr_info = %s", (qr_code,))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"☁️ Sincronizado nube: {qr_code}")
    except Exception as e:
        print(f"⚠️ Error sinc: {e}")

# --- RUTAS ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pasaporte')
def pasaporte_demo():
    return render_template('pasaporte.html', sellos={})

# --- NUEVAS RUTAS DE PASAPORTE ---
@app.route('/registro_pasaporte', methods=['GET', 'POST'])
def registro_pasaporte():
    if request.method == 'GET':
        return render_template('ingreso_pasaporte.html')
    else:
        email = request.form.get('email', '').strip()
        if not email:
            return render_template('ingreso_pasaporte.html', error="El correo es requerido.")
        
        conn = get_db_connection()
        if not conn:
            return "Error conectando a la base de datos.", 500
            
        try:
            cursor = conn.cursor()
            # Validar si ya existe el pasaporte
            cursor.execute("SELECT passport_code FROM sellos_pasaporte_al_cubo WHERE email = %s", (email,))
            row = cursor.fetchone()
            
            if row:
                passport_code = row[0]
            else:
                # Generar código de 9 dígitos y crear
                passport_code = str(random.randint(100000000, 999999999))
                cursor.execute("INSERT INTO sellos_pasaporte_al_cubo (email, passport_code) VALUES (%s, %s)", (email, passport_code))
                conn.commit()
                
            return redirect(url_for('ver_pasaporte', passport_code=passport_code))
        except Exception as e:
            return f"Error en BD: {str(e)}", 500
        finally:
            if conn: conn.close()

@app.route('/pasaporte/<passport_code>')
def ver_pasaporte(passport_code):
    conn = get_db_connection()
    if not conn: return "Error BD"
    
    nombre, documento = "Usuario Invitado", "000.000"
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT email, sello_1, sello_2, sello_3, sello_4, sello_5, sello_6, passport_code FROM sellos_pasaporte_al_cubo WHERE passport_code = %s", (passport_code,))
        row = cursor.fetchone()
        if not row:
            return "Pasaporte no encontrado", 404
            
        email = row[0]
        sellos = {
            "sello_1": row[1],
            "sello_2": row[2],
            "sello_3": row[3],
            "sello_4": row[4],
            "sello_5": row[5],
            "sello_6": row[6],
        }
        documento = row[7]
        try:
            # Buscar el nombre en la tabla entradas_qr que suponemos tiene el correo "email"
            cursor.execute("SELECT name FROM entradas_qr_al_cubo WHERE email = %s", (email,))
            user_data = cursor.fetchone()[0]
            if user_data:
                nombre = user_data
        except Exception:
            conn.rollback() # Si la columna email no existe en la tabla entradas_qr
            
        return render_template('pasaporte.html', nombre=nombre, documento=documento, passport_code=passport_code, sellos=sellos)
    finally:
        if conn: conn.close()

@app.route('/registrar_sello', methods=['POST'])
def registrar_sello():
    data = request.json
    passport_code = data.get('passport_code')
    qr_sello = data.get('qr_sello')
    
    if not passport_code or not qr_sello:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400
        
    sellos_validos = ["sello_1", "sello_2", "sello_3", "sello_4", "sello_5", "sello_6"]
    if qr_sello not in sellos_validos:
        return jsonify({"status": "error", "message": "Sello no válido o no reconocido."}), 400
        
    conn = get_db_connection()
    if not conn: return jsonify({"status": "error", "message": "Error de BD"}), 500
    
    try:
        cursor = conn.cursor()
        query = f"UPDATE sellos_pasaporte_al_cubo SET {qr_sello} = TRUE WHERE passport_code = %s"
        cursor.execute(query, (passport_code,))
        conn.commit()
        return jsonify({"status": "success", "sello": qr_sello})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/pasaporte/<passport_code>/reset', methods=['POST'])
def resetear_pasaporte_api(passport_code):
    conn = get_db_connection()
    if not conn: return jsonify({"status": "error", "message": "Error BD"}), 500
    try:
        cursor = conn.cursor()
        # Reseteamos todos los sellos a False
        cursor.execute("""
            UPDATE sellos_pasaporte_al_cubo 
            SET sello_1 = FALSE, sello_2 = FALSE, sello_3 = FALSE, 
                sello_4 = FALSE, sello_5 = FALSE, sello_6 = FALSE 
            WHERE passport_code = %s
        """, (passport_code,))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: conn.close()

# --- NUEVA RUTA PARA EL BOTÓN DE RECARGAR ---
@app.route('/recargar_db', methods=['POST'])
def recargar_db():
    cantidad = cargar_datos_en_memoria()
    return jsonify({"status": "success", "count": cantidad})

@app.route('/validar_qr', methods=['POST'])
def validar_qr():
    data = request.json
    codigo_leido = data.get('qr_data')
    
    usuario = BASE_DATOS_LOCAL.get(codigo_leido)
    response = {}

    if usuario:
        nombre = usuario['name']
        documento = usuario['doc']
        usado = usuario['used']
        activo = usuario['active']
        
        if not usado and activo:
            # Actualizamos RAM
            BASE_DATOS_LOCAL[codigo_leido]['used'] = True
            
            response = {"status": "success", "nombre": nombre, "documento": documento}
            
            # Sincronizamos Nube
            hilo = threading.Thread(target=actualizar_db_segundo_plano, args=(codigo_leido,))
            hilo.start()
            
        elif not activo:
            response = {"status": "inactive", "nombre": nombre, "documento": documento}
        else:
            response = {"status": "used", "nombre": nombre, "documento": documento}
    else:
        response = {"status": "not_found"}

    return jsonify(response)

if __name__ == '__main__':
    # Carga inicial
    cargar_datos_en_memoria()
    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context='adhoc')