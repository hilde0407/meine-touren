"""Sammel-Korrektur der Höhen (3.13.0): „Alle auffälligen Höhen korrigieren …“ in der Genauigkeit einer Gerätekarte.

Ablauf (nichts davon läuft von selbst):
1. Vorschau (GET …/quality/fix-preview, nur Lesen): Touren des Geräts mit OFFENER Höhen-Auffälligkeit, je Tour Aufstieg laut Uhr, laut Gelände und der
   voraussichtliche neue Aufstieg je Methode. Es werden nur gespeicherte Werte der Auswertung gelesen – kein Netz, keine Änderung.
2. Start (POST …/quality/fix): Auswahl und Methode ('dem' Geländemodell = elev.fix, 'zepp' Uhr = elev.zepp_fix) werden geprüft und als Hintergrundjob
   „dev-quality-fix“ gestartet (steht auch in JOBS). Jede Tour wird EINZELN mit den vorhandenen Funktionen korrigiert (Original bleibt, einzeln wiederherstellbar);
   Strecke und Zeit werden nie angefasst. Je erfolgreich korrigierter Tour entsteht eine Zeile in quality_batch.
3. Rückgängig (POST …/quality/fix-undo): stellt NUR die Touren dieses einen Laufs wieder her, und nur, wenn deren Korrektur noch genau die des Laufs ist
   (hat der Nutzer sie inzwischen von Hand geändert oder zurückgenommen, bleibt sie unangetastet).

Obergrenzen je Lauf (Einstellungen, wie bei der Auswertung): quality_batch_max (Standard 100 Touren, 1–1000) und quality_tile_max (Standard 60 NEUE
Geländekacheln, 0–600; Kacheln aus dem Zwischenspeicher kosten nichts). Was darüber hinausgeht, bleibt offen – die Touren sind danach noch „auffällig“,
ein neuer Start der Sammel-Korrektur nimmt sie wieder auf (idempotent: schon korrigierte Touren werden übersprungen).
"""
import time
import uuid

from fastapi import APIRouter, HTTPException, Request

from . import ctx, db, devquality, elev, jobs
from .jobs import log, progress

router = APIRouter()

LABEL = "Auffällige Höhen korrigieren"
BATCH_DEFAULT, BATCH_MAX = 100, 1000
FAIL_STREAK = 5                      # so viele Netz-/Zepp-Fehler in Folge: sauber abbrechen (Rest bleibt offen, erneut starten)
_REQ = {}                            # Benutzer -> {"batch", "device", "method", "tours"} (nur im Speicher: ein abgebrochener Lauf wird einfach neu angefordert)


def _cap():
    return max(1, min(BATCH_MAX, db.get_int("quality_batch_max", BATCH_DEFAULT)))


def _zepp_ok():
    return bool(db.get("zepp_token") or (db.get("zepp_email") and db.get("zepp_password")))


def methods(dev):
    """Methoden, die für dieses Gerät zutreffen: Geländemodell immer; Uhr (Zepp) nur bei einer Zepp-Uhr mit eingerichtetem Zepp-Zugang."""
    out = [{"id": "dem", "label": "Aus dem Geländemodell berechnen"}]
    if dev["kind"] == "zepp" and _zepp_ok():
        out.append({"id": "zepp", "label": "Von der Uhr (Zepp) übernehmen"})
    return out


def open_height_tours(did):
    """[(Zeile der Auswertung, Höhen-Flag)] der Touren des Geräts, deren Höhe noch offen auffällig ist (wie die Liste „Auffällige Touren“)."""
    per, _tours, _asg = devquality._current_rows()
    fh, fg = devquality._fixed_sets()
    out = []
    for r in per.get(did, []):
        h = [f for f in devquality.open_flags(r, r["tour_id"] in fh, r["tour_id"] in fg) if f["kind"] == "height"]
        if h:
            out.append((r, h[0]))
    return out


def _device(did):
    d = db.one("SELECT * FROM devices WHERE id=?", (did,))
    if not d:
        raise HTTPException(404, "Gerät nicht gefunden")
    return d


def _owner_only(request):
    u = getattr(request.state, "user", None)
    if u and u.get("role") == "viewer":
        raise HTTPException(403, "Dieser Zugang darf nur ansehen")


@router.get("/api/devices/{did}/quality/fix-preview")
def api_preview(did: int, request: Request):
    """Nur Lesen: keine Änderung an Touren, kein Netzabruf."""
    _owner_only(request)
    d = _device(did)
    cur = {t["id"]: t for t in db.query("SELECT id,name,up_m,down_m FROM tours")}
    items = []
    for r, f in open_height_tours(did):
        t = cur.get(r["tour_id"])
        if not t:
            continue
        items.append({"id": r["tour_id"], "name": t["name"] or r["tour_id"], "day": r["day"], "up_now": t["up_m"], "up_dev": r["up_dev"], "up_dem": r["up_dem"],
                      "rough": r["h_src"] == "summary", "new": {"dem": r["up_dem"], "zepp": r["up_dev"]}})
    items.sort(key=lambda x: x["day"] or "", reverse=True)
    m = methods(d)
    return {"device": {"id": d["id"], "name": d["name"], "kind": d["kind"]}, "methods": m, "zepp_missing": d["kind"] == "zepp" and len(m) == 1,
            "cap": _cap(), "total": len(items), "tours": items}


@router.post("/api/devices/{did}/quality/fix")
def api_start(did: int, body: dict):
    """Auswahl prüfen und den Job starten. Nur Touren mit offener Höhen-Auffälligkeit dieses Geräts werden angenommen (alles andere wird ignoriert)."""
    d = _device(did)
    method = str(body.get("method") or "")
    if method not in {m["id"] for m in methods(d)}:
        raise HTTPException(400, "Diese Methode passt nicht zu diesem Gerät")
    want = [str(x) for x in (body.get("tours") or []) if isinstance(x, (str, int))]
    ok = {r["tour_id"] for r, _f in open_height_tours(did)}
    ids = [t for t in dict.fromkeys(want) if t in ok]
    if not ids:
        raise HTTPException(400, "Keine passende Tour ausgewählt")
    _REQ[ctx.uid() or ""] = {"batch": uuid.uuid4().hex[:12], "device": did, "method": method, "tours": ids}
    if not jobs.start(LABEL, run):
        _REQ.pop(ctx.uid() or "", None)
        raise HTTPException(409, "Es läuft bereits ein Job")
    return {"started": LABEL, "n": len(ids), "ignored": len(want) - len(ids), "cap": _cap(), "will_run": min(len(ids), _cap())}


@router.post("/api/devices/{did}/quality/fix-undo")
def api_undo(did: int, body: dict):
    """Nur dieser Sammel-Lauf: jede Tour des Laufs, deren Korrektur noch die des Laufs ist, wird wiederhergestellt."""
    _device(did)
    if jobs.get_state().get("running"):
        raise HTTPException(409, "Es läuft gerade ein Job – bitte warten")
    bid = str(body.get("batch") or "")
    devquality.ensure_batch_table()
    rows = db.query("SELECT * FROM quality_batch WHERE batch_id=? AND device_id=? AND state='done'", (bid, did))
    if not rows:
        raise HTTPException(404, "Dieser Lauf hat nichts mehr zum Rückgängigmachen")
    restored = changed = 0
    for r in rows:
        cur = db.one("SELECT * FROM elev_fix WHERE id=?", (r["tour_id"],))
        if cur and abs((cur["up_m"] or 0) - (r["new_up"] or 0)) <= 0.5 and (cur["src"] == "zepp") == (r["method"] == "zepp"):
            elev.restore(r["tour_id"])
            db.execute("UPDATE quality_batch SET state='undone' WHERE batch_id=? AND tour_id=?", (bid, r["tour_id"]))
            restored += 1
        else:                                          # inzwischen von Hand geändert oder zurückgenommen: nicht anfassen
            db.execute("UPDATE quality_batch SET state='gone' WHERE batch_id=? AND tour_id=?", (bid, r["tour_id"]))
            changed += 1
    log(f"Sammel-Korrektur rückgängig: {restored} Touren wiederhergestellt, {changed} inzwischen anders geändert (unberührt)")
    return {"restored": restored, "changed": changed}


class _HistApi:
    """Zepp-Verlauf nur EINMAL je Lauf laden (elev.zepp_fix fragt ihn sonst bei jeder Tour neu ab)."""

    def __init__(self, api):
        self.api, self._h = api, None

    def history(self):
        if self._h is None:
            self._h = self.api.history()
        return self._h

    def detail(self, s):
        return self.api.detail(s)


def run(api=None, tile_max=None, cap=None):
    """Job: die angeforderten Touren einzeln korrigieren. Rückgabe: Zähler. Ohne Anforderung (z. B. /api/jobs/dev-quality-fix von Hand) passiert nichts."""
    req = _REQ.pop(ctx.uid() or "", None)
    if not req:
        log("Sammel-Korrektur: Es liegt keine Anforderung vor (bitte in der Gerätekarte unter „Genauigkeit“ starten) – nichts geändert")
        return {"done": 0}
    devquality.ensure_batch_table()
    cap = cap if cap is not None else _cap()
    budget = {"tiles": tile_max if tile_max is not None else devquality._cfg("quality_tile_max", 60, 0, 600)}
    method, did, bid, ids = req["method"], req["device"], req["batch"], req["tours"]
    todo, later = ids[:cap], max(0, len(ids) - cap)
    log(f"Sammel-Korrektur: {len(ids)} Touren angefordert, Methode {'Geländemodell' if method == 'dem' else 'Uhr (Zepp)'}, in diesem Lauf höchstens {cap}")
    capi = None
    if method == "zepp":
        try:
            from . import sync
            capi = _HistApi(api if api is not None else sync._zepp_api())
        except Exception as e:  # noqa
            log(f"Sammel-Korrektur: Zepp nicht erreichbar ({type(e).__name__}) – nichts geändert, bitte später erneut starten")
            return {"done": 0, "aborted": True}
    tile = devquality._tile_factory(budget)
    n = ok = skipped = failed = streak = 0
    up0 = up1 = 0.0
    aborted, after = False, 0
    for i, tid in enumerate(todo, 1):
        progress(f"Höhe {i - 1}/{len(todo)} korrigiert", i - 1, len(todo))
        t = db.one("SELECT id,up_m FROM tours WHERE id=?", (tid,))
        if not t or db.one("SELECT 1 x FROM elev_fix WHERE id=?", (tid,)):
            skipped += 1                                  # gelöscht oder inzwischen (von Hand) korrigiert: nicht noch einmal anfassen
            continue
        n += 1
        try:
            r = elev.fix(tid, tile=tile) if method == "dem" else elev.zepp_fix(tid, api=capi)
        except devquality.NoDem:
            skipped += 1
            log(f"  {tid}: übersprungen – Geländekacheln fehlen (Obergrenze {budget['tiles'] if tile_max is None else tile_max} neue Kacheln je Lauf erreicht)")
            continue
        except Exception as e:  # noqa
            failed += 1
            streak += 1
            log(f"  {tid}: nicht korrigiert ({e if isinstance(e, (elev.ZeppFixError, RuntimeError, KeyError)) else type(e).__name__})")
            if streak >= FAIL_STREAK:
                aborted, after = True, len(todo) - i
                log(f"Sammel-Korrektur: {FAIL_STREAK} Fehler in Folge – sauber abgebrochen, schon Korrigiertes bleibt (einzeln wiederherstellbar). Später erneut starten.")
                break
            continue
        streak = 0
        ok += 1
        up0 += r["orig_up"] or 0
        up1 += r["up_m"] or 0
        db.execute("INSERT OR REPLACE INTO quality_batch(batch_id,tour_id,device_id,method,ts,orig_up,orig_down,new_up,new_down,state) VALUES(?,?,?,?,?,?,?,?,?,'done')",
                   (bid, tid, did, method, int(time.time()), r["orig_up"], r["orig_down"], r["up_m"], r["down_m"]))
        log(f"  Korrigiert: {tid}: Aufstieg {round(r['orig_up'] or 0)} m → {round(r['up_m'])} m")
        if method == "zepp":
            time.sleep(0.2)
    progress(f"Höhe {ok} von {len(todo)} korrigiert", len(todo) - after, len(todo))
    log(f"Korrigiert: {ok} Touren, Aufstieg zusammen {round(up0)} m → {round(up1)} m ({round(up1 - up0):+d} m)"
        + (f"; {skipped} übersprungen" if skipped else "") + (f"; {failed} nicht möglich" if failed else "")
        + (f"; {later} weitere folgen beim nächsten Start (Obergrenze {cap} je Lauf)" if later else "")
        + (f"; {after} nach dem Abbruch offen" if after else ""))
    return {"done": ok, "skipped": skipped, "failed": failed, "later": later, "aborted": aborted, "batch": bid}
