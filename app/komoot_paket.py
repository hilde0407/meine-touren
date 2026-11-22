"""3.58.0 – Komoot-Paket: alles, um eine Tour selbst bei Komoot hochzuladen, als ZIP (für die Weboberfläche und Mein Tourentagebuch).

GET /api/tours/{id}/komoot-paket?fotos=1,2&ohne_ort=1&notiz=1
  tour.gpx      Strecke wie gespeichert, dazu (notiz=1, Vorgabe) die Notiz als Beschreibung und die Pins als Wegpunkte
  notiz.txt     die Notiz zum Einfügen in Komoot (nur wenn vorhanden und notiz=1)
  fotos/…       nur die ausdrücklich gewählten Fotos dieser Tour (Vorgabe: keine), verkleinert auf höchstens 2000 Pixel, mit Aufnahmezeit;
                den Aufnahmeort nur mit ohne_ort=0 (Vorgabe: entfernt)
  README.txt    Anleitung (deutsch): wie man das Paket in Komoot hochlädt, Sichtbarkeit selbst wählen, Fotos einzeln, Rechte
  manifest.json Inhalt maschinenlesbar (Format „meine-touren-komoot-paket“, Version 1)
Nur lesend; ein Betrachter-Konto darf es abrufen (wie GPX und Fotos). Nichts geht an Komoot.
"""
import io
import json
import re
import time
import urllib.parse
import zipfile
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from . import db, gpxtools, photos, portals, tracks
from .gpxtools import TZ

router = APIRouter()

FORMAT = "meine-touren-komoot-paket"
FOTO_MAX_PX = 2000
FOTO_MAX_N = 60

README = """Komoot-Paket aus Meine Touren
=============================

Tour: {name}
Datum: {datum}
Erstellt: {erstellt}

Inhalt
------
- {gpx}: die Strecke{gpx_extra}
{notiz_zeile}{fotos_zeile}- manifest.json: Inhaltsverzeichnis für Programme (kannst du ignorieren)

So lädst du die Tour selbst in Komoot hoch
------------------------------------------
1. ZIP-Datei entpacken.
2. In Komoot (Webseite komoot.com oder App) die GPX-Datei importieren:
   Webseite: Planen bzw. Profil -> „GPX-Datei importieren“ (oder „Datei hochladen“).
   Als „abgeschlossene Aktivität“ (nicht als geplante Route) speichern, Sportart und Datum prüfen.
3. SICHTBARKEIT SELBST WÄHLEN: Komoot fragt beim Import nach der Sichtbarkeit bzw. nimmt die
   Vorgabe deines Kontos. Wähle „Nur ich“ (privat), wenn die Tour nicht für alle sichtbar sein soll.
   Prüfe danach in der Tour, welche Sichtbarkeit eingestellt ist.
4. Notiz: Ob Komoot die Beschreibung und die Wegpunkte aus der GPX-Datei übernimmt, ist nicht sicher.
   Den Text aus notiz.txt kannst du in Komoot selbst einfügen.
5. Fotos: in Komoot einzeln über „Foto hinzufügen“ an die Tour hängen.

Wichtig zu Fotos und Rechten
----------------------------
- Du hast die Fotos selbst ausgewählt und verantwortest die Auswahl.
- Meine Touren erkennt keine Gesichter. Sind Personen erkennbar, brauchst du für eine Veröffentlichung
  in der Regel deren Einwilligung. Kinder und Kennzeichen besonders beachten.
- Lade nur Fotos hoch, die du selbst gemacht hast oder für die du die Rechte hast.
- Fotos und Tipps in Komoot-Highlights sind immer öffentlich. Was einmal öffentlich war, lässt sich
  nicht zuverlässig zurückholen (Kopien, Suchmaschinen).
- Aufnahmeort in den Fotos: {ort}
"""


def _ids(s):
    out = []
    for x in (s or "").split(","):
        x = x.strip()
        if not x:
            continue
        if not x.isdigit():
            raise HTTPException(400, f"Ungültige Foto-Kennung „{x[:20]}“")
        if int(x) not in out:
            out.append(int(x))
    if len(out) > FOTO_MAX_N:
        raise HTTPException(400, f"Höchstens {FOTO_MAX_N} Fotos je Paket")
    return out


def _safe(name, fallback):
    s = re.sub(r"[^\w .-]+", "_", name or "", flags=re.U).strip(" ._")[:80]
    return s or fallback


def _foto(pid, row, ohne_ort):
    """Verkleinerte JPEG-Kopie (ohne alle EXIF-Daten des Originals); Aufnahmezeit wieder eingetragen, Ort nur wenn gewünscht."""
    p = photos.thumb(pid, FOTO_MAX_PX)
    if not p:
        return None
    data = p.read_bytes()
    if row["taken_ts"]:
        d = datetime.fromtimestamp(int(row["taken_ts"]), TZ)
        off = d.utcoffset()
        m = int(off.total_seconds() // 60) if off else 0
        offs = f"{'-' if m < 0 else '+'}{abs(m) // 60:02d}:{abs(m) % 60:02d}"
        la, lo = (None, None) if ohne_ort else (row["lat"], row["lng"])
        data = photos.with_exif_time(data, d.strftime("%Y:%m:%d %H:%M:%S"), la, lo, offs)
    return data


def build(tid, foto_ids=(), ohne_ort=True, notiz=True):
    """Gibt (zip_bytes, dateiname, manifest) zurück."""
    t = db.one("SELECT id,name,sport,start_ts,dist_m FROM tours WHERE id=?", (str(tid),))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    try:
        gpx = tracks.gpx_for(tid)
    except RuntimeError as e:
        raise HTTPException(404, str(e))
    gpx, n_wpt, has_note = portals.upload_copy(tid, gpx, notiz)
    note = portals.note_for(tid) if notiz else ""
    rows = {}
    if foto_ids:
        q = ",".join("?" * len(foto_ids))
        rows = {r["id"]: r for r in db.query(f"SELECT id,taken_ts,lat,lng FROM photos WHERE id IN ({q}) AND tour_id=? AND COALESCE(manual,0)!=2",
                                             (*foto_ids, str(tid)))}
        fremd = [i for i in foto_ids if i not in rows]
        if fremd:
            raise HTTPException(400, f"Foto {fremd[0]} gehört nicht zu dieser Tour")
    base = _safe(t["name"], str(tid))
    gname = f"{base}.gpx"
    datum = datetime.fromtimestamp(t["start_ts"], TZ).strftime("%d.%m.%Y %H:%M") if t["start_ts"] else "unbekannt"
    buf = io.BytesIO()
    fotos_out = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(gname, gpx)
        if note:
            z.writestr("notiz.txt", gpxtools.clean_text(note, 20000).replace("\n", "\r\n") + "\r\n")
        for i, pid in enumerate(foto_ids, 1):
            data = _foto(pid, rows[pid], ohne_ort)
            if data is None:
                continue
            ts = rows[pid]["taken_ts"]
            stamp = datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d_%H-%M-%S") if ts else "ohne-zeit"
            fn = f"fotos/{i:02d}_{stamp}.jpg"
            z.writestr(zipfile.ZipInfo(fn, time.localtime()[:6]), data, compress_type=zipfile.ZIP_STORED)
            fotos_out.append({"datei": fn, "foto_id": pid, "taken_ts": ts, "ort": (not ohne_ort) and rows[pid]["lat"] is not None})
        manifest = {"format": FORMAT, "version": 1, "erstellt": int(time.time()),
                    "tour": {"id": t["id"], "name": t["name"], "sport": t["sport"], "start_ts": t["start_ts"], "dist_m": t["dist_m"]},
                    "gpx": gname, "wegpunkte": n_wpt, "notiz": bool(note), "fotos": fotos_out, "ort_entfernt": bool(ohne_ort),
                    "hinweis": "Sichtbarkeit in Komoot selbst wählen; Fotos einzeln hochladen; Auswahl und Rechte verantwortet der Nutzer."}
        readme = README.format(
            name=t["name"] or t["id"], datum=datum, erstellt=datetime.now(TZ).strftime("%d.%m.%Y %H:%M"), gpx=gname,
            gpx_extra=(f" mit {n_wpt} Wegpunkten (Pins)" if n_wpt else "") + (" und deiner Notiz als Beschreibung" if has_note else ""),
            notiz_zeile="- notiz.txt: deine Notiz zum Einfügen in Komoot\n" if note else "",
            fotos_zeile=f"- fotos/: {len(fotos_out)} ausgewählte Fotos (höchstens {FOTO_MAX_PX} Pixel)\n" if fotos_out else "- keine Fotos (keine ausgewählt)\n",
            ort="entfernt" if ohne_ort else "enthalten (GPS-Position in den Bilddaten)")
        z.writestr("README.txt", readme.replace("\n", "\r\n"))
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    return buf.getvalue(), f"Komoot-Paket {base}.zip", manifest


@router.get("/api/tours/{tour_id}/komoot-paket")
def api_komoot_paket(tour_id: str, fotos: str = "", ohne_ort: int = 1, notiz: int = 1):
    data, fn, _ = build(tour_id, _ids(fotos), ohne_ort != 0, notiz != 0)
    ascii_fn = fn.encode("ascii", "replace").decode().replace("?", "_").replace('"', "_")
    cd = f"attachment; filename=\"{ascii_fn}\"; filename*=UTF-8''{urllib.parse.quote(fn)}"
    return Response(data, media_type="application/zip", headers={"Content-Disposition": cd, "Cache-Control": "no-store"})
