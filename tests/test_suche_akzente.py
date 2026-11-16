"""3.31.0 – Suche ohne Akzente, Sonderbuchstaben und Apostrophe (Python-Helfer app/suche.py + Server-Endpunkt /api/tours?q=)."""
import pytest

from app import suche
from tests.test_core import fresh  # noqa: F401

PAARE = [
    ("Réunion", "reunion"), ("Réunion", "Reunion"), ("Lucía", "lucia"), ("Lucia", "Lucía"),
    ("Côte d'Azur", "d'Azur"), ("Côte d'Azur", "d’Azur"), ("Côte d'Azur", "dazur"), ("Côte d’Azur", "d azur"), ("Côte d'Azur", "cote d`azur"),
    ("Straße am See", "strasse"), ("Strasse", "STRAßE"), ("Ålesund", "alesund"), ("Ødegård", "odegard"), ("Ødegård", "ødegård"),
    ("Köln", "koeln"), ("Köln", "koln"), ("Köln", "köln"), ("Koeln", "Köln"), ("Ärzte-Weg", "aerzte"), ("Ärzte-Weg", "arzte"),
    ("Groß Gerau", "GROSS"), ("GROSSER Berg", "groß"), ("Łódź", "lodz"), ("Æsir", "aesir"), ("Cœur", "coeur"), ("Đakovo", "dakovo"), ("Işık", "isik"),
    ("Über den Wolken", "ueber"), ("Über den Wolken", "uber"),
]
KEINE = [("Réunion", "reunions"), ("Lucía", "luzia"), ("Köln", "kon"), ("Côte d'Azur", "azur cote x")]


@pytest.mark.parametrize("hay,needle", PAARE)
def test_trifft(hay, needle):
    assert suche.smatch(hay, needle), (hay, needle)


@pytest.mark.parametrize("hay,needle", KEINE)
def test_trifft_nicht(hay, needle):
    assert not suche.smatch(hay, needle), (hay, needle)


def test_leere_eingabe_trifft_alles():
    assert suche.smatch("irgendwas", "") and suche.smatch("", "  ") and suche.smatch(None, "")


def test_sfold_hauptform():
    assert suche.sfold("Réunion") == "reunion"
    assert suche.sfold("d’Azur") == "dazur"
    assert suche.sfold("Straße") == "strasse"
    assert suche.sfold("Ødegård Ålesund") == "odegard alesund"
    assert suche.sfold("Köln") == "koln"


def test_endpunkt_filtert_ohne_akzent(fresh):
    from app import db
    from fastapi.testclient import TestClient
    from app import main
    for i, n in enumerate(["Réunion Rundweg", "Lucía am See", "Anderes"]):
        db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,1000,600,10,10,'t','komoot')", (f"x{i}", n, "hike", 1750000000 + i, 1750000600 + i))
    c = TestClient(main.app)
    names = lambda q: sorted(t["name"] for t in c.get("/api/tours", params={"q": q}).json())
    assert names("reunion") == ["Réunion Rundweg"]
    assert names("RÉUNION") == ["Réunion Rundweg"]
    assert names("lucia") == ["Lucía am See"]
    assert names("andere") == ["Anderes"]
    assert len(names("")) == 3
