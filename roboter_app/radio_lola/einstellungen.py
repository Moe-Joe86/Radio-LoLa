"""Aufgabe: Liest die Einstellungen des Radios aus `einstellungen.toml` neben dieser Datei und prüft sie.

Knöpfe: `laden`, `sender_lesen`, `Radioeinstellungen`, `DATEI`.
Darf nicht: etwas schreiben; nur Standardbibliothek.
"""
# Fehlende Werte nehmen den Standard. Fehlerhafte oder unbekannte Werte brechen den Start mit einer deutschen
# Meldung ab, statt still einen Standard zu nehmen; die Meldung erscheint im Daemon und in der Handy-App.

import tomllib
from dataclasses import dataclass
from pathlib import Path

DATEI = Path(__file__).with_name("einstellungen.toml")
STANDARD = {"sender": [], "lautstaerke": 60, "bereich_grad": 360, "richtung": 1, "ueberblendung_grad": 6}


@dataclass(frozen=True)
class Radioeinstellungen:
    sender: list[tuple[str, str]]  # (Name, Adresse)
    lautstaerke: float  # 0 bis 1
    bereich: float  # nutzbarer Winkel der Sender-Antenne in Grad
    richtung: int  # +1 oder -1: Zählrichtung der Sender-Antenne
    ueberblendung: float  # Breite der Überblendung an Feldrändern in Grad


def sender_lesen(eintraege: object) -> list[tuple[str, str]]:
    """Die [[sender]]-Blöcke als Liste (Name, Adresse)."""
    if not isinstance(eintraege, list):
        raise ValueError("sender: jeder Sender braucht einen eigenen Block [[sender]] mit name und adresse")
    sender = []
    for nummer, eintrag in enumerate(eintraege, start=1):
        name = eintrag.get("name") if isinstance(eintrag, dict) else None
        adresse = eintrag.get("adresse") if isinstance(eintrag, dict) else None
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"sender Nr. {nummer}: name fehlt")
        if not isinstance(adresse, str) or not adresse.strip().startswith(("http://", "https://")):
            raise ValueError(f"sender Nr. {nummer} „{name.strip()}“: adresse beginnt nicht mit http:// oder https://")
        unbekannt = sorted(set(eintrag) - {"name", "adresse"})
        if unbekannt:
            raise ValueError(f"sender Nr. {nummer}: unbekannt ist {', '.join(unbekannt)}")
        sender.append((name.strip(), adresse.strip()))
    return sender


def _zahl(werte: dict, name: str, kleinste: float, groesste: float) -> float:
    zahl = werte[name]
    if isinstance(zahl, bool) or not isinstance(zahl, int | float):
        raise ValueError(f"{name}: „{zahl}“ ist keine Zahl")
    if not kleinste <= zahl <= groesste:
        raise ValueError(f"{name}: {zahl:g} liegt nicht zwischen {kleinste:g} und {groesste:g}")
    return float(zahl)


def laden(datei: Path = DATEI) -> Radioeinstellungen:
    try:
        gelesen = tomllib.loads(datei.read_text(encoding="utf-8")) if datei.exists() else {}
    except tomllib.TOMLDecodeError as fehler:
        raise ValueError(f"{datei.name}: Schreibfehler ({fehler})") from None
    unbekannt = set(gelesen) - set(STANDARD)
    if unbekannt:
        raise ValueError(f"{datei.name}: unbekannte Einstellung {', '.join(sorted(unbekannt))}")
    werte = STANDARD | gelesen
    if werte["richtung"] not in (1, -1) or isinstance(werte["richtung"], bool):
        raise ValueError(f"richtung: „{werte['richtung']}“, erlaubt sind 1 und -1")
    return Radioeinstellungen(
        sender=sender_lesen(werte["sender"]),
        lautstaerke=_zahl(werte, "lautstaerke", 0, 100) / 100,
        bereich=_zahl(werte, "bereich_grad", 10, 360),
        richtung=int(werte["richtung"]),
        ueberblendung=_zahl(werte, "ueberblendung_grad", 0, 30),
    )
