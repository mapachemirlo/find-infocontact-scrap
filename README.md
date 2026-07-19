# Buscador de contactos por zona / provincia — Argentina

Busca en **todos los buscadores disponibles** lo que vos quieras (ferreterías,
gimnasios, veterinarias, escuelas, estudios contables, etc.), visita las páginas
encontradas, **extrae emails, teléfonos y redes sociales**, elimina lo repetido,
y guarda lo único en un **archivo .csv**.

**Dónde buscar:**

- **En Buenos Aires** → elegís una **zona** del Gran Buenos Aires
  (`oeste`, `sur`, `este`, `norte`) y busca localidad por localidad.
- **En cualquier otra provincia** → elegís la **provincia** (ej: Córdoba,
  Santa Fe) y busca por la provincia entera. La zona se ignora.

**Buscadores usados:** DuckDuckGo, Google, Bing, Brave, Yahoo, Mojeek,
Startpage, Yandex y Wikipedia (vía el metabuscador `ddgs`), más una consulta
extra e independiente a Google. Si un buscador está caído o limitado en ese
momento, se ignora y se sigue con los demás.

**Redes sociales detectadas:** WhatsApp, Instagram, Facebook, X/Twitter,
LinkedIn, YouTube y TikTok. Se filtran los enlaces genéricos (botones de
"compartir", búsquedas, etc.).

**Sin repetidos:** las URLs se normalizan y deduplican entre todos los
buscadores, y además cada email, teléfono y red social aparece **una sola vez**
en todo el CSV, aunque venga de varias páginas o de distintos buscadores.

Funciona igual en **macOS** y en **Windows 11**.

---

## Archivos del proyecto

| Archivo | Qué hace |
|---|---|
| `buscar_contactos.py` | Programa principal (el que se ejecuta) |
| `zonas.py` | Localidades de cada zona y lista de provincias (podés editarlas) |
| `buscadores.py` | Búsqueda en todos los buscadores |
| `extractor.py` | Descarga páginas y extrae emails, teléfonos y redes |
| `requirements.txt` | Dependencias a instalar |

---

## Instalación

### macOS / Linux

```bash
cd scrap-mail-tel
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Windows 11 (PowerShell)

```powershell
cd scrap-mail-tel
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

> Si al activar el venv en PowerShell da un error de permisos, ejecutá una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

---

## Uso

### Modo simple (te pregunta qué y dónde)

```bash
python buscar_contactos.py
```

### Modo por línea de comandos

```bash
# Ferreterías en zona oeste (Buenos Aires) -> genera contactos_ferreterias_oeste.csv
python buscar_contactos.py --buscar "ferreterias" --zona oeste

# Gimnasios en zona norte (Buenos Aires), más resultados por búsqueda
python buscar_contactos.py --buscar "gimnasios" --zona norte --resultados 20

# Veterinarias en la provincia de Córdoba (busca por la provincia entera)
python buscar_contactos.py --buscar "veterinarias" --provincia "Cordoba"

# Escuelas en Santa Fe, con nombre de archivo propio
python buscar_contactos.py --buscar "escuelas" --provincia "Santa Fe" --salida escuelas_sf.csv

# Estudios contables en zona este (Buenos Aires), sin la consulta extra de Google
python buscar_contactos.py --buscar "estudios contables" --zona este --sin-google
```

### Opciones

| Opción | Descripción | Default |
|---|---|---|
| `--buscar` (o `--termino`) | Qué buscar (ej: `"ferreterias"`) | (pregunta) |
| `--zona` | `oeste`, `sur`, `este` o `norte` (solo aplica en Buenos Aires) | (pregunta) |
| `--provincia` | Provincia a buscar (ej: `"Cordoba"`, `"Santa Fe"`) | Buenos Aires |
| `--resultados` | Páginas a revisar por cada búsqueda | 12 |
| `--salida` | Nombre del CSV de salida | `contactos_<termino>_<zona|provincia>.csv` |
| `--sin-google` | No usar la consulta extra de Google | usa Google |
| `--pausa` | Segundos de espera entre páginas | 1.0 |
| `--autoguardar` | Guarda un respaldo cada N registros nuevos (`0` = desactivar) | 20 |

---

## Resultado

Se crea una **carpeta con el nombre de la búsqueda** (ej: `ferreterias_oeste/`)
y adentro se guardan **dos archivos .csv al mismo tiempo**:

1. **`contactos_<nombre>.csv`** — todo, con estas columnas (se abre bien en Excel):
   `termino, zona, url, emails, telefonos, whatsapp, instagram, facebook, twitter_x, linkedin, youtube, tiktok`
   Varios valores en una misma celda van separados por `; `.

2. **`mails_<nombre>.csv`** — solo la lista de emails (un mail por línea, sin
   datos de a quién pertenecen). Pensado para importar directo en una
   herramienta de campañas de email.

Ejemplo de estructura generada:

```
ferreterias_oeste/
├── contactos_ferreterias_oeste.csv   (datos completos)
└── mails_ferreterias_oeste.csv       (solo emails, para campaña)
```

---

## Personalizar

- **Zonas y localidades:** editá las listas en `zonas.py`.
- **Provincias:** agregá o quitá provincias en la lista `PROVINCIAS` de `zonas.py`.
- **Buscadores:** comentá los que no quieras en `MOTORES_DDGS` (en `buscadores.py`).
- **Redes sociales:** agregá o quitá redes en `REDES_DOMINIOS` (en `extractor.py`).

---

## Notas y buenas prácticas

- Los datos provienen de **páginas web públicas**. Usalos de forma responsable.
- Google a veces bloquea búsquedas automáticas si hacés muchas seguidas.
  Si ves errores de Google, usá `--sin-google` o esperá un rato.
- Si obtenés pocos resultados, subí `--resultados` (ej: `--resultados 20`).
- Al buscar **por provincia** se hacen menos consultas que en Buenos Aires
  (que busca localidad por localidad). Si querés más cobertura en una
  provincia, subí `--resultados` (ej: `--resultados 25`).
- El programa se puede cortar en cualquier momento con `Ctrl + C`: guarda
  automáticamente todo lo conseguido hasta ese momento.
- **Respaldo automático:** cada 20 registros nuevos (configurable con
  `--autoguardar`) escribe el CSV, por si se corta la luz o se cierra la
  terminal de golpe. El archivo de respaldo es el mismo CSV de salida, así que
  al terminar simplemente queda completo.
- **No necesitás VPN**: funciona directo desde Argentina (está optimizado con
  región `ar-es`).
