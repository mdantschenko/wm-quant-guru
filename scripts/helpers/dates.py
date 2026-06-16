"""Datumsnormalisierung auf das ISO-Format yyyy-mm-dd.

Die Quotenquellen liefern Datumsangaben in unterschiedlichen Formaten
(football-data dd/mm/yy und dd/mm/yyyy, FootyStats "Mon DD YYYY - H:MMam").
Damit alle Datensaetze in Data/Custom_Data einheitlich nach Zeitpunkt
sortiert und verlustfrei gejoint werden koennen, werden sie hier auf ein
einziges ISO-Format gebracht. Reine Standardbibliothek.
"""
from __future__ import annotations

from datetime import datetime

_MONTH_ABBREVIATIONS: dict[str, int] = {
    name: index for index, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun",
         "jul", "aug", "sep", "oct", "nov", "dec"), start=1)
}


def _expand_two_digit_year(year: int) -> int:
    """Ergaenzt zweistellige Jahre (football-data reicht zurueck bis 1993)."""
    return 1900 + year if year >= 90 else 2000 + year


def to_iso_date(value: str) -> str:
    """Gibt das Datum als yyyy-mm-dd zurueck, leere Zeichenkette bei Fehlschlag."""
    text = value.strip()
    if not text:
        return ""
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    if "/" in text:
        return _parse_slash_date(text)
    return _parse_month_name_date(text)


def _parse_slash_date(text: str) -> str:
    """Parst dd/mm/yy und dd/mm/yyyy."""
    parts = text.split("/")
    if len(parts) != 3:
        return ""
    try:
        day, month, year = (int(part) for part in parts)
    except ValueError:
        return ""
    if year < 100:
        year = _expand_two_digit_year(year)
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _parse_month_name_date(text: str) -> str:
    """Parst 'Mon DD YYYY - H:MMam' (FootyStats)."""
    tokens = text.replace("-", " ").split()
    if len(tokens) < 3:
        return ""
    month = _MONTH_ABBREVIATIONS.get(tokens[0][:3].lower())
    if month is None:
        return ""
    try:
        return datetime(int(tokens[2]), month, int(tokens[1])).strftime("%Y-%m-%d")
    except ValueError:
        return ""
