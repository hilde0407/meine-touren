"""Aufruf: python -m app.backup [Zielordner] [Anzahl behalten]  (z. B. per Cron). Sichert jeden Benutzer einzeln."""
import sys

from . import auth, config, ctx, db, extras

if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else str(config.BACKUP_ROOT)
    keep = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    auth.load_first()
    for u in auth.active_uids():
        with ctx.as_user(u):
            db.init()
            print(extras.make_backup(dest if not u else f"{dest}/{u}", keep=keep))
