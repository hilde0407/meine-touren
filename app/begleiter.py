"""Sicherheit unterwegs: Wetterwarnung für den eigenen Standort und zeitlich begrenzte Live-Standort-Links für Kontakte."""
import html as _h
import json
import secrets
import threading
import time

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import auth, ctx, db

router = APIRouter()
UA = {"User-Agent": "MeineTouren/1.0 (privates Selbsthosting; https://github.com/hilde0407/meine-touren)"}

# ---------------------------------------------------------------- Wetterwarnung
_wc, _wl = {}, threading.Lock()
THUNDER = {95, 96, 99}
HEAVY = {65, 82, 67}
SNOW = {71, 73, 75, 77, 85, 86}


def analyze(h):
    """Warnungen aus den nächsten Stunden. h: Listen 'temperature_2m', 'precipitation', 'weather_code', 'wind_gusts_10m' (Index 0 = jetzt)."""
    t, p, c, g = (h.get(k) or [] for k in ("temperature_2m", "precipitation", "weather_code", "wind_gusts_10m"))
    ev = {}

    def add(kind, i, val=None):
        if kind not in ev:
            ev[kind] = {"kind": kind, "in_h": i, "val": val}
    for i in range(min(6, len(c) if c else len(p))):
        code = c[i] if i < len(c) and c[i] is not None else 0
        pr = p[i] if i < len(p) and p[i] is not None else 0
        gu = g[i] if i < len(g) and g[i] is not None else 0
        if code in THUNDER and i <= 4:
            add("thunder", i)
        if (pr >= 4 or code in HEAVY) and i <= 3:
            add("rain", i, round(pr, 1))
        if gu >= 60 and i <= 3:
            add("wind", i, round(gu))
        if (code in SNOW or (pr >= 0.5 and i < len(t) and t[i] is not None and t[i] <= 0)) and i <= 3:
            add("snow", i)
    if len(t) >= 4 and t[0] is not None:
        later = [x for x in t[1:4] if x is not None]
        if later and t[0] - min(later) >= 8:
            add("cold", 1 + [x for x in t[1:4]].index(min(later)), round(t[0] - min(later)))
    out = sorted(ev.values(), key=lambda e: (e["in_h"], e["kind"]))
    danger = "thunder" in ev or (ev.get("wind") and ev["wind"]["val"] >= 80)
    return {"level": "danger" if danger else ("warn" if out else "ok"), "events": out}


def _forecast(lat, lon):
    r = requests.get("https://api.open-meteo.com/v1/forecast", headers=UA, timeout=10, params={
        "latitude": lat, "longitude": lon, "forecast_hours": 7, "timezone": "auto",
        "hourly": "temperature_2m,precipitation,weather_code,wind_gusts_10m"})
    if r.status_code != 200:
        raise RuntimeError(f"Wetterdienst: HTTP {r.status_code}")
    return r.json().get("hourly") or {}


@router.get("/api/weather/alert")
def api_weather_alert(lat: float, lon: float):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(400, "Ungültige Position")
    key = (round(lat, 1), round(lon, 1))
    with _wl:
        hit = _wc.get(key)
        if hit and time.time() - hit[0] < 600:
            return hit[1]
    try:
        res = analyze(_forecast(lat, lon))
    except Exception as e:  # noqa
        raise HTTPException(502, f"Wetterdienst nicht erreichbar: {e.__class__.__name__}")
    res["ts"] = int(time.time())
    with _wl:
        _wc[key] = (time.time(), res)
        if len(_wc) > 200:
            _wc.clear()
    return res


# ---------------------------------------------------------------- Live-Standort-Links
def ensure():
    db.execute("CREATE TABLE IF NOT EXISTS live_links (token TEXT PRIMARY KEY, ts INTEGER, exp INTEGER, label TEXT)")


@router.post("/api/live/link")
async def api_live_link(request: Request):
    ensure()
    if (db.get("live_mode") or "off") == "off":
        raise HTTPException(403, "Die Standort-Freigabe ist ausgeschaltet (Verwaltung → Standort teilen)")
    try:
        d = await request.json()
    except Exception:  # noqa
        d = {}
    hours = max(1, min(int(d.get("hours") or 12), 72))
    token = secrets.token_urlsafe(12)
    now = int(time.time())
    db.execute("INSERT INTO live_links(token,ts,exp,label) VALUES(?,?,?,?)", (token, now, now + hours * 3600, str(d.get("label") or "")[:60]))
    auth.q("INSERT OR REPLACE INTO share_index(token,uid) VALUES(?,?)", (token, ctx.uid() or ""))
    try:
        from . import security
        base = security._base_url()
    except Exception:  # noqa
        base = ""
    if not base:
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        base = f"{proto}://{request.headers.get('x-forwarded-host') or request.headers.get('host') or request.url.netloc}"
    return {"token": token, "url": f"{base}/pub/live/{token}", "exp": now + hours * 3600, "https": base.startswith("https://")}


@router.get("/api/live/links")
def api_live_links():
    ensure()
    return db.query("SELECT token,ts,exp,label FROM live_links WHERE exp>? ORDER BY ts DESC", (int(time.time()),))


@router.delete("/api/live/link/{token}")
def api_live_link_del(token: str):
    ensure()
    db.execute("DELETE FROM live_links WHERE token=?", (token,))
    auth.q("DELETE FROM share_index WHERE token=? AND uid=?", (token, ctx.uid() or ""))
    return {"ok": True}


def _owner(token):
    ensure()
    idx = auth.q1("SELECT uid FROM share_index WHERE token=?", (token,))
    if idx:
        ctx._uid.set(idx["uid"] or None)
    elif auth.users_exist():
        return None
    row = db.one("SELECT exp FROM live_links WHERE token=?", (token,))
    return row


@router.get("/api/public/live/{token}")
def api_public_live(token: str):
    row = _owner(token)
    if not row or row["exp"] < time.time():
        return JSONResponse({"gone": True}, status_code=410, headers={"Cache-Control": "no-store"})
    try:
        p = json.loads(db.get("live_pos") or "{}")
    except ValueError:
        p = {}
    out = {"exp": row["exp"]}
    if p and (db.get("live_mode") or "off") != "off":
        out.update({"lat": p["lat"], "lon": p["lon"], "acc": p.get("acc"), "age_s": int(time.time() - p.get("ts", 0)), "name": p.get("name") or ""})
    return JSONResponse(out, headers={"Cache-Control": "no-store"})


_T = {
    "de": ("Live-Standort", "Noch keine Position empfangen.", "Zuletzt aktualisiert vor {} Min.", "Dieser Link ist abgelaufen oder wurde beendet.", "In Karten-App öffnen", "Der Link gilt bis {}."),
    "en": ("Live location", "No position received yet.", "Last updated {} min ago.", "This link has expired or was ended.", "Open in maps app", "The link is valid until {}."),
    "fr": ("Position en direct", "Aucune position reçue pour l’instant.", "Dernière mise à jour il y a {} min.", "Ce lien a expiré ou a été arrêté.", "Ouvrir dans l’appli de cartes", "Le lien est valable jusqu’à {}."),
    "es": ("Ubicación en directo", "Aún no se ha recibido ninguna posición.", "Última actualización hace {} min.", "Este enlace ha caducado o se ha finalizado.", "Abrir en la app de mapas", "El enlace es válido hasta {}."),
}


@router.get("/pub/live/{token}")
def pub_live(token: str, request: Request):
    from .more2 import _req_lang
    lang = _req_lang(request)
    t = _T[lang]
    page = f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>{_h.escape(t[0])}</title><link rel="stylesheet" href="/vendor/leaflet.css"><script src="/vendor/leaflet.js"></script>
<style>html,body{{margin:0;height:100%;font:16px/1.4 system-ui,sans-serif}}#map{{position:absolute;inset:0 0 86px 0}}#bar{{position:absolute;left:0;right:0;bottom:0;height:86px;box-sizing:border-box;padding:10px 14px;background:#10282a;color:#fff}}#bar a{{color:#f2c230}}#bar small{{opacity:.8}}</style></head>
<body><div id="map"></div><div id="bar"><b id="nm">{_h.escape(t[0])}</b><div id="st">…</div><small id="ex"></small></div>
<script>
const T={json.dumps(t)};let map=L.map("map").setView([50,10],5),mk=null,first=true;L.tileLayer("/tiles/osm/{{z}}/{{x}}/{{y}}",{{maxZoom:18,attribution:"© OpenStreetMap"}}).addTo(map);
async function poll(){{try{{const r=await fetch("/api/public/live/{token}",{{cache:"no-store"}});const j=await r.json();
 if(r.status===410||j.gone){{document.getElementById("st").textContent=T[3];clearInterval(iv);return}}
 if(j.lat===undefined){{document.getElementById("st").textContent=T[1];return}}
 const p=[j.lat,j.lon];if(!mk)mk=L.circleMarker(p,{{radius:10,color:"#fff",weight:3,fillColor:"#d9534f",fillOpacity:1}}).addTo(map);else mk.setLatLng(p);
 if(first){{map.setView(p,15);first=false}}
 document.getElementById("nm").textContent=j.name||T[0];
 document.getElementById("st").innerHTML=T[2].replace("{{}}",Math.max(0,Math.round(j.age_s/60)))+' · <a target="_blank" rel="noopener" href="https://www.openstreetmap.org/?mlat='+j.lat+'&mlon='+j.lon+'#map=16/'+j.lat+'/'+j.lon+'">'+T[4]+'</a>';
 document.getElementById("ex").textContent=T[5].replace("{{}}",new Date(j.exp*1000).toLocaleString());
}}catch(e){{}}}}
poll();const iv=setInterval(poll,20000);
</script></body></html>"""
    return HTMLResponse(page, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
