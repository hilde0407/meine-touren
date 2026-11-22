"""Komoot-Client (inoffizielle API, wie von Komoot-Web/App genutzt)."""
import time
import urllib.parse
from datetime import datetime, timezone

import requests

BASE = "https://api.komoot.de"


class KomootError(Exception):
    pass


def parse_date(s):
    """Komoot-Datum (z. B. 2026-10-16T12:23:00.000+02:00 oder +0200) -> Unix-Sekunden."""
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        import re
        m = re.match(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?([+-]\d\d):?(\d\d)?$", s)
        if not m:
            return None
        d = datetime.fromisoformat(f"{m.group(1)}{m.group(2)}:{m.group(3) or '00'}")
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp())


VIS_PRIVATE = "private"          # Sichtbarkeit bei Komoot (Feld „status“ einer Tour): private | friends | public (laut kompy, nicht offiziell dokumentiert)


class KomootNotFound(KomootError):
    pass


def user_agent():
    """3.58.0: eigener User-Agent statt des requests-Standards (die Partner-API verlangt einen; schadet der App-API nicht)."""
    try:
        from . import config
        return f"MeineTouren/{config.VERSION.split()[0]}"
    except Exception:  # noqa
        return "MeineTouren"


def _vis(j):
    """Sichtbarkeit aus einer Tour-Antwort; None, wenn das Feld fehlt oder unbekannt aussieht."""
    v = j.get("status") if isinstance(j, dict) else None
    return v if isinstance(v, str) and 0 < len(v) <= 30 and v.replace("_", "").isalpha() else None


class Komoot:
    def __init__(self, email, password):
        self.email, self.password = email, password
        self.user_id = None
        self.token = None

    def login(self):
        r = requests.get(f"{BASE}/v006/account/email/{urllib.parse.quote(self.email)}/",
                         auth=(self.email, self.password), timeout=30, headers={"User-Agent": user_agent()})
        if r.status_code == 401:
            raise KomootError("Komoot-Anmeldung abgelehnt (E-Mail/Passwort falsch?)")
        if r.status_code != 200:
            raise KomootError(f"Komoot-Anmeldung fehlgeschlagen (HTTP {r.status_code})")
        j = r.json()
        self.user_id, self.token = str(j["username"]), j["password"]
        return self.user_id

    def _auth(self):
        if not self.token:
            self.login()
        return (self.user_id, self.token)

    def _req(self, method, url, tries=1, headers=None, **kw):
        """Eine Anfrage mit eigenem User-Agent, einmaliger Neuanmeldung bei 401 (Token abgelaufen) und – bei tries > 1 – kurzem
        Backoff bei 429/5xx bzw. Netzfehlern. Gibt die letzte Antwort zurück; nur bei dauerhaftem Netzfehler eine KomootError.
        Zugangsdaten stehen nie in einer Fehlermeldung (requests nennt höchstens die Adresse)."""
        h = {"User-Agent": user_agent(), **(headers or {})}
        send = getattr(requests, method.lower())       # requests.get/post/patch/delete (in Tests einzeln ersetzbar)
        relogin = False
        r = None
        for i in range(max(1, tries)):
            try:
                r = send(url, auth=self._auth(), headers=h, **kw)
                if r.status_code == 401 and not relogin:
                    relogin = True
                    self.token = None             # Token abgelaufen: einmal neu anmelden und dieselbe Anfrage wiederholen
                    r = send(url, auth=self._auth(), headers=h, **kw)
            except requests.RequestException as e:
                if i >= tries - 1:
                    raise KomootError(f"Komoot nicht erreichbar ({type(e).__name__})")
                time.sleep(0.5 * 2 ** i)
                continue
            if (r.status_code == 429 or r.status_code >= 500) and i < tries - 1:
                time.sleep(0.5 * 2 ** i)
                continue
            return r
        return r

    def _get(self, url, params=None, timeout=30, tries=3):
        """GET mit Neuanmeldung bei 401 und kurzem Backoff bei 429/5xx bzw. Netzfehlern."""
        return self._req("GET", url, tries=tries, params=params, timeout=timeout)

    @staticmethod
    def _parse(t, status="tour_recorded"):
        sp = t.get("start_point") or {}
        start = parse_date(t.get("date"))
        dur = t.get("duration") or t.get("time_in_motion") or 0
        return {"id": str(t["id"]), "name": t.get("name", ""), "sport": t.get("sport", ""),
                "start_ts": start, "end_ts": (start + int(dur)) if start else None,
                "dist_m": t.get("distance") or 0, "dur_s": dur,
                "up_m": t.get("elevation_up") or 0, "down_m": t.get("elevation_down") or 0,
                "lat": sp.get("lat"), "lng": sp.get("lng"), "status": t.get("type", status)}

    def tour_raw(self, tour_id):
        """Rohantwort einer Tour (enthält u. a. „type“ und die Sichtbarkeit „status“)."""
        r = self._get(f"{BASE}/v007/tours/{tour_id}")
        if r.status_code == 404:
            raise KomootNotFound("Tour bei Komoot nicht gefunden (gelöscht?)")
        if r.status_code != 200:
            raise KomootError(f"Tour laden: HTTP {r.status_code}")
        try:
            return r.json()
        except ValueError:
            raise KomootError("Tour laden: Antwort von Komoot nicht lesbar")

    def tour(self, tour_id):
        return self._parse(self.tour_raw(tour_id))

    def visibility(self, tour_id):
        """3.58.0: Sichtbarkeit einer Tour bei Komoot lesen (private | friends | public | None = unbekannt). Nur lesend."""
        return _vis(self.tour_raw(tour_id))

    def set_visibility(self, tour_id, status=VIS_PRIVATE):
        """3.58.0: Sichtbarkeit ändern (PATCH status, Muster wie kompy). Meine Touren ruft das nur mit „private“ auf."""
        r = self._req("PATCH", f"{BASE}/v007/tours/{tour_id}", timeout=30, json={"status": status},
                      headers={"Content-Type": "application/json"})
        if r.status_code == 404:
            raise KomootNotFound("Tour bei Komoot nicht gefunden (gelöscht?)")
        if r.status_code not in (200, 204):
            raise KomootError(f"Sichtbarkeit bei Komoot ändern fehlgeschlagen (HTTP {r.status_code})")
        try:
            return _vis(r.json()) if r.content else None
        except ValueError:
            return None

    def tours(self, status="tour_recorded"):
        out, page = [], 0
        while True:
            r = self._get(f"{BASE}/v007/users/{self.user_id or self._auth()[0]}/tours/",
                          {"type": status, "limit": 100, "page": page, "sort_field": "date", "sort_direction": "desc"}, timeout=60)
            if r.status_code != 200:
                raise KomootError(f"Tourenliste: HTTP {r.status_code}")
            j = r.json()
            for t in (j.get("_embedded") or {}).get("tours", []):
                out.append(self._parse(t, status))
            total = (j.get("page") or {}).get("totalPages", 1)
            page += 1
            if page >= total:
                break
        return out

    def coordinates(self, tour_id):
        """Liste [(lat, lng, alt, t_ms)]. Zwei bekannte Varianten, die zweite als Rückfall.
        [] heißt wirklich „Komoot hat keine Punkte“; ein Fehler (HTTP, Netz) wird als KomootError gemeldet,
        damit er nicht als leere Strecke gespeichert wird."""
        got200, status = False, None
        for url, params in ((f"{BASE}/v007/tours/{tour_id}/coordinates", {}),
                            (f"{BASE}/v007/tours/{tour_id}", {"_embedded": "coordinates"})):
            r = self._get(url, params, timeout=60)
            if r.status_code != 200:
                status = r.status_code
                continue
            got200 = True
            j = r.json()
            items = j.get("items") or ((j.get("_embedded") or {}).get("coordinates") or {}).get("items")
            if items:
                return [(i["lat"], i["lng"], i.get("alt"), i.get("t")) for i in items]
        if not got200:
            raise KomootError(f"Streckenpunkte laden: HTTP {status}")
        return []

    def rename(self, tour_id, name):
        r = self._req("PATCH", f"{BASE}/v007/tours/{tour_id}", timeout=30, json={"name": name}, headers={"Content-Type": "application/json"})
        if r.status_code not in (200, 204):
            raise KomootError(f"Umbenennen bei Komoot fehlgeschlagen (HTTP {r.status_code}): {r.text[:160]}")

    def set_sport(self, tour_id, sport):
        r = self._req("PATCH", f"{BASE}/v007/tours/{tour_id}", timeout=30, json={"sport": sport}, headers={"Content-Type": "application/json"})
        if r.status_code not in (200, 204):
            raise KomootError(f"Sportart bei Komoot ändern fehlgeschlagen (HTTP {r.status_code}): {r.text[:160]}")

    def delete(self, tour_id):
        """Tour bei Komoot endgültig löschen."""
        r = self._req("DELETE", f"{BASE}/v007/tours/{tour_id}", timeout=30)
        if r.status_code == 404:
            return False                      # dort schon nicht (mehr) vorhanden
        if r.status_code not in (200, 202, 204):
            raise KomootError(f"Löschen bei Komoot fehlgeschlagen (HTTP {r.status_code}): {r.text[:160]}")
        return True

    def upload(self, gpx_text, sport, name, time_in_motion=None, info=None):
        """GPX hochladen. Gibt ("created"|"duplicate", tour_id) zurück; tour_id kann leer sein, wenn Komoot keine nennt.
        3.58.0: eigener User-Agent, Neuanmeldung bei 401 mit einmaliger Wiederholung, ein zweiter Versuch bei 429/5xx bzw. Netzfehler
        (eine doppelt angekommene Datei erkennt Komoot als Duplikat, HTTP 202). „status=private“ wird mitgeschickt, wirkt laut kompy aber
        nicht – die Sichtbarkeit setzt portals.komoot_upload danach eigens. time_in_motion (Sekunden) nur, wenn belegt.
        info (dict, optional) bekommt die Sichtbarkeit aus der Antwort („vis“), falls Komoot sie nennt."""
        params = {"data_type": "gpx", "sport": sport, "name": name, "status": VIS_PRIVATE}
        if time_in_motion is not None and int(time_in_motion) > 0:
            params["time_in_motion"] = int(time_in_motion)
        r = self._req("POST", f"{BASE}/v007/tours/", tries=2, timeout=120, params=params,
                      data=gpx_text.encode("utf-8"), headers={"Content-Type": "application/octet-stream"})
        j = {}
        try:
            j = r.json() if r.content else {}
        except ValueError:
            j = {}
        if not isinstance(j, dict):
            j = {}
        if info is not None:
            info["vis"] = _vis(j)
        if r.status_code == 201:
            return "created", str(j.get("id", "") or "")
        if r.status_code == 202:
            return "duplicate", str(j.get("id", "") or "")
        if r.status_code == 401:
            raise KomootError("Upload: Komoot hat die Anmeldung abgelehnt (E-Mail/Passwort in der Verwaltung prüfen)")
        if r.status_code == 400:
            raise KomootError(f"Upload: Komoot hat die Datei abgelehnt (HTTP 400): {r.text[:200]}")
        if r.status_code == 429:
            raise KomootError("Upload: Komoot meldet zu viele Anfragen (HTTP 429) – bitte später erneut versuchen")
        raise KomootError(f"Upload fehlgeschlagen (HTTP {r.status_code}): {r.text[:200]}")
