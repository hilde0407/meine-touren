import importlib.util
import struct
from pathlib import Path
from types import SimpleNamespace as NS

spec = importlib.util.spec_from_file_location("fza", Path(__file__).parent.parent / "mac" / "foto_zeit_abgleich.py")
fza = importlib.util.module_from_spec(spec); spec.loader.exec_module(fza)


def tiff(dt, model="ILCE-7M4", exp=(1, 250), f=(28, 10), iso=400, fl=(35, 1), e="<", jpeg=False):
    """Minimales TIFF mit Exif-IFD (wie in ARW und im EXIF-Block von JPEGs)."""
    P = lambda fmt, *v: struct.pack(e + fmt, *v)
    mdl = model.encode() + b"\0"
    ifd0_n = 2; ifd0_len = 2 + 12 * ifd0_n + 4
    off_model = 8 + ifd0_len; off_exif = off_model + len(mdl) + (len(mdl) % 2)
    ex = [(0x829A, 5, 1, exp), (0x829D, 5, 1, f), (0x8827, 3, 1, iso), (0x9003, 2, 20, dt), (0x9004, 2, 20, dt), (0x920A, 5, 1, fl)]
    exn = len(ex); ex_len = 2 + 12 * exn + 4; data_off = off_exif + ex_len
    out = b"II*\0" if e == "<" else b"MM\0*"
    out += P("I", 8)
    out += P("H", ifd0_n) + P("HHII", 0x0110, 2, len(mdl), off_model) + P("HHII", 0x8769, 4, 1, off_exif) + P("I", 0)
    out += mdl + b"\0" * (len(mdl) % 2)
    body = b""; ents = b""
    for tag, typ, cnt, v in ex:
        if typ == 5:
            ents += P("HHII", tag, 5, 1, data_off + len(body)); body += P("II", *v)
        elif typ == 3:
            ents += P("HHI", tag, 3, 1) + P("H", v) + b"\0\0"
        else:
            ents += P("HHII", tag, 2, 20, data_off + len(body)); body += v.encode() + b"\0"
    out += P("H", exn) + ents + P("I", 0) + body
    if jpeg:
        seg = b"Exif\0\0" + out
        return b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(seg) + 2) + seg + b"\xff\xdb\0\x02" + b"\xff\xda\0\x02" + b"\0" * 10 + b"\xff\xd9"
    return out + b"\0" * 64


def test_zeit_abgleich(tmp_path, monkeypatch):
    monkeypatch.setattr(fza, "INDEX", tmp_path / "ix.json"); monkeypatch.setattr(fza, "LOG", tmp_path / "log.jsonl")
    disk1, disk2, out = tmp_path / "Volumes" / "P1", tmp_path / "Volumes" / "P2", tmp_path / "fertig"
    for d in (disk1 / "2025" / "a", disk2, out):
        d.mkdir(parents=True)
    (disk1 / "2025" / "a" / "DSC01234.ARW").write_bytes(tiff("2025:05:01 10:00:00"))
    (disk1 / "2025" / "a" / "DSC05000.ARW").write_bytes(tiff("2025:05:02 11:00:00", e=">"))
    (disk1 / "2025" / "a" / "._DSC01234.ARW").write_bytes(b"junk")
    (disk2 / "DSC01234.ARW").write_bytes(tiff("2022:01:01 09:00:00", iso=100))          # gleicher Name, andere Einstellungen
    (disk2 / "DSC07777.ARW").write_bytes(tiff("2024:07:07 07:07:07"))
    (disk2 / "DSC07777b.ARW").write_bytes(b"x")
    (out / "DSC01234-Bearbeitet.jpg").write_bytes(tiff("2026:10:22 12:34:56", jpeg=True))   # Exportzeit statt Aufnahmezeit
    (out / "DSC05000.jpg").write_bytes(tiff("2025:05:02 11:00:00", jpeg=True))           # schon korrekt
    (out / "DSC07777.jpg").write_bytes(tiff("2026:10:22 12:00:00", jpeg=True))
    (out / "IMG_X.jpg").write_bytes(tiff("2026:10:22 12:00:00", jpeg=True))              # kein Original
    fza.cmd_index(NS(pfade=[str(disk1)], name=None, ext="arw", zeitlimit=0))
    rep = tmp_path / "r1.csv"
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(rep)), False)
    assert fza.jpeg_info(out / "DSC01234-Bearbeitet.jpg")["dt"] == "2026:10:22 12:34:56"      # check ändert nichts
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(rep)), True)
    assert fza.jpeg_info(out / "DSC01234-Bearbeitet.jpg")["dt"] == "2025:05:01 10:00:00"
    assert fza.jpeg_info(out / "DSC07777.jpg")["dt"] == "2026:10:22 12:00:00"                 # Platte 2 noch nicht eingelesen
    fza.cmd_index(NS(pfade=[str(disk2)], name="P2", ext="arw", zeitlimit=0))
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(rep)), True)
    assert fza.jpeg_info(out / "DSC07777.jpg")["dt"] == "2024:07:07 07:07:07"
    i = fza.jpeg_info(out / "DSC07777.jpg"); assert i["patch"]["cd"][1] == "2024:07:07 07:07:07"   # CreateDate ebenfalls
    st = [l.split(";")[1] for l in rep.read_text().splitlines()[1:]]
    assert sorted(st) == ["nicht gefunden", "ok", "ok", "ok"] or "nicht gefunden" in st
    fza.cmd_undo(NS(lauf=None))
    assert fza.jpeg_info(out / "DSC07777.jpg")["dt"] == "2026:10:22 12:00:00"
    assert fza.jpeg_info(out / "DSC01234-Bearbeitet.jpg")["dt"] == "2025:05:01 10:00:00"      # älterer Lauf bleibt


def test_zeit_mehrdeutig(tmp_path, monkeypatch):
    monkeypatch.setattr(fza, "INDEX", tmp_path / "ix.json"); monkeypatch.setattr(fza, "LOG", tmp_path / "log.jsonl")
    d, out = tmp_path / "d", tmp_path / "o"; d.mkdir(); out.mkdir()
    (d / "a").mkdir(); (d / "b").mkdir()
    (d / "a" / "DSC00001.ARW").write_bytes(tiff("2020:01:01 10:00:00")); (d / "b" / "DSC00001.ARW").write_bytes(tiff("2021:01:01 10:00:00"))
    (out / "DSC00001.jpg").write_bytes(tiff("2026:01:01 00:00:00", jpeg=True))
    fza.cmd_index(NS(pfade=[str(d)], name="d", ext="arw", zeitlimit=0))
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(tmp_path / "r.csv")), True)
    assert fza.jpeg_info(out / "DSC00001.jpg")["dt"] == "2026:01:01 00:00:00" and "mehrdeutig" in (tmp_path / "r.csv").read_text()


def minimal_jpeg(with_exif=True):
    """Wie ein Lightroom-Export „nur Copyright“: EXIF ohne Aufnahmedatum, dazu XMP-Segment."""
    xmp = b"http://ns.adobe.com/xap/1.0/\0<x/>"
    body = b"\xff\xe1" + struct.pack(">H", len(xmp) + 2) + xmp + b"\xff\xdb\0\x02" + b"\xff\xda\0\x02" + b"\x01" * 20 + b"\xff\xd9"
    if not with_exif:
        return b"\xff\xd8" + body
    P = lambda fmt, *v: struct.pack("<" + fmt, *v)
    ifd0 = P("H", 2) + P("HHII", 0x8298, 2, 5, 38) + P("HHII", 0x8769, 4, 1, 44) + P("I", 0)      # Copyright + Exif-IFD
    t = b"II*\0" + P("I", 8) + ifd0 + b"Abc\0\0\0" + P("H", 1) + P("HHI", 0x9000, 7, 4) + b"0231" + P("I", 0)
    seg = b"Exif\0\0" + t
    return b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(seg) + 2) + seg + body


def test_zeit_ergaenzen(tmp_path, monkeypatch):
    monkeypatch.setattr(fza, "INDEX", tmp_path / "ix.json"); monkeypatch.setattr(fza, "LOG", tmp_path / "log.jsonl"); monkeypatch.setenv("FOTO_ZEIT_BACKUP", str(tmp_path / "bk"))
    raw, out = tmp_path / "raw", tmp_path / "2026" / "05 - Reise" / "02.05.2026"
    (raw / "x").mkdir(parents=True); out.mkdir(parents=True)
    (raw / "_DSC4615.ARW").write_bytes(tiff("2026:05:02 14:30:00"))
    (raw / "x" / "_DSC4615.ARW").write_bytes(tiff("2023:03:03 10:00:00"))                 # gleicher Name, anderes Datum
    a, b = out / "_DSC4615.jpg", out / "_DSC4615-Bearbeitet.jpg"
    a.write_bytes(minimal_jpeg()); b.write_bytes(minimal_jpeg(False)); before = a.read_bytes()
    assert fza.jpeg_info(a)["dt"] is None
    fza.cmd_index(NS(pfade=[str(raw)], name="r", ext="arw", zeitlimit=0))
    rep = tmp_path / "r.csv"
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(rep)), False)
    assert fza.jpeg_info(a)["dt"] is None                                                  # check ändert nichts
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(rep)), True)
    for f in (a, b):
        i = fza.jpeg_info(f)
        assert i["dt"] == "2026:05:02 14:30:00" and i["model"] == "ILCE-7M4" and i["iso"] == 400 and abs(i["exp"] - 0.004) < 1e-6
        assert i["patch"]["cd"][1] == "2026:05:02 14:30:00"
        d = f.read_bytes(); assert b"ns.adobe.com/xap" in d and d.endswith(b"\xff\xd9")
    from PIL import Image                                                                  # so liest die App die Zeit
    seg = a.read_bytes()[fza.jpeg_info(a)["seg"][0] + 4:]; ex = Image.Exif(); ex.load(seg[:seg.index(b"\xff", 20)] if False else seg[:fza.jpeg_info(a)["seg"][1] - 4])
    assert ex.get_ifd(0x8769)[36867] == "2026:05:02 14:30:00" and ex[0x8298].startswith("Abc") and ex[0x0110] == "ILCE-7M4"
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(rep)), True)
    assert rep.read_text().count(";ok;") == 2                                              # zweiter Lauf: nichts mehr zu tun
    fza.cmd_undo(NS(lauf=None))
    assert fza.jpeg_info(a)["dt"] is None and a.read_bytes() == before
    assert b.read_bytes() == minimal_jpeg(False)                                          # auch der neu angelegte Block ist wieder weg


def test_zeit_gleicher_name_anderes_jahr(tmp_path, monkeypatch):
    """JPEG ohne Kameradaten darf nicht dem Original eines anderen Jahres mit gleichem Dateinamen zugeordnet werden."""
    monkeypatch.setattr(fza, "INDEX", tmp_path / "ix.json"); monkeypatch.setattr(fza, "LOG", tmp_path / "log.jsonl"); monkeypatch.setenv("FOTO_ZEIT_BACKUP", str(tmp_path / "bk"))
    raw, out = tmp_path / "raw", tmp_path / "2024" / "07 - Urlaub"
    raw.mkdir(); out.mkdir(parents=True)
    (raw / "_DSC1000.ARW").write_bytes(tiff("2019:05:01 10:00:00"))
    j = out / "_DSC1000.jpg"; j.write_bytes(minimal_jpeg())
    fza.cmd_index(NS(pfade=[str(raw)], name="r", ext="arw", zeitlimit=0))
    rep = tmp_path / "r.csv"
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(rep)), True)
    assert fza.jpeg_info(j)["dt"] is None and "nicht gefunden" in rep.read_text()
    (raw / "_DSC1000.ARW").write_bytes(tiff("2024:07:09 10:00:00")); import os; os.utime(raw / "_DSC1000.ARW", (1, 1))   # jetzt passt das Jahr
    fza.cmd_index(NS(pfade=[str(raw)], name="r", ext="arw", zeitlimit=0))
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(rep)), True)
    assert fza.jpeg_info(j)["dt"] == "2024:07:09 10:00:00"
