# -*- coding: utf-8 -*-
"""
Modulo de extraccion: descarga paginas web y saca emails, telefonos y
redes sociales.

Las expresiones regulares de telefono estan adaptadas a formatos argentinos
(codigos de area, +54, 011, celulares con 15, etc.).
"""

import re
import time
import requests
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup

# Cabecera para parecer un navegador normal y evitar bloqueos simples.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}

# ---- Emails ---------------------------------------------------------------
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# Extensiones de archivo que NO son emails aunque tengan @ o parezcan.
EMAILS_BASURA = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js",
    ".ico", ".woff", ".ttf", "example.com", "email.com", "dominio.com",
    "sentry.io", "wixpress.com", "@2x", "@3x",
)

# ---- Telefonos argentinos -------------------------------------------------
# Cubre: +54 11 1234-5678 / 011 4123-4567 / (011) 15-2345-6789 /
#        0220 456-7890 / 11 2345 6789, etc.
TELEFONO_RE = re.compile(
    r"""
    (?:(?:\+?54\s*)?         # prefijo pais opcional +54 / 54
       (?:0?11|0?2\d{2,3}|0?3\d{2,3})?\s*)?   # codigo de area opcional
    (?:15\s*)?               # prefijo celular 15 opcional
    (?:\(?\d{2,4}\)?[\s.\-]*)   # primer bloque
    \d{3,4}[\s.\-]?\d{4}    # resto del numero
    """,
    re.VERBOSE,
)

# ---- Redes sociales -------------------------------------------------------
# Para cada red: lista de dominios que la identifican.
REDES_DOMINIOS = {
    "whatsapp":  ["wa.me", "api.whatsapp.com", "web.whatsapp.com", "chat.whatsapp.com"],
    "instagram": ["instagram.com"],
    "facebook":  ["facebook.com", "fb.com", "fb.me"],
    "twitter_x": ["twitter.com", "x.com"],
    "linkedin":  ["linkedin.com"],
    "youtube":   ["youtube.com", "youtu.be"],
    "tiktok":    ["tiktok.com"],
}

# Nombres de red en orden (define tambien el orden de columnas del CSV).
REDES = list(REDES_DOMINIOS.keys())

# Rutas genericas (no son perfiles/paginas reales) que hay que descartar.
REDES_RUTAS_BASURA = {
    "facebook":  {"sharer", "sharer.php", "share.php", "dialog", "plugins",
                  "tr", "login", "help", "policies"},
    "twitter_x": {"intent", "share", "home", "search", "hashtag", "i",
                  "login", "signup"},
    "instagram": {"p", "reel", "reels", "explore", "stories", "accounts",
                  "about", "developer"},
    "linkedin":  {"sharing", "sharearticle", "shareactive", "cws", "help"},
    "youtube":   {"watch", "results", "embed", "shorts", "hashtag"},
    "tiktok":    {"tag", "search", "about", "legal"},
    "whatsapp":  set(),
}


def _normalizar_telefono(txt):
    """Deja solo digitos y el + inicial; devuelve None si no parece valido."""
    limpio = re.sub(r"[^\d+]", "", txt)
    solo_digitos = re.sub(r"\D", "", limpio)
    # Un telefono argentino valido tiene entre 8 y 13 digitos aprox.
    if 8 <= len(solo_digitos) <= 13:
        return limpio
    return None


def _email_valido(email):
    e = email.lower()
    return not any(b in e for b in EMAILS_BASURA)


def _red_de_dominio(host):
    """Devuelve el nombre de red al que pertenece un host, o None."""
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    for red, dominios in REDES_DOMINIOS.items():
        for d in dominios:
            if host == d or host.endswith("." + d):
                return red
    return None


def _limpiar_url_red(url):
    """Normaliza una URL de red social: quita query/#, barra final, www."""
    try:
        p = urlparse(url)
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = p.path.rstrip("/")
        # WhatsApp necesita el query (?phone=... o ?text=), lo conservamos.
        query = p.query if "whatsapp" in host or host == "wa.me" else ""
        return urlunparse(("https", host, path, "", query, ""))
    except Exception:
        return url.strip()


def _es_perfil_valido(red, url):
    """Filtra rutas genericas (botones de compartir, busquedas, etc.)."""
    try:
        p = urlparse(url)
        partes = [x for x in p.path.split("/") if x]
        if not partes:
            # WhatsApp puede no tener path (wa.me/<num> si; wa.me solo no).
            return red == "whatsapp" and bool(p.query)
        primera = partes[0].lower().lstrip("@")
        return primera not in REDES_RUTAS_BASURA.get(red, set())
    except Exception:
        return True


def descargar(url, timeout=15):
    """Descarga el HTML de una URL. Devuelve texto o None si falla."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "")
        if "text/html" not in ctype and "text" not in ctype:
            return None
        return resp.text
    except Exception:
        return None


def extraer_de_html(html):
    """
    Devuelve (emails, telefonos, redes) a partir de un HTML.
      - emails, telefonos: sets de strings.
      - redes: dict {nombre_red -> set de URLs}.
    """
    emails = set()
    telefonos = set()
    redes = {r: set() for r in REDES}

    if not html:
        return emails, telefonos, redes

    soup = BeautifulSoup(html, "html.parser")

    # 1) Enlaces (mailto:, tel: y redes sociales por href)
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        low = href.lower()

        if low.startswith("mailto:"):
            correo = href[7:].split("?")[0].strip()
            if EMAIL_RE.fullmatch(correo) and _email_valido(correo):
                emails.add(correo.lower())
        elif low.startswith("tel:"):
            tel = _normalizar_telefono(href[4:])
            if tel:
                telefonos.add(tel)
        elif low.startswith("http"):
            host = urlparse(href).netloc
            red = _red_de_dominio(host)
            if red:
                limpia = _limpiar_url_red(href)
                if _es_perfil_valido(red, limpia):
                    redes[red].add(limpia)

    # 2) Texto plano de la pagina (emails y telefonos sueltos)
    texto = soup.get_text(separator=" ")

    for m in EMAIL_RE.findall(texto):
        if _email_valido(m):
            emails.add(m.lower())

    for m in TELEFONO_RE.findall(texto):
        tel = _normalizar_telefono(m)
        if tel:
            telefonos.add(tel)

    return emails, telefonos, redes


def procesar_url(url, pausa=1.0):
    """Descarga y extrae de una URL. Devuelve (emails, telefonos, redes)."""
    html = descargar(url)
    if pausa:
        time.sleep(pausa)   # cortesia: no golpear los sitios muy rapido
    return extraer_de_html(html)
