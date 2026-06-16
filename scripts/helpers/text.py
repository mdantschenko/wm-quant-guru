"""Textnormalisierung fuer Namen aus den Eventquellen.

Die Wyscout-Stammdaten speichern Namen mit literalen \\uXXXX-Escapes
(etwa "Modri\\u0107" statt "Modric"). Damit Spieler- und Teamnamen in allen
Datensaetzen lesbar und einheitlich sind, werden sie hier in echte Zeichen
umgewandelt. Reine Standardbibliothek.
"""
from __future__ import annotations


def decode_escapes(text: str) -> str:
    """Wandelt literale \\uXXXX-Escapes der Quelle in echte Zeichen um."""
    if "\\u" not in text:
        return text
    try:
        return text.encode("latin-1", "backslashreplace").decode("unicode_escape")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text
