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


class Komoot:
    def __init__(self, email, password):
        self.email, self.password = email, password
        self.user_id = None
        self.token = None

    def login(self):
        r = requests.get(f"{BASE}/v006/account/email/{urllib.parse.quote(self.email)}/",
                         auth=(self.email, self.password), timeout=30)
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

    def tour(self, tour_id):
        r = requests.get(f"{BASE}/v007/tours/{tour_id}", auth=self._auth(), timeout=30)
        if r.status_code == 404:
            raise KomootError("Tour bei Komoot nicht gefunden (gelöscht?)")
        if r.status_code != 200:
            raise KomootError(f"Tour laden: HTTP {r.status_code}")
        return self._parse(r.json())

    def tours(self, status="tour_recorded"):
        out, page = [], 0
        while True:
            r = requests.get(f"{BASE}/v007/users/{self.user_id or self._auth()[0]}/tours/", auth=self._auth(),
                             params={"type": status, "limit": 100, "page": page,
                                     "sort_field": "date", "sort_direction": "desc"}, timeout=60)
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
        """Liste [(lat, lng, alt, t_ms)]. Zwei bekannte Varianten, die zweite als Rückfall."""
        for url, params in ((f"{BASE}/v007/tours/{tour_id}/coordinates", {}),
                            (f"{BASE}/v007/tours/{tour_id}", {"_embedded": "coordinates"})):
            r = requests.get(url, params=params, auth=self._auth(), timeout=60)
            if r.status_code != 200:
                continue
            j = r.json()
            items = j.get("items") or ((j.get("_embedded") or {}).get("coordinates") or {}).get("items")
            if items:
                return [(i["lat"], i["lng"], i.get("alt"), i.get("t")) for i in items]
        return []

    def rename(self, tour_id, name):
        r = requests.patch(f"{BASE}/v007/tours/{tour_id}", auth=self._auth(), timeout=30,
                           json={"name": name}, headers={"Content-Type": "application/json"})
        if r.status_code == 401:
            self.token = None
            r = requests.patch(f"{BASE}/v007/tours/{tour_id}", auth=self._auth(), timeout=30, json={"name": name})
        if r.status_code not in (200, 204):
            raise KomootError(f"Umbenennen bei Komoot fehlgeschlagen (HTTP {r.status_code}): {r.text[:160]}")

    def delete(self, tour_id):
        """Tour bei Komoot endgültig löschen."""
        r = requests.delete(f"{BASE}/v007/tours/{tour_id}", auth=self._auth(), timeout=30)
        if r.status_code == 401:
            self.token = None
            r = requests.delete(f"{BASE}/v007/tours/{tour_id}", auth=self._auth(), timeout=30)
        if r.status_code == 404:
            return False                      # dort schon nicht (mehr) vorhanden
        if r.status_code not in (200, 202, 204):
            raise KomootError(f"Löschen bei Komoot fehlgeschlagen (HTTP {r.status_code}): {r.text[:160]}")
        return True

    def upload(self, gpx_text, sport, name):
        r = requests.post(f"{BASE}/v007/tours/", auth=self._auth(), timeout=120,
                          params={"data_type": "gpx", "sport": sport, "name": name},
                          data=gpx_text.encode("utf-8"), headers={"Content-Type": "application/octet-stream"})
        if r.status_code == 201:
            try:
                return "created", str(r.json().get("id", ""))
            except ValueError:
                return "created", ""
        if r.status_code == 202:
            return "duplicate", ""
        raise KomootError(f"Upload fehlgeschlagen (HTTP {r.status_code}): {r.text[:200]}")
