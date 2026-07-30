# -*- coding: utf-8 -*-
"""
Filtro de calidad + dedup para el pipeline de prospeccion (Fase A2).

Portado del nodo "Filtro calidad" de n8n (Code) a Python, con las extensiones
acordadas (jul-2026): bloqueo de agregadores detectados en pruebas y lista de
dominios extranjeros reforzada (Palermo=Italia).

Es un MODULO NUEVO e independiente: NO modifica api.py / buscar_contactos.py /
zonas.py. El orquestador (Fase A3) lo importa para limpiar los contactos que
devuelve el scraper antes de escribir el CSV.

Uso tipico:
    import filtro_calidad
    aprobados, descartados = filtro_calidad.filtrar(contactos, vistos_emails)

- `contactos`: lista de dicts como los devuelve buscar_contactos.buscar()
  (campos: termino, zona, url, emails, telefonos, whatsapp, instagram, ...).
  Los campos de valores multiples vienen separados por "; ".
- `vistos_emails`: set opcional de emails ya vistos en corridas anteriores
  (dedup historico). Se puede cargar de un CSV maestro con emails_de_csv().

Devuelve (aprobados, descartados):
- `aprobados`: UNA fila por email valido y nuevo (default, para maximizar
  destinatarios en la campania). Cada fila trae los datos del comercio.
- `descartados`: filas que no pasaron, con `_motivo_descarte` para auditar.
"""

import csv
import os
import re

# --- Dominios NO comerciales / basura / agregadores (se descartan) ----------
DB = [
    'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com', 'facebook.com/watch',
    'wikipedia.org', 'wikiwand.com', 'cookpad', 'recetas', 'blogspot.com',
    'clarin.com', 'lanacion.com.ar', 'infobae.com', 'pagina12.com.ar', 'ambito.com',
    'cronista.com', 'telam.com.ar', 'tn.com.ar', 'perfil.com', 'lavoz.com.ar',
    'minutouno.com', 'a24.com', 'c5n.com', 'lanueva.com', 'ellitoral.com', 'iprofesional.com',
    'mercadolibre.com', 'tripadvisor', 'booking.com', 'yelp.com', 'foursquare.com',
    'paginasamarillas', 'guiaclarin', 'cybo.com', 'opendi', 'tuugo', 'cylex',
    '.gob.ar', '.gov.ar', '.edu.ar',
    # Agregadores/directorios detectados en la prueba real (28-jul-2026):
    'todoresto.com', 'buscabaires.com', 'lamejorpizzeria.com',
]

# --- Dominios extranjeros (se descartan; ojo Palermo=Italia) ----------------
EX = [
    '.com.mx', '.mx/', '.com.uy', '.uy/', '.cl/', '.com.br', '.br/', '.com.es',
    '.es/', '.com.co', '.pe/', '.ec/', '.bo/', '.py/', '.ve/', '.it/', '.com.it',
    '.eu/', '.fr/', '.de/', '.pt/', '.co.uk', '.us/',
]

# --- Rubros NO gastronomicos (se descartan si el dominio los menciona) -------
NG = [
    'inmobiliaria', 'automotor', 'concesionaria', 'ferreteria', 'farmacia',
    'abogado', 'veterinaria', 'peluqueria',
]

# Buzones que no sirven para una campania (rebotan o nadie los lee) -----------
LOCALES_DESCARTADOS = {'no-reply', 'noreply', 'no_reply'}

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _norm(s):
    return (str(s) if s is not None else '').lower()


def _partes(valor):
    """Separa un campo multi-valor ('a; b; c') en lista limpia."""
    return [p.strip() for p in _norm(valor).split(';') if p.strip()]


def email_valido(e):
    """True si el email tiene formato valido y no es un buzon descartable."""
    e = _norm(e).strip()
    if not _EMAIL_RE.match(e):
        return False
    local = e.split('@', 1)[0]
    return local not in LOCALES_DESCARTADOS


def _motivo_dominio(url):
    """Devuelve el motivo de descarte por dominio, o '' si el dominio pasa."""
    u = _norm(url)
    if any(d in u for d in DB):
        return 'dominio_no_comercial'
    if any(d in u for d in EX):
        return 'extranjero'
    if any(d in u for d in NG):
        return 'no_gastronomico'
    return ''


def _score(url, instagram, whatsapp):
    """Puntaje simple para priorizar los mejores (mismo criterio que n8n)."""
    u = _norm(url)
    sc = 0
    if '.com.ar' in u or '.ar/' in u or u.endswith('.ar'):
        sc += 2
    if _norm(instagram):
        sc += 1
    if _norm(whatsapp):
        sc += 1
    return sc


def filtrar(contactos, vistos_emails=None, fecha=None, una_fila_por_email=True):
    """Filtra y deduplica los contactos del scraper.

    Args:
        contactos: lista de dicts de buscar_contactos.buscar().
        vistos_emails: set de emails ya cargados antes (dedup historico).
        fecha: string YYYY-MM-DD para estampar la fila (opcional).
        una_fila_por_email: True -> una fila por cada email valido (maximiza
            destinatarios). False -> una fila por comercio (primer email).

    Returns:
        (aprobados, descartados) como listas de dicts.
    """
    vistos = set(vistos_emails) if vistos_emails else set()
    aprobados = []
    descartados = []

    for c in contactos:
        url = c.get('url') or c.get('nombre_o_url') or ''
        termino = c.get('termino', '')
        zona = c.get('zona') or c.get('lugar') or ''
        instagram = _partes(c.get('instagram', ''))
        whatsapp = _partes(c.get('whatsapp', ''))
        telefono = _partes(c.get('telefonos') or c.get('telefono', ''))
        facebook = _partes(c.get('facebook', ''))

        # 1) Descarte por dominio (agregador / extranjero / no gastronomico).
        motivo = _motivo_dominio(url)

        # 2) Emails validos de este comercio.
        emails = [e for e in _partes(c.get('emails') or c.get('email', ''))
                  if email_valido(e)]

        base = {
            'fecha': fecha or '',
            'termino': termino,
            'zona': zona,
            'nombre_o_url': url,
            'url': url,
            'telefono': telefono[0] if telefono else '',
            'whatsapp': whatsapp[0] if whatsapp else '',
            'instagram': instagram[0] if instagram else '',
            'facebook': facebook[0] if facebook else '',
        }

        if motivo:
            descartados.append({**base, 'email': (emails[0] if emails else ''),
                                '_pasa': False, '_motivo_descarte': motivo})
            continue
        if not emails:
            descartados.append({**base, 'email': '', '_pasa': False,
                                '_motivo_descarte': 'sin_email'})
            continue

        objetivo = emails if una_fila_por_email else emails[:1]
        for em in objetivo:
            if em in vistos:
                descartados.append({**base, 'email': em, '_pasa': False,
                                    '_motivo_descarte': 'duplicado'})
                continue
            vistos.add(em)
            aprobados.append({**base, 'email': em, '_pasa': True,
                              '_score': _score(url, base['instagram'], base['whatsapp'])})

    # Prioriza los de mayor score (mismo comportamiento que el filtro n8n).
    aprobados.sort(key=lambda r: r.get('_score', 0), reverse=True)
    return aprobados, descartados


def emails_de_csv(ruta):
    """Carga el set de emails ya presentes en un CSV maestro (dedup historico).

    Devuelve set vacio si el archivo no existe todavia.
    """
    vistos = set()
    if not ruta or not os.path.exists(ruta):
        return vistos
    with open(ruta, newline='', encoding='utf-8-sig') as f:
        for fila in csv.DictReader(f):
            em = _norm(fila.get('email', '')).strip()
            if em:
                vistos.add(em)
    return vistos


# --- Autotest rapido (python filtro_calidad.py) ------------------------------
if __name__ == '__main__':
    # Muestra basada en la prueba real pizzeria/CABA (28-jul-2026).
    muestra = [
        {'termino': 'pizzeria', 'zona': 'caba',
         'url': 'https://lamejorpizzeria.com/caracteristicas/pizzeria-en-palermo/',
         'emails': 'contacto@lapecarestaurant.com.ar; info@melmacbar.com',
         'telefonos': '486742804864', 'instagram': 'https://instagram.com/lamejorpizzeria'},
        {'termino': 'pizzeria', 'zona': 'caba',
         'url': 'https://ornopizzeria.com/en/',
         'emails': 'encargado.palermo@ornopizzeria.com; info@ornopizzeria.com',
         'telefonos': '1140685330', 'instagram': 'https://instagram.com/orno.pizzeria.cantina'},
        {'termino': 'pizzeria', 'zona': 'caba',
         'url': 'http://www.luciopizzaypasta.com/',
         'emails': 'info@luciopizzaypasta.com', 'telefonos': '01173695654',
         'whatsapp': 'https://wa.me/+5491173695654', 'instagram': 'x'},
        {'termino': 'pizzeria', 'zona': 'caba',
         'url': 'https://todoresto.com/restaurantes/.../orno-pizzeria/',
         'emails': '', 'telefonos': '+541132119706'},
        {'termino': 'pizzeria', 'zona': 'caba',
         'url': 'https://ristorante-palermo.it/contatti',
         'emails': 'info@ristorante-palermo.it'},
        {'termino': 'pizzeria', 'zona': 'caba',
         'url': 'https://www.pizzerialatentacion.com.ar/Contacto.html',
         'emails': 'info@pizzerialatentacion.com.ar; no-reply@pizzerialatentacion.com.ar',
         'telefonos': '1123312534'},
    ]
    ap, de = filtrar(muestra, fecha='2026-07-28')
    print(f"APROBADOS ({len(ap)}):")
    for r in ap:
        print(f"  [{r['_score']}] {r['email']:45} <- {r['nombre_o_url']}")
    print(f"\nDESCARTADOS ({len(de)}):")
    for r in de:
        print(f"  {r['_motivo_descarte']:22} <- {r['nombre_o_url']}  ({r.get('email','')})")
