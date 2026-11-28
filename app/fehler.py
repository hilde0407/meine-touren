"""Lesbare Fehlermeldungen (3.71.0, Prüfbericht M-06): Der Server gibt keine rohen Python-Ausnahmen („HTTPSConnectionPool(host=…): Max retries exceeded …“) an die Oberfläche weiter.
`lesbar(text)` ersetzt technische Teile einer Meldung durch einen verständlichen Grund („Geländemodell nicht erreichbar (kein Internet?)“); alles andere bleibt unverändert.
Eingebunden in main.py als Handler für HTTPException und für unbehandelte Ausnahmen (500); die ursprüngliche Meldung steht im Protokoll."""
import logging
import re

_LOG = logging.getLogger("meine-touren")

# Rechnername aus der Ausnahme → verständlicher Name des Dienstes
DIENSTE = (
    ("amazonaws.com", "Geländemodell"), ("open-meteo", "Wetterdienst"), ("nominatim", "Ortssuche"), ("overpass", "Ortssuche"), ("openstreetmap", "Kartendienst"),
    ("brouter", "Routing-Dienst"), ("komoot", "Komoot"), ("strava", "Strava"), ("suunto", "Suunto"), ("garmin", "Garmin"), ("zepp", "Zepp"), ("huami", "Zepp"),
    ("github", "GitHub"), ("opentopodata", "Geländemodell"), ("open-elevation", "Geländemodell"), ("opentopomap", "Kartendienst"), ("arcgisonline", "Kartendienst"),
)
# Muster, an denen man eine technische Ausnahme erkennt
NETZ = re.compile(r"HTTPS?ConnectionPool|Max retries exceeded|NewConnectionError|NameResolutionError|Name or service not known|Temporary failure in name resolution|"
                  r"ConnectionError|ConnectTimeout|ReadTimeout|Read timed out|timed out|SSLError|CERTIFICATE_VERIFY|urlopen error|RemoteDisconnected|Connection (?:refused|reset|aborted)|"
                  r"Network is unreachable|getaddrinfo failed|\[Errno -?\d+\]", re.I)
TECHNISCH = re.compile(r"Traceback \(most recent call last\)|<[A-Za-z_.]+ object at 0x|^\s*[A-Za-z_.]+(?:Error|Exception)\b\s*[:(]|^\s*[A-Za-z_.]+(?:Error|Exception)\s*$")     # nur, wenn die Meldung selbst eine Ausnahme ist (nicht, wenn sie einen verständlichen Satz mit „Grund: …Error“ enthält)
HOST = re.compile(r"host=['\"]?([\w.\-]+)|https?://([\w.\-]+)|//([\w.\-]+)")


def dienst(text):
    """Verständlicher Name des Dienstes, der in der Meldung vorkommt (sonst der Rechnername, sonst „Ein Dienst im Internet“)."""
    m = HOST.search(text or "")
    host = next((g for g in (m.groups() if m else ()) if g), "")
    for k, v in DIENSTE:
        if k in host.lower():
            return v
    return f"Ein Dienst im Internet ({host})" if host else "Ein Dienst im Internet"


def lesbar(text):
    """Technische Meldung → Grund in einfachen Worten. Meldungen ohne technische Anteile bleiben unverändert."""
    t = str(text or "")
    if NETZ.search(t):
        d = dienst(t)
        pre = re.match(r"^(.{3,80}?): ", t)                     # „Wetterdienst nicht erreichbar: …“ – Anfang behalten, wenn er nicht selbst technisch ist
        if pre and not NETZ.search(pre.group(1)) and not TECHNISCH.search(pre.group(1)) and "nicht erreichbar" not in pre.group(1):
            return f"{pre.group(1)}: {d} nicht erreichbar (kein Internet?)"
        if pre and "nicht erreichbar" in pre.group(1):
            return f"{pre.group(1)} (kein Internet?)"
        return f"{d} nicht erreichbar (kein Internet?)"
    if TECHNISCH.search(t):
        return "Unerwarteter Fehler im Server. Bitte noch einmal versuchen."
    return t


def melden(was, exc):
    _LOG.warning("%s: %s", was, exc)
