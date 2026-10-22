"""Zepp/Amazfit-Cloud: Anmeldung (E-Mail/Passwort), Trainingsverlauf, GPS-Punkte.

Anmeldung nach huami-token (MIT, Kirill Snezhko); Verlauf/Spurdekodierung nach
Mi-Fit-and-Zepp-workout-exporter (MIT, rolandsz) bzw. MiFitDataExport (mireq).
"""
import array
import logging
import urllib.parse
import uuid
from bisect import bisect_left
from itertools import accumulate

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

log = logging.getLogger("zepp")

KEY = b"xeNtBVqzDc6tuNTh"
IV = b"MAAAYAAAAAAAAABg"
TOKENS_URL = "https://api-user-us2.zepp.com/v2/registrations/tokens"
LOGIN_URL = "https://api-mifit-us2.zepp.com/v2/client/login"
HOSTS = ["https://api-mifit-de2.zepp.com", "https://api-mifit-us2.zepp.com",
         "https://api-mifit.huami.com", "https://api-mifit.zepp.com"]

TOKEN_PAYLOAD = {
    "emailOrPhone": None, "state": "REDIRECTION", "client_id": "HuaMi", "password": None,
    "redirect_uri": "https://s3-us-west-2.amazonaws.com/hm-registration/successsignin.html",
    "region": "us-west-2", "token": ["access", "refresh"], "country_code": "US",
}
TOKEN_HEADERS = {
    "app_name": "com.huami.midong", "appname": "com.huami.midong", "cv": "151689_9.12.5", "v": "2.0",
    "appplatform": "android_phone", "vb": "202509151347", "vn": "9.12.5",
    "user-agent": "Zepp/9.12.5 (Pixel 4; Android 12; Density/2.75)", "x-hm-ekv": "1",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8", "accept-encoding": "gzip",
}
LOGIN_PAYLOAD = {
    "code": None, "device_id": None, "device_model": "android_phone", "app_version": "9.12.5",
    "dn": "api-mifit.zepp.com,api-user.zepp.com,api-mifit.zepp.com,api-watch.zepp.com,app-analytics.zepp.com,auth.zepp.com,api-analytics.zepp.com",
    "third_name": "huami", "source": "com.huami.watch.hmwatchmanager:9.12.5:151689",
    "app_name": "com.huami.midong", "country_code": "US", "grant_type": "access_token",
    "allow_registration": "false", "lang": "en", "countryState": "US-NY",
}
LOGIN_HEADERS = {
    "app_name": "com.huami.webapp", "appname": "com.huami.webapp", "origin": "https://user.zepp.com",
    "referer": "https://user.zepp.com/",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "accept": "application/json, text/plain, */*", "accept-language": "en-US,en;q=0.5",
}


class ZeppError(Exception):
    pass


def login(email, password):
    """Gibt (app_token, user_id) zurück."""
    payload = dict(TOKEN_PAYLOAD, emailOrPhone=email, password=password)
    enc = AES.new(KEY, AES.MODE_CBC, iv=IV).encrypt(pad(urllib.parse.urlencode(payload, doseq=True).encode(), 16))
    r = requests.post(TOKENS_URL, data=enc, headers=TOKEN_HEADERS, allow_redirects=False, timeout=30)
    if r.status_code != 303:
        raise ZeppError(f"Zepp-Anmeldung abgelehnt (HTTP {r.status_code}). E-Mail/Passwort prüfen; "
                        "Konten mit reinem Google-/Apple-Login haben kein Passwort – dann Token-Notlösung nutzen.")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.headers.get("Location", "")).query)
    access = (q.get("access") or [None])[0]
    if not access:
        info = {k: v[0] for k, v in q.items() if k not in ("access", "refresh")}
        hint = ""
        err = str(info.get("error", "")).lower()
        if "password" in err or "pwd" in err or "acct" in err or "account" in err:
            hint = " – E-Mail/Passwort prüfen (genau wie in der Zepp-App)"
        raise ZeppError(f"Zepp-Anmeldung: kein Zugriffstoken erhalten. Antwort des Servers: {info or 'leer'}{hint}. "
                        "Bei Mi-/Xiaomi-, Google- oder Apple-Konten gibt es kein Passwort → in den Einstellungen „Token holen“ nutzen.")
    r = requests.post(LOGIN_URL, data=dict(LOGIN_PAYLOAD, code=access, device_id=str(uuid.uuid4())),
                      headers=LOGIN_HEADERS, timeout=30)
    if r.status_code != 200:
        raise ZeppError(f"Zepp-Login fehlgeschlagen (HTTP {r.status_code})")
    ti = r.json().get("token_info") or {}
    if not ti.get("app_token"):
        raise ZeppError("Zepp-Login: kein app_token in der Antwort")
    return ti["app_token"], str(ti.get("user_id", ""))


class ZeppApi:
    def __init__(self, token, host=""):
        self.token = token
        self.hosts = [host] if host else HOSTS
        self.host = None

    def _get(self, host, endpoint, params):
        last = None
        for platform, appname in (("android_phone", "com.huami.midong"), ("web", "com.xiaomi.hm.health")):
            r = requests.get(host.rstrip("/") + endpoint, params=params, timeout=60,
                             headers={"apptoken": self.token, "appPlatform": platform, "appname": appname})
            last = r
            if r.status_code == 200:
                try:
                    j = r.json()
                except ValueError:
                    continue
                if j.get("code") in (1, None) and "data" in j:
                    return j
        raise ZeppError(f"Zepp-Anfrage {endpoint} fehlgeschlagen (HTTP {last.status_code if last is not None else '?'}). "
                        "Token abgelaufen? Neu holen unter Einstellungen → Zepp → „Token holen“.")

    def request(self, endpoint, params):
        if self.host:
            return self._get(self.host, endpoint, params)
        err = None
        for h in self.hosts:
            try:
                j = self._get(h, endpoint, params)
                self.host = h
                return j
            except (ZeppError, requests.RequestException) as e:
                err = e
        raise ZeppError(f"Kein Zepp-Server antwortet ({err})")

    def ping(self):
        """Prüft das Token mit einer kleinen Anfrage. Gibt (Server, Anzahl auf erster Seite) zurück."""
        j = self.request("/v1/sport/run/history.json", {})
        return self.host, len(j["data"].get("summary") or [])

    def history(self):
        out, nxt = [], None
        while True:
            j = self.request("/v1/sport/run/history.json", {"trackid": nxt} if nxt is not None else {})
            d = j["data"]
            out.extend(d.get("summary") or [])
            nxt = d.get("next", -1)
            if nxt in (-1, None):
                break
        return out

    def detail(self, summary):
        return self.request("/v1/sport/run/detail.json",
                            {"trackid": summary["trackid"], "source": summary.get("source", "")})["data"]


# ---- Spurdekodierung -------------------------------------------------------
NO_VALUE = -2000000


def _col(s, idx=None, default_one=False):
    out = []
    for v in filter(None, (s or "").split(";")):
        if idx is not None:
            v = v.split(",")[idx]
        out.append(int(v or (1 if default_one else 0)))
    return array.array("q", out)


class _Interp:
    def __init__(self, xs, ys):
        self.xs, self.ys = xs, ys
        self.slopes = [(y2 - y1) // ((x2 - x1) or 1) for x1, x2, y1, y2 in zip(xs, xs[1:], ys, ys[1:])]

    def __getitem__(self, x):
        i = bisect_left(self.xs, x) - 1
        if i >= len(self.slopes):
            return self.ys[-1]
        if i < 0:
            return self.ys[0]
        return self.ys[i] + self.slopes[i] * (x - self.xs[i])


def _interp_col(data, orig, new):
    data = array.array("q", data)
    old = NO_VALUE
    for old in data:
        if old != NO_VALUE:
            break
    for i, v in enumerate(data):
        if v == NO_VALUE:
            data[i] = old
        else:
            old = v
    if not new:
        return []
    if not orig:
        return [0] * len(new)
    if len(orig) == 1:
        return [orig[0]] * len(new)
    ip = _Interp(list(orig), list(data))
    return [ip[p] for p in new]


def decode_points(summary, detail):
    """Liste (unix_ts, lat, lon, alt_m) – nur wenn GPS vorhanden."""
    start = int(summary["trackid"])
    ll = detail.get("longitude_latitude") or ""
    if not ll:
        return []
    times = _col(detail.get("time"))
    lat = _col(ll, 0)
    lon = _col(ll, 1)
    alt = _col(detail.get("altitude"))
    track_times = array.array("q", accumulate(times))
    hr_times = array.array("q", accumulate(_col(detail.get("heart_rate"), 0, True)))
    step_times = array.array("q", accumulate(_col(detail.get("gait"), 0)))
    all_t = sorted(set(track_times).union(hr_times).union(step_times))
    la = _interp_col(accumulate(lat), track_times, all_t)
    lo = _interp_col(accumulate(lon), track_times, all_t)
    al = _interp_col(alt, track_times, all_t)
    return [(start + t, a / 1e8, o / 1e8, h / 100) for t, a, o, h in zip(all_t, la, lo, al)]


def points_to_gpx(summary, pts, sport):
    from datetime import datetime, timezone
    iso = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = "".join(f'<trkpt lat="{la}" lon="{lo}"><ele>{al}</ele><time>{iso(t)}</time></trkpt>\n' for t, la, lo, al in pts)
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Zepp" xmlns="http://www.topografix.com/GPX/1/1">\n'
            f'<metadata><time>{iso(int(summary["trackid"]))}</time></metadata>\n'
            f'<trk><name>{iso(int(summary["trackid"]))}</name><type>{sport}</type><trkseg>\n{body}</trkseg></trk></gpx>\n')
