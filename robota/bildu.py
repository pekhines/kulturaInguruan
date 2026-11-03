"""
ROBOTA: iturri guztietatik ekitaldiak bildu, datu-basean gorde eta webarentzat esportatu.

Exekutatu:
    python robota/bildu.py

Pausoak:
  1. Iturri bakoitza irakurri (bat hausten bada, besteek aurrera jarraitzen dute)
  2. SQLite datu-basean gorde (datuak/ekitaldiak.db)
  3. Iraganeko ekitaldiak ezabatu
  4. Bikoiztuak bateratu (robota/bateratu.py) eta docs/datuak/ekitaldiak.json idatzi
     (frontendak hau irakurtzen du)

ITURRI BERRI bat gehitzeko: robota/iturriak/ karpetan fitxategi bat sortu
`ekitaldiak(udalerriak)` funtzio batekin, eta ITURRIAK zerrendan gehitu.
"""
import json
import sqlite3
import sys
import traceback
from collections import Counter
from datetime import date, datetime, timezone

from bateratu import bateratu
from lagungarriak import ERROA, Udalerriak, hizkuntza_asmatu, normalizatu
from iturriak import (culturanavarra, dantzan, eke, elkarte_agendak, iparralde_turismoa, irunea, kulturklik,
                      llm_agendak, tokikom, turismoa, udal_agendak, visitnavarra, zarata, zernonikusi)

# Ordena garrantzitsua da: bikoiztuetan, lehenengo iturriarena gordetzen da
# (datu egituratuak lehenengo, LLM bidez ateratakoak azkenik)
ITURRIAK = [
    ("Kulturklik", kulturklik),
    ("Tokikom", tokikom),
    ("Udal agendak", udal_agendak),
    ("Iruñea (udala)", irunea),
    ("Elkarte agendak", elkarte_agendak),
    ("EKE", eke),
    ("Dantzan.eus", dantzan),
    ("Cultura Navarra", culturanavarra),
    ("Pays Basque turismoa", iparralde_turismoa),
    ("Visit Navarra", visitnavarra),
    ("Zarata", zarata),
    ("Pantailak Euskaraz", zernonikusi),
    ("Agenda Turistikoa", turismoa),
    ("LLM agendak", llm_agendak),
]

# Webguneko "Iturriak" iragazkirako taldeak (bilduma → taldea)
TALDEAK = {
    "Kulturklik": "kulturklik",
    "Tokikom": "hedabideak",
    "Udal agendak": "udalak", "Iruñea (udala)": "udalak",
    "Elkarte agendak": "elkarteak",
    # Iturri espezializatuak: bakoitzak bere txipa webgunean
    "EKE": "eke", "Dantzan.eus": "dantzan", "Cultura Navarra": "culturanavarra",
    "Pantailak Euskaraz": "pantailak", "Zarata": "zarata",
    "Pays Basque turismoa": "turismoa", "Visit Navarra": "turismoa", "Agenda Turistikoa": "turismoa",
}


def taldea(bilduma, iturria):
    if iturria.endswith("(udala)"):  # udal baten agenda, edozein irakurlerekin irakurrita
        return "udalak"
    if bilduma == "LLM agendak":
        return "elkarteak"
    return TALDEAK.get(bilduma, "elkarteak")


DB = ERROA / "datuak" / "ekitaldiak.db"
JSON_IRTEERA = ERROA / "docs" / "datuak" / "ekitaldiak.json"


def db_ireki():
    DB.parent.mkdir(exist_ok=True)
    berria = not DB.exists()
    konexioa = sqlite3.connect(DB)
    konexioa.execute("""
        CREATE TABLE IF NOT EXISTS ekitaldiak (
            id TEXT PRIMARY KEY,
            iturria TEXT NOT NULL,
            data_hasiera TEXT NOT NULL,
            data_amaiera TEXT NOT NULL,
            datuak TEXT NOT NULL,          -- ekitaldi osoa JSON gisa
            lehen_ikusia TEXT NOT NULL,
            azken_ikusia TEXT NOT NULL
        )""")
    if berria and JSON_IRTEERA.exists():
        # Datu-basea ez dago (adib. GitHub Actions-en): aurreko esportaziotik berreraiki,
        # iturri bat hausten bada aurreko datuak gal ez daitezen
        aurrekoak = json.loads(JSON_IRTEERA.read_text(encoding="utf-8"))
        for e in aurrekoak["ekitaldiak"]:
            for eremua in ("beste_iturriak", "taldeak"):  # bateratzean sortuak; berriro kalkulatzen dira
                e.pop(eremua, None)
            konexioa.execute("INSERT OR IGNORE INTO ekitaldiak VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (e["id"], e.get("bilduma", e["iturria"]), e["data_hasiera"], e["data_amaiera"],
                              json.dumps(e, ensure_ascii=False), aurrekoak["sortua"], aurrekoak["sortua"]))
        konexioa.commit()
    return konexioa


def iturria_bildu(konexioa, izena, modulua, udalerriak, orain):
    n = 0
    for e in modulua.ekitaldiak(udalerriak):
        # "bilduma" = robotaren iturria (adib. "Tokikom"); "iturria" = jatorria (adib. "Goiena").
        # JSONean gordetzen da, datu-basea JSONetik berreraikitzean (GitHub-en) iturri bakoitzaren
        # ekitaldi zaharrak ondo ezabatzeko.
        e["bilduma"] = izena
        konexioa.execute("""
            INSERT INTO ekitaldiak VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                iturria=excluded.iturria,
                data_hasiera=excluded.data_hasiera, data_amaiera=excluded.data_amaiera,
                datuak=excluded.datuak, azken_ikusia=excluded.azken_ikusia""",
            (e["id"], izena, e["data_hasiera"], e["data_amaiera"],
             json.dumps(e, ensure_ascii=False), orain, orain))
        n += 1
    # Iturrian jada agertzen ez diren etorkizuneko ekitaldiak (bertan behera utziak?) kendu
    konexioa.execute("DELETE FROM ekitaldiak WHERE iturria=? AND azken_ikusia<>?", (izena, orain))
    konexioa.commit()
    return n


def bikoiztuak_kendu(ekitaldiak):
    """Izenburu bera + hasiera-data bera + herri bera = ekitaldi bera (zehatz-mehatz).
    Antzekoak (izen desberdin samarrarekin) gero bateratzen dira: ikus bateratu.py."""
    ikusiak, emaitza = {}, []
    for e in ekitaldiak:
        gakoa = (normalizatu(e["izenburua"]), e["data_hasiera"], e["kokapenak"][0]["herria"])
        if gakoa not in ikusiak:
            ikusiak[gakoa] = e
            emaitza.append(e)
        else:  # iturria gorde, webguneak esteka erakusteko
            ikusiak[gakoa].setdefault("_bikoiztuak", []).append(e)
    return emaitza


def esportatu(konexioa):
    gaur = date.today().isoformat()
    konexioa.execute("DELETE FROM ekitaldiak WHERE data_amaiera < ?", (gaur,))
    konexioa.commit()

    ordena = {izena: i for i, (izena, _) in enumerate(ITURRIAK)}
    errenkadak = konexioa.execute("SELECT iturria, datuak FROM ekitaldiak").fetchall()
    errenkadak.sort(key=lambda r: ordena.get(r[0], 99))
    ekitaldiak = bikoiztuak_kendu([{**json.loads(d), "bilduma": i} for i, d in errenkadak])
    ekitaldiak = bateratu(ekitaldiak)
    for e in ekitaldiak:
        e["taldea"] = taldea(e["bilduma"], e["iturria"])
        # Batutako ekitaldiak iturri-talde guztietan agertzen dira (adib. Kulturklik + Pantailak Euskaraz)
        taldeak = [e["taldea"]]
        for b in e.get("beste_iturriak", []):
            t = taldea(b.pop("bilduma"), b["iturria"])
            if t not in taldeak:
                taldeak.append(t)
        if len(taldeak) > 1:
            e["taldeak"] = taldeak
        if not e.get("hizkuntza"):
            e["hizkuntza"] = hizkuntza_asmatu(e["izenburua"], e.get("deskribapena"), e.get("mota_jatorrizkoa"))
        if not e["hizkuntza"] and e["kategoria"] == "bertsolaritza":
            e["hizkuntza"] = "eu"
    ekitaldiak.sort(key=lambda e: (e["data_hasiera"], e["izenburua"]))

    JSON_IRTEERA.write_text(json.dumps({
        "sortua": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ekitaldiak": ekitaldiak,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return ekitaldiak


def main():
    udalerriak = Udalerriak()
    konexioa = db_ireki()
    orain = datetime.now(timezone.utc).isoformat(timespec="seconds")
    hutsak = []

    # Iturri batzuk bakarrik:   python robota/bildu.py Dantzan.eus EKE
    # Iturri batzuk izan ezik:  python robota/bildu.py --salbu "LLM agendak"
    # (exekutatzen ez diren iturrien datuak datu-basean geratzen dira, ez dira ukitzen)
    argumentuak = sys.argv[1:]
    salbuak = set()
    if "--salbu" in argumentuak:
        i = argumentuak.index("--salbu")
        salbuak = {a.lower() for a in argumentuak[i + 1:]}
        argumentuak = argumentuak[:i]
    hautatuak = {a.lower() for a in argumentuak}
    izenak = {i.lower() for i, _ in ITURRIAK}
    if (hautatuak | salbuak) - izenak:
        sys.exit("Ez dago izen horretako iturririk: " + ", ".join((hautatuak | salbuak) - izenak)
                 + "\nAukerak: " + ", ".join(i for i, _ in ITURRIAK))
    iturriak = [(i, m) for i, m in ITURRIAK
                if (not hautatuak or i.lower() in hautatuak) and i.lower() not in salbuak]

    for izena, modulua in iturriak:
        print(f"→ {izena}…", flush=True)
        try:
            n = iturria_bildu(konexioa, izena, modulua, udalerriak, orain)
            print(f"  {n} ekitaldi")
        except Exception:
            # Iturri bat hausten bada, aurreko datuak mantentzen dira eta besteekin jarraitzen da
            konexioa.rollback()
            hutsak.append(izena)
            print(f"  ✗ ERROREA {izena} iturrian (aurreko datuak mantentzen dira):")
            traceback.print_exc()

    ekitaldiak = esportatu(konexioa)
    print(f"\n{len(ekitaldiak)} ekitaldi esportatuta → {JSON_IRTEERA.relative_to(ERROA)}")
    lurraldeak = Counter(e["kokapenak"][0]["lurraldea"] or "?" for e in ekitaldiak)
    for lurraldea, n in lurraldeak.most_common():
        print(f"  {lurraldea}: {n}")
    print("Kategoriak:", dict(Counter(e["kategoria"] for e in ekitaldiak).most_common()))

    if hutsak:
        print("\nHautsitako iturriak:", ", ".join(hutsak))
        sys.exit(1)  # GitHub Actions-ek abisua emateko


if __name__ == "__main__":
    main()
