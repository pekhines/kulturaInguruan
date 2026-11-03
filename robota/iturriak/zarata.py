"""
Zarata (MondoSonoro-ren Euskal Herriko edizioa): kontzertuen agenda.
https://www.mondosonoro.com/agenda-zarata/

Orri bakarra da (WordPress), eskuz idatzia baina formatu oso erregularrarekin:

    NOVIEMBRE
    MARTES 3
    <strong>Brilet</strong> Parral · Gasteiz 20:30
    <strong>Eli Paperboy Reed</strong> Dabadaba · Donostia 20:00

Edukia WordPress-en APItik irakurtzen da (orri osoa baino arinagoa). LLMrik ez da behar.
Errioxako kontzertuak (Logroño…) ez dira sartzen: udalerrien zerrendan ez daude.
"""
import re

import requests
from bs4 import BeautifulSoup

from lagungarriak import GOIBURUAK, normalizatu, udal_kokapena, urtea_asmatu

ORRIA = "https://www.mondosonoro.com/agenda-zarata/"
APIA = "https://www.mondosonoro.com/wp-json/wp/v2/pages/380570"

HILABETEAK = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
              "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
EGUNA = re.compile(r"(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(\d{1,2})")
ORDUA = re.compile(r"(?:^|\s)(\d{1,2})[:.](\d{2})\s*h?$")


def ekitaldiak(udalerriak):
    r = requests.get(APIA, params={"_fields": "content,modified"}, headers=GOIBURUAK, timeout=60)
    r.raise_for_status()
    edukia = r.json()["content"]["rendered"]
    hilabetea = eguna = None
    ikusiak = set()
    for p in BeautifulSoup(edukia, "html.parser").find_all("p"):
        for zatia in re.split(r"<br\s*/?>", p.decode_contents()):
            if "</strong>" in zatia and "<strong" not in zatia:  # "<strong>LUNES 9<br/>Garazi Esnaola</strong> Fnac…"
                zatia = "<strong>" + zatia
            lerroa = BeautifulSoup(zatia, "html.parser")
            testua = re.sub(r"\s+", " ", lerroa.get_text(" ")).strip()
            n = normalizatu(testua)
            if not n:
                continue
            if n in HILABETEAK:
                hilabetea, eguna = HILABETEAK[n], None
                continue
            m = EGUNA.fullmatch(n)
            if m:
                eguna = int(m.group(2))
                continue
            if not hilabetea or not eguna:
                continue
            e = bihurtu(lerroa, testua, hilabetea, eguna, udalerriak)
            if e and e["id"] not in ikusiak:
                ikusiak.add(e["id"])
                yield e


def herria_bilatu(herria, udalerriak):
    """'Maule' → Maule-Lextarre (izen ofizial luzearen lehen zatia bakarrik idazten dute batzuetan)."""
    if not herria or re.search(r"suspendido|aplazado|cancelado", herria, re.I):
        return None
    u = udalerriak.bilatu(herria)
    if u:
        return u
    gakoa = normalizatu(herria) + " "
    hautagaiak = {id(x): x for k, v in udalerriak.izenez.items() if k.startswith(gakoa)
                  for x in v if x.get("mota") == "udalerria"}
    return next(iter(hautagaiak.values())) if len(hautagaiak) == 1 else None


def bihurtu(lerroa, testua, hilabetea, eguna, udalerriak):
    """'<strong>Brilet</strong> Parral · Gasteiz 20:30' → ekitaldia."""
    lodiak = lerroa.find_all("strong")
    if not lodiak:
        return None
    izenburua = re.sub(r"\s+", " ", " ".join(s.get_text(" ") for s in lodiak)).strip()
    gainerakoa = testua[len(izenburua):].strip() if testua.startswith(izenburua) else testua
    ordua = ""
    m = ORDUA.search(gainerakoa)
    if m:
        ordua = f"{int(m.group(1)):02d}:{m.group(2)}"
        gainerakoa = gainerakoa[: m.start()].strip()
    if "·" in gainerakoa:
        lekua, herria = [x.strip() for x in gainerakoa.rsplit("·", 1)]
    else:  # aretorik gabe: "AMUA Jaialdia: El Combo Batanga</strong> Hondarribia 22:00"
        lekua, herria = "", gainerakoa
    u = herria_bilatu(herria, udalerriak)
    if not u or not izenburua:
        return None
    data = urtea_asmatu(hilabetea, eguna)
    if not data:
        return None
    data = data.isoformat()
    return {
        "id": f"zarata:{data}:{normalizatu(u['izena'])}:{normalizatu(izenburua)[:60]}".replace(" ", "-"),
        "iturria": "Zarata (MondoSonoro)",
        "izenburua": izenburua,
        "kategoria": "musika",
        "data_hasiera": data,
        "data_amaiera": data,
        "ordua": ordua,
        "lekua": lekua,
        "prezioa": "",
        "deskribapena": "",
        "url": ORRIA,
        "irudia": "",
        "kokapenak": [udal_kokapena(u)],
    }
