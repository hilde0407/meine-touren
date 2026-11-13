"""Meine Geräte: Aufnahmegeräte (Uhr, Handy …) selbst anlegen und benennen; jede Tour gehört zu einem Gerät.

Zuordnung: Eine ausdrückliche Wahl (Tabelle tour_device) hat immer Vorrang. Sonst gilt automatisch: die Art der Tour-Quelle (zepp, garmin, suunto,
polar, phone, other – siehe Tabelle tour_source bzw. metrics.py) wird mit der Art der Geräte verglichen; gibt es mehrere Geräte gleicher Art,
entscheidet das Tourdatum anhand „seit/bis“ (bei mehreren Treffern das Gerät mit dem späteren „seit“). Passt keines zum Datum, aber es gibt nur ein
Gerät dieser Art, bekommt dieses die Tour. Geräte werden nie ungefragt angelegt und nie gelöscht, solange Touren daran hängen."""
import re
from datetime import datetime

from fastapi import APIRouter, HTTPException

from . import db
from .gpxtools import TZ

router = APIRouter()
KINDS = ("zepp", "garmin", "suunto", "polar", "phone", "other")
KIND_LABEL = {"zepp": "Amazfit/Zepp", "garmin": "Garmin", "suunto": "Suunto", "polar": "Polar", "phone": "Handy-Aufzeichnung", "other": "Anderes Gerät"}
_DATE = re.compile(r"^\d{4}-\d\d-\d\d$")


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


def _row(d):
    return {"id": d["id"], "name": d["name"], "kind": d["kind"], "model": d["model"] or "", "since": d["since"] or "", "until": d["until"] or "",
            "active": bool(d["active"]), "note": d["note"] or ""}


def _auto(devs, kind, day):
    cand = [d for d in devs if d["kind"] == kind]
    if not cand:
        return None
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
    out = {}
    for t in db.query("SELECT id, start_ts FROM tours"):
        tid = t["id"]
        if tid in manual and manual[tid] in byid:
            out[tid] = (byid[manual[tid]], True)
        elif devs:
            out[tid] = (_auto(devs, tour_kind(tid, srcs.get(tid, "")), _day(t["start_ts"])), False)
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
        d = _auto(devs, tour_kind(tid), _day(t["start_ts"]))
    return {"id": d["id"], "name": d["name"], "kind": d["kind"], "active": bool(d["active"]), "manual": manual} if d else None


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
    i = db.execute("INSERT INTO devices(name,kind,model,since,until,active,note) VALUES(?,?,?,?,?,?,?)",
                   (c["name"], c["kind"], c["model"], c["since"], c["until"], c["active"], c["note"]))
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
