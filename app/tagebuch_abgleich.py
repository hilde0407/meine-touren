"""3.57.0: Abgleich von Notizen, Fotos und Videos mit der Android-App „Mein Tourentagebuch“ (Server-Seite).

Das Tagebuch gleicht nur auf Knopfdruck ab und zeigt vorher, was neu ist. Dafür gibt es hier:

Lesen (auch für Betrachter, wie /api/tours/<id>, /api/photos und /pic/<id>, die Notiz und Fotos einer Tour ohnehin zeigen):
  GET  /api/tours/{id}/tagebuch                    Notiz (Text, geändert am) und Liste der Fotos und Videos der Tour – ohne Bilddaten, nie ein Dateipfad
  GET  /api/tours/{id}/tagebuch/photo/{pid}?w=…    ein Foto verkleinert (JPEG, längste Seite höchstens w, 120…2400), Cache wie bei Titelbildern (&v=…)
  GET  /api/tours/{id}/tagebuch/video/{vid}?video=1  ein Video (nur mit video=1, mit Range), höchstens VIDEO_MAX groß
  GET  /api/tagebuch/uebersicht?ids=a,b,…          je Tour nur Zahlen und Stempel (für die Vorschau „was ist neu“ über viele Touren)
Schreiben (nur Konten mit Schreibrechten; ein Betrachter bekommt 403 von der Anmeldeprüfung in main.py, weil POST nie in VIEWER_GET steht):
  POST /api/tours/{id}/notiz   JSON {text, basis}: zusammenführen statt überschreiben (siehe notiz_merge)
  POST /api/tours/{id}/photo   multipart: Foto (JPEG/PNG/WebP, HEIC nur mit pillow-heif), verkleinert wie die vorhandene Foto-Pipeline, Doppelte werden erkannt
  POST /api/tours/{id}/video   multipart, nur mit bestaetigt=1: Video (MP4/MOV/3GP/WebM) bis VIDEO_MAX, je Tour höchstens VIDEO_TOUR_MAX

Tabellen (nur ergänzend, db.migrate): tour_notes.ts (geändert am, ms), photo_src (Herkunft hochgeladener Fotos), tour_videos.
Alles betrifft nur die Datenbank und den Datenordner des angemeldeten Kontos (ctx.uid(), bei Betrachtern der Besitzer).
Fotos landen als normale Fotos der Bibliothek in <Fotoordner>/tagebuch/<Tour>/ und sind fest der Tour zugeordnet (manual=1).
Videos liegen in <Datenordner des Kontos>/videos/<Tour>/ (gehören damit zum Umzugspaket, nicht zur täglichen Datenbanksicherung).
"""
import hashlib
import io
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from . import config, db, photos
from .gpxtools import TZ

router = APIRouter()

NOTIZ_MAX = 20000                 # Zeichen; die Notiz-Box der Tourseite speichert seit 3.57.0 ebenso viel (vorher 5000), damit eine zusammengeführte Notiz nie gekürzt wird
FOTO_MAX = 40 * 1024 * 1024       # Bytes je Foto (Original vom Handy); gespeichert wird verkleinert (photo_max_side, Vorgabe 2200 px)
VIDEO_MAX = 200 * 1024 * 1024     # Bytes je Video
VIDEO_TOUR_MAX = 1024 * 1024 * 1024   # Bytes aller Videos einer Tour
BREITE_MAX = 2400
VIDEO_EXT = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".3gp": "video/3gpp", ".webm": "video/webm"}
_REF = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_OFF = re.compile(r"^[+-]\d\d:\d\d$")


def _tour(tid):
    t = db.one("SELECT id,name,start_ts FROM tours WHERE id=?", (str(tid),))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    return t


def _now_ms():
    return int(time.time() * 1000)


def _darf_schreiben(request):
    u = getattr(request.state, "user", None)
    return not (u and u.get("role") == "viewer")


# ---------------------------------------------------------------- Notiz ----------------------------------------------------------------
def notiz_get(tid):
    r = db.one("SELECT note,ts FROM tour_notes WHERE id=?", (str(tid),))
    return {"text": (r["note"] or "") if r else "", "geaendert": (r["ts"] if r else None)}


def notiz_set(tid, text):
    """Notiz speichern (leer = löschen) und den Stempel „geändert am“ setzen. Benutzt auch POST /api/tours/{id}/note der Oberfläche."""
    text = (text or "").strip()
    if text:
        ts = _now_ms()
        old = db.one("SELECT ts FROM tour_notes WHERE id=?", (str(tid),))
        if old and old["ts"] and ts <= old["ts"]:
            ts = old["ts"] + 1                      # Stempel ändert sich mit jeder Änderung, auch zweimal in derselben Millisekunde
        db.execute("INSERT OR REPLACE INTO tour_notes(id,note,ts) VALUES(?,?,?)", (str(tid), text, ts))
    else:
        db.execute("DELETE FROM tour_notes WHERE id=?", (str(tid),))
    return notiz_get(tid)


def _norm(s):
    return re.sub(r"[ \t]+\n", "\n", str(s or "").replace("\r\n", "\n").replace("\r", "\n")).strip()


def trennzeile(when=None):
    d = datetime.fromtimestamp(when if when is not None else time.time(), TZ)
    return f"——— Aus Mein Tourentagebuch, {d:%d.%m.%Y %H:%M} ———"


def notiz_merge(cur, cur_ts, new, basis, when=None):
    """Regel für POST /notiz. Gibt (status, text_oder_None) zurück; None = nichts speichern.
    gleich: der Server hat schon genau diesen Text.  leer: leerer Text löscht nie etwas.  uebernommen: der Server hatte nichts, oder seit dem Stand des
    Tagebuchs (basis = „geaendert“ beim letzten Abruf) hat sich am Server nichts geändert, oder der neue Text enthält den des Servers vollständig.
    schon_enthalten: der Text des Tagebuchs steht am Server schon vollständig drin.  zusammengefuehrt: beide wurden unabhängig geändert – die Fassung
    des Servers bleibt, die des Tagebuchs wird mit Trennzeile und Datum angehängt. So geht nie etwas verloren."""
    cur, new = _norm(cur), _norm(new)
    if not new:
        return "leer", None
    if new == cur:
        return "gleich", None
    if not cur:
        return "uebernommen", new
    if basis is not None and cur_ts is not None and int(basis) == int(cur_ts):
        return "uebernommen", new
    if new in cur:
        return "schon_enthalten", None
    if cur in new:
        return "uebernommen", new
    return "zusammengefuehrt", f"{cur}\n\n{trennzeile(when)}\n{new}"


@router.post("/api/tours/{tour_id}/notiz")
def api_notiz(tour_id: str, body: dict):
    _tour(tour_id)
    if not isinstance(body, dict) or not isinstance(body.get("text", ""), str):
        raise HTTPException(400, "Feld „text“ fehlt")
    basis = body.get("basis")
    if basis is not None:
        try:
            basis = int(basis)
        except (TypeError, ValueError):
            raise HTTPException(400, "„basis“ muss der Stempel „geaendert“ (Zahl) oder null sein")
    if len(body.get("text") or "") > NOTIZ_MAX:
        raise HTTPException(413, f"Die Notiz ist zu lang (höchstens {NOTIZ_MAX} Zeichen)")
    cur = notiz_get(tour_id)
    status, text = notiz_merge(cur["text"], cur["geaendert"], body.get("text") or "", basis)
    if text is not None and len(text) > NOTIZ_MAX:
        raise HTTPException(413, f"Zusammengeführt wäre die Notiz zu lang (höchstens {NOTIZ_MAX} Zeichen). Bitte am Server oder im Tagebuch kürzen.")
    out = notiz_set(tour_id, text) if text is not None else cur
    return {"status": status, "konflikt": status == "zusammengefuehrt", "notiz": out}


# ---------------------------------------------------------------- Lesen ----------------------------------------------------------------
def _fotos(tid):
    rows = db.query("SELECT p.id,p.taken_ts,p.lat,p.lng,p.size,p.path,p.mtime,p.fp,s.ref,s.name,s.sha1 FROM photos p LEFT JOIN photo_src s ON s.photo_id=p.id "
                    "WHERE p.tour_id=? AND COALESCE(p.manual,0)!=2 ORDER BY p.taken_ts,p.id", (str(tid),))
    out = []
    for r in rows:
        out.append({"id": r["id"], "taken_ts": r["taken_ts"], "lat": r["lat"], "lng": r["lng"], "size": r["size"], "v": photos.ver(r["path"], r["mtime"], r["size"]),
                    "video": False, "fp": r["fp"] or None, "sha1": r["sha1"], "ref": r["ref"], "name": r["name"]})
    return out


def _videos(tid):
    rows = db.query("SELECT id,taken_ts,lat,lng,size,dur_ms,sha1,ref,name FROM tour_videos WHERE tour_id=? ORDER BY taken_ts,id", (str(tid),))
    return [{"id": r["id"], "taken_ts": r["taken_ts"], "lat": r["lat"], "lng": r["lng"], "size": r["size"], "v": (r["sha1"] or "")[:12],
             "video": True, "dur_ms": r["dur_ms"], "sha1": r["sha1"], "ref": r["ref"], "name": r["name"]} for r in rows]


def grenzen():
    return {"foto_mb": FOTO_MAX // 1048576, "video_mb": VIDEO_MAX // 1048576, "video_tour_mb": VIDEO_TOUR_MAX // 1048576, "breite_max": BREITE_MAX,
            "notiz_zeichen": NOTIZ_MAX, "heic": photos.heic_supported()}


@router.get("/api/tours/{tour_id}/tagebuch")
def api_tagebuch(tour_id: str, request: Request):
    t = _tour(tour_id)
    return {"tour": {"id": t["id"], "name": t["name"], "start_ts": t["start_ts"]}, "notiz": notiz_get(tour_id),
            "fotos": _fotos(tour_id), "videos": _videos(tour_id), "grenzen": grenzen(), "darf_schreiben": _darf_schreiben(request)}


@router.get("/api/tagebuch/uebersicht")
def api_uebersicht(ids: str = ""):
    """Je Tour (höchstens 500, kommagetrennt): Zahl der Fotos und Videos, Stempel der Notiz und eine Kennzahl „stand“, die sich ändert, sobald
    an Notiz, Fotos oder Videos der Tour etwas anders ist. Unbekannte Touren fehlen in der Antwort."""
    want = [x for x in dict.fromkeys(s.strip() for s in ids.split(",")) if x][:500]
    out = {}
    for i in range(0, len(want), 250):
        part = want[i:i + 250]
        q = ",".join("?" * len(part))
        for t in db.query(f"SELECT id FROM tours WHERE id IN ({q})", part):
            out[t["id"]] = {"fotos": 0, "videos": 0, "notiz_geaendert": None, "notiz": False, "_h": []}
        for r in db.query(f"SELECT tour_id,id,path,mtime,size FROM photos WHERE tour_id IN ({q}) AND COALESCE(manual,0)!=2 ORDER BY id", part):
            o = out.get(r["tour_id"])
            if o is not None:
                o["fotos"] += 1; o["_h"].append(f"p{r['id']}:{photos.ver(r['path'], r['mtime'], r['size'])}")
        for r in db.query(f"SELECT tour_id,id,sha1 FROM tour_videos WHERE tour_id IN ({q}) ORDER BY id", part):
            o = out.get(r["tour_id"])
            if o is not None:
                o["videos"] += 1; o["_h"].append(f"v{r['id']}:{r['sha1']}")
        for r in db.query(f"SELECT id,note,ts FROM tour_notes WHERE id IN ({q})", part):
            o = out.get(r["id"])
            if o is not None:
                o["notiz"] = bool((r["note"] or "").strip()); o["notiz_geaendert"] = r["ts"]
                o["_h"].append(f"n{r['ts']}:{hashlib.sha1((r['note'] or '').encode()).hexdigest()[:8]}")
    for o in out.values():
        o["stand"] = hashlib.sha1("|".join(o.pop("_h")).encode()).hexdigest()[:12]
    return out


@router.get("/api/tours/{tour_id}/tagebuch/photo/{pid}")
def api_tagebuch_photo(tour_id: str, pid: int, request: Request, w: int = 1600, v: str = ""):
    _tour(tour_id)
    if not db.one("SELECT 1 x FROM photos WHERE id=? AND tour_id=?", (pid, str(tour_id))):
        raise HTTPException(404, "Foto nicht gefunden")
    p = photos.thumb(pid, max(120, min(int(w or 1600), BREITE_MAX)))
    if not p:
        raise HTTPException(404, "Foto nicht gefunden")
    return photos.respond(request, p, immutable=bool(v) and v == photos.ver_of(pid))


@router.get("/api/tours/{tour_id}/tagebuch/video/{vid}")
def api_tagebuch_video(tour_id: str, vid: int, video: int = 0):
    _tour(tour_id)
    if video != 1:
        raise HTTPException(400, "Videos werden nur auf ausdrücklichen Wunsch geladen (video=1)")
    r = db.one("SELECT path,size,sha1 FROM tour_videos WHERE id=? AND tour_id=?", (vid, str(tour_id)))
    if not r or not os.path.isfile(r["path"]):
        raise HTTPException(404, "Video nicht gefunden")
    if os.path.getsize(r["path"]) > VIDEO_MAX:
        raise HTTPException(413, f"Das Video ist größer als {VIDEO_MAX // 1048576} MB und wird nicht übertragen")
    mt = VIDEO_EXT.get(Path(r["path"]).suffix.lower(), "application/octet-stream")
    return FileResponse(r["path"], media_type=mt, headers={"Cache-Control": "private, max-age=31536000, immutable"})


# ---------------------------------------------------------------- Foto hochladen ----------------------------------------------------------------
def _ref(x):
    x = (x or "").strip()
    return x if _REF.match(x) else None


def _name(x):
    x = re.sub(r"[^\w.\- ()]+", "_", str(x or "").replace("\\", "/").split("/")[-1]).strip()[:120]
    return x or None


def _float(x, lo, hi):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi and v == v else None


def _zu_gross(request, limit):
    try:
        n = int(request.headers.get("content-length") or 0)
    except ValueError:
        n = 0
    return n > limit + 64 * 1024


def _read(file, limit, msg):
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, msg)
    return data


def _ts_text(taken_ms, offset):
    """Aufnahmezeit (ms seit 1970, UTC) → ('JJJJ:MM:TT hh:mm:ss' in der Zeitzone der Aufnahme, '+hh:mm'). Ohne Zeitzone gilt die des Servers."""
    secs = int(taken_ms) / 1000
    if offset and _OFF.match(offset):
        sign = -1 if offset[0] == "-" else 1
        tz = timezone(sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[4:6])))
    else:
        tz = TZ
    d = datetime.fromtimestamp(secs, tz)
    off = d.utcoffset() or timedelta(0)
    m = int(off.total_seconds() // 60)
    return d.strftime("%Y:%m:%d %H:%M:%S"), f"{'-' if m < 0 else '+'}{abs(m) // 60:02d}:{abs(m) % 60:02d}"


def _vorhanden(pid, how):
    r = db.one("SELECT id,path,mtime,size,tour_id FROM photos WHERE id=?", (pid,))
    return {"status": "vorhanden", "id": r["id"], "wie": how, "v": photos.ver(r["path"], r["mtime"], r["size"]), "tour_id": r["tour_id"]}


def _safe_dir(tid):
    return re.sub(r"[^\w-]+", "_", str(tid))[:80] or "tour"


@router.post("/api/tours/{tour_id}/photo")
def api_photo_upload(tour_id: str, request: Request, file: UploadFile = File(...), ref: str = Form(""), name: str = Form(""), taken: str = Form(""),
                     offset: str = Form(""), lat: str = Form(""), lng: str = Form(""), force: str = Form("")):
    """Foto aus dem Tagebuch zu dieser Tour. Felder: file (Bilddatei), ref (Kennung im Tagebuch, optional), name (Dateiname), taken (Aufnahmezeit in ms, optional –
    sonst aus dem EXIF des Bildes), offset ('+01:00', optional), lat/lng (optional – sonst aus dem EXIF), force=1 (auch ein in Meine Touren gelöschtes Foto wieder aufnehmen).
    Antwort: {status: 'neu'|'vorhanden'|'geloescht', id, v, …}."""
    t = _tour(tour_id)
    if _zu_gross(request, FOTO_MAX):
        raise HTTPException(413, f"Das Foto ist größer als {FOTO_MAX // 1048576} MB")
    raw = _read(file, FOTO_MAX, f"Das Foto ist größer als {FOTO_MAX // 1048576} MB")
    if not raw:
        raise HTTPException(400, "Leere Datei")
    ref, name = _ref(ref), _name(name or file.filename)
    sha1 = hashlib.sha1(raw).hexdigest()
    # 1) gleicher Inhalt (SHA-1 der Datei) oder gleiche Kennung des Tagebuchs schon da?
    for col, val, how in (("sha1", sha1, "inhalt"), ("ref", ref, "kennung")):
        if not val:
            continue
        r = db.one(f"SELECT s.photo_id FROM photo_src s JOIN photos p ON p.id=s.photo_id WHERE s.{col}=? ORDER BY s.photo_id LIMIT 1", (val,))
        if r:
            return _vorhanden(r["photo_id"], how)
    # 2) Aufnahmezeit und Ort: Angaben des Tagebuchs vor EXIF
    ex_raw, ex_off, ex_lat, ex_lng = photos.exif_fields(io.BytesIO(raw))
    offset = offset if _OFF.match(offset or "") else ""
    taken_txt, off_txt, ts = None, None, None
    tk = _float(taken, 0, 4102444800000)               # bis 2100
    if tk:
        taken_txt, off_txt = _ts_text(tk, offset)
        ts = int(tk // 1000)
    elif ex_raw:
        taken_txt = str(ex_raw).strip()[:19]
        off_txt = offset or (str(ex_off) if ex_off and _OFF.match(str(ex_off)) else None)
        ts = photos._raw_ts(taken_txt, off_txt)
        if ts is not None and not off_txt:
            off_txt = _ts_text(ts * 1000, "")[1]          # wie gedeutet, so gespeichert (Zeitzone des Servers bzw. Kamera-Einstellung)
            taken_txt = _ts_text(ts * 1000, off_txt)[0]
    la, lo = _float(lat, -90, 90), _float(lng, -180, 180)
    if la is None or lo is None:
        la, lo = ex_lat, ex_lng
    # 3) verkleinern wie die vorhandene Foto-Pipeline (JPEG, längste Seite photo_max_side), dann Zeit und Ort als EXIF eintragen
    try:
        jpeg = photos.to_jpeg_bytes(raw)
    except ValueError as e:
        raise HTTPException(415, str(e))
    fp = photos.fingerprint(jpeg)
    # 4) dasselbe Bild schon in der Bibliothek (gleiche Aufnahmezeit ± 2 s und gleicher Bildinhalt) oder gleicher Name und gleiche Zeit?
    dup = photos.find_duplicate(ts, fp)
    if dup:
        r = db.one("SELECT id FROM photos WHERE path=?", (dup,))
        if r:
            return _vorhanden(r["id"], "bild")
    if name and ts is not None:
        r = db.one("SELECT s.photo_id FROM photo_src s JOIN photos p ON p.id=s.photo_id WHERE s.name=? AND p.taken_ts BETWEEN ? AND ? LIMIT 1", (name, ts - 2, ts + 2))
        if r:
            return _vorhanden(r["photo_id"], "name_zeit")
    data = photos.with_exif_time(jpeg, taken_txt, la, lo, off_txt) if taken_txt else jpeg
    lib = config.LIB_DIR
    dst = lib / "tagebuch" / _safe_dir(t["id"]) / f"{sha1[:20]}.jpg"
    rel = dst.relative_to(lib).with_suffix("").as_posix()
    if not force and db.one("SELECT 1 x FROM photo_deleted WHERE rel=?", (rel,)):
        return {"status": "geloescht", "id": None, "wie": "in Meine Touren gelöscht – mit force=1 wieder aufnehmen"}
    db.execute("DELETE FROM photo_deleted WHERE rel=?", (rel,))
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f"{dst.stem}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    tmp.replace(dst)
    st = dst.stat()
    dated = 1 if ts is not None else 0
    photos._store([(str(dst), st.st_mtime, st.st_size, ts if ts is not None else int(st.st_mtime), la, lo, dated)])
    pid = db.one("SELECT id FROM photos WHERE path=?", (str(dst),))["id"]
    db.execute("UPDATE photos SET tour_id=?, manual=1, fp=? WHERE id=?", (t["id"], fp or "", pid))
    db.execute("INSERT OR REPLACE INTO photo_src(photo_id,sha1,ref,name,src,ts) VALUES(?,?,?,?,?,?)", (pid, sha1, ref, name, "tagebuch", _now_ms()))
    photos.warm_strip_bg([t["id"]], metrics=True)
    return {"status": "neu", "id": pid, "v": photos.ver(str(dst), st.st_mtime, st.st_size), "taken_ts": ts, "lat": la, "lng": lo, "size": st.st_size}


# ---------------------------------------------------------------- Video hochladen ----------------------------------------------------------------
def _video_ext(head, name):
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand == b"qt  ":
            return ".mov"
        if brand[:3] == b"3gp":
            return ".3gp"
        return ".mp4"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return ".webm"
    return None


@router.post("/api/tours/{tour_id}/video")
def api_video_upload(tour_id: str, request: Request, file: UploadFile = File(...), bestaetigt: str = Form(""), ref: str = Form(""), name: str = Form(""),
                     taken: str = Form(""), lat: str = Form(""), lng: str = Form(""), dur_ms: str = Form("")):
    """Video aus dem Tagebuch zu dieser Tour – nur mit bestaetigt=1 (nie automatisch). Grenzen: VIDEO_MAX je Video, VIDEO_TOUR_MAX je Tour.
    Antwort: {status: 'neu'|'vorhanden', id, …}; zu groß → 413 mit Meldung."""
    t = _tour(tour_id)
    if bestaetigt != "1":
        raise HTTPException(400, "Videos werden nur auf ausdrücklichen Wunsch übertragen (bestaetigt=1)")
    msg = f"Das Video ist zu groß: höchstens {VIDEO_MAX // 1048576} MB je Video"
    if _zu_gross(request, VIDEO_MAX):
        raise HTTPException(413, msg)
    ref, name = _ref(ref), _name(name or file.filename)
    if ref:
        r = db.one("SELECT id FROM tour_videos WHERE ref=? AND tour_id=?", (ref, t["id"]))
        if r:
            return {"status": "vorhanden", "id": r["id"], "wie": "kennung"}
    used = db.one("SELECT COALESCE(SUM(size),0) n FROM tour_videos WHERE tour_id=?", (t["id"],))["n"]
    vdir = config.LIB_DIR.parent / "videos" / _safe_dir(t["id"])
    vdir.mkdir(parents=True, exist_ok=True)
    tmp = vdir / f".upload-{os.getpid()}-{time.time_ns()}.part"
    h, n, head = hashlib.sha1(), 0, b""
    try:
        with open(tmp, "wb") as out:
            while True:
                chunk = file.file.read(1 << 20)
                if not chunk:
                    break
                if not head:
                    head = chunk[:16]
                n += len(chunk)
                if n > VIDEO_MAX:
                    raise HTTPException(413, msg)
                h.update(chunk)
                out.write(chunk)
        if not n:
            raise HTTPException(400, "Leere Datei")
        ext = _video_ext(head, name)
        if not ext:
            raise HTTPException(415, "Kein unterstütztes Video (MP4, MOV, 3GP oder WebM)")
        sha1 = h.hexdigest()
        r = db.one("SELECT id FROM tour_videos WHERE sha1=? AND tour_id=?", (sha1, t["id"]))
        if r:
            return {"status": "vorhanden", "id": r["id"], "wie": "inhalt"}
        if used + n > VIDEO_TOUR_MAX:
            raise HTTPException(413, f"Für diese Tour ist kein Platz mehr für Videos: höchstens {VIDEO_TOUR_MAX // 1048576} MB je Tour (belegt {used // 1048576} MB)")
        dst = vdir / f"{sha1[:20]}{ext}"
        tmp.replace(dst)
    finally:
        tmp.unlink(missing_ok=True)
    tk = _float(taken, 0, 4102444800000)
    la, lo = _float(lat, -90, 90), _float(lng, -180, 180)
    du = _float(dur_ms, 0, 864e5)
    vid = db.execute("INSERT INTO tour_videos(tour_id,path,size,taken_ts,lat,lng,dur_ms,sha1,ref,name,src,ts) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                     (t["id"], str(dst), n, int(tk // 1000) if tk else None, la if lo is not None else None, lo if la is not None else None,
                      int(du) if du is not None else None, sha1, ref, name, "tagebuch", _now_ms()))
    return {"status": "neu", "id": vid, "size": n, "v": sha1[:12]}
