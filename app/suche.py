"""Gemeinsame Such-Normalisierung (3.31.0): Akzente, Sonderbuchstaben und Apostrophe sind beim Suchen egal.

Das Gegenstück im Browser steht in static/js/01-grundlagen.js (sfold / sforms / sin / smatch) und muss dasselbe tun.

Regeln:
- Groß/Klein egal; Akzente und Diakritika fallen weg (NFD ohne Combining Marks): Réunion = Reunion, Lucía = Lucia.
- ß→ss, æ→ae, œ→oe, ø→o, đ→d, ł→l, ı→i.
- Apostrophe und typografische Anführungszeichen (' ’ ‘ ʼ ` ´ ...) sind neutral: sie zählen als "nichts" ODER als Leerzeichen,
  so findet "dazur", "d azur" und "d'azur" dasselbe wie "d’Azur".
- Umlaute: jeder Text hat zwei Formen, "ä"→"a" und "ä"→"ae" (ö/oe, ü/ue). Es genügt, wenn eine Form der Eingabe in einer Form der
  Daten steckt: "Koeln", "Köln" und "Koln" finden "Köln"; "Aerzte" findet "Ärzte", "Arzte" ebenso.
"""
import re
import unicodedata

_SPEZ = str.maketrans({"ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "đ": "d", "ł": "l", "ı": "i"})
_UML = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue"})
_APO = re.compile("['’‘ʼʻ′`´]")


def _basis(s, umlaut_e):
    t = str(s if s is not None else "").lower().translate(_SPEZ)
    if umlaut_e:
        t = t.translate(_UML)
    return "".join(c for c in unicodedata.normalize("NFD", t) if not unicodedata.category(c).startswith("M"))


def sfold(s):
    """Hauptform: klein, ohne Akzente, Apostrophe entfernt, ä→a."""
    return _APO.sub("", _basis(s, False))


def sforms(s):
    """Alle Vergleichsformen (ä→a / ä→ae  x  Apostroph weg / Apostroph = Leerzeichen)."""
    out = []
    for e in (False, True):
        b = _basis(s, e)
        for f in (_APO.sub("", b), _APO.sub(" ", b)):
            if f not in out:
                out.append(f)
    return out


def sin(forms, needle):
    """True, wenn irgendeine Form von needle in irgendeiner der (vorberechneten) forms steckt. Leere Eingabe trifft immer."""
    nf = sforms(needle)
    if not any(n.strip() for n in nf):
        return True
    return any(n.strip() in f for n in nf for f in forms)


def smatch(hay, needle):
    return sin(sforms(hay), needle)
