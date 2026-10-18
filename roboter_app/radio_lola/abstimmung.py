"""Aufgabe: Rechnet aus den Antennenwinkeln, welcher Sender wie stark spielt und wie laut.

Knöpfe: `gerichtet`, `feld`, `pegel`, `lautstaerke`, `angleichen`; umgekehrt `ziel_sender`, `ziel_lautstaerke`.
Darf nicht: Hardware, Netz oder Ton anfassen; nur Standardbibliothek, alle Winkel in Grad.
"""
# Der nutzbare Bereich wird in 2N gleich große Felder geteilt, abwechselnd Sender und Rauschen; Feld 0 ist ein
# Sender und beginnt bei 0°. Der Anfang gehört zum Feld, das Ende nicht. An jedem Rand eines Senderfelds blendet
# `pegel` über `ueberblendung` Grad weich zwischen Sender und Rauschen über, damit es beim Zittern nicht springt.
# Bei weniger als 360° ist alles außerhalb des Bereichs Rauschen.

VOLL = 360.0


def gerichtet(roh: float, richtung: int = 1) -> float:
    """Rohwinkel der Antenne (auch über 360° oder negativ) als Winkel von 0 bis unter 360° in Zählrichtung."""
    return (richtung * roh) % VOLL


def _breite(n: int, bereich: float) -> float:
    return bereich / (2 * n)


def feld(winkel: float, n: int, bereich: float = VOLL) -> tuple[str, int | None]:
    """("sender", Index) oder ("rauschen", None) für den Winkel."""
    w = winkel % VOLL
    if n <= 0 or w >= bereich:
        return ("rauschen", None)
    k = min(int(w // _breite(n, bereich)), 2 * n - 1)
    return ("sender", k // 2) if k % 2 == 0 else ("rauschen", None)


def _senderfelder(n: int, bereich: float) -> list[tuple[int, float, float]]:
    """(Index, Anfang, Ende) jedes Senderfelds; Sender 0 noch einmal hinter 360°, für den Übergang über null."""
    b = _breite(n, bereich)
    felder = [(i, 2 * i * b, (2 * i + 1) * b) for i in range(n)]
    return felder + [(0, VOLL, VOLL + b)]


def pegel(winkel: float, n: int, bereich: float = VOLL, ueberblendung: float = 0.0) -> tuple[int | None, float]:
    """Nächster Sender und sein Anteil von 0 (nur Rauschen) bis 1 (nur Sender); am Feldrand genau 0,5."""
    if n <= 0:
        return (None, 0.0)
    w = winkel % VOLL
    bester, abstand, drin = None, float("-inf"), False
    for i, anfang, ende in _senderfelder(n, bereich):
        innen = anfang <= w < ende
        d = min(w - anfang, ende - w) if innen else -min(abs(w - anfang), abs(w - ende))
        if d > abstand:
            bester, abstand, drin = i, d, innen
    if ueberblendung <= 0:
        return (bester, 1.0 if drin else 0.0)
    return (bester, min(1.0, max(0.0, 0.5 + abstand / ueberblendung)))


def lautstaerke(roh: float) -> float:
    """Anteil 0 bis 1 aus der Lautstärke-Antenne: über eine ganze Runde gleichmäßig lauter.

    Oben (0°) ist leise, von vorn gegen den Uhrzeigersinn steigt es bis kurz vor oben auf voll; der Sprung liegt
    oben (Patrick, 15. Oktober 2026).
    """
    return (-roh % VOLL) / VOLL


def angleichen(alt: float, ziel: float, schritt: float = 0.05) -> float:
    """Nähert die Lautstärke je Tonblock höchstens um `schritt` an, damit sie weich und ohne Knacken folgt."""
    return alt + max(-schritt, min(schritt, ziel - alt))


def _naechste(phase: float, jetzt: float) -> float:
    """Rohwinkel mit dieser Phase, der `jetzt` am nächsten liegt (kürzester Weg, auch über null)."""
    return jetzt + ((phase - jetzt + VOLL / 2) % VOLL - VOLL / 2)


def ziel_sender(index: int, n: int, jetzt: float, bereich: float = VOLL, richtung: int = 1) -> float:
    """Rohwinkel der Sender-Antenne in der Mitte des Senderfelds `index`, auf dem kürzesten Weg von `jetzt`."""
    mitte = (2 * index + 0.5) * _breite(n, bereich)
    return _naechste((richtung * mitte) % VOLL, jetzt)


HOECHSTE = 0.995  # ganz oben springt die Lautstärke von voll auf leise; so weit fährt das Handy nie


def ziel_lautstaerke(anteil: float, jetzt: float) -> float:
    """Rohwinkel der Lautstärke-Antenne für `anteil` (0 bis 1), ohne über den Sprung oben zu fahren."""
    anteil = min(HOECHSTE, max(0.0, anteil))
    return jetzt - (anteil - lautstaerke(jetzt)) * VOLL
