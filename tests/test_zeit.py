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
    fza.cmd_index(NS(pfade=[str(disk1)], name=None, ext="arw"))
    rep = tmp_path / "r1.csv"
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(rep)), False)
    assert fza.jpeg_info(out / "DSC01234-Bearbeitet.jpg")["dt"] == "2026:10:22 12:34:56"      # check ändert nichts
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(rep)), True)
    assert fza.jpeg_info(out / "DSC01234-Bearbeitet.jpg")["dt"] == "2025:05:01 10:00:00"
    assert fza.jpeg_info(out / "DSC07777.jpg")["dt"] == "2026:10:22 12:00:00"                 # Platte 2 noch nicht eingelesen
    fza.cmd_index(NS(pfade=[str(disk2)], name="P2", ext="arw"))
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
    fza.cmd_index(NS(pfade=[str(d)], name="d", ext="arw"))
    fza.run_check(NS(ordner=str(out), toleranz=1, bericht=str(tmp_path / "r.csv")), True)
    assert fza.jpeg_info(out / "DSC00001.jpg")["dt"] == "2026:01:01 00:00:00" and "mehrdeutig" in (tmp_path / "r.csv").read_text()
