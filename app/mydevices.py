"""Meine Geräte: Aufnahmegeräte (Uhr, Handy …) selbst anlegen und benennen; jede Tour gehört zu einem Gerät.

Zuordnung: Eine ausdrückliche Wahl (Tabelle tour_device) hat immer Vorrang. Sonst gilt automatisch: die Art der Tour-Quelle (zepp, garmin, suunto,
polar, phone, other – siehe Tabelle tour_source bzw. metrics.py) wird mit der Art der Geräte verglichen; gibt es mehrere Geräte gleicher Art,
entscheidet das Tourdatum anhand „seit/bis“ (bei mehreren Treffern das Gerät mit dem späteren „seit“). Passt keines zum Datum, aber es gibt nur ein
Gerät dieser Art, bekommt dieses die Tour. Hat ein Gerät eine Zepp-Kennung (zsrc, z. B. „run.46.huami.com“) und kennt die Tour dieselbe Kennung
(Tabelle tour_zsrc), wird dieses Gerät bevorzugt. Geräte werden nie ungefragt angelegt und nie gelöscht, solange Touren daran hängen.
Gerätefotos liegen als <Datenordner des Benutzers>/devices/<id>.jpg (höchstens 512 px, JPEG)."""
import io
import re
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import config, db
from .gpxtools import TZ

router = APIRouter()
KINDS = ("zepp", "garmin", "suunto", "polar", "phone", "other")
KIND_LABEL = {"zepp": "Amazfit/Zepp", "garmin": "Garmin", "suunto": "Suunto", "polar": "Polar", "phone": "Handy-Aufzeichnung", "other": "Anderes Gerät"}
_DATE = re.compile(r"^\d{4}-\d\d-\d\d$")
PHOTO_MAX_BYTES = 8 * 1024 * 1024
PHOTO_MAX_PIXELS = 60_000_000
PHOTO_SIDE = 512


def photo_dir():
    return config.DB_PATH.parent / "devices"


def photo_path(did):
    return photo_dir() / f"{int(did)}.jpg"


def _day(ts):
    return datetime.fromtimestamp(ts, tz=TZ).strftime("%Y-%m-%d") if ts else ""


def tour_kind(tid, src=None):
    """Art der Quelle einer Tour ('' = unbekannt, z. B. Komoot ohne Datei)."""
    if src is None:
        r = db.one("SELECT src FROM tour_source WHERE tour_id=?", (str(tid),))
        src = r["src"] if r else ""
    if src in KINDS:
        return src
    if re.fullmatch(r"z\d+", str(tid)):
        return "zepp"
    return ""


def _photo_v(did):
    """Änderungsstempel des Fotos (0 = kein Foto) – hängt die Oberfläche an die Adresse, damit ein neues Foto sofort erscheint."""
    try:
        return photo_path(did).stat().st_mtime_ns // 1_000_000
    except OSError:
        return 0


def _row(d):
    return {"id": d["id"], "name": d["name"], "kind": d["kind"], "model": d["model"] or "", "since": d["since"] or "", "until": d["until"] or "",
            "active": bool(d["active"]), "note": d["note"] or "", "zsrc": d.get("zsrc") or "", "photo": _photo_v(d["id"])}


def note_zsrc(summaries):
    """Zepp-Kennung (Feld „source“) je Training merken: gilt für die Tour z<trackid>. Nur vorhandene Touren; gleiche Werte werden nicht neu geschrieben."""
    have = {r["tour_id"]: r["zsrc"] for r in db.query("SELECT tour_id, zsrc FROM tour_zsrc")}
    n = 0
    for s in summaries:
        if not isinstance(s, dict):
            continue
        src, tr = str(s.get("source") or "").strip()[:120], str(s.get("trackid") or "").strip()
        if not src or not tr.isdigit():
            continue
        tid = "z" + tr
        if have.get(tid) != src and db.one("SELECT 1 FROM tours WHERE id=?", (tid,)):
            db.execute("INSERT OR REPLACE INTO tour_zsrc(tour_id,zsrc) VALUES(?,?)", (tid, src))
            n += 1
    return n


def _auto(devs, kind, day, zsrc=""):
    cand = [d for d in devs if d["kind"] == kind]
    if not cand:
        return None
    if zsrc:                                              # gleiche Art UND gleiche Zepp-Kennung: bevorzugen
        pref = [d for d in cand if (d.get("zsrc") or "") == zsrc]
        if pref:
            fit = [d for d in pref if (not d["since"] or day >= d["since"]) and (not d["until"] or day <= d["until"])]
            if fit:
                return max(fit, key=lambda d: (d["since"] or "", d["id"]))
            if len(pref) == 1:
                return pref[0]
    fit = [d for d in cand if (not d["since"] or day >= d["since"]) and (not d["until"] or day <= d["until"])]
    if fit:
        return max(fit, key=lambda d: (d["since"] or "", d["id"]))
    return cand[0] if len(cand) == 1 else None


def assignments():
    """{tour_id: (device_dict_oder_None, manuell)} für alle Touren."""
    devs = db.query("SELECT * FROM devices")
    byid = {d["id"]: d for d in devs}
    manual = {r["tour_id"]: r["device_id"] for r in db.query("SELECT tour_id, device_id FROM tour_device")}
    srcs = {r["tour_id"]: r["src"] for r in db.query("SELECT tour_id, src FROM tour_source")}
    zs = {r["tour_id"]: r["zsrc"] for r in db.query("SELECT tour_id, zsrc FROM tour_zsrc")}
    out = {}
    for t in db.query("SELECT id, start_ts FROM tours"):
        tid = t["id"]
        if tid in manual and manual[tid] in byid:
            out[tid] = (byid[manual[tid]], True)
        elif devs:
            out[tid] = (_auto(devs, tour_kind(tid, srcs.get(tid, "")), _day(t["start_ts"]), zs.get(tid, "")), False)
        else:
            out[tid] = (None, False)
    return out


def device_of(tid):
    """Gerät einer Tour für die Oberfläche: {id,name,kind,active,manual} oder None."""
    t = db.one("SELECT id, start_ts FROM tours WHERE id=?", (str(tid),))
    if not t:
        return None
    devs = db.query("SELECT * FROM devices")
    man = db.one("SELECT device_id FROM tour_device WHERE tour_id=?", (str(tid),))
    d, manual = None, False
    if man:
        d = next((x for x in devs if x["id"] == man["device_id"]), None)
        manual = d is not None
    if d is None:
        z = db.one("SELECT zsrc FROM tour_zsrc WHERE tour_id=?", (str(tid),))
        d = _auto(devs, tour_kind(tid), _day(t["start_ts"]), z["zsrc"] if z else "")
    return {"id": d["id"], "name": d["name"], "kind": d["kind"], "model": d["model"] or "", "active": bool(d["active"]), "manual": manual,
            "photo": _photo_v(d["id"])} if d else None


def _clean(body, partial=False):
    out = {}
    if "name" in body or not partial:
        n = str(body.get("name") or "").strip()[:80]
        if not n:
            raise HTTPException(400, "Bitte einen Namen eingeben")
        out["name"] = n
    if "kind" in body or not partial:
        k = body.get("kind") or "other"
        if k not in KINDS:
            raise HTTPException(400, "Unbekannte Art des Geräts")
        out["kind"] = k
    for f in ("since", "until"):
        if f in body or not partial:
            v = str(body.get(f) or "").strip()
            if v and not _DATE.match(v):
                raise HTTPException(400, "Datum bitte als JJJJ-MM-TT")
            out[f] = v
    if "model" in body:
        out["model"] = str(body.get("model") or "").strip()[:80]
    if "note" in body:
        out["note"] = str(body.get("note") or "").strip()[:300]
    if "zsrc" in body:
        out["zsrc"] = str(body.get("zsrc") or "").strip()[:120]
    if "active" in body:
        out["active"] = 1 if body.get("active") in (True, 1, "1", "true") else 0
    if out.get("since") and out.get("until") and out["until"] < out["since"]:
        raise HTTPException(400, "„bis“ liegt vor „seit“")
    return out


def list_payload():
    devs = db.query("SELECT * FROM devices ORDER BY active DESC, kind, COALESCE(NULLIF(since,''),'0000'), name")
    cnt = {}
    for d, _m in assignments().values():
        if d:
            cnt[d["id"]] = cnt.get(d["id"], 0) + 1
    out = [dict(_row(d), n=cnt.get(d["id"], 0)) for d in devs]
    return {"devices": out, "kinds": [{"kind": k, "label": KIND_LABEL[k]} for k in KINDS]}


@router.get("/api/my-devices")
def api_my_devices():
    return list_payload()


@router.post("/api/devices")
def api_devices_add(body: dict):
    c = _clean(body)
    c.setdefault("model", "")
    c.setdefault("note", "")
    c.setdefault("active", 1)
    c.setdefault("zsrc", "")
    i = db.execute("INSERT INTO devices(name,kind,model,since,until,active,note,zsrc) VALUES(?,?,?,?,?,?,?,?)",
                   (c["name"], c["kind"], c["model"], c["since"], c["until"], c["active"], c["note"], c["zsrc"]))
    return {"id": i}


@router.patch("/api/devices/{did}")
def api_devices_patch(did: int, body: dict):
    d = db.one("SELECT * FROM devices WHERE id=?", (did,))
    if not d:
        raise HTTPException(404, "Gerät nicht gefunden")
    c = _clean(body, partial=True)
    merged = {k: d[k] for k in ("since", "until")}
    merged.update({k: c[k] for k in ("since", "until") if k in c})
    if merged["since"] and merged["until"] and merged["until"] < merged["since"]:
        raise HTTPException(400, "„bis“ liegt vor „seit“")
    if c:
        db.execute("UPDATE devices SET " + ",".join(f"{k}=?" for k in c) + " WHERE id=?", tuple(c.values()) + (did,))
    return {"ok": True}


@router.delete("/api/devices/{did}")
def api_devices_delete(did: int, move_to: int = 0):
    """Löschen nur ohne zugeordnete Touren; mit move_to werden die Touren vorher dem anderen Gerät fest zugeordnet."""
    if not db.one("SELECT 1 FROM devices WHERE id=?", (did,)):
        raise HTTPException(404, "Gerät nicht gefunden")
    mine = [tid for tid, (d, _m) in assignments().items() if d and d["id"] == did]
    if mine:
        if not move_to:
            raise HTTPException(409, f"Diesem Gerät sind noch {len(mine)} Touren zugeordnet. Bitte zuerst auf ein anderes Gerät umhängen.")
        if move_to == did or not db.one("SELECT 1 FROM devices WHERE id=?", (move_to,)):
            raise HTTPException(400, "Zielgerät ungültig")
        for tid in mine:
            db.execute("INSERT OR REPLACE INTO tour_device(tour_id,device_id) VALUES(?,?)", (tid, move_to))
    db.execute("DELETE FROM tour_device WHERE device_id=?", (did,))
    db.execute("DELETE FROM devices WHERE id=?", (did,))
    photo_path(did).unlink(missing_ok=True)
    return {"ok": True, "moved": len(mine)}


@router.post("/api/tours/{tour_id}/device")
def api_tour_device(tour_id: str, body: dict):
    """Gerät einer Tour festlegen (device_id) oder zur automatischen Zuordnung zurückkehren (device_id leer/0 oder auto=true)."""
    if not db.one("SELECT 1 FROM tours WHERE id=?", (tour_id,)):
        raise HTTPException(404, "Tour nicht gefunden")
    did = body.get("device_id")
    if body.get("auto") or not did:
        db.execute("DELETE FROM tour_device WHERE tour_id=?", (tour_id,))
    else:
        try:
            did = int(did)
        except (TypeError, ValueError):
            raise HTTPException(400, "Gerät ungültig")
        if not db.one("SELECT 1 FROM devices WHERE id=?", (did,)):
            raise HTTPException(404, "Gerät nicht gefunden")
        db.execute("INSERT OR REPLACE INTO tour_device(tour_id,device_id) VALUES(?,?)", (tour_id, did))
    return {"ok": True, "device": device_of(tour_id)}


@router.post("/api/devices/assign-range")
def api_assign_range(body: dict):
    """Sammelaktion: alle Touren von … bis … (Datum, einschließlich) fest diesem Gerät zuordnen."""
    try:
        did = int(body.get("device_id"))
    except (TypeError, ValueError):
        raise HTTPException(400, "Gerät fehlt")
    if not db.one("SELECT 1 FROM devices WHERE id=?", (did,)):
        raise HTTPException(404, "Gerät nicht gefunden")
    a, b = str(body.get("from") or ""), str(body.get("to") or "")
    for v in (a, b):
        if v and not _DATE.match(v):
            raise HTTPException(400, "Datum bitte als JJJJ-MM-TT")
    if not a and not b:
        raise HTTPException(400, "Bitte mindestens ein Datum angeben")
    n = 0
    for t in db.query("SELECT id, start_ts FROM tours WHERE start_ts IS NOT NULL"):
        d = _day(t["start_ts"])
        if (not a or d >= a) and (not b or d <= b):
            db.execute("INSERT OR REPLACE INTO tour_device(tour_id,device_id) VALUES(?,?)", (t["id"], did))
            n += 1
    return {"ok": True, "n": n}


@router.get("/api/devices/suggestions")
def api_suggestions():
    """Vorschläge aus vorhandenen Touren: Quellenarten, für die es noch kein Gerät gibt. Es wird nichts angelegt."""
    have = {d["kind"] for d in db.query("SELECT kind FROM devices")}
    cnt = {}
    srcs = {r["tour_id"]: r["src"] for r in db.query("SELECT tour_id, src FROM tour_source")}
    for t in db.query("SELECT id FROM tours"):
        k = tour_kind(t["id"], srcs.get(t["id"], ""))
        if k and k not in have:
            cnt[k] = cnt.get(k, 0) + 1
    names = {r["src"]: r["name"] for r in db.query("SELECT src, name FROM tour_source WHERE name!='' ORDER BY rowid")}
    return [{"kind": k, "label": KIND_LABEL[k], "n": n, "name": names.get(k) or KIND_LABEL[k]} for k, n in sorted(cnt.items(), key=lambda x: -x[1])]


# ---------------------------------------------------------------------------------------------- Foto
def _make_jpeg(raw):
    """Beliebiges Bild (JPEG, PNG, WebP, GIF, HEIC) -> JPEG, längste Seite höchstens PHOTO_SIDE. Wirft ValueError bei Nicht-Bildern."""
    from PIL import Image, ImageOps
    try:
        import pillow_heif  # optional
        pillow_heif.register_heif_opener()
    except Exception:  # noqa
        pass
    try:
        im = Image.open(io.BytesIO(raw))
        if im.format not in ("JPEG", "PNG", "WEBP", "GIF", "HEIF", "MPO"):
            raise ValueError("Format nicht unterstützt")
        if im.width * im.height > PHOTO_MAX_PIXELS:
            raise ValueError("Bild zu groß")
        im.load()
    except ValueError:
        raise
    except Exception as e:  # noqa
        raise ValueError(str(e) or "kein Bild")
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    im.thumbnail((PHOTO_SIDE, PHOTO_SIDE), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=86, optimize=True)
    return out.getvalue()


@router.post("/api/my-devices/{did}/photo")
async def api_photo_put(did: int, file: UploadFile = File(...)):
    if not db.one("SELECT 1 FROM devices WHERE id=?", (did,)):
        raise HTTPException(404, "Gerät nicht gefunden")
    raw = await file.read(PHOTO_MAX_BYTES + 1)
    if len(raw) > PHOTO_MAX_BYTES:
        raise HTTPException(413, f"Das Bild ist zu groß (höchstens {PHOTO_MAX_BYTES // 1048576} MB)")
    try:
        data = _make_jpeg(raw)
    except ValueError:
        raise HTTPException(400, "Das ist keine Bilddatei, die ich lesen kann (JPEG, PNG, WebP, GIF oder HEIC)")
    p = photo_path(did)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(p)
    return {"ok": True, "photo": _photo_v(did)}


@router.get("/api/my-devices/{did}/photo")
def api_photo_get(did: int):
    p = photo_path(did)
    if not p.is_file():
        raise HTTPException(404, "Kein Foto")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.delete("/api/my-devices/{did}/photo")
def api_photo_del(did: int):
    if not db.one("SELECT 1 FROM devices WHERE id=?", (did,)):
        raise HTTPException(404, "Gerät nicht gefunden")
    photo_path(did).unlink(missing_ok=True)
    return {"ok": True}


# ---------------------------------------------------------------------------------------------- Aus Zepp ermitteln
def probe_summaries(summaries):
    """Aus den Verlaufseinträgen der Zepp-Cloud je verschiedener Kennung („source“): Anzahl, erstes/letztes Datum, Sportarten.
    Der Modellname kommt aus der Zepp-Geräteliste (app/zepp_devices.py), sofern die Kennung dort vorkommt."""
    from . import gpxtools
    groups, keys, nokey = {}, set(), 0
    sample = None
    for s in summaries:
        if not isinstance(s, dict):
            continue
        if sample is None or len(s) > len(sample):
            sample = s
        try:
            tr = int(str(s.get("trackid")))
        except (TypeError, ValueError):
            continue
        src = str(s.get("source") or "").strip()
        if not src:
            nokey += 1
            continue
        g = groups.setdefault(src, {"zsrc": src, "n": 0, "ts": [], "sports": {}})
        g["n"] += 1
        g["ts"].append(tr)
        try:
            sp = gpxtools.ZEPP_SPORT.get(int(s.get("type", 0)), "type_%s" % s.get("type"))
        except (TypeError, ValueError):
            sp = "type_%s" % s.get("type")
        sp = gpxtools.ALIAS.get(sp, sp)
        g["sports"][sp] = g["sports"].get(sp, 0) + 1
    known = {d["zsrc"]: d for d in db.query("SELECT * FROM devices WHERE COALESCE(zsrc,'')!=''")}
    tours = {r["zsrc"]: r["n"] for r in db.query("SELECT zsrc, COUNT(*) n FROM tour_zsrc GROUP BY zsrc")}
    out = []
    for g in groups.values():
        a, b = _day(min(g["ts"])), _day(max(g["ts"]))
        k = known.get(g["zsrc"])
        out.append({"zsrc": g["zsrc"], "n": g["n"], "first": a, "last": b,
                    "sports": [{"sport": sp, "label": gpxtools.LABEL.get(sp, sp), "n": n} for sp, n in sorted(g["sports"].items(), key=lambda x: -x[1])],
                    "device": {"id": k["id"], "name": k["name"]} if k else None, "model": _zg(g["zsrc"])[0], "model_sure": _zg(g["zsrc"])[1]})
    out.sort(key=lambda x: (x["first"], x["zsrc"]))
    for x in out:
        x["overlaps"] = [y["zsrc"] for y in out if y is not x and y["first"] <= x["last"] and x["first"] <= y["last"]]
    return {"sources": out, "total": sum(x["n"] for x in out), "without_source": nokey,
            "sample_keys": sorted(sample.keys()) if sample else []}


def _overlap(tr, dis, rt, tours):
    """Zweite Chance für Touren, deren Zeiten/Strecke nicht exakt zum Zepp-Training passen (z. B. Komoot zählt Pausen mit, Start um Minuten
    verschoben): zeitliche Überlappung von mindestens 60 % der kürzeren Dauer UND ähnliche Strecke (±35 %). Beste Überlappung gewinnt."""
    if rt <= 0:
        return None
    best, bs = None, 0.0
    for t in tours:
        st, du = t["start_ts"], t["dur_s"]
        if not st or not du:
            continue
        ov = min(tr + rt, st + du) - max(tr, st)
        if ov <= 0 or ov < 0.6 * min(rt, du):
            continue
        d = t["dist_m"]
        if dis and d and not (0.65 <= d / dis <= 1.35):
            continue
        if ov > bs:
            best, bs = t, ov
    return best


def match_summaries(summaries, tours=None):
    """Zepp-Trainings den vorhandenen Touren zuordnen (gleiche ID z<Nr> oder gleicher Start/gleiche Strecke – auch Komoot- und Datei-Touren,
    die mit der Uhr aufgezeichnet wurden) und je Tour Art=zepp sowie die Zepp-Kennung merken. Danach findet die automatische Geräte-Zuordnung
    das richtige Gerät. Unberührt bleiben: manuell zugeordnete Touren und Touren mit einer anderen bekannten Art (Garmin, Suunto, Polar, Handy).
    Rückgabe: {matched, changed, skipped_manual, skipped_other, unmatched}."""
    from . import sync
    tours = tours if tours is not None else db.query("SELECT id,start_ts,dist_m,dur_s FROM tours")
    byid = {t["id"]: t for t in tours}
    tol = db.get_int("dup_tolerance_s", 300)
    manual = {r["tour_id"] for r in db.query("SELECT tour_id FROM tour_device")}
    srcs = {r["tour_id"]: (r["src"] or "") for r in db.query("SELECT tour_id, src FROM tour_source")}
    zs = {r["tour_id"]: r["zsrc"] for r in db.query("SELECT tour_id, zsrc FROM tour_zsrc")}
    res = {"matched": 0, "changed": 0, "skipped_manual": 0, "skipped_other": 0, "unmatched": 0}
    seen = set()
    for s in summaries:
        if not isinstance(s, dict):
            continue
        try:
            tr = int(s["trackid"])
            dis, rt = float(s.get("dis") or 0), int(float(s.get("run_time") or 0))
            t = byid.get(f"z{tr}") or sync.is_duplicate(tr, dis, rt, tours, tol) or _overlap(tr, dis, rt, tours)
        except (KeyError, TypeError, ValueError):
            continue
        if not t:
            res["unmatched"] += 1
            continue
        tid = t["id"]
        if tid in seen:
            continue
        seen.add(tid)
        res["matched"] += 1
        if tid in manual:
            res["skipped_manual"] += 1
            continue
        if srcs.get(tid, "") in KINDS and srcs[tid] != "zepp":
            res["skipped_other"] += 1
            continue
        z = str(s.get("source") or "").strip()[:120]
        ch = False
        if srcs.get(tid) != "zepp":
            db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,?,COALESCE((SELECT name FROM tour_source WHERE tour_id=?),''))", (tid, "zepp", tid))
            ch = True
        if z and zs.get(tid) != z:
            db.execute("INSERT OR REPLACE INTO tour_zsrc(tour_id,zsrc) VALUES(?,?)", (tid, z))
            ch = True
        res["changed"] += ch
    return res


def match_all(api=None):
    """Job: alle Touren mit passendem Zepp-Training als „mit der Uhr aufgezeichnet“ markieren und ihrem Gerät zuordnen."""
    from . import sync
    from .jobs import log
    api = api or sync._zepp_api()
    r = match_summaries(api.history())
    log(f"Touren den Uhren zuordnen: {r['matched']} Touren mit Zepp-Training gefunden, {r['changed']} neu zugeordnet"
        + (f", {r['skipped_manual']} von Hand zugeordnete unverändert" if r["skipped_manual"] else "")
        + (f", {r['skipped_other']} mit anderer Quelle unverändert" if r["skipped_other"] else ""))
    return r


def _zg(src):
    from . import zepp_devices
    return zepp_devices.guess_for(src)


@router.post("/api/devices/zepp-probe")
def api_zepp_probe():
    """Liest den ganzen Trainingsverlauf der Zepp-Cloud und gruppiert nach Quellenkennung. Legt nichts an; merkt nur je vorhandener Tour die Kennung."""
    from . import sync, zepp
    import requests
    try:
        api = sync._zepp_api()
        summ = api.history()
    except (zepp.ZeppError, requests.RequestException, RuntimeError) as e:
        raise HTTPException(422, f"Zepp ist nicht erreichbar oder die Zugangsdaten stimmen nicht: {e}")
    except Exception as e:  # noqa
        raise HTTPException(422, f"Zepp-Verlauf konnte nicht gelesen werden: {e}")
    res = probe_summaries(summ)
    try:
        note_zsrc(summ)
        res = probe_summaries(summ)
        res["match"] = match_summaries(summ)
    except Exception:  # noqa
        pass
    res["suggest_from_zepp"] = True
    return res


@router.post("/api/devices/zepp-apply")
def api_zepp_apply(body: dict):
    """Die im Dialog bestätigten Geräte anlegen. Je Eintrag: zsrc, name, model, since, until, attach_to (vorhandenes Gerät: nur Kennung ergänzen).
    Eine Kennung, die schon ein Gerät hat, wird übersprungen (nie doppelt)."""
    items = body.get("devices")
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "Nichts ausgewählt")
    created, attached, skipped = [], [], []
    for it in items:
        if not isinstance(it, dict):
            continue
        z = str(it.get("zsrc") or "").strip()[:120]
        if not z:
            raise HTTPException(400, "Kennung fehlt")
        if db.one("SELECT 1 FROM devices WHERE zsrc=?", (z,)):
            skipped.append(z)
            continue
        att = it.get("attach_to")
        if att:
            d = db.one("SELECT * FROM devices WHERE id=?", (int(att),))
            if not d:
                raise HTTPException(404, "Gerät nicht gefunden")
            db.execute("UPDATE devices SET zsrc=? WHERE id=?", (z, d["id"]))
            attached.append(d["id"])
            continue
        c = _clean({"name": it.get("name"), "kind": "zepp", "model": it.get("model"), "since": it.get("since"), "until": it.get("until"), "zsrc": z})
        i = db.execute("INSERT INTO devices(name,kind,model,since,until,active,note,zsrc) VALUES(?,?,?,?,?,1,'',?)",
                       (c["name"], "zepp", c.get("model", ""), c["since"], c["until"], z))
        created.append(i)
    return {"ok": True, "created": created, "attached": attached, "skipped": skipped}
