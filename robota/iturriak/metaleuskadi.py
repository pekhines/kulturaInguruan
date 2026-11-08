"""
METAL EUSKADI: metal eta rock gogorreko kontzertuen agenda, lurraldeka (gaztetxe askotan).
https://www.metaleuskadi.com/agenda-araba-fecha/ (eta bizkaia, gipuzkoa, nafarroa, ipar-euskal-herria)

Lurralde bakoitzeko taula bat, errenkada bikoitzekin:
    | 14/11/26            | Girls On Fire Rock Fest | Gasteiz, Araba | Gasteiz Urban Rock Concept |
    |                     | Hora: 8:30pm. Dirección: Gamarrako Atea, 1 …                     |
Data tarte bat ere izan daiteke: "20/11/26 - 21/11/26". LLMrik ez da behar.
"""
import re
import time
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from iturriak.zarata import herria_bilatu
from lagungarriak import GOIBURUAK, html_garbitu, normalizatu, udal_kokapena

LURRALDEAK = ["araba", "bizkaia", "gipuzkoa", "nafarroa", "ipar-euskal-herria"]
URL = "https://www.metaleuskadi.com/agenda-{}-fecha/"
DATA = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
ORDUA = re.compile(r"Hora:\s*(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?", re.I)


def _data(testua):
    m = DATA.search(testua)
    if not m:
        return None
    eguna, hila, urtea = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(urtea + 2000 if urtea < 100 else urtea, hila, eguna)
    except ValueError:
        return None


def _ordua(testua):
    m = ORDUA.search(testua or "")
    if not m:
        return ""
    h, mm = int(m.group(1)), int(m.group(2) or 0)
    if (m.group(3) or "").lower() == "pm" and h < 12:
        h += 12
    return f"{h:02d}:{mm:02d}" if h < 24 else ""


def ekitaldiak(udalerriak):
    gaur = date.today()
    ikusiak = set()
    for lurraldea in LURRALDEAK:
        orria = URL.format(lurraldea)
        r = requests.get(orria, headers=GOIBURUAK, timeout=30)
        r.raise_for_status()
        errenkadak = BeautifulSoup(r.text, "html.parser").select("table tr")
        for i, er in enumerate(errenkadak):
            gelaxkak = [re.sub(r"\s+", " ", g.get_text(" ", strip=True)) for g in er.select("td")]
            if len(gelaxkak) < 4 or not DATA.search(gelaxkak[0]):
                continue
            datak = DATA.findall(gelaxkak[0])
            hasiera = _data(gelaxkak[0])
            amaiera = _data("/".join(datak[-1])) if len(datak) > 1 else hasiera
            if not hasiera or (amaiera or hasiera) < gaur:
                continue
            taldeak, hiria, lekua = gelaxkak[1], gelaxkak[2], gelaxkak[3]
            # Azpiko errenkada: "Hora: 8:30pm. Dirección: …"
            xehetasunak = ""
            if i + 1 < len(errenkadak):
                xehetasunak = errenkadak[i + 1].get_text(" ", strip=True)
            u = herria_bilatu(hiria.split(",")[0].strip(), udalerriak)
            if not u or not taldeak:
                continue
            gakoa = f"{hasiera}:{normalizatu(u['izena'])}:{normalizatu(taldeak)[:60]}".replace(" ", "-")
            if gakoa in ikusiak:
                continue
            ikusiak.add(gakoa)
            yield {
                "id": "metaleuskadi:" + gakoa,
                "iturria": "Metal Euskadi",
                "izenburua": html_garbitu(taldeak, 200),
                "kategoria": "musika",
                "data_hasiera": hasiera.isoformat(),
                "data_amaiera": (amaiera or hasiera).isoformat(),
                "ordua": _ordua(xehetasunak),
                "lekua": html_garbitu(lekua, 80),
                "prezioa": "",
                "deskribapena": "",
                "url": orria,
                "irudia": "",
                "kokapenak": [udal_kokapena(u)],
            }
        time.sleep(1)
