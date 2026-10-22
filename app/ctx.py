"""Aktueller Benutzer (pro Anfrage / Hintergrundjob). None = Altbetrieb ohne Benutzerverwaltung."""
from contextlib import contextmanager
from contextvars import ContextVar

_uid = ContextVar("kh_uid", default=None)
first_uid = None          # ältester Benutzer (erbt die Altdaten und den globalen Foto-Quellordner)


def uid():
    return _uid.get()


@contextmanager
def as_user(u):
    tok = _uid.set(u)
    try:
        yield
    finally:
        _uid.reset(tok)
