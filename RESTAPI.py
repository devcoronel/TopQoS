# Página de inicio: localhost:3000/home
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_mysqldb import MySQL

from flask_jwt_extended import create_access_token
from flask_jwt_extended import jwt_required
from flask_jwt_extended import JWTManager
from flask_jwt_extended import set_access_cookies
from flask_jwt_extended import unset_jwt_cookies
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import get_jwt

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import requests, json
from variables import *

app = Flask(__name__)

#Conectar con la Base de Datos MySQL en Linux Ubuntu
app.config['MYSQL_HOST'] = host
app.config['MYSQL_USER'] = user
app.config['MYSQL_PASSWORD'] = password
app.config['MYSQL_DB'] = db
mysql = MySQL(app)

# Hacer que los JWT funcionen con cookies
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]

# Por el momento debe estar en false ya que no estamos usando HTTPS
# pero son buenas prácticas usar HTTPS y activar a True
app.config["JWT_COOKIE_SECURE"] = False

# Configurar una llave para el JWT
app.config['JWT_SECRET_KEY'] = 'cambiar-esto'

# Curiosidad
app.config['JWT_COOKIE_CSRF_PROTECT'] = True

# Dar un tiempo de expiración al JWT
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)

# Activar JWT con todos los parámetros configurados
jwt = JWTManager(app)

# Key para permitir insertar texto en index.html
app.secret_key = 'mysecretkey'

@app.errorhandler(404)
def error_404(error):
    return render_template('404.html')

@app.errorhandler(500)
def error_500(error):
    return render_template('500.html')

# Refrescar JWT
@app.after_request
def refresh_expiring_jwts(response):
    try:
        if response.status_code == 401: # Si no estamos autorizados (JWT vencido o no logueado) se borrarán esas cookies  
            response = redirect('/login')
            unset_jwt_cookies(response)
            return response
            
        exp_timestamp = get_jwt()["exp"] # Obtener la fecha de expiración del JWT actual
        now = datetime.now(timezone.utc) # Obtener la hora local
        target_timestamp = datetime.timestamp(now + timedelta(hours=20)) # A la hora actual aumentar 15min
        
        if target_timestamp > exp_timestamp:
            additional_claims = {"roleuser": get_jwt()["roleuser"]} # Obtenemos el rol del JWT anterior para conservarlo
            access_token = create_access_token(identity=get_jwt_identity(), additional_claims=additional_claims) # crear el nuevo JWT con su misma identidad y rol
            set_access_cookies(response, access_token) # Configuramos el JWT y retornamos el request que se estaba pidiendo

        return response

    except (RuntimeError, KeyError):
        # Case where there is not a valid JWT. Just return the original response
        return response


@app.route('/login', methods=['GET'])
@jwt_required(optional=True)
def main():
    current_identity = get_jwt_identity()
    if current_identity:
        return redirect('/home')
    else:
        return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        clave = request.form['clave']

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT IF (username = %s AND pass = %s, True, False), roleuser FROM users where username = %s", [usuario, clave, usuario])
        resultado = cursor.fetchall()

        if resultado == ():
            return render_template('login.html')
        else:
            validador = (resultado[0])[0]
            roluser = (resultado[0])[1]

            if validador == True:
                response = redirect('/home')
                additional_claims = {"roleuser": roluser}
                access_token = create_access_token(identity= usuario, additional_claims=additional_claims)
                set_access_cookies(response, access_token)
                return response
            else:
                return render_template('login.html')

@app.route("/logout", methods=["POST"])
def logout():
    response = redirect('/login')
    unset_jwt_cookies(response)
    return response


@app.route('/home', methods=['GET'])
@jwt_required()
def home():
    #Orden de los switches
    orden_switch = []
    # Nombres de los switches
    nombre_switch = []
    # Tipo de switch
    tipo_switch = []
    # Versión del switches
    version_switch = []

    response = requests.get(url_switches_variable)

    if response.status_code == 200:
        var_a = response.content
        data = json.loads(var_a)
        
        #Averiguar si en la tabla ya existe registro de los switches
        for i in data:
            # Crear el orden del análisis de los switches
            orden_switch.append(i)

            #Obtener las características del switch de turno
            str_i = str(i)
            url_caracteristicas = url_caracteristicas_variable +str_i
            caracteristicas = requests.get(url_caracteristicas)

            #Formar nombre del switch y almacenarlo
            var_b = "sw_"+str_i
            nombre_switch.append(var_b)
            
            if caracteristicas.status_code == 200:
                #Obtener el tipo y version de switch y almacenarlo
                var_c = caracteristicas.content
                var_d = json.loads(var_c)
                var_e = var_d[str_i]
                var_f = var_e["hw_desc"]
                tipo_switch.append(var_f)
                var_g = var_e["sw_desc"]
                version_switch.append(var_g)
            
            else:
                print("Ocurrió un error con la API ofctl.rest.py")
    
    # Número de switches
    n_switch = len(orden_switch)
    
    return render_template('index.html', numero = n_switch, orden = orden_switch , nombre = nombre_switch, tipo = tipo_switch, version = version_switch) , 200

# Mostrar las tablas de flujos de cada switch
@app.route('/home/showflows/<string:n>', methods=['GET'])
@jwt_required()
def showflows(n):
    # Primero obtener las tablas de flujo del switch
    url_tablas_flujo = url_tablas_flujo_variable + n
    print(url_tablas_flujo)
    tablas_flujo = requests.get(url_tablas_flujo)

    #Obtener los flujos del switch de turno
    url_flujos = url_flujos_variable + n
    flujos = requests.get(url_flujos)

    flujos_por_tablas = []

    if tablas_flujo.status_code == 200 and flujos.status_code == 200:
        # Obtener las tablas en json
        contenido = tablas_flujo.content
        data = json.loads(contenido)
        tablas = data[n]
        n_tablas = len(tablas)

        #Obtener los flujos en json
        var_a = flujos.content
        var_b = json.loads(var_a)
        var_c = var_b[n]
        var_d = len(var_c)
        
        tablas_activas = []
        for i in range(n_tablas):
            if (tablas[i])["active_count"] != 0:
                str_i = str(i)
                tablas_activas.append(str_i)
                for j in var_c:
                    if j["table_id"] == i:
                        formato = {
                            str_i: j
                        }

                        flujos_por_tablas.append(formato)
    # print(flujos_por_tablas)
    return render_template('showflows.html', numero = n, total = flujos_por_tablas, nflujos = var_d, tablas_activas = tablas_activas), 200

@app.route('/home/addflow/<string:n>', methods = ['GET'])
@jwt_required()
def addflow(n):
    return render_template('addflow.html', numero = n)

@app.route('/home/addflow/<string:n>', methods = ['POST'])
@jwt_required()
def add(n):
    if request.method == 'POST':
        id_tabla = request.form['id_tabla']
        print(type(id_tabla))

        return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug = True, port = port)