# -*- coding: utf-8 -*-
"""
Modulo de busqueda web: obtiene URLs consultando TODOS los buscadores
disponibles y combina los resultados sin repetir.

Buscadores usados (via la libreria ddgs, un metabuscador):
    duckduckgo, google, bing, brave, yahoo, mojeek, startpage, yandex, wikipedia
Ademas se usa googlesearch-python como fuente extra e independiente de Google.

Si un buscador falla o esta limitado en ese momento, se ignora y se sigue
con los demas. Al final se devuelven URLs unicas (sin duplicados).
"""

import time

# Todos los motores que soporta el metabuscador ddgs para busqueda de texto.
# El orden es el de consulta. Podes comentar los que no quieras usar.
MOTORES_DDGS = [
    "duckduckgo",
    "google",
    "bing",
    "brave",
    "yahoo",
    "mojeek",
    "startpage",
    "yandex",
    "wikipedia",
]


def _normalizar_url(url):
    """Normaliza una URL para detectar duplicados (quita / final y #ancla)."""
    if not url:
        return url
    u = url.strip()
    u = u.split("#")[0]          # saca el ancla
    if u.endswith("/"):
        u = u[:-1]              # saca la barra final
    return u


def buscar_en_motor(motor, consulta, cantidad):
    """Consulta UN motor via ddgs. Devuelve lista de URLs (o [] si falla)."""
    urls = []
    try:
        from ddgs import DDGS
        resultados = DDGS().text(
            consulta, backend=motor, region="ar-es", max_results=cantidad
        )
        for r in resultados:
            href = r.get("href") or r.get("url")
            if href:
                urls.append(href)
    except Exception as e:
        # "No results found" y rate-limits entran aca; no es un error grave.
        motivo = str(e)[:50]
        print(f"      [-] {motor}: sin resultados ({motivo})")
    return urls


def buscar_google_extra(consulta, cantidad):
    """Fuente extra e independiente de Google (googlesearch-python)."""
    urls = []
    try:
        from googlesearch import search
        for href in search(consulta, num_results=cantidad, lang="es"):
            if href:
                urls.append(href)
            time.sleep(0.4)   # evitar bloqueo por velocidad
    except Exception as e:
        print(f"      [-] google-extra: {str(e)[:50]}")
    return urls


def buscar_todos(consulta, cantidad=15, usar_google=True):
    """
    Consulta TODOS los buscadores y devuelve una lista de URLs UNICAS.

    - Recorre cada motor de MOTORES_DDGS.
    - Agrega googlesearch-python como fuente extra (si usar_google=True).
    - Elimina duplicados normalizando las URLs (misma pagina con / o sin /,
      con o sin #ancla, se considera una sola).
    """
    vistos = set()          # URLs normalizadas ya agregadas
    resultado = []          # URLs originales, en orden, sin repetir
    por_motor = {}          # cuantas URLs unicas aporto cada motor

    fuentes = list(MOTORES_DDGS)
    if usar_google:
        fuentes.append("google-extra")

    for motor in fuentes:
        if motor == "google-extra":
            urls = buscar_google_extra(consulta, cantidad)
        else:
            urls = buscar_en_motor(motor, consulta, cantidad)

        nuevas = 0
        for url in urls:
            clave = _normalizar_url(url)
            if clave and clave not in vistos:
                vistos.add(clave)
                resultado.append(url)
                nuevas += 1

        if urls:
            por_motor[motor] = nuevas

        # Pequena pausa entre motores para no ser bloqueado por rate-limit.
        time.sleep(0.8)

    # Resumen de aporte por buscador (solo los que dieron algo).
    if por_motor:
        detalle = ", ".join(f"{m}:{n}" for m, n in por_motor.items())
        print(f"      buscadores que aportaron -> {detalle}")

    return resultado
