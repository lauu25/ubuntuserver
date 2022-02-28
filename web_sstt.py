# coding=utf-8
# !/usr/bin/env python3

import socket
import selectors  # https://docs.python.org/3/library/selectors.html
import select
import types  # Para definir el tipo de datos data
import argparse  # Leer parametros de ejecución
import os  # Obtener ruta y extension
from datetime import datetime, timedelta  # Fechas de los mensajes HTTP
import time  # Timeout conexión
import sys  # sys.exit
import re  # Analizador sintáctico
import logging  # Para imprimir logs
from typing import List, Any

BUFSIZE = 8192  # Tamaño máximo del buffer que se puede utilizar
TIMEOUT_CONNECTION = 20  # Timout para la conexión persistente
MAX_ACCESOS = 10

# Extensiones admitidas (extension, name in HTTP)
filetypes = {"gif": "image/gif", "jpg": "image/jpg", "jpeg": "image/jpeg", "png": "image/png", "htm": "text/htm",
             "html": "text/html", "css": "text/css", "js": "text/js"}

# Configuración de logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s.%(msecs)03d] [%(levelname)-7s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()


def enviar_mensaje(cs, data):
    """ Esta función envía datos (data) a través del socket cs
        Devuelve el número de bytes enviados.
    """
    return cs.send(data)


def recibir_mensaje(cs, data):
    """ Esta función recibe datos a través del socket cs
        Leemos la información que nos llega. recv() devuelve un string con los datos.
    """
    data = (cs.recv(data)).decode()
    return data


def cerrar_conexion(cs):
    """ Esta función cierra una conexión activa.
    """
    return cs.close()


def process_cookies(headers):
    """ Esta función procesa la cookie cookie_counter
        1. Se analizan las cabeceras en headers para buscar la cabecera Cookie
        2. Una vez encontrada una cabecera Cookie se comprueba si el valor es cookie_counter
        3. Si no se encuentra cookie_counter , se devuelve 1
        4. Si se encuentra y tiene el valor MAX_ACCESSOS se devuelve MAX_ACCESOS
        5. Si se encuentra y tiene un valor 1 <= x < MAX_ACCESOS se incrementa en 1 y se devuelve el valor
    """
    patron_cookie = r'cookie_counter=(\d*)'  # Expresión regular para los atributos
    er_cookie = re.compile(patron_cookie)

    for i in headers.keys():
        if i == "Cookie":
            cookie_counter = er_cookie.match(headers[i])
            if cookie_counter:
                if cookie_counter.group(1) == MAX_ACCESOS:
                    return MAX_ACCESOS
                else:
                    return cookie_counter.group(1) + 1
            else:
                return 1


def process_web_request(cs, webroot):
    """ Procesamiento principal de los mensajes recibidos.
            Típicamente se seguirá un procedimiento similar al siguiente (aunque el alumno puede modificarlo si lo desea)

            * Bucle para esperar hasta que lleguen datos en la red a través del socket cs con select()

            * Se comprueba si hay que cerrar la conexión por exceder TIMEOUT_CONNECTION segundos
              sin recibir ningún mensaje o hay datos. Se utiliza select.select

            * Si no es por timeout y hay datos en el socket cs.
                * Leer los datos con recv.
                * Analizar que la línea de solicitud y comprobar está bien formateada según HTTP 1.1
                    * Devuelve una lista con los atributos de las cabeceras.
                    * Comprobar si la versión de HTTP es 1.1
                    * Comprobar si es un método GET. Si no devolver un error Error 405 "Method Not Allowed".
                    * Leer URL y eliminar parámetros si los hubiera
                    * Comprobar si el recurso solicitado es /, En ese caso el recurso es index.html
                    * Construir la ruta absoluta del recurso (webroot + recurso solicitado)
                    * Comprobar que el recurso (fichero) existe, si no devolver Error 404 "Not found"
                    * Analizar las cabeceras. Imprimir cada cabecera y su valor. Si la cabecera es Cookie comprobar
                      el valor de cookie_counter para ver si ha llegado a MAX_ACCESOS.
                      Si se ha llegado a MAX_ACCESOS devolver un Error "403 Forbidden"
                    * Obtener el tamaño del recurso en bytes.
                    * Extraer extensión para obtener el tipo de archivo. Necesario para la cabecera Content-Type
                    * Preparar respuesta con código 200. Construir una respuesta que incluya: la línea de respuesta y
                      las cabeceras Date, Server, Connection, Set-Cookie (para la cookie cookie_counter),
                      Content-Length y Content-Type.
                    * Leer y enviar el contenido del fichero a retornar en el cuerpo de la respuesta.
                    * Se abre el fichero en modo lectura y modo binario
                        * Se lee el fichero en bloques de BUFSIZE bytes (8KB)
                        * Cuando ya no hay más información para leer, se corta el bucle

            * Si es por timeout, se cierra el socket tras el período de persistencia.
                * NOTA: Si hay algún error, enviar una respuesta de error con una pequeña página HTML que informe del error.
    """
    cond = True
    while cond:
        rsublist, wsublist, xsublist = select.select([cs], [], [cs], TIMEOUT_CONNECTION)

        if not (rsublist or xsublist):
            print("Error: Timeout exceeded")
            cond = False
            cerrar_conexion(cs)

        elif rsublist:
            data = recibir_mensaje(cs, BUFSIZE)
            data = data.split('\r\n')

            patron_met = r'([A-Z]*) /(.*) HTTP\/1.([0-4])'  ## Expresión regular para la primera línea del mensaje
            patron_atrib = r'([A-Za-z-]*): (.*)'  ## Expresión regular para los atributos
            er_met = re.compile(patron_met)
            er_atrib = re.compile(patron_atrib)
            reg = er_met.fullmatch(data[0])
            if not reg:
                mensaje =   "HTTP/1.1 400 Bad Request\r\n" \
                            "Date: " + datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')  + "\r\n" \
                            "Server: laura@ubuntuserver\r\n" \
                            "\r\n"
                enviar_mensaje(cs, mensaje.encode())
            else:
                print(data)

                if int(reg.group(3)) != 1:
                    mensaje = "HTTP/1.1 505 HTTP Version not supported\r\n" \
                              "Date: " + datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n" \
                              "Server: laura@ubuntuserver\r\n" \
                              "\r\n"
                    enviar_mensaje(cs, mensaje.encode())
                    continue

                if reg.group(1) != "GET":
                    mensaje = "HTTP/1.1 405 Method not allowed\r\n" \
                              "Date: " + datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n" \
                              "Server: laura@ubuntuserver\r\n" \
                              "\r\n"
                    enviar_mensaje(cs, mensaje.encode())
                    continue

                URL = reg.group(2).split('?', 1)[0]

                if URL == "":
                    recurso = "index.html"
                else:
                    recurso = URL

                ruta = str(webroot) + recurso

                if not os.path.isfile(ruta):
                    mensaje = "HTTP/1.1 404 Not found\r\n" \
                              "Date: " + datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n" \
                              "Server: laura@ubuntuserver\r\n" \
                              "\r\n"
                    enviar_mensaje(cs, mensaje.encode())
                    continue

                Atr = {}
                for i in range(1, len(data)):
                    atr = er_atrib.fullmatch(data[i])
                    if atr:
                        Atr[str(atr.group(1))] = str(atr.group(2))
                        print(str(atr.group(1)) + ": " + str(atr.group(2)))
                    else:
                        break

                num_accesos = process_cookies(Atr)
                if num_accesos == MAX_ACCESOS:
                    mensaje = "HTTP/1.1 403 Forbidden\r\n" \
                              "Date: " + datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n" \
                              "Server: laura@ubuntuserver\r\n" \
                              "\r\n"
                    enviar_mensaje(cs, mensaje.encode())
                    continue

                size = os.stat(ruta).st_size

                ruta = os.path.basename(ruta)

                patron_extension = r'([A-Za-z-\/]*?)\.(.*)'  ## Expresión regular para los atributos
                er_extension = re.compile(patron_extension)
                rut = er_extension.fullmatch(ruta)
                extension = str(rut.group(2))
                cabecera = "HTTP/1.1 200 OK\r\n" \
                           "Date: " + str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')) + "\r\n" \
                           "Server: laura@ubuntuserver\r\n" \
                           "Connection: Keep-Alive\r\n" \
                           "Set-Cookie: " + str(num_accesos) + "\r\n" \
                           "Content-Length: " + str(size) + "\r\n" \
                           "Content-Type: " + extension + "\r\n" \
                           "\r\n"
                cabecera = cabecera.encode()

                f = open(ruta, "rb")
                cuerpo = b''
                linea = f.read(BUFSIZE)
                while linea != b'':
                    cuerpo += linea
                    linea = f.read(BUFSIZE)
                mensaje = cabecera + cuerpo
                enviar_mensaje(cs, mensaje)


def main():
    """ Función principal del servidor
    """
    try:

        # Argument parser para obtener la ip y puerto de los parámetros de ejecución del programa. IP por defecto 0.0.0.0
        parser = argparse.ArgumentParser()
        parser.add_argument("-p", "--port", help="Puerto del servidor", type=int, required=True)
        parser.add_argument("-ip", "--host", help="Dirección IP del servidor o localhost", required=True)
        parser.add_argument("-wb", "--webroot",
                            help="Directorio base desde donde se sirven los ficheros (p.ej. /home/user/mi_web)")
        parser.add_argument('--verbose', '-v', action='store_true', help='Incluir mensajes de depuración en la salida')
        args = parser.parse_args()

        if args.verbose:
            logger.setLevel(logging.DEBUG)

        logger.info('Enabling server in address {} and port {}.'.format(args.host, args.port))

        logger.info("Serving files from {}".format(args.webroot))

        """ Funcionalidad a realizar """

        # * Crea un socket TCP (SOCK_STREAM)
        mysocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)

        # * Permite reusar la misma dirección previamente vinculada a otro proceso. Debe ir antes de sock.bind
        mysocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # * Vinculamos el socket a una IP y puerto elegidos
        mysocket.bind((args.host, args.port))


        # * Escucha conexiones entrantes
        mysocket.listen()

        # * Bucle infinito para mantener el servidor activo indefinidamente
        while True:
            # - Aceptamos la conexión
            (conn, addr) = mysocket.accept()
            # - Creamos un proceso hijo
            pid = os.fork()
            # - Si es el proceso hijo se cierra el socket del padre y procesar la petición con process_web_request()
            if not pid:
                mysocket.close()
                process_web_request(conn, args.webroot)
                break
            # - Si es el proceso padre cerrar el socket que gestiona el hijo.
            else:
                conn.close()
    except KeyboardInterrupt:
        True


if __name__ == "__main__":
    main()
