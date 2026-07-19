# -*- coding: utf-8 -*-
"""
================================================================================
 API HTTP para el buscador de contactos (capa FastAPI)
================================================================================

Expone el buscador ya existente (buscar_contactos.buscar) como un endpoint HTTP
para que n8n (u otra herramienta) lo llame por la red y reciba los contactos en
formato JSON, sin tener que ejecutar el script a mano ni leer los CSV.

No modifica el scraper: solo lo envuelve. El CLI (python buscar_contactos.py)
sigue funcionando igual que siempre.

Levantar en local para probar:
    uvicorn api:app --host 0.0.0.0 --port 8000

Documentacion interactiva (probar apretando botones):
    http://localhost:8000/docs
"""

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import zonas
from buscar_contactos import buscar, _emails_de

app = FastAPI(
    title="Buscador de contactos - API",
    description="Envuelve el scraper de emails/telefonos/redes como endpoint HTTP.",
    version="1.0.0",
)


class BusquedaRequest(BaseModel):
    """Parametros de una busqueda (equivalen a los flags del CLI)."""
    termino: str = Field(..., description='Que buscar. Ej: "ferreterias".')
    zona: Optional[str] = Field(
        None, description="Zona de Buenos Aires: oeste, sur, este, norte."
    )
    provincia: str = Field(
        "Buenos Aires",
        description='Provincia. Ej: "Cordoba". Por defecto Buenos Aires (por zona).',
    )
    resultados: int = Field(12, ge=1, le=50, description="Resultados por consulta.")
    usar_google: bool = Field(True, description="Incluir la consulta extra de Google.")
    pausa: float = Field(1.0, ge=0, description="Segundos de espera entre paginas.")


class BusquedaResponse(BaseModel):
    """Resultado de una busqueda."""
    termino: str
    lugar: str
    total: int
    emails: list[str]
    contactos: list[dict]


@app.get("/health")
def health():
    """Chequeo simple para saber si la API esta viva (lo usa Docker/n8n)."""
    return {"status": "ok"}


@app.get("/opciones")
def opciones():
    """Devuelve las zonas y provincias validas (util para armar el pedido)."""
    return {"zonas": zonas.listar_zonas(), "provincias": zonas.listar_provincias()}


@app.post("/buscar", response_model=BusquedaResponse)
def buscar_endpoint(req: BusquedaRequest):
    """Ejecuta la busqueda y devuelve los contactos encontrados como JSON.

    Definido como 'def' (no 'async def') a proposito: la busqueda es lenta y
    bloqueante (red), asi FastAPI la corre en un hilo aparte sin trabar el server.
    """
    en_bsas = zonas.es_buenos_aires(req.provincia)

    # Si es Buenos Aires, la zona es obligatoria y debe ser valida.
    if en_bsas:
        if not req.zona:
            raise HTTPException(
                status_code=422,
                detail=f"Para Buenos Aires indica 'zona'. Validas: "
                       f"{', '.join(zonas.listar_zonas())}.",
            )
        if req.zona not in zonas.listar_zonas():
            raise HTTPException(
                status_code=422,
                detail=f"Zona '{req.zona}' invalida. Validas: "
                       f"{', '.join(zonas.listar_zonas())}.",
            )

    # carpeta/base=None y autoguardar=0 -> la API no escribe archivos CSV.
    filas = buscar(
        termino=req.termino,
        zona=req.zona or "",
        provincia=req.provincia,
        resultados_por_consulta=req.resultados,
        usar_google=req.usar_google,
        pausa=req.pausa,
        carpeta=None,
        base=None,
        autoguardar=0,
    )

    lugar = (req.zona or "").upper() if en_bsas else req.provincia
    return BusquedaResponse(
        termino=req.termino,
        lugar=lugar,
        total=len(filas),
        emails=_emails_de(filas),
        contactos=filas,
    )
