# coding=utf-8
# !/usr/bin/env python3


## CONTENT LEGNHT y type y connection = keep-alive

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
ORGANITATION_NAME = "web.residenzamilano48.org"
ERROR_TOUT = "errorTOUT.html"
ERROR_400 = "error400.html"
ERROR_403 = "error403.html"
ERROR_404 = "error404.html"
ERROR_405 = "error405.html"
ERROR_505 = "error505.html"
MAX_AGE = 20


# Extensiones admitidas (extension, name in HTTP)
filetypes = {"gif": "image/gif", "jpg": "image/jpg", "jpeg": "image/jpeg", "png": "image/png", "htm": "text/htm",
             "html": "text/html", "css": "text/css", "js": "text/js"}

# Configuración de logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s.%(msecs)03d] [%(levelname)-7s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()


def enviar_mensaje(cs, ruta, cabecera):
    """ Esta función envía datos leidos desde la ruta + cabecera a través del socket cs
        Devuelve el número de bytes enviados.
    """
    f = open(ruta, "rb")
    cuerpo = b''
    linea = f.read(BUFSIZE)
    while linea != b'':
        cuerpo += linea
        linea = f.read(BUFSIZE)
    mensaje = cabecera.encode()+cuerpo
    print("\n************ HTTP_RESPONSE ************")
    print(cabecera)
    return cs.send(mensaje)


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
                if int(cookie_counter.group(1)) == MAX_ACCESOS:
                    return MAX_ACCESOS
                else:
                    return int(cookie_counter.group(1)) + 1
            else:
                break
    return 1


def process_web_request(cs, webroot):
    cond = True
    """ Bucle para escuchar peticiones por el socket, hasta que pase el timeout
        sin recibir ninguna """
    while cond:
        rsublist, wsublist, xsublist = select.select([cs], [], [cs], TIMEOUT_CONNECTION)

        # Comprobación de TIMEOUT
        if not (rsublist or xsublist):
            size = os.stat(ERROR_TOUT).st_size
            cabecera = "HTTP/1.1 Timeout exceeded \r\n" \
                       "Date: " + datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n" \
                       "Server: " + ORGANITATION_NAME + "\r\n" \
                       "Connection: close\r\n" \
                       "Keep-Alive: timeout=" + str(TIMEOUT_CONNECTION) + "\r\n" \
                       "Content-Length: " + str(size) + "\r\n" \
                       "\r\n"
            msj = enviar_mensaje(cs,ERROR_TOUT, cabecera)
            if not msj:
                print("ERROR al enviar mensajes por el socket")
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
            # Comprobación de que la primera línea sigue el formato HTTP\1.1
            if not reg:
                size = os.stat(ERROR_400).st_size
                cabecera = "HTTP/1.1 400 Bad Request\r\n" \
                           "Date: " + str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')) + "\r\n" \
                           "Server: " + ORGANITATION_NAME + "\r\n" \
                           "Connection: keep-alive\r\n" \
                           "Keep-Alive: timeout=" + str(TIMEOUT_CONNECTION) + "\r\n" \
                           "Content-Length: " + str(size) + "\r\n" \
                           "\r\n"
                msj = enviar_mensaje(cs, ERROR_400, cabecera)
                if not msj:
                    print("ERROR al enviar mensajes por el socket")
            else:
                print(data)

                if reg.group(1) != "GET":
                    size = os.stat(ERROR_405).st_size
                    cabecera = "HTTP/1.1 405 Method not allowed\r\n" \
                               "Date: " + str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')) + "\r\n" \
                               "Server: " + ORGANITATION_NAME + "\r\n" \
                               "Connection: keep-alive\r\n" \
                               "Keep-Alive: timeout=" + str(TIMEOUT_CONNECTION) + "\r\n" \
                               "Content-Length: " + str(size) + "\r\n" \
                               "\r\n"
                    msj = enviar_mensaje(cs, ERROR_405, cabecera)
                    if not msj:
                        print("ERROR al enviar mensajes por el socket")
                    continue

                URL = reg.group(2)

                if URL == '':
                    recurso = "index.html"
                else:
                    recurso = URL.split('?', 1)[0]

                ruta = str(webroot) + recurso

                patron_extension = r'([A-Za-z-\/]*?)\.(.*)'  ## Expresión regular para los atributos
                er_extension = re.compile(patron_extension)
                rut = er_extension.fullmatch(ruta)
                extension = str(rut.group(2))

                if int(reg.group(3)) != 1:
                    size = os.stat(ERROR_505).st_size
                    cabecera = "HTTP/1.1 505 HTTP Version not supported\r\n" \
                               "Date: " + str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')) + "\r\n" \
                               "Server: " + ORGANITATION_NAME + "\r\n" \
                               "Connection: keep-alive\r\n" \
                               "Keep-Alive: timeout=" + str(TIMEOUT_CONNECTION) + "\r\n" \
                               "Content-Length: " + str(size) + "\r\n" \
                               "Content-Type: " + extension + "\r\n" \
                               "\r\n"
                    msj = enviar_mensaje(cs, ERROR_505, cabecera)
                    if not msj:
                        print("ERROR al enviar mensajes por el socket")
                    continue

                Atr = {}
                host = 0
                print("\n************ HTTP_REQUEST ************")
                for i in range(1, len(data)):
                    atr = er_atrib.fullmatch(data[i])
                    if atr:
                        if str(atr.group(1)) == "Host":
                            host = 1
                        Atr[str(atr.group(1))] = str(atr.group(2))
                        print(str(atr.group(1)) + ": " + str(atr.group(2)))
                    else:
                        break

                if not host:
                    print("Error: Not host especified ")
                    continue

                if not os.path.isfile(ruta):
                    size = os.stat(ERROR_404).st_size
                    cabecera = "HTTP/1.1 404 Not found\r\n" \
                               "Date: " + str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')) + "\r\n" \
                               "Server: " + ORGANITATION_NAME + "\r\n" \
                               "Connection: keep-alive\r\n" \
                               "Keep-Alive: timeout=" + str(TIMEOUT_CONNECTION) + "\r\n" \
                               "Content-Length: " + str(size) + "\r\n" \
                               "Content-Type: " + extension + "\r\n" \
                               "\r\n"
                    msj = enviar_mensaje(cs, ERROR_404, cabecera)
                    if not msj:
                        print("ERROR al enviar mensajes por el socket")
                    continue

                num_accesos = process_cookies(Atr)

                if num_accesos == MAX_ACCESOS:
                    size = os.stat(ERROR_403).st_size
                    cabecera = "HTTP/1.1 403 Forbidden\r\n" \
                               "Date: " + str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')) + "\r\n" \
                               "Server: " + ORGANITATION_NAME + "\r\n" \
                               "Connection: keep-alive\r\n" \
                               "Keep-Alive: timeout=" + str(TIMEOUT_CONNECTION) + "\r\n" \
                               "Content-Length: " + str(size) + "\r\n" \
                               "Content-Type: " + extension + "\r\n" \
                               "\r\n"
                    msj = enviar_mensaje(cs, ERROR_403, cabecera)
                    if not msj:
                        print("ERROR al enviar mensajes por el socket")
                    continue

                ruta = os.path.basename(ruta)
                size = os.stat(ruta).st_size
                cabecera = "HTTP/1.1 200 OK\r\n" \
                           "Date: " + str(datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')) + "\r\n" \
                           "Server: " + ORGANITATION_NAME + "\r\n" \
                           "Connection: keep-alive"  + "\r\n" \
                           "Keep-Alive: timeout=" + str(TIMEOUT_CONNECTION) + "\r\n" \
                           "Set-Cookie: cookie_counter=" + str(num_accesos) + "; Max-Age=" + str(MAX_AGE) + "\r\n" \
                           "Content-Length: " + str(size) + "\r\n" \
                           "Content-Type: " + extension + "\r\n" \
                           "\r\n"
                msj = enviar_mensaje(cs, ruta, cabecera)
                if not msj:
                    print("ERROR al enviar mensajes por el socket")


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
