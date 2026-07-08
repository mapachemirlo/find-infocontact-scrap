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


def listar_zonas():
    return list(ZONAS.keys())


def localidades_de(zona):
    return ZONAS.get(zona.lower(), [])
