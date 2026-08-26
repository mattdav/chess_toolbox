#!/usr/bin/env python3
"""
Filename: Utilities.py
Author: John DeMastri
Create Date: 2025-05-01
Version: 0.1
Description: Placeholder for general-purpose functions and code.

License: MIT License
Contact: chess@demastri.com
"""

import sys

from beartype import beartype


@beartype
def getOptionFromList(i: int, paramName: str, optList: list[str]) -> int | None:
    """Résout un argument de ligne de commande vers son index dans une liste d'options.

    Args:
        i: Index de l'argument dans ``sys.argv``.
        paramName: Nom du paramètre, utilisé dans les messages d'erreur.
        optList: Liste des valeurs autorisées (comparaison insensible à la casse).

    Returns:
        L'index de la valeur dans ``optList``, ou None si l'argument est
        absent ou invalide.
    """
    if i >= len(sys.argv):
        print("- No argument provided for " + paramName + ".  Exiting.")
        return None
    thisParam = sys.argv[i].lower()
    if thisParam not in optList:
        print(
            "- Invalid argument <"
            + thisParam
            + "> provided for "
            + paramName
            + ".  Exiting."
        )
        return None
    print("- Setting " + paramName + " to <" + thisParam + ">")
    return optList.index(thisParam)


@beartype
def getOpenOption(i: int, paramName: str) -> str | None:
    """Récupère la valeur brute d'un argument de ligne de commande.

    Args:
        i: Index de l'argument dans ``sys.argv``.
        paramName: Nom du paramètre, utilisé dans les messages d'erreur.

    Returns:
        La valeur de l'argument, ou None si absent.
    """
    if i >= len(sys.argv):
        print("- No argument provided for " + paramName + ".  Exiting.")
        return None
    thisParam = sys.argv[i]
    print("- Setting " + paramName + " to <" + thisParam + ">")
    return thisParam


@beartype
def is_integer(str_val: str) -> bool:
    """Indique si une chaîne représente un entier valide.

    Args:
        str_val: Chaîne à tester.

    Returns:
        True si convertible en ``int``, False sinon.
    """
    try:
        int(str_val)
        return True
    except ValueError:
        return False
