"""Pipeline: Zepp-Import -> GPX-Dateien -> Doppelten-Prüfung -> Komoot-Upload."""
import time
from datetime import datetime, timezone
from pathlib import Path

from . import elev, config, db, gpxtools, jobs, komoot as komoot_mod, photos, portals, routes, tracks, zepp
from .jobs import log


_kc = {"key": None, "client": None}


def _komoot(fresh=False):
    em, pw = db.get("komoot_email"), db.get("komoot_password")
    if not em or not pw:
        raise RuntimeError("Komoot-Zugangsdaten fehlen (Einstellungen)")
    if fresh or _kc["key"] != (em, pw) or _kc["client"] is None:
        k = komoot_mod.Komoot(em, pw)
        k.login()
        _kc.update(key=(em, pw), client=k)
    return _kc["client"]


def refresh_tours(k=None):
    k = k or _komoot()
    tours = k.tours()
    tours = _link_local(tours)
    old = {r["id"]: (r["dist_m"], r["dur_s"], r["up_m"]) for r in db.query("SELECT id,dist_m,dur_s,up_m FROM tours")}
    changed = [t["id"] for t in tours if t["id"] in old and (
        abs((old[t["id"]][0] or 0) - (t["dist_m"] or 0)) > 5 or abs((old[t["id"]][1] or 0) - (t["dur_s"] or 0)) > 5)]
    for tid in changed:  # bei Komoot geänderte Strecke: Zwischenspeicher verwerfen, wird neu geladen
        elev.drop(tid)
        for p in (routes.path_full(tid), routes.path_small(tid)):
            p.unlink(missing_ok=True)
    if changed:
        log(f"Komoot: {len(changed)} Tour(en) mit geänderter Strecke – Routen werden neu geladen")
    with db.cur() as c:
        c.execute("DELETE FROM tours WHERE COALESCE(source,'komoot')='komoot'")   # lokale Touren bleiben unangetastet
        c.executemany(
            "INSERT OR REPLACE INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) "
            "VALUES(:id,:name,:sport,:start_ts,:end_ts,:dist_m,:dur_s,:up_m,:down_m,:lat,:lng,:status,'komoot')", tours)
        # lokale Umbenennungen erhalten (solange Komoot den Namen nicht selbst geändert hat)
        for o in c.execute("SELECT id,name,orig FROM tour_names").fetchall():
            cur_name = next((t["name"] for t in tours if str(t["id"]) == o["id"]), None)
            if cur_name is None or cur_name == o["name"] or cur_name != o["orig"]:
                c.execute("DELETE FROM tour_names WHERE id=?", (o["id"],))
            else:
                c.execute("UPDATE tours SET name=? WHERE id=?", (o["name"], o["id"]))
    elev.reapply(tours)
    log(f"Komoot: {len(tours)} abgeschlossene Touren geladen")
    return tours


def _link_local(tours):
    """Komoot-Touren, die schon als lokale Tour vorliegen (selbst hochgeladen oder gleicher Start), nicht doppelt führen."""
    local = db.query("SELECT id,start_ts FROM tours WHERE source='local'")
    if not local:
        return tours
    remote = {r["remote_id"]: r["tour_id"] for r in db.query("SELECT tour_id,remote_id FROM tour_uploads WHERE portal='komoot' AND remote_id!=''")}
    tol = db.get_int("dup_tolerance_s", 300)
    out = []
    for t in tours:
        tid = str(t["id"])
        if tid in remote and db.one("SELECT 1 x FROM tours WHERE id=? AND source='local'", (remote[tid],)):
            continue
        hit = next((l for l in local if l["start_ts"] and t["start_ts"] and abs(l["start_ts"] - t["start_ts"]) <= tol), None)
        if hit:
            portals.record(hit["id"], "komoot", "linked", tid, "Bei Komoot gefunden")
            continue
        out.append(t)
    return out


def sync_tour(tour_id):
    """Eine Tour mit Komoot abgleichen: Daten + GPS-Track neu laden."""
    tid = str(tour_id)
    row = db.one("SELECT source FROM tours WHERE id=?", (tid,))
    if not row:
        raise KeyError(tid)
    if row["source"] == "local":
        raise RuntimeError("Lokale Tour – es gibt nichts abzugleichen")
    k = _komoot()
    t = k.tour(tid)
    items = k.coordinates(tid)
    if not items:
        raise RuntimeError("Komoot lieferte keine Streckenpunkte")
    elev.drop(tid)                       # Komoot-Abgleich ersetzt eine lokale Höhenkorrektur
    with db.cur() as c:
        o = c.execute("SELECT name,orig FROM tour_names WHERE id=?", (tid,)).fetchone()
        if o and t["name"] == o["orig"]:
            t["name"] = o["name"]          # lokale Umbenennung bleibt
        else:
            c.execute("DELETE FROM tour_names WHERE id=?", (tid,))
        c.execute("UPDATE tours SET name=:name,sport=:sport,start_ts=:start_ts,end_ts=:end_ts,dist_m=:dist_m,dur_s=:dur_s,"
                  "up_m=:up_m,down_m=:down_m,lat=:lat,lng=:lng WHERE id=:id", t)
    routes.store(tid, items)
    try:
        photos.assign_all()
    except Exception:  # noqa
        pass
    return db.one("SELECT * FROM tours WHERE id=?", (tid,))


def rename_tour(tour_id, name, komoot=False):
    """Benennt lokal um; optional auch bei Komoot. Gibt (ok_komoot, meldung) zurück."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Name darf nicht leer sein")
    row = db.query("SELECT name,source FROM tours WHERE id=?", (str(tour_id),))
    if not row:
        raise KeyError(tour_id)
    msg = ""
    if row[0]["source"] == "local":
        with db.cur() as c:
            c.execute("UPDATE tours SET name=? WHERE id=?", (name, str(tour_id)))
        return False, ""
    if komoot:
        try:
            _komoot().rename(tour_id, name)
        except Exception as e:  # Komoot-Fehler: lokal trotzdem umbenennen
            komoot, msg = False, str(e)
    with db.cur() as c:
        c.execute("UPDATE tours SET name=? WHERE id=?", (name, str(tour_id)))
        if komoot:
            c.execute("DELETE FROM tour_names WHERE id=?", (str(tour_id),))
        else:
            prev = c.execute("SELECT orig FROM tour_names WHERE id=?", (str(tour_id),)).fetchone()
            orig = prev["orig"] if prev else row[0]["name"]
            c.execute("INSERT OR REPLACE INTO tour_names(id,name,orig) VALUES(?,?,?)", (str(tour_id), name, orig))
    return komoot, msg


def is_duplicate(start_ts, dist_m, dur_s, tours, tol=300):
    """Gleicher Start (±tol s) ODER praktisch gleiche Distanz+Dauer (±1 %/±60 s)."""
    for t in tours:
        if t["start_ts"] and abs(t["start_ts"] - start_ts) <= tol:
            return t
        if (dist_m and t["dist_m"] and abs(t["dist_m"] - dist_m) <= 0.01 * dist_m
                and dur_s and t["dur_s"] and abs(t["dur_s"] - dur_s) <= 60
                and t["start_ts"] and abs(t["start_ts"] - start_ts) <= 3 * 3600):
            return t
        if (dist_m and t["dist_m"] and abs(t["dist_m"] - dist_m) <= 0.01 * dist_m and dur_s and t["dur_s"] and abs(t["dur_s"] - dur_s) <= 60
                and t["start_ts"] and any(abs(abs(t["start_ts"] - start_ts) - h * 3600) <= tol for h in (1, 2))):
            return t                                     # gleiche Aktivität, Startzeit um ganze Stunden verschoben (Zeitzone/Sommerzeit)
    return None


def gpx_path_for(start_ts):
    d = datetime.fromtimestamp(start_ts, tz=gpxtools.TZ)
    return config.EXPORT_DIR / f"{d:%Y}" / f"{d:%m}" / f"Workout--{d:%Y-%m-%d--%H-%M-%S}.gpx"


def export_zepp(limit=None):
    token = db.get("zepp_token")
    em, pw = db.get("zepp_email"), db.get("zepp_password")
    if em and pw:
        log("Zepp: Anmeldung mit E-Mail/Passwort …")
        try:
            token, uid = zepp.login(em, pw)
            log(f"Zepp: angemeldet (Nutzer {uid})")
        except Exception as e:
            if not token:
                raise
            log(f"Zepp-Login fehlgeschlagen ({e}); versuche gespeichertes Token")
    if not token:
        raise RuntimeError("Zepp-Zugangsdaten fehlen (Einstellungen)")
    api = zepp.ZeppApi(token, db.get("zepp_host"))
    summaries = api.history()
    log(f"Zepp: {len(summaries)} Trainings im Verlauf (Server {api.host})")
    tours_k = db.query("SELECT start_ts,dist_m,dur_s FROM tours")
    tol = db.get_int("dup_tolerance_s", 300)
    known = {r["trackid"] for r in db.query("SELECT trackid FROM workouts")}
    new = [s for s in summaries if int(s["trackid"]) not in known]
    if limit:
        new = new[:limit]
    log(f"Zepp: {len(new)} neue Trainings")
    n_gps = 0
    for i, s in enumerate(new, 1):
        tid = int(s["trackid"])
        jobs.progress(f"Export {i}/{len(new)}")
        sport = gpxtools.ZEPP_SPORT.get(int(s.get("type", 0)), "type_%s" % s.get("type"))
        sport = gpxtools.ALIAS.get(sport, sport)
        if sport not in gpxtools.LABEL:
            sport = db.get("default_sport") or "hike"
        dist, dur = float(s.get("dis") or 0), int(float(s.get("run_time") or 0))
        end_ts = int(s.get("end_time") or tid + dur)
        try:
            pts = zepp.decode_points(s, api.detail(s))
        except Exception as e:
            log(f"  {tid}: Detail-Fehler {e}")
            continue
        if not pts:
            db.execute("INSERT OR REPLACE INTO workouts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (tid, tid, end_ts, s.get("type"), sport, dist, dur, None, "no_gps", None, "ohne GPS", int(time.time())))
            continue
        path = gpx_path_for(tid)
        path.parent.mkdir(parents=True, exist_ok=True)
        gpx = zepp.points_to_gpx(s, pts, sport)
        path.write_text(gpx, encoding="utf-8")
        n_gps += 1
        db.execute("INSERT OR REPLACE INTO workouts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (tid, tid, end_ts, s.get("type"), sport, dist, dur, str(path),
                    "in_komoot" if is_duplicate(tid, dist, dur, tours_k, tol) else "new", None, "", int(time.time())))
        time.sleep(0.2)
    if db.get("zepp_auto_adopt") == "1":          # auch früher exportierte, noch nicht übernommene Trainings
        n_ad = 0
        for r in db.query("SELECT trackid FROM workouts WHERE status='new' AND gpx_path IS NOT NULL"):
            try:
                adopt_workout(r["trackid"]); n_ad += 1
            except Exception as e:  # noqa
                log(f"  {r['trackid']}: lokale Übernahme fehlgeschlagen: {e}")
        photos.assign_all()
        log(f"Zepp: {n_ad} Training(s) als lokale Tour übernommen")
    log(f"Zepp: {n_gps} GPS-Dateien geschrieben nach {config.EXPORT_DIR} (es wird nichts hochgeladen)")


def adopt_workout(trackid):
    """Zepp-Training als lokale Tour übernehmen (kein Upload). Gibt die Tour-ID zurück."""
    r = db.one("SELECT * FROM workouts WHERE trackid=?", (int(trackid),))
    if not r or not r["gpx_path"] or not Path(r["gpx_path"]).exists():
        raise RuntimeError("Keine GPX-Datei für dieses Training")
    p = Path(r["gpx_path"])
    tid = f"z{int(trackid)}"
    if not db.one("SELECT 1 x FROM tours WHERE id=?", (tid,)):
        try:                                             # dieselbe Aktivität schon vorhanden (z. B. doppelt von der Uhr gemeldet)?
            c = gpxtools.convert(p.read_text(encoding="utf-8"), p.name, db.get("default_sport") or "hike")
            dup = is_duplicate(c["start_ts"], c["dist_m"], c["end_ts"] - c["start_ts"], db.query("SELECT id,start_ts,dist_m,dur_s FROM tours"), db.get_int("dup_tolerance_s", 300))
        except Exception:  # noqa
            dup = None
        if dup:
            db.execute("UPDATE workouts SET status=?, komoot_id=?, updated=? WHERE trackid=? AND status IN ('new','local')", ("dup", dup["id"], int(time.time()), int(trackid)))
            log(f"  Training {trackid}: schon vorhanden als Tour {dup['id']} – nicht doppelt übernommen")
            return dup["id"]
        tracks.adopt(p.read_text(encoding="utf-8"), p.name, ident=tid)
        photos.assign_all()
    db.execute("UPDATE workouts SET status=?, komoot_id=?, updated=? WHERE trackid=? AND status IN ('new','local')",
               ("local", tid, int(time.time()), int(trackid)))
    return tid


def import_items(items, portals_=(), dry_run=False, k=None):
    """items: Liste (label, gpx_oder_tcx_text, dateiname). Jede neue Tour wird zuerst lokal gespeichert,
    danach – nur auf ausdrücklichen Wunsch – zu den gewählten Portalen gesendet. Gibt [(label, status, tour_id)] zurück."""
    if "komoot" in portals_:
        refresh_tours(k or _komoot())          # aktueller Stand bei Komoot für die Doppelten-Prüfung
    tours = db.query("SELECT id,start_ts,dist_m,dur_s,source FROM tours")
    tol = db.get_int("dup_tolerance_s", 300)
    pause = float(db.get("upload_pause_s") or 2)
    results = []
    for i, (label, text, fname) in enumerate(items, 1):
        jobs.progress(f"Import {i}/{len(items)}")
        try:
            c = gpxtools.convert(text, fname, db.get("default_sport") or "hike")
        except gpxtools.NoGps:
            results.append((label, "no_gps", "")); log(f"  {label}: keine GPS-Punkte"); continue
        dup = is_duplicate(c["start_ts"], c["dist_m"], c["end_ts"] - c["start_ts"], tours, tol)
        if dup:
            tid, state = dup["id"], "skipped_dup"
            log(f"  {c['name']}: schon vorhanden (Tour {tid})")
        else:
            if dry_run:
                results.append((label, "would_upload", "")); log(f"  {c['name']}: wäre neu ({c['dist_m']/1000:.1f} km)"); continue
            t, _ = tracks.adopt(text, fname)
            tid, state = t["id"], "imported"
            tours.append({"id": tid, "start_ts": c["start_ts"], "dist_m": c["dist_m"], "dur_s": c["end_ts"] - c["start_ts"], "source": "local"})
            log(f"  {c['name']}: lokal gespeichert")
        for p in portals_:
            try:
                st, rid, msg = portals.upload_tour(tid, p, gpx=c["gpx"], dry_run=dry_run)
                if st == "uploaded":
                    state = "uploaded"
                time.sleep(pause)
            except Exception as e:  # noqa
                log(f"  {c['name']}: {portals.PORTALS.get(p, p)}: {e}")
                state = "error"
        results.append((label, state, tid))
    photos.assign_all()
    return results


def import_gpx_texts(items, dry_run=False, k=None):          # Kompatibilität (Tests, alte Aufrufe)
    return import_items(items, ("komoot",), dry_run, k)


def upload_selected(trackids, dry_run=False, portals_=("komoot",), local_only=False):
    """Nur die ausdrücklich gewählten Zepp-Trainings: lokal übernehmen und (optional) zu Portalen senden."""
    items, ids = [], []
    for t in trackids:
        r = db.one("SELECT * FROM workouts WHERE trackid=?", (int(t),))
        if r and r["gpx_path"] and Path(r["gpx_path"]).exists():
            p = Path(r["gpx_path"])
            items.append((r["trackid"], p.read_text(encoding="utf-8"), p.name)); ids.append(int(t))
    log(f"Import: {len(items)} ausgewählte Dateien → lokal" + ("" if local_only else " + " + ", ".join(portals.PORTALS.get(p, p) for p in portals_)))
    res = import_items(items, () if local_only else tuple(portals_), dry_run)
    if not dry_run:
        for tid, st, tour in res:
            src = (db.one("SELECT source FROM tours WHERE id=?", (tour,)) or {}).get("source") if tour else None
            if st == "uploaded":
                new = "in_komoot" if "komoot" in portals_ and not local_only else "local"
            elif st == "skipped_dup":
                new = "in_komoot" if src == "komoot" or ("komoot" in portals_ and not local_only) else "local"
            elif st == "imported":
                new = "local"
            else:
                new = st
            db.execute("UPDATE workouts SET status=?, komoot_id=?, updated=? WHERE trackid=?", (new, tour, int(time.time()), tid))
    log("Import fertig: " + ", ".join(f"{s}={sum(1 for _, x, _ in res if x == s)}" for s in sorted({x for _, x, _ in res})))
    return res


def check_zepp():
    """Prüft das gespeicherte Zepp-Token und merkt sich das Ergebnis (für Hinweis in der Oberfläche)."""
    token = db.get("zepp_token")
    if not token:
        db.put("zepp_state", "none"); return "none"
    try:
        zepp.ZeppApi(token, db.get("zepp_host")).ping()
        state = "ok"
    except Exception as e:  # noqa
        state = "fail:" + str(e)[:160]
    db.put("zepp_state", state); db.put("zepp_checked", str(int(time.time())))
    return state


def import_inbox():
    """Fotos aus dem Eingangsordner (und, falls vorhanden, dem Fotoquellordner) komprimiert übernehmen und zuordnen."""
    from . import photos
    n = 0
    for root in (config.INBOX_DIR, config.PHOTOS_DIR):
        try:
            if root.exists() and any(root.iterdir()):
                n += photos.import_from(root)
        except Exception as e:  # noqa
            log(f"Fotoeingang {root}: {e}")
    photos.scan()
    return n


def inbox_newest():
    """Neueste Änderungszeit im Eingangsordner (0 = leer/nicht vorhanden)."""
    import os
    m = 0
    root = config.INBOX_DIR
    if root.exists():
        for dp, dn, fn in os.walk(root):
            for f in fn:
                try:
                    m = max(m, int(os.stat(os.path.join(dp, f)).st_mtime))
                except OSError:
                    pass
    return m


def refresh_all(with_routes=True, with_photos=True):
    """Tägliche Aktualisierung: Komoot-Touren, Routen, Fotos. Lädt NIE etwas zu Komoot hoch."""
    k = _komoot()
    refresh_tours(k)
    from . import photos, routes
    if with_routes:
        routes.fetch_missing(k)
    if with_photos:
        import_inbox()
    else:
        photos.assign_all()
    try:
        from . import extras
        extras.geo_fill()
        from . import more
        more.peaks_fill(limit=100)
    except Exception as e:  # noqa
        log(f"Regionen: {e}")
    check_zepp()
