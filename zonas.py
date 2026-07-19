# -*- coding: utf-8 -*-
"""
Definicion de las zonas de Buenos Aires y sus localidades.

Se usan para generar las consultas de busqueda. Podes agregar, quitar o
modificar localidades libremente sin tocar el resto del programa.
"""

ZONAS = {
    "oeste": [
        "Moron", "Merlo", "Moreno", "La Matanza", "Ituzaingo",
        "Hurlingham", "Tres de Febrero", "Ramos Mejia", "Castelar",
        "Haedo", "San Justo", "Gonzalez Catan", "Libertad",
    ],
    "sur": [
        "Avellaneda", "Lanus", "Lomas de Zamora", "Quilmes",
        "Berazategui", "Florencio Varela", "Almirante Brown",
        "Esteban Echeverria", "Ezeiza", "Adrogue", "Wilde",
        "Banfield", "Temperley",
    ],
    "norte": [
        "San Isidro", "Vicente Lopez", "Tigre", "San Fernando",
        "General San Martin", "Pilar", "Escobar", "Martinez",
        "Olivos", "Boulogne", "Beccar", "Villa Adelina", "San Miguel",
    ],
    "este": [
        # Buenos Aires "este" se toma como Capital Federal (CABA) y zona
        # costera/riberena. Ajustar a gusto.
        "Capital Federal", "CABA", "Puerto Madero", "La Boca",
        "Barracas", "San Telmo", "Palermo", "Belgrano", "Nunez",
    ],
}


# Provincias de Argentina (sugerencias para el modo interactivo y para
# validar/mostrar opciones). Buenos Aires se maneja aparte, por zonas.
PROVINCIAS = [
    "Buenos Aires", "CABA", "Catamarca", "Chaco", "Chubut", "Cordoba",
    "Corrientes", "Entre Rios", "Formosa", "Jujuy", "La Pampa", "La Rioja",
    "Mendoza", "Misiones", "Neuquen", "Rio Negro", "Salta", "San Juan",
    "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero",
    "Tierra del Fuego", "Tucuman",
]

# Formas de escribir "Buenos Aires" que activan la busqueda por zonas.
_ALIAS_BUENOS_AIRES = {
    "buenos aires", "provincia de buenos aires", "bsas", "bs as", "ba",
}


def listar_zonas():
    return list(ZONAS.keys())


def listar_provincias():
    return list(PROVINCIAS)


def es_buenos_aires(provincia):
    """True si la provincia es Buenos Aires (se busca por zonas).

    Si no se indica provincia, se asume Buenos Aires (comportamiento previo).
    """
    if not provincia:
        return True
    return provincia.strip().lower() in _ALIAS_BUENOS_AIRES


def localidades_de(zona):
    return ZONAS.get(zona.lower(), [])
