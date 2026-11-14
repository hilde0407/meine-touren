"""Zepp-Geräteliste: deviceSource-Nummer → Modellname (Quelle: docs.zepp.com → Reference → Device Basic Information).
Die Nummer taucht in der Quellenkennung eines Trainings auf (z. B. „run.9568515.huami.com“ oder nur „9568515“).
Mehrere Nummern pro Modell: Varianten (Festlandchina, global, Farben)."""
import re

_T = {
    "Amazfit Balance 3": "11141376 11141377 11141379", "Amazfit Balance Ultra": "11075840 11075841",
    "Amazfit Cheetah 2 Ultra": "9961728 9961729", "Amazfit Cheetah 2 Pro": "11010304 11010305 11010307",
    "Amazfit Active 3 Premium": "10944768 10944769 10944771 10948867", "Amazfit T-Rex Ultra 2": "10879232 10879233 10879235",
    "Amazfit Active Max": "10813697 10813699", "Amazfit T-Rex 3 Pro (44 mm)": "10682624 10682625 10682627",
    "Amazfit T-Rex 3 Pro (48 mm)": "10551552 10551553 10551555", "Amazfit Active 2 (eckig)": "10223872 10223873 10223875",
    "Amazfit Balance 2": "9568512 9568513 9568515", "Amazfit Bip 6": "9765120 9765121 10158337",
    "Amazfit Active 2 (rund)": "8913152 8913153 8913155 8913159 10092800 10092801 10092803 10092807",
    "Amazfit T-Rex 3": "8716544 8716545 8716547", "Amazfit Bip 5 Unity": "8782081 8782088 8782089",
    "Amazfit Active Edge": "8388864 8388865", "Amazfit Active": "8323328 8323329", "Amazfit Balance": "8519936 8519937 8519939",
    "Amazfit Cheetah (eckig)": "8257793", "Amazfit Bip 5": "8454400 8454401", "Amazfit Cheetah Pro": "8126720 8126721",
    "Amazfit Cheetah (rund)": "8192256 8192257", "Amazfit T-Rex Ultra": "6553856 6553857", "Amazfit GTR Mini": "250 251",
    "Amazfit GTR 4": "7930112 7930113 7864577", "Amazfit GTS 4": "7995648 7995649", "Amazfit GTS 4 mini": "246 247",
    "Amazfit Falcon": "414 415", "Amazfit Band 7": "252 253 254", "Amazfit GTR 3 Pro": "229 230 242 6095106",
    "Amazfit GTR 3": "226 227", "Amazfit GTS 3": "224 225", "Amazfit T-Rex 2": "418 419",
    "Amazfit GTR 2": "63 64 244", "Amazfit GTR 2e": "206 209", "Zepp E (rund)": "57 81", "Zepp E (eckig)": "61 82",
    "Amazfit T-Rex Pro": "83 200", "Amazfit Pop": "68", "Amazfit GTS 2 mini": "91 92",
}
CODES = {int(c): n for n, cs in _T.items() for c in cs.split()}


# Ältere Huami-Uhren melden statt einer Nummer nur einen allgemeinen Codenamen (z. B. „run.watch.everest.huami.com“) oder eine kurze
# Altnummer (z. B. „run.36.huami.com“). Daraus lässt sich KEIN Modell sicher ableiten – deshalb wird dort nichts vorgeschlagen.
def guess_for(src) -> tuple:
    """(Modellname, sicher?) – nur bei einer Nummer aus der offiziellen Zepp-Geräteliste, sonst ('', False)."""
    m = model_for(src)
    return (m, True) if m else ("", False)


def model_for(src) -> str:
    """Modellname zur Quellenkennung, sonst ''. Nur exakte Treffer einer Nummer (≥ 2 Stellen) in der Kennung."""
    for m in re.findall(r"\d{2,9}", str(src or "")):
        if int(m) in CODES:
            return CODES[int(m)]
    return ""
