"""Anmeldung, Benutzerverwaltung, Freigaben und Zugriff auf geteilte Fotos."""
import os
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse

from . import auth, config, ctx, db, more2, photos

router = APIRouter()


def _user(request: Request):
    u = getattr(request.state, "user", None)
    if not u:
        raise HTTPException(401, "Bitte anmelden")
    return u


def _admin(request: Request):
    u = _user(request)
    if u["role"] != "admin":
        raise HTTPException(403, "Nur für Administratoren")
    return u


def _ip(request: Request):
    return request.client.host if request.client else ""


def _cookie(resp: Response, tok, request: Request, clear=False):
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    if clear:
        resp.delete_cookie(auth.COOKIE, path="/")
    else:
        resp.set_cookie(auth.COOKIE, tok, max_age=auth.SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=secure, path="/")


@router.get("/api/me")
def api_me(request: Request):
    u = getattr(request.state, "user", None)
    exist = auth.users_exist()
    return {"users_enabled": exist, "needs_setup": not exist, "user": u, "legacy_protected": bool(config.UI_PASSWORD) and not exist}


@router.post("/api/setup")
async def api_setup(request: Request, response: Response):
    if auth.users_exist():
        raise HTTPException(403, "Es gibt schon Benutzer")
    d = await request.json()
    try:
        uid = auth.create_user(d.get("name"), d.get("password"), "admin")
    except ValueError as e:
        raise HTTPException(400, str(e))
    adopted = auth.adopt_legacy(uid)
    tok, _ = auth.login(d["name"], d["password"], _ip(request))
    _cookie(response, tok, request)
    return {"ok": True, "uid": uid, "adopted": adopted}


@router.post("/api/login")
async def api_login(request: Request, response: Response):
    d = await request.json()
    try:
        tok, u = auth.login(str(d.get("name", "")), str(d.get("password", "")), _ip(request))
    except PermissionError as e:
        raise HTTPException(429 if "Zu viele" in str(e) else 401, str(e))
    _cookie(response, tok, request)
    return {"ok": True, "user": {"uid": u["uid"], "name": u["name"], "role": u["role"]}}


@router.post("/api/logout")
def api_logout(request: Request, response: Response):
    auth.logout(request.cookies.get(auth.COOKIE))
    _cookie(response, None, request, clear=True)
    return {"ok": True}


@router.post("/api/me/password")
async def api_my_password(request: Request):
    u = _user(request); d = await request.json()
    row = auth.q1("SELECT pw FROM users WHERE uid=?", (u["uid"],))
    if not row or not auth.check_pw(str(d.get("old", "")), row["pw"]):
        raise HTTPException(400, "Das alte Passwort stimmt nicht")
    try:
        auth.set_password(u["uid"], str(d.get("new", "")))
    except ValueError as e:
        raise HTTPException(400, str(e))
    tok, _ = auth.login(u["name"], str(d["new"]), _ip(request))
    resp = Response(content='{"ok":true}', media_type="application/json"); _cookie(resp, tok, request)
    return resp


# ---------- Verwaltung (Admin) ----------
@router.get("/api/users")
def api_users(request: Request):
    me = _user(request)
    if me["role"] == "admin":
        return [{**u, "me": u["uid"] == me["uid"]} for u in auth.list_users()]
    return [{"uid": u["uid"], "name": u["name"]} for u in auth.list_users() if u["active"] and u["uid"] != me["uid"]]


@router.post("/api/users")
async def api_user_add(request: Request):
    _admin(request); d = await request.json()
    try:
        uid = auth.create_user(d.get("name"), d.get("password"), d.get("role", "user"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"uid": uid}


@router.patch("/api/users/{uid}")
async def api_user_edit(uid: str, request: Request):
    me = _admin(request); d = await request.json()
    if not auth.q1("SELECT 1 x FROM users WHERE uid=?", (uid,)):
        raise HTTPException(404)
    if "password" in d and d["password"]:
        try:
            auth.set_password(uid, d["password"])
        except ValueError as e:
            raise HTTPException(400, str(e))
    admins = auth.q1("SELECT COUNT(*) n FROM users WHERE role='admin' AND active=1")["n"]
    target = auth.q1("SELECT role,active FROM users WHERE uid=?", (uid,))
    if "role" in d and d["role"] in ("admin", "user"):
        if target["role"] == "admin" and d["role"] != "admin" and admins <= 1:
            raise HTTPException(400, "Es muss mindestens einen Administrator geben")
        auth.q("UPDATE users SET role=? WHERE uid=?", (d["role"], uid))
    if "active" in d:
        if not d["active"] and uid == me["uid"]:
            raise HTTPException(400, "Du kannst dich nicht selbst sperren")
        if not d["active"] and target["role"] == "admin" and admins <= 1:
            raise HTTPException(400, "Es muss mindestens einen Administrator geben")
        auth.q("UPDATE users SET active=? WHERE uid=?", (1 if d["active"] else 0, uid))
        if not d["active"]:
            auth.q("DELETE FROM sessions WHERE uid=?", (uid,))
    return {"ok": True}


@router.delete("/api/users/{uid}")
def api_user_del(uid: str, request: Request, data: int = 0):
    me = _admin(request)
    if uid == me["uid"]:
        raise HTTPException(400, "Du kannst dich nicht selbst löschen")
    t = auth.q1("SELECT role FROM users WHERE uid=?", (uid,))
    if not t:
        raise HTTPException(404)
    if t["role"] == "admin" and auth.q1("SELECT COUNT(*) n FROM users WHERE role='admin' AND active=1")["n"] <= 1:
        raise HTTPException(400, "Es muss mindestens einen Administrator geben")
    auth.delete_user(uid, bool(data))
    return {"ok": True}


# ---------- Freigaben ----------
@router.get("/api/grants")
def api_grants(request: Request):
    u = _user(request)
    names = {x["uid"]: x["name"] for x in auth.list_users()}
    mine = auth.q("SELECT id,grantee,scope,ref,ts FROM grants WHERE owner=? ORDER BY ts DESC", (u["uid"],))
    tn = {t["id"]: t["name"] for t in db.query("SELECT id,name FROM tours")}
    for g in mine:
        g["grantee_name"] = "Alle Benutzer" if g["grantee"] == "*" else names.get(g["grantee"], g["grantee"])
        g["ref_name"] = tn.get(g["ref"]) if g["scope"] == "tour" else None
    got = [{**g, "owner_name": names.get(g["owner"], g["owner"])} for g in auth.grants_to(u["uid"])]
    return {"mine": mine, "received": got}


@router.post("/api/grants")
async def api_grant_add(request: Request):
    u = _user(request); d = await request.json()
    grantee, scope, ref = str(d.get("grantee", "")), d.get("scope", "all"), str(d.get("ref") or "")
    if scope not in ("all", "tour") or (scope == "tour" and not db.one("SELECT 1 x FROM tours WHERE id=?", (ref,))):
        raise HTTPException(400, "Ungültige Freigabe")
    if grantee != "*" and (grantee == u["uid"] or not auth.q1("SELECT 1 x FROM users WHERE uid=? AND active=1", (grantee,))):
        raise HTTPException(400, "Unbekannter Benutzer")
    if auth.q1("SELECT 1 x FROM grants WHERE owner=? AND grantee=? AND scope=? AND ref=?", (u["uid"], grantee, scope, ref if scope == "tour" else "")):
        return {"ok": True}
    auth.q("INSERT INTO grants(owner,grantee,scope,ref,ts) VALUES(?,?,?,?,?)", (u["uid"], grantee, scope, ref if scope == "tour" else "", int(time.time())))
    return {"ok": True}


@router.delete("/api/grants/{gid}")
def api_grant_del(gid: int, request: Request):
    u = _user(request)
    auth.q("DELETE FROM grants WHERE id=? AND owner=?", (gid, u["uid"]))
    return {"ok": True}


# ---------- Geteilte Fotos ----------
def _owner_photos(owner, scopes, tour_window=None):
    """Fotos des Besitzers, die laut Freigabe sichtbar sind."""
    with ctx.as_user(owner):
        tours = {t["id"]: t["name"] for t in db.query("SELECT id,name FROM tours")}
        allp = any(s["scope"] == "all" for s in scopes)
        ids = [s["ref"] for s in scopes if s["scope"] == "tour"]
        sql = "SELECT id,taken_ts,tour_id,lat,lng,path FROM photos WHERE COALESCE(manual,0)!=2"
        args = []
        if not allp:
            if not ids:
                return [], tours
            sql += f" AND tour_id IN ({','.join('?' * len(ids))})"; args += ids
        if tour_window:
            sql += " AND taken_ts BETWEEN ? AND ?"; args += list(tour_window)
        rows = db.query(sql + " ORDER BY taken_ts LIMIT 3000", tuple(args))
    return rows, tours


@router.get("/api/shared/photos")
def api_shared_photos(request: Request):
    u = _user(request)
    names = {x["uid"]: x["name"] for x in auth.list_users()}
    by = {}
    for g in auth.grants_to(u["uid"]):
        by.setdefault(g["owner"], []).append(g)
    out = []
    for owner, sc in by.items():
        rows, tours = _owner_photos(owner, sc)
        out.append({"owner": owner, "name": names.get(owner, owner), "tours": tours, "photos": [{k: r[k] for k in ("id", "taken_ts", "tour_id", "lat", "lng")} for r in rows]})
    return out


@router.get("/spic/{owner}/{pid}")
@router.get("/sphoto/{owner}/{pid}")
def api_shared_photo(owner: str, pid: int, request: Request, size: int = 600):
    u = _user(request)
    with ctx.as_user(owner):
        r = db.one("SELECT tour_id FROM photos WHERE id=?", (pid,))
        if not r or not auth.can_see_photo(u["uid"], owner, r["tour_id"]):
            raise HTTPException(404)
        p = photos.thumb(pid, max(120, min(size, 2400)))
    if not p:
        raise HTTPException(404)
    return photos.respond(request, p)


def _imported_keys():
    return {Path(r["path"]).name for r in db.query("SELECT path FROM photos WHERE path LIKE ?", (f"%{os.sep}von-%",))}


@router.get("/api/shared/for-tour/{tour_id}")
def api_shared_for_tour(tour_id: str, request: Request):
    u = _user(request)
    t = db.one("SELECT start_ts,end_ts FROM tours WHERE id=?", (tour_id,))
    if not t:
        raise HTTPException(404)
    m = db.get_int("photo_margin_min", 30) * 60
    win = (t["start_ts"] - m, (t["end_ts"] or t["start_ts"]) + m)
    names = {x["uid"]: x["name"] for x in auth.list_users()}
    have = _imported_keys(); by = {}; out = []
    for g in auth.grants_to(u["uid"]):
        by.setdefault(g["owner"], []).append(g)
    for owner, sc in by.items():
        rows, _ = _owner_photos(owner, sc, win)
        for r in rows:
            if Path(r["path"]).name not in have:
                out.append({"owner": owner, "owner_name": names.get(owner, owner), "id": r["id"], "taken_ts": r["taken_ts"]})
    return out


@router.post("/api/shared/import")
async def api_shared_import(request: Request):
    """Geteilte Fotos in die eigene Bibliothek kopieren (landen dann bei passenden eigenen Touren)."""
    u = _user(request); d = await request.json()
    owner = str(d.get("owner", "")); ids = [int(i) for i in d.get("ids") or []][:3000]
    if not owner or owner == u["uid"] or not auth.q1("SELECT 1 x FROM users WHERE uid=? AND active=1", (owner,)):
        raise HTTPException(400, "Unbekannter Besitzer")
    src = []
    with ctx.as_user(owner):
        for i in ids:
            r = db.one("SELECT path,mtime,taken_ts,lat,lng,tour_id FROM photos WHERE id=?", (i,))
            if r and auth.can_see_photo(u["uid"], owner, r["tour_id"]) and os.path.exists(r["path"]):
                src.append(r)
    dst_dir = config.LIB_DIR / f"von-{owner}"
    dst_dir.mkdir(parents=True, exist_ok=True)
    rows, n = [], 0
    for r in src:
        dst = dst_dir / Path(r["path"]).name
        if not dst.exists():
            shutil.copy2(r["path"], dst); n += 1
        st = dst.stat()
        rows.append((str(dst), st.st_mtime, st.st_size, r["taken_ts"], r["lat"], r["lng"]))
    photos._store(rows)
    photos.assign_all()
    return {"imported": n, "total": len(rows)}
