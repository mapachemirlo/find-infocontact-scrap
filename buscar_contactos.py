# -*- coding: utf-8 -*-
"""
================================================================================
 Buscador de contactos por zona (emails, telefonos y redes sociales)
================================================================================

Busca en TODOS los buscadores disponibles lo que vos quieras (escuelas,
ferreterias, gimnasios, veterinarias, estudios contables, etc.), visita las
paginas encontradas, extrae emails, telefonos y redes sociales, elimina lo
repetido, y guarda lo unico en un archivo .csv.

Donde buscar:
    - En Buenos Aires: elegis una zona (oeste, sur, este, norte).
    - En cualquier otra provincia: elegis la provincia (se ignora la zona).

USO RAPIDO (interactivo, te pregunta que y donde):
    python buscar_contactos.py

USO POR LINEA DE COMANDOS:
    python buscar_contactos.py --buscar "ferreterias" --zona oeste
    python buscar_contactos.py --buscar "gimnasios" --zona norte --resultados 20
    python buscar_contactos.py --buscar "veterinarias" --provincia "Cordoba"
    python buscar_contactos.py --buscar "escuelas" --provincia "Santa Fe" --salida escuelas_sf.csv

Funciona igual en macOS y en Windows 11.
"""

import os
import csv
import sys
import argparse

import zonas
import buscadores
import extractor


def construir_consultas(termino, zona, provincia="Buenos Aires"):
    """Genera las frases de busqueda segun donde se quiera buscar.

    - En Buenos Aires: una consulta por cada localidad de la ZONA elegida
      (oeste, sur, este, norte), como siempre.
    - En cualquier otra provincia: se busca por la provincia entera
      (la zona se ignora).
    """
    if zonas.es_buenos_aires(provincia):
        consultas = []
        for loc in zonas.localidades_de(zona):
            consultas.append(f'{termino} "{loc}" Buenos Aires contacto email telefono')
            consultas.append(f'{termino} en {loc} telefono direccion')
        return consultas

    # Fuera de Buenos Aires: busqueda por provincia completa.
    return [
        f'{termino} "{provincia}" Argentina contacto email telefono',
        f'{termino} en {provincia} Argentina telefono direccion',
    ]


def _fila_vacia(termino, zona, url):
    """Crea una fila con todas las columnas (emails, telefonos y redes)."""
    fila = {"termino": termino, "zona": zona, "url": url,
            "emails": "", "telefonos": ""}
    for red in extractor.REDES:
        fila[red] = ""
    return fila


def buscar(termino, zona, provincia, resultados_por_consulta, usar_google, pausa,
           carpeta=None, base=None, autoguardar=20):
    """Ejecuta la busqueda completa. Devuelve lista de filas.

    Si 'carpeta', 'base' y 'autoguardar' estan definidos, guarda los CSV como
    respaldo cada 'autoguardar' registros nuevos (por si se corta la luz, se
    cierra la terminal, etc.). Poner autoguardar=0 para desactivar el respaldo.
    """
    en_bsas = zonas.es_buenos_aires(provincia)
    # Etiqueta del lugar: la zona (en Buenos Aires) o el nombre de la provincia.
    etiqueta = zona if en_bsas else provincia

    consultas = construir_consultas(termino, zona, provincia)
    if not consultas:
        if en_bsas:
            print(f"[!] Zona desconocida: '{zona}'. Zonas validas: "
                  f"{', '.join(zonas.listar_zonas())}")
        else:
            print(f"[!] No se pudo armar la busqueda para '{provincia}'.")
        return []

    print(f"\n=== Buscando '{termino}' en {etiqueta.upper()} ===")
    print(f"    {len(consultas)} consultas | "
          f"{resultados_por_consulta} resultados c/u | "
          f"Google extra: {'si' if usar_google else 'no'}\n")

    urls_vistas = set()
    # Sets para dedup GLOBAL de cada tipo de dato.
    emails_glob = set()
    telefonos_glob = set()
    redes_glob = {red: set() for red in extractor.REDES}
    filas = {}   # url -> fila

    # Si el usuario aprieta Ctrl + C, se corta la busqueda pero se devuelve
    # todo lo conseguido hasta ese momento (no se pierde nada).
    try:
        for i, consulta in enumerate(consultas, 1):
            print(f"[{i}/{len(consultas)}] Buscando: {consulta}")
            urls = buscadores.buscar_todos(
                consulta, resultados_por_consulta, usar_google
            )
            print(f"    -> {len(urls)} paginas unicas encontradas")

            for url in urls:
                if url in urls_vistas:
                    continue
                urls_vistas.add(url)

                emails, telefonos, redes = extractor.procesar_url(url, pausa)

                # Dedup GLOBAL: dejar solo lo que no aparecio antes.
                emails_nuevos = emails - emails_glob
                tel_nuevos = telefonos - telefonos_glob
                redes_nuevas = {r: redes[r] - redes_glob[r]
                                for r in extractor.REDES}

                hay_algo = (emails_nuevos or tel_nuevos
                            or any(redes_nuevas.values()))
                if not hay_algo:
                    continue

                emails_glob |= emails_nuevos
                telefonos_glob |= tel_nuevos
                for r in extractor.REDES:
                    redes_glob[r] |= redes_nuevas[r]

                n_redes = sum(len(v) for v in redes_nuevas.values())
                print(f"       [OK] {url}")
                print(f"            emails: {len(emails_nuevos)} | "
                      f"tel: {len(tel_nuevos)} | redes: {n_redes}")

                fila = _fila_vacia(termino, etiqueta, url)
                fila["emails"] = "; ".join(sorted(emails_nuevos))
                fila["telefonos"] = "; ".join(sorted(tel_nuevos))
                for r in extractor.REDES:
                    fila[r] = "; ".join(sorted(redes_nuevas[r]))
                filas[url] = fila

                # Respaldo automatico cada 'autoguardar' registros nuevos.
                if carpeta and base and autoguardar and \
                        len(filas) % autoguardar == 0:
                    guardar_resultados(list(filas.values()), carpeta, base,
                                       respaldo=True)

    except KeyboardInterrupt:
        print("\n\n[!] Interrupcion detectada (Ctrl + C). "
              "Guardando lo conseguido hasta ahora...")

    total_redes = sum(len(v) for v in redes_glob.values())
    print(f"\n    Totales unicos -> emails: {len(emails_glob)} | "
          f"telefonos: {len(telefonos_glob)} | redes: {total_redes}")
    return list(filas.values())


def _emails_de(filas):
    """Devuelve la lista ordenada y sin repetir de todos los emails."""
    emails = set()
    for fila in filas:
        for e in fila.get("emails", "").split("; "):
            if e:
                emails.add(e)
    return sorted(emails)


def guardar_resultados(filas, carpeta, base, respaldo=False):
    """
    Guarda DOS archivos .csv dentro de 'carpeta' (que se crea si no existe):

      1) contactos_<base>.csv  -> todo (termino, url, emails, telefonos, redes).
      2) mails_<base>.csv      -> solo la lista de emails, un mail por linea,
                                  sin datos de a quien pertenecen (para campanias).

    Ambos se guardan al mismo tiempo. UTF-8 con BOM para abrir bien en Excel.
    """
    os.makedirs(carpeta, exist_ok=True)

    # 1) CSV completo
    ruta_full = os.path.join(carpeta, f"contactos_{base}.csv")
    campos = ["termino", "zona", "url", "emails", "telefonos"] + extractor.REDES
    with open(ruta_full, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        for fila in filas:
            writer.writerow(fila)

    # 2) CSV solo con mails (para la campania)
    ruta_mails = os.path.join(carpeta, f"mails_{base}.csv")
    emails = _emails_de(filas)
    with open(ruta_mails, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["email"])
        for e in emails:
            writer.writerow([e])

    if respaldo:
        print(f"       (respaldo -> {carpeta}/  |  "
              f"{len(filas)} registros, {len(emails)} mails)")
    else:
        print(f"\n[+] Guardado en la carpeta '{carpeta}/':")
        print(f"    - contactos_{base}.csv   ({len(filas)} registros completos)")
        print(f"    - mails_{base}.csv       ({len(emails)} mails para campania)")


def modo_interactivo(termino=None, provincia=None, zona=None):
    """Completa de forma interactiva los datos que falten.

    Pregunta que buscar, en que provincia y (solo si es Buenos Aires) en que
    zona. Devuelve (termino, provincia, zona).
    """
    print("=" * 64)
    print(" Buscador de contactos por zona/provincia (emails, telefonos y redes)")
    print("=" * 64)

    while not termino:
        termino = input(
            "\n Que queres buscar? (ej: ferreterias, gimnasios, escuelas): "
        ).strip()

    if provincia is None:
        print("\n Provincias disponibles:")
        for i, p in enumerate(zonas.listar_provincias(), 1):
            print(f"   {i:2}. {p}")
        provincia = input(
            "\n En que provincia? (Enter = Buenos Aires): "
        ).strip() or "Buenos Aires"

    # Solo en Buenos Aires se elige zona; en otras provincias no aplica.
    if zonas.es_buenos_aires(provincia) and not zona:
        print("\n Zonas disponibles (Buenos Aires):")
        for z in zonas.listar_zonas():
            locs = ", ".join(zonas.localidades_de(z)[:4])
            print(f"   - {z:6} ({locs}...)")

        zona = ""
        while zona not in zonas.listar_zonas():
            zona = input(
                "\n Elegi una zona (oeste/sur/este/norte): "
            ).strip().lower()
            if zona not in zonas.listar_zonas():
                print("   Zona invalida, proba de nuevo.")

    return termino, provincia, zona


def _slug(texto):
    """Convierte un texto en algo apto para nombre de archivo."""
    limpio = "".join(c if c.isalnum() else "_" for c in texto.lower())
    return "_".join(p for p in limpio.split("_") if p)


def main():
    parser = argparse.ArgumentParser(
        description="Busca emails, telefonos y redes sociales de lo que "
                    "indiques, por zona de Buenos Aires, y guarda un CSV."
    )
    parser.add_argument("--buscar", "--termino", dest="termino",
                        help='Que buscar. Ej: "ferreterias", "gimnasios".')
    parser.add_argument("--zona", choices=zonas.listar_zonas(), default=None,
                        help="Zona de Buenos Aires (oeste, sur, este, norte). "
                             "Solo aplica si la provincia es Buenos Aires.")
    parser.add_argument("--provincia", default=None,
                        help='Provincia a buscar. Ej: "Cordoba", "Santa Fe". '
                             'Por defecto Buenos Aires (que se busca por zona).')
    parser.add_argument("--resultados", type=int, default=12,
                        help="Resultados por consulta (default: 12).")
    parser.add_argument("--salida", default=None,
                        help="Nombre base para la carpeta y los CSV de salida "
                             "(por defecto: <termino>_<zona>).")
    parser.add_argument("--sin-google", action="store_true",
                        help="No usar la consulta extra de Google.")
    parser.add_argument("--pausa", type=float, default=1.0,
                        help="Segundos de espera entre paginas (default: 1.0).")
    parser.add_argument("--autoguardar", type=int, default=20,
                        help="Guarda un respaldo cada N registros nuevos "
                             "(default: 20; usar 0 para desactivar).")
    args = parser.parse_args()

    termino = args.termino
    provincia = args.provincia
    zona = args.zona

    # Si dieron zona pero no provincia, se asume Buenos Aires.
    if provincia is None and zona:
        provincia = "Buenos Aires"

    # Falta algo si: no hay termino, no se sabe la provincia, o es Buenos
    # Aires pero todavia no se eligio la zona. En esos casos, se pregunta.
    faltan_datos = (
        not termino
        or provincia is None
        or (zonas.es_buenos_aires(provincia) and not zona)
    )
    if faltan_datos:
        termino, provincia, zona = modo_interactivo(termino, provincia, zona)

    # Etiqueta del lugar para nombrar los archivos: zona o provincia.
    etiqueta = zona if zonas.es_buenos_aires(provincia) else provincia

    # 'base' es el nombre que llevan los archivos y la carpeta que se crea.
    base = _slug(args.salida.replace(".csv", "")) if args.salida \
        else f"{_slug(termino)}_{_slug(etiqueta)}"
    carpeta = base   # se crea al momento con el nombre de la busqueda

    filas = buscar(
        termino, zona, provincia,
        resultados_por_consulta=args.resultados,
        usar_google=not args.sin_google,
        pausa=args.pausa,
        carpeta=carpeta,
        base=base,
        autoguardar=args.autoguardar,
    )

    if filas:
        guardar_resultados(filas, carpeta, base)
    else:
        print("\n[!] No se encontraron datos. Proba con mas resultados "
              "(--resultados 20) o cambia el termino de busqueda.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Interrumpido por el usuario.")
        sys.exit(1)
