# -*- coding: utf-8 -*-
"""
Orquestador de prospeccion nocturna (Fase A3) — Capitan Comanda.

Recorre TODAS las zonas x TODOS los rubros de forma secuencial, limpia y
deduplica con filtro_calidad, y acumula los contactos en un CSV maestro. Esta
pensado para correr una vez por noche (cron): cada corrida procesa zonas
pendientes hasta agotar el "presupuesto de tiempo" de la noche, guarda el
estado y se detiene. La noche siguiente sigue donde quedo. Cuando no quedan
zonas pendientes, avisa "pais cubierto".

NO modifica el scraper: importa buscar_contactos (sin tocarlo) y filtro_calidad.
NO envia mails: eso lo dispara Ivana despues, aparte.

Uso (dentro del contenedor del scraper):
    python orquestador.py --plan          # muestra el cronograma estimado, NO scrapea
    python orquestador.py                  # corre una noche (presupuesto por defecto)
    python orquestador.py --budget-min 180 # corre una noche con 3 h de tope
    python orquestador.py --solo-zona oeste  # corre una sola zona (prueba)
    python orquestador.py --reset          # borra el estado (arranca de cero)

Secretos de Telegram: se leen de las variables de entorno TELEGRAM_BOT_TOKEN y
TELEGRAM_CHAT_ID (no se hardcodean). Si no estan, el aviso se saltea.
"""

import argparse
import csv
import datetime
import json
import os
import time
import urllib.parse
import urllib.request

import buscar_contactos
import filtro_calidad
import zonas as zonas_mod

# ============================================================================
#  CONFIG (editable)
# ============================================================================

# Los 10 rubros de Capitan Comanda (Grupo A + Grupo B).
RUBROS = [
    "pancherias", "hamburgueserias", "casas de empanadas", "pizzerias",
    "comida rapida", "rotiserias",                       # Grupo A
    "bares", "restaurantes", "bodegones", "parrillas",   # Grupo B
]

# Zonas a cubrir, EN ORDEN DE PRIORIDAD (las 5 finas de GBA/CABA primero).
#   tipo="gba"       -> se busca por ZONA (provincia="Buenos Aires").
#   tipo="provincia" -> se busca por PROVINCIA entera (zona="").
# Volumen DIFERENCIADO: bajo en GBA (ya tienen muchas localidades = muchas
# consultas), alto en provincias (solo 2 consultas -> "traer todo lo que haya").
GBA_RESULTADOS = 20
PROV_RESULTADOS = 250

ZONAS = [
    # --- 5 zonas finas GBA/CABA (prioridad 1) ---
    {"nombre": "caba",  "tipo": "gba", "resultados": GBA_RESULTADOS},
    {"nombre": "este",  "tipo": "gba", "resultados": GBA_RESULTADOS},
    {"nombre": "oeste", "tipo": "gba", "resultados": GBA_RESULTADOS},
    {"nombre": "sur",   "tipo": "gba", "resultados": GBA_RESULTADOS},
    {"nombre": "norte", "tipo": "gba", "resultados": GBA_RESULTADOS},
    # --- 22 provincias restantes (prioridad 2) ---
    {"nombre": "Catamarca", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Chaco", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Chubut", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Cordoba", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Corrientes", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Entre Rios", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Formosa", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Jujuy", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "La Pampa", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "La Rioja", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Mendoza", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Misiones", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Neuquen", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Rio Negro", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Salta", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "San Juan", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "San Luis", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Santa Cruz", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Santa Fe", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Santiago del Estero", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Tierra del Fuego", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    {"nombre": "Tucuman", "tipo": "provincia", "resultados": PROV_RESULTADOS},
    # --- ZONA 28 PENDIENTE (interior de Buenos Aires) ---
    # Requiere agregar una zona nueva en zonas.py con ciudades del interior
    # (La Plata, Mar del Plata, Bahia Blanca, ...). NO se puede buscar como
    # provincia="Buenos Aires" (el scraper la rutea por zonas). A confirmar con
    # Ivana. Cuando este, descomentar:
    # {"nombre": "bsas_interior", "tipo": "gba", "resultados": GBA_RESULTADOS},
]

PAUSA = 0.2                 # segundos entre paginas (afinado)
USAR_GOOGLE = False         # regla del proyecto: Google bloquea el scraping
NIGHT_BUDGET_MIN = 240      # tope de tiempo por noche (min). Ajustable por --budget-min.
# Tope de ZONAS por noche (ritmo pedido por Ivana). Ademas del tope de tiempo:
# corta la noche cuando se cumple CUALQUIERA de los dos. 4 zonas/noche reparte
# las 27-28 zonas en ~7 noches y es mas suave con los buscadores (menos riesgo
# de bloqueo por IP que amontonar muchas provincias en una sola noche).
MAX_ZONAS_NOCHE = 4

# Salida. OUTPUT_DIR conviene que sea un volumen compartido con n8n (Fase B).
OUTPUT_DIR = os.environ.get("PROSPECCION_OUT", "/data/prospeccion")
MASTER_CSV = "contactos_master.csv"
DESCARTADOS_CSV = "descartados.csv"
ESTADO_JSON = "estado.json"

CAMPOS = ["fecha", "termino", "zona", "nombre_o_url", "url", "email",
          "telefono", "whatsapp", "instagram", "facebook", "_score"]

# ============================================================================
#  Utilidades
# ============================================================================

def _hoy():
    return datetime.date.today().isoformat()


def _ruta(nombre):
    return os.path.join(OUTPUT_DIR, nombre)


def telegram(texto):
    """Manda un aviso por Telegram si estan las variables de entorno."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print(f"[telegram-skip] {texto}")
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20)
    except Exception as e:
        print(f"[telegram-error] {str(e)[:80]}")


def cargar_estado():
    ruta = _ruta(ESTADO_JSON)
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return {"zonas": {}}


def guardar_estado(estado):
    with open(_ruta(ESTADO_JSON), "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def append_csv(ruta, filas, campos):
    if not filas:
        return
    nuevo = not os.path.exists(ruta)
    with open(ruta, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        if nuevo:
            w.writeheader()
        for fila in filas:
            w.writerow(fila)


def est_minutos(z):
    """Estimacion GRUESA de minutos por zona (10 rubros), solo para --plan."""
    if z["tipo"] == "gba":
        n_loc = len(zonas_mod.localidades_de(z["nombre"])) or 1
        # anclaje: oeste (13 loc) ~ 7.5 min/rubro a res 20.
        return round(n_loc * 0.58 * len(RUBROS))
    # provincia: se agota rapido (2 frases) -> ~1.5 min/rubro.
    return round(1.5 * len(RUBROS))


# ============================================================================
#  Nucleo
# ============================================================================

def procesar_zona(z, vistos, fecha):
    """Corre los 10 rubros de una zona, filtra y deduplica. Devuelve
    (aprobados, descartados) acumulados de la zona."""
    ap_zona, de_zona = [], []
    for rubro in RUBROS:
        if z["tipo"] == "gba":
            filas = buscar_contactos.buscar(
                termino=rubro, zona=z["nombre"], provincia="Buenos Aires",
                resultados_por_consulta=z["resultados"], usar_google=USAR_GOOGLE,
                pausa=PAUSA, carpeta=None, base=None, autoguardar=0)
        else:
            filas = buscar_contactos.buscar(
                termino=rubro, zona="", provincia=z["nombre"],
                resultados_por_consulta=z["resultados"], usar_google=USAR_GOOGLE,
                pausa=PAUSA, carpeta=None, base=None, autoguardar=0)
        ap, de = filtro_calidad.filtrar(filas, vistos_emails=vistos, fecha=fecha,
                                        una_fila_por_email=True)
        for r in ap:
            vistos.add(r["email"])   # dedup incremental dentro de la corrida
        ap_zona.extend(ap)
        de_zona.extend(de)
    return ap_zona, de_zona


def correr_noche(budget_min):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    estado = cargar_estado()
    fecha = _hoy()
    vistos = filtro_calidad.emails_de_csv(_ruta(MASTER_CSV))  # dedup historico

    pendientes = [z for z in ZONAS
                  if estado["zonas"].get(z["nombre"], {}).get("estado") != "hecha"]
    if not pendientes:
        telegram("🍽️ Prospeccion: no quedan zonas pendientes. Pais cubierto ✅")
        print("Sin zonas pendientes.")
        return

    t0 = time.time()
    hechas_hoy = []
    for z in pendientes:
        if len(hechas_hoy) >= MAX_ZONAS_NOCHE:
            print(f"Tope de {MAX_ZONAS_NOCHE} zonas/noche alcanzado. Corto la noche.")
            break
        if (time.time() - t0) / 60 >= budget_min:
            print(f"Presupuesto de {budget_min} min agotado. Corto la noche.")
            break
        print(f"\n==== ZONA: {z['nombre']} ({z['tipo']}) ====")
        try:
            ap, de = procesar_zona(z, vistos, fecha)
            append_csv(_ruta(MASTER_CSV), ap, CAMPOS)
            append_csv(_ruta(DESCARTADOS_CSV), de, CAMPOS + ["_motivo_descarte"])
            estado["zonas"][z["nombre"]] = {
                "estado": "hecha", "emails_nuevos": len(ap),
                "descartados": len(de), "fecha": fecha}
            hechas_hoy.append((z["nombre"], len(ap)))
        except Exception as e:
            estado["zonas"][z["nombre"]] = {"estado": "error",
                                            "detalle": str(e)[:150], "fecha": fecha}
            print(f"[ERROR zona {z['nombre']}] {str(e)[:150]}")
        guardar_estado(estado)

    total_master = len(filtro_calidad.emails_de_csv(_ruta(MASTER_CSV)))
    restantes = [z["nombre"] for z in ZONAS
                 if estado["zonas"].get(z["nombre"], {}).get("estado") != "hecha"]
    resumen = (f"🍽️ Prospeccion nocturna\n"
               f"Zonas hechas hoy: {len(hechas_hoy)} "
               f"({', '.join(f'{n}:{c}' for n, c in hechas_hoy) or '-'})\n"
               f"Emails unicos en el maestro: {total_master}\n"
               f"Zonas pendientes: {len(restantes)}"
               + (" — PAIS CUBIERTO ✅" if not restantes else ""))
    telegram(resumen)
    print("\n" + resumen)


def mostrar_plan(budget_min):
    """Dry-run: imprime el cronograma estimado sin scrapear."""
    print(f"CRONOGRAMA ESTIMADO (tope {budget_min} min/noche y {MAX_ZONAS_NOCHE} zonas/noche)\n")
    noche, acum, en_noche = 1, 0, 0
    for z in ZONAS:
        m = est_minutos(z)
        if en_noche > 0 and (en_noche >= MAX_ZONAS_NOCHE or acum + m > budget_min):
            noche += 1
            acum, en_noche = 0, 0
        acum += m
        en_noche += 1
        print(f"  Noche {noche:2}  {z['nombre']:22} {z['tipo']:9} ~{m:4} min  "
              f"(res {z['resultados']})")
    print(f"\nTotal: {len(ZONAS)} zonas x {len(RUBROS)} rubros = "
          f"{len(ZONAS) * len(RUBROS)} busquedas. Estimado ~{noche} noches "
          f"(+ buffer hasta 2 semanas).")
    print("NOTA: tiempos ESTIMADOS; el real se ajusta con las primeras corridas.")


# ============================================================================
#  CLI
# ============================================================================

def main():
    ap = argparse.ArgumentParser(description="Orquestador de prospeccion nocturna.")
    ap.add_argument("--plan", action="store_true", help="Muestra el cronograma, no scrapea.")
    ap.add_argument("--budget-min", type=int, default=NIGHT_BUDGET_MIN,
                    help=f"Tope de minutos por noche (default {NIGHT_BUDGET_MIN}).")
    ap.add_argument("--solo-zona", default=None, help="Corre una sola zona (prueba).")
    ap.add_argument("--reset", action="store_true", help="Borra el estado guardado.")
    args = ap.parse_args()

    if args.plan:
        mostrar_plan(args.budget_min)
        return
    if args.reset:
        r = _ruta(ESTADO_JSON)
        if os.path.exists(r):
            os.remove(r)
        print("Estado reiniciado.")
        return
    if args.solo_zona:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        z = next((x for x in ZONAS if x["nombre"] == args.solo_zona), None)
        if not z:
            print(f"Zona '{args.solo_zona}' no esta en la config.")
            return
        vistos = filtro_calidad.emails_de_csv(_ruta(MASTER_CSV))
        ap_, de_ = procesar_zona(z, vistos, _hoy())
        append_csv(_ruta(MASTER_CSV), ap_, CAMPOS)
        append_csv(_ruta(DESCARTADOS_CSV), de_, CAMPOS + ["_motivo_descarte"])
        print(f"Zona {z['nombre']}: {len(ap_)} emails nuevos, {len(de_)} descartados.")
        return

    correr_noche(args.budget_min)


if __name__ == "__main__":
    main()
