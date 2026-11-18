"""Aufruf: python -m app.backup [Zielordner] [Anzahl behalten]  (z. B. per Cron). Sichert jeden Benutzer einzeln.
Schlägt eine Sicherung fehl, steht der Grund in der Ausgabe und im Zustand der App; der Rückgabewert ist dann 1."""
import sys
import time

from . import auth, config, ctx, db, extras

if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else str(config.BACKUP_ROOT)
    keep = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    auth.load_first()
    failed = 0
    for u in auth.active_uids():
        with ctx.as_user(u):
            db.init()
            try:
                print(extras.make_backup(dest if not u else f"{dest}/{u}", keep=keep))
                db.put("backup_err", ""); db.put("backup_err_ts", "")
            except Exception as e:  # noqa
                failed += 1
                print(f"Sicherung fehlgeschlagen ({u or 'Hauptbenutzer'}): {e}", file=sys.stderr)
                db.put("backup_err", str(e)); db.put("backup_err_ts", str(int(time.time())))
    sys.exit(1 if failed else 0)
