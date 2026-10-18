"""Aufgabe: Plant Antennenfahrten ohne Zusammenstoß: heim auf die Nullstellung und auf Wunsch vom Handy.

Knöpfe: `heimweg`, `zuege`, `zeigt_nach_innen`, `streift_innen`, `nach_oben`, `dauer`.
Darf nicht: Hardware anfassen oder beide Antennen gleichzeitig bewegen; nur Standardbibliothek, Winkel in Grad.
"""
# Gemessen am 15. Oktober 2026 am Roboter: Beide Antennen zählen von vorn gesehen im Uhrzeigersinn aufwärts, über
# viele Runden (−1444° bis +1086°, oben bleibt die Messung bei +1086,3° stehen). 0° zeigt nach oben. Die rechte
# Antenne des Roboters (Index 0, von vorn links) zeigt zwischen 0° und 180° zur Mitte, die linke (Index 1) zwischen
# 180° und 360°. Stoßen können sie nur, wenn beide zur Mitte zeigen (Patrick). Deshalb: erst eine Antenne auf dem
# kürzesten Weg aus der inneren Hälfte nach oben parken, dann die andere ganz zurückdrehen, dann die erste.
# Für eine Fahrt vom Handy (`zuege`) gilt dasselbe: Zeigt die andere Antenne nach innen und müsste die bewegte durch
# ihre innere Hälfte, parkt die andere kurz oben und kehrt danach zurück. Liegt das Ziel selbst innen, zeigen am Ende
# wieder beide nach innen; nur die Rückkehr der geparkten Antenne bewegt sich dann neben einer inneren.

import math

RECHTS, LINKS = 0, 1
GRAD_JE_SEKUNDE = 360.0  # höchstens eine Runde pro Sekunde
KUERZESTE_FAHRT = 0.3


def zeigt_nach_innen(index: int, roh: float) -> bool:
    phase = roh % 360.0
    return 0.0 < phase < 180.0 if index == RECHTS else 180.0 < phase < 360.0


def nach_oben(index: int, roh: float) -> float:
    """Nächste Stellung nach oben (Vielfaches von 360°), auf dem Weg, der die innere Hälfte am schnellsten verlässt."""
    phase = roh % 360.0
    if phase == 0.0:
        return roh
    rueckwaerts = phase < 90.0 if index == RECHTS else phase <= 270.0
    return roh - phase if rueckwaerts else roh + (360.0 - phase)


def heimweg(rechts: float, links: float) -> list[tuple[float, float]]:
    """Ziele [rechts, links] nacheinander; bei jedem Ziel bewegt sich nur eine Antenne."""
    zuerst = LINKS if zeigt_nach_innen(LINKS, links) or not zeigt_nach_innen(RECHTS, rechts) else RECHTS
    dann = RECHTS if zuerst == LINKS else LINKS
    stellung, ziele = [rechts, links], []
    for index, ziel in ((zuerst, nach_oben(zuerst, stellung[zuerst])), (dann, 0.0), (zuerst, 0.0)):
        if stellung[index] != ziel:
            stellung[index] = ziel
            ziele.append((stellung[RECHTS], stellung[LINKS]))
    return ziele


def dauer(von: tuple[float, float], nach: tuple[float, float]) -> float:
    """Sekunden für eine Fahrt, höchstens eine Runde pro Sekunde."""
    return max(KUERZESTE_FAHRT, max(abs(b - a) for a, b in zip(von, nach, strict=True)) / GRAD_JE_SEKUNDE)


def streift_innen(index: int, von: float, nach: float) -> bool:
    """Ob die Antenne auf dem Weg von `von` nach `nach` (Rohwinkel) durch ihre innere Hälfte fährt."""
    anfang = 0.0 if index == RECHTS else 180.0
    unten, oben = min(von, nach), max(von, nach)
    runde = math.floor((unten - anfang) / 360.0) - 1
    while anfang + 360.0 * runde < oben:
        if oben > anfang + 360.0 * runde and unten < anfang + 360.0 * runde + 180.0:
            return True
        runde += 1
    return False


def zuege(index: int, ziel: float, rechts: float, links: float) -> list[tuple[float, float]]:
    """Stellungen [rechts, links] nacheinander, damit Antenne `index` nach `ziel` kommt; je Zug bewegt sich eine."""
    stellung = [rechts, links]
    andere = LINKS if index == RECHTS else RECHTS
    if stellung[index] == ziel:
        return []
    parken = zeigt_nach_innen(andere, stellung[andere]) and streift_innen(index, stellung[index], ziel)
    ablauf = [(andere, nach_oben(andere, stellung[andere])), (index, ziel), (andere, stellung[andere])] if parken \
        else [(index, ziel)]
    ziele = []
    for welche, wohin in ablauf:
        if stellung[welche] != wohin:
            stellung[welche] = wohin
            ziele.append((stellung[RECHTS], stellung[LINKS]))
    return ziele
