"""E-Mail-Versand, „Passwort vergessen“ und Zwei-Faktor-Anmeldung (TOTP, RFC 6238). Nur Standardbibliothek."""
import base64
import hashlib
import hmac
import json
import secrets
import smtplib
import ssl
import struct
import threading
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pathlib import Path

from . import auth, users_api

router = APIRouter()
RESET_MIN = 60
ISSUER = "Meine Touren"


# ---------- Systemeinstellungen (gelten für alle Benutzer) ----------
def conf(k, default=""):
    r = auth.q1("SELECT v FROM sysconf WHERE k=?", (k,))
    return r["v"] if r and r["v"] is not None else default


def conf_set(k, v):
    auth.q("INSERT OR REPLACE INTO sysconf(k,v) VALUES(?,?)", (k, v))


# ---------- E-Mail ----------
def mail_ready():
    return bool(conf("smtp_host") and conf("smtp_from"))


def send_mail(to, subject, body):
    """Sendet eine Textmail über den eingerichteten SMTP-Server; wirft RuntimeError mit lesbarer Meldung."""
    if not mail_ready():
        raise RuntimeError("Der E-Mail-Versand ist noch nicht eingerichtet (Verwaltung → Automatik & Meldungen)")
    host, mode = conf("smtp_host"), conf("smtp_mode", "starttls")
    port = int(conf("smtp_port") or (465 if mode == "ssl" else 587 if mode == "starttls" else 25))
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = subject, conf("smtp_from"), to
    m["Date"], m["Message-ID"] = formatdate(localtime=True), make_msgid(domain=(conf("smtp_from").split("@")[-1] or "localhost"))
    m.set_content(body)
    try:
        if mode == "ssl":
            s = smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context())
        else:
            s = smtplib.SMTP(host, port, timeout=20)
        with s:
            if mode == "starttls":
                s.starttls(context=ssl.create_default_context())
            if conf("smtp_user"):
                s.login(conf("smtp_user"), conf("smtp_pw"))
            s.send_message(m)
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError("Der Mailserver hat Benutzername oder Passwort abgelehnt")
    except (OSError, smtplib.SMTPException) as e:
        raise RuntimeError("Mailversand fehlgeschlagen: " + (str(e) or e.__class__.__name__)[:160])


_MAILS = {
    "mail_changed": {
        "de": ("Meine Touren: E-Mail-Adresse geändert", "Hallo {name},\n\ndie E-Mail-Adresse deines Kontos wurde auf {email} geändert.\nWar das nicht deine Absicht, melde dich bitte beim Administrator.\n"),
        "en": ("Meine Touren: Email address changed", "Hello {name},\n\nthe email address of your account was changed to {email}.\nIf this was not intended, please contact the administrator.\n"),
        "fr": ("Meine Touren : adresse e-mail modifiée", "Bonjour {name},\n\nl’adresse e-mail de votre compte a été modifiée en {email}.\nSi ce n’était pas voulu, contactez l’administrateur.\n"),
        "es": ("Meine Touren: dirección de correo cambiada", "Hola {name}:\n\nla dirección de correo de tu cuenta se ha cambiado a {email}.\nSi no fue intencionado, ponte en contacto con el administrador.\n")},
    "2fa_on": {
        "de": ("Meine Touren: Zwei-Faktor-Anmeldung eingeschaltet", "Hallo {name},\n\ndie Zwei-Faktor-Anmeldung für dein Konto wurde eingeschaltet.\nWar das nicht deine Absicht, melde dich bitte beim Administrator.\n"),
        "en": ("Meine Touren: Two-factor sign-in turned on", "Hello {name},\n\ntwo-factor sign-in was turned on for your account.\nIf this was not intended, please contact the administrator.\n"),
        "fr": ("Meine Touren : authentification à deux facteurs activée", "Bonjour {name},\n\nl’authentification à deux facteurs a été activée pour votre compte.\nSi ce n’était pas voulu, contactez l’administrateur.\n"),
        "es": ("Meine Touren: inicio de sesión en dos pasos activado", "Hola {name}:\n\nse ha activado el inicio de sesión en dos pasos en tu cuenta.\nSi no fue intencionado, ponte en contacto con el administrador.\n")},
    "2fa_off": {
        "de": ("Meine Touren: Zwei-Faktor-Anmeldung ausgeschaltet", "Hallo {name},\n\ndie Zwei-Faktor-Anmeldung für dein Konto wurde ausgeschaltet.\nWar das nicht deine Absicht, ändere bitte sofort dein Passwort.\n"),
        "en": ("Meine Touren: Two-factor sign-in turned off", "Hello {name},\n\ntwo-factor sign-in was turned off for your account.\nIf this was not intended, please change your password immediately.\n"),
        "fr": ("Meine Touren : authentification à deux facteurs désactivée", "Bonjour {name},\n\nl’authentification à deux facteurs a été désactivée pour votre compte.\nSi ce n’était pas voulu, changez immédiatement votre mot de passe.\n"),
        "es": ("Meine Touren: inicio de sesión en dos pasos desactivado", "Hola {name}:\n\nse ha desactivado el inicio de sesión en dos pasos en tu cuenta.\nSi no fue intencionado, cambia tu contraseña de inmediato.\n")},
    "pw_changed": {
        "de": ("Meine Touren: Passwort geändert", "Hallo {name},\n\ndein Passwort wurde soeben über den Link „Passwort vergessen“ geändert. Alle bisherigen Anmeldungen wurden beendet.\nWar das nicht deine Absicht, wende dich bitte an den Administrator.\n"),
        "en": ("Meine Touren: Password changed", "Hello {name},\n\nyour password was just changed via the “Forgot password” link. All previous sign-ins have been ended.\nIf this was not intended, please contact the administrator.\n"),
        "fr": ("Meine Touren : mot de passe modifié", "Bonjour {name},\n\nvotre mot de passe vient d’être modifié via le lien « Mot de passe oublié ». Toutes les connexions précédentes ont été fermées.\nSi ce n’était pas voulu, contactez l’administrateur.\n"),
        "es": ("Meine Touren: contraseña cambiada", "Hola {name}:\n\ntu contraseña se acaba de cambiar mediante el enlace «¿Olvidaste tu contraseña?». Se han cerrado todas las sesiones anteriores.\nSi no fue intencionado, ponte en contacto con el administrador.\n")},
    "reset": {
        "de": ("Meine Touren: Passwort zurücksetzen", "Für dein Konto bei „Meine Touren“ wurde ein neues Passwort angefordert.\n\n", "Konto „{n}“:\n{u}", "\n\nDer Link gilt {m} Minuten und kann nur einmal benutzt werden.\nHast du das nicht angefordert, kannst du diese Nachricht ignorieren – dein Passwort bleibt unverändert.\n"),
        "en": ("Meine Touren: Reset password", "A new password was requested for your “Meine Touren” account.\n\n", "Account “{n}”:\n{u}", "\n\nThe link is valid for {m} minutes and can only be used once.\nIf you did not request this, you can ignore this message – your password stays unchanged.\n"),
        "fr": ("Meine Touren : réinitialiser le mot de passe", "Un nouveau mot de passe a été demandé pour votre compte « Meine Touren ».\n\n", "Compte « {n} » :\n{u}", "\n\nLe lien est valable {m} minutes et ne peut être utilisé qu’une seule fois.\nSi vous n’en êtes pas à l’origine, ignorez ce message – votre mot de passe reste inchangé.\n"),
        "es": ("Meine Touren: restablecer contraseña", "Se ha solicitado una nueva contraseña para tu cuenta de «Meine Touren».\n\n", "Cuenta «{n}»:\n{u}", "\n\nEl enlace es válido durante {m} minutos y solo se puede usar una vez.\nSi no lo solicitaste, ignora este mensaje: tu contraseña no cambia.\n")},
    "test": {
        "de": ("Meine Touren: Testnachricht", "Der E-Mail-Versand funktioniert. 🎉\n"),
        "en": ("Meine Touren: Test message", "Email delivery works. 🎉\n"),
        "fr": ("Meine Touren : message de test", "L’envoi d’e-mails fonctionne. 🎉\n"),
        "es": ("Meine Touren: mensaje de prueba", "El envío de correos funciona. 🎉\n")},
}


def _mlang(request=None):
    """Mailsprache aus Accept-Language der auslösenden Anfrage (de/en/fr/es; sonst Englisch, ohne Header Deutsch)."""
    try:
        al = (request.headers.get("accept-language") or "de").lower()
    except Exception:
        return "de"
    for part in al.split(","):
        c = part.strip()[:2]
        if c in ("de", "en", "fr", "es"):
            return c
    return "en"


def _mail_t(key, request, **kw):
    t = _MAILS[key][_mlang(request)]
    return t[0], t[1].format(**kw)


def send_async(to, subject, body):
    """Hinweismails (z. B. „Passwort geändert“) im Hintergrund, Fehler werden nur geschluckt."""
    if not to or not mail_ready():
        return

    def run():
        try:
            send_mail(to, subject, body)
        except Exception:  # noqa
            pass
    threading.Thread(target=run, daemon=True).start()


# ---------- TOTP ----------
def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret, counter, digits=6):
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 15
    return str((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 10 ** digits).zfill(digits)


def totp_now(secret, t=None, digits=6):
    return _hotp(secret, int((t if t is not None else time.time()) // 30), digits)


def totp_verify(secret, code, last=0, t=None):
    """Prüft einen 6-stelligen Code (±30 s Toleranz). Gibt den Zeitschritt zurück oder None; ein Schritt gilt nur einmal."""
    code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(code) != 6:
        return None
    step = int((t if t is not None else time.time()) // 30)
    for st in (step, step - 1, step + 1):
        if st > last and hmac.compare_digest(_hotp(secret, st), code):
            return st
    return None


def otp_uri(name, secret):
    return f"otpauth://totp/{quote(ISSUER)}:{quote(name)}?secret={secret}&issuer={quote(ISSUER)}&algorithm=SHA1&digits=6&period=30"


def make_recovery(uid, n=8):
    codes = [secrets.token_hex(3) + "-" + secrets.token_hex(3) for _ in range(n)]
    auth.q("DELETE FROM recovery WHERE uid=?", (uid,))
    for c in codes:
        auth.q("INSERT INTO recovery(uid,h) VALUES(?,?)", (uid, hashlib.sha256(c.encode()).hexdigest()))
    return codes


def _use_recovery(uid, code):
    h = hashlib.sha256(str(code or "").strip().lower().replace(" ", "").encode()).hexdigest()
    if auth.q1("SELECT 1 x FROM recovery WHERE uid=? AND h=?", (uid, h)):
        auth.q("DELETE FROM recovery WHERE uid=? AND h=?", (uid, h))
        return True
    return False


def check_second_factor(u, code):
    """TOTP-Code oder Wiederherstellungscode prüfen (verbraucht ihn)."""
    st = totp_verify(u["totp_secret"] or "", code, u["totp_last"] or 0)
    if st:
        auth.q("UPDATE users SET totp_last=? WHERE uid=?", (st, u["uid"]))
        return True
    return _use_recovery(u["uid"], code)


# ---------- Anmeldung mit zweitem Faktor ----------
_ip_tries = {}


def _throttle(key, limit, window):
    now = time.time(); t = [x for x in _ip_tries.get(key, []) if now - x < window]
    if len(t) >= limit:
        _ip_tries[key] = t
        return False
    _ip_tries[key] = t + [now]
    return True


def make_ticket(uid):
    tok = secrets.token_urlsafe(24)
    auth.q("DELETE FROM tickets WHERE exp<?", (int(time.time()),))
    auth.q("INSERT INTO tickets(th,uid,exp,tries) VALUES(?,?,?,0)", (hashlib.sha256(tok.encode()).hexdigest(), uid, int(time.time()) + 300))
    return tok


@router.post("/api/login/2fa")
async def api_login_2fa(request: Request, response: Response):
    d = await request.json()
    th = hashlib.sha256(str(d.get("ticket", "")).encode()).hexdigest()
    t = auth.q1("SELECT * FROM tickets WHERE th=? AND exp>?", (th, int(time.time())))
    if not t or t["tries"] >= 5:
        raise HTTPException(401, "Die Anmeldung ist abgelaufen – bitte noch einmal mit Name und Passwort beginnen")
    u = auth.q1("SELECT * FROM users WHERE uid=? AND active=1 AND totp_on=1", (t["uid"],))
    if not u:
        raise HTTPException(401, "Anmeldung nicht möglich")
    if not _throttle("2fa|" + users_api._ip(request), 20, 600):
        raise HTTPException(429, "Zu viele Versuche – bitte in ein paar Minuten erneut versuchen")
    if not check_second_factor(u, d.get("code")):
        auth.q("UPDATE tickets SET tries=tries+1 WHERE th=?", (th,))
        raise HTTPException(401, "Der Code stimmt nicht")
    auth.q("DELETE FROM tickets WHERE th=?", (th,))
    users_api._cookie(response, auth.start_session(u["uid"]), request)
    left = auth.q1("SELECT COUNT(*) n FROM recovery WHERE uid=?", (u["uid"],))["n"]
    return {"ok": True, "user": {"uid": u["uid"], "name": u["name"], "role": u["role"]}, "recovery_left": left}


# ---------- Eigenes Konto: E-Mail und Zwei-Faktor ----------
def _me(request):
    u = users_api._user(request)
    if u["role"] == "viewer":
        raise HTTPException(403, "Dieser Zugang darf nur ansehen")
    return auth.q1("SELECT * FROM users WHERE uid=?", (u["uid"],))


def _pw_ok(row, pw):
    if not auth.check_pw(str(pw or ""), row["pw"]):
        raise HTTPException(400, "Das Passwort stimmt nicht")


@router.post("/api/me/email")
async def api_my_email(request: Request):
    row = _me(request); d = await request.json()
    _pw_ok(row, d.get("password"))
    try:
        e = auth.clean_email(d.get("email"), required=True)
    except ValueError as x:
        raise HTTPException(400, str(x))
    old = row["email"]
    auth.q("UPDATE users SET email=? WHERE uid=?", (e, row["uid"]))
    if old and old.lower() != e.lower():
        send_async(old, *_mail_t("mail_changed", request, name=row['name'], email=e))
    return {"ok": True, "email": e}


@router.get("/api/me/2fa")
def api_2fa_state(request: Request):
    row = _me(request)
    return {"on": bool(row["totp_on"]), "recovery_left": auth.q1("SELECT COUNT(*) n FROM recovery WHERE uid=?", (row["uid"],))["n"], "email": row["email"], "mail_ready": mail_ready()}


@router.post("/api/me/2fa/setup")
def api_2fa_setup(request: Request):
    row = _me(request)
    if row["totp_on"]:
        raise HTTPException(400, "Die Zwei-Faktor-Anmeldung ist schon eingeschaltet")
    s = new_secret()
    auth.q("UPDATE users SET totp_pending=? WHERE uid=?", (s, row["uid"]))
    return {"secret": s, "uri": otp_uri(row["name"], s)}


@router.post("/api/me/2fa/enable")
async def api_2fa_enable(request: Request):
    row = _me(request); d = await request.json()
    s = row["totp_pending"]
    if not s:
        raise HTTPException(400, "Bitte zuerst „Einrichten“ wählen")
    st = totp_verify(s, d.get("code"))
    if not st:
        raise HTTPException(400, "Der Code stimmt nicht – prüfe die Uhrzeit des Handys und versuche es noch einmal")
    auth.q("UPDATE users SET totp_secret=?, totp_on=1, totp_pending=NULL, totp_last=? WHERE uid=?", (s, st, row["uid"]))
    send_async(row["email"], *_mail_t("2fa_on", request, name=row['name']))
    return {"ok": True, "codes": make_recovery(row["uid"])}


@router.post("/api/me/2fa/disable")
async def api_2fa_disable(request: Request):
    row = _me(request); d = await request.json()
    _pw_ok(row, d.get("password"))
    if row["totp_on"] and not check_second_factor(row, d.get("code")):
        raise HTTPException(400, "Der Code stimmt nicht")
    auth.q("UPDATE users SET totp_on=0, totp_secret=NULL, totp_pending=NULL, totp_last=0 WHERE uid=?", (row["uid"],))
    auth.q("DELETE FROM recovery WHERE uid=?", (row["uid"],))
    send_async(row["email"], *_mail_t("2fa_off", request, name=row['name']))
    return {"ok": True}


@router.post("/api/me/2fa/recovery")
async def api_2fa_recovery(request: Request):
    row = _me(request); d = await request.json()
    _pw_ok(row, d.get("password"))
    if not row["totp_on"] or not check_second_factor(row, d.get("code")):
        raise HTTPException(400, "Der Code stimmt nicht")
    return {"codes": make_recovery(row["uid"])}


# ---------- Passwort vergessen ----------
def _base_url():
    return (conf("public_url") or "").rstrip("/")


@router.post("/api/forgot")
async def api_forgot(request: Request):
    d = await request.json()
    who = str(d.get("who", "")).strip()
    ip = users_api._ip(request)
    if not _throttle("forgot|" + ip, 5, 900):
        raise HTTPException(429, "Zu viele Anfragen – bitte in einer Viertelstunde erneut versuchen")
    if not mail_ready() or not _base_url():
        raise HTTPException(503, "Das Zurücksetzen per E-Mail ist noch nicht eingerichtet. Bitte den Administrator bitten, dein Passwort zu setzen.")
    rows = []
    if who:
        rows = auth.q("SELECT uid,name,email FROM users WHERE active=1 AND email IS NOT NULL AND email!='' AND (lower(email)=lower(?) OR lower(name)=lower(?))", (who, who))
    by_mail = {}
    for r in rows:
        if auth.q1("SELECT COUNT(*) n FROM resets WHERE uid=? AND exp>?", (r["uid"], int(time.time()) + (RESET_MIN - 60) * 60))["n"] >= 3:
            continue                                  # höchstens 3 Links pro Stunde und Konto
        tok = secrets.token_urlsafe(32)
        auth.q("INSERT INTO resets(th,uid,exp) VALUES(?,?,?)", (hashlib.sha256(tok.encode()).hexdigest(), r["uid"], int(time.time()) + RESET_MIN * 60))
        by_mail.setdefault(r["email"], []).append((r["name"], f"{_base_url()}/reset/{tok}"))
    auth.q("DELETE FROM resets WHERE exp<?", (int(time.time()),))
    for to, items in by_mail.items():
        subj, intro, item, outro = _MAILS["reset"][_mlang(request)]
        body = intro + "\n\n".join(item.format(n=n, u=u) for n, u in items) + outro.format(m=RESET_MIN)
        send_async(to, subj, body)
    return {"ok": True}                              # immer dieselbe Antwort – man erfährt nicht, ob eine Adresse bekannt ist


def _reset_row(token):
    r = auth.q1("SELECT * FROM resets WHERE th=? AND exp>?", (hashlib.sha256(str(token).encode()).hexdigest(), int(time.time())))
    if not r:
        raise HTTPException(404, "Dieser Link ist abgelaufen oder wurde schon benutzt")
    return r


@router.get("/reset/{token}")
def reset_page(token: str):
    return FileResponse(Path(__file__).parent / "static" / "reset.html", media_type="text/html", headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.get("/api/reset/{token}")
def api_reset_info(token: str):
    r = _reset_row(token)
    u = auth.q1("SELECT name FROM users WHERE uid=?", (r["uid"],))
    return {"name": u["name"] if u else ""}


@router.post("/api/reset")
async def api_reset(request: Request):
    d = await request.json()
    if not _throttle("reset|" + users_api._ip(request), 20, 900):
        raise HTTPException(429, "Zu viele Versuche")
    r = _reset_row(d.get("token", ""))
    try:
        auth.set_password(r["uid"], str(d.get("password", "")))
    except ValueError as e:
        raise HTTPException(400, str(e))
    auth.q("DELETE FROM resets WHERE uid=?", (r["uid"],))
    u = auth.q1("SELECT name,email,totp_on FROM users WHERE uid=?", (r["uid"],))
    if u:
        send_async(u["email"], *_mail_t("pw_changed", request, name=u['name']))
    return {"ok": True, "totp": bool(u and u["totp_on"])}


# ---------- Verwaltung: E-Mail-Versand einrichten (nur Administratoren) ----------
MAIL_KEYS = ("smtp_host", "smtp_port", "smtp_mode", "smtp_user", "smtp_from", "public_url")


@router.get("/api/mail/settings")
def api_mail_get(request: Request):
    users_api._admin(request)
    return {**{k: conf(k) for k in MAIL_KEYS}, "smtp_mode": conf("smtp_mode", "starttls"), "pw_set": bool(conf("smtp_pw")), "ready": mail_ready() and bool(_base_url())}


@router.post("/api/mail/settings")
async def api_mail_set(request: Request):
    users_api._admin(request); d = await request.json()
    for k in MAIL_KEYS:
        if k in d:
            v = str(d[k] or "").strip()
            if k == "smtp_mode" and v not in ("ssl", "starttls", "none"):
                raise HTTPException(400, "Ungültige Verschlüsselung")
            if k == "smtp_port" and v and not v.isdigit():
                raise HTTPException(400, "Der Port muss eine Zahl sein")
            if k == "public_url" and v and not v.startswith(("http://", "https://")):
                raise HTTPException(400, "Die öffentliche Adresse muss mit https:// beginnen")
            conf_set(k, v)
    if d.get("smtp_pw"):
        conf_set("smtp_pw", str(d["smtp_pw"]))
    if d.get("clear_pw"):
        conf_set("smtp_pw", "")
    return {"ok": True}


@router.post("/api/mail/test")
def api_mail_test(request: Request):
    me = users_api._admin(request)
    row = auth.q1("SELECT email FROM users WHERE uid=?", (me["uid"],))
    if not row or not row["email"]:
        raise HTTPException(400, "Für dein Konto ist keine E-Mail-Adresse hinterlegt (Konto & Freigaben)")
    try:
        send_mail(row["email"], *_mail_t("test", request))
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "to": row["email"]}
