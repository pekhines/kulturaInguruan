"""
Euskal Kultur Erakundea (EKE): Ipar Euskal Herriko euskal kulturaren agenda.
https://www.eke.eus/eu/agenda

Ez du API publikorik; HTML orria irakurtzen dugu (16 ekitaldi orriko).
Ekitaldi batek herri bat baino gehiago izan ditzake (adib. antzerki zikloak).
"""
import re
import time

import requests
from bs4 import BeautifulSoup

from lagungarriak import GOIBURUAK

URLA = "https://www.eke.eus/eu/agenda"
ORRIKO = 16
GEHIENEZ_ORRIAK = 30  # babesa: inoiz ez begizta amaigabean

# EKE-ren kategoriak -> gure kategoriak
MOTAK = {
    "kontzertuak": "musika",
    "ikuskizunak": "antzerkia",
    "bertso saioak": "bertsolaritza",
    "ekitaldiak & festibalak": "jaialdia",
    "erakusketak": "erakusketa",
    "film emanaldiak": "zinema",
    "gertakari erritualak": "jaiak",
    "hitzaldiak": "hitzaldia",
    "aurkezpenak": "hitzaldia",
    "animazioak": "haurrak",
    "ikastaroak & formakuntzak": "ikastaroa",
    "omenaldiak": "bestelakoa",
}


def ekitaldiak(udalerriak):
    for orria in range(GEHIENEZ_ORRIAK):
        r = requests.get(URLA, params={"b_start:int": orria * ORRIKO},
                         headers=GOIBURUAK, timeout=60)
        r.raise_for_status()
        elementuak = BeautifulSoup(r.text, "html.parser").select("div.event-item")
        if not elementuak:
            break
        for el in elementuak:
            ekitaldia = bihurtu(el, udalerriak)
            if ekitaldia:
                yield ekitaldia
        if len(elementuak) < ORRIKO:
            break
        time.sleep(1)


def bihurtu(el, udalerriak):
    izenburua = el.select_one("h3.event-title a")
    data = el.select_one(".event-date")
    if not izenburua or not data:
        return None

    datak = re.findall(r"\d{4}/\d{2}/\d{2}", data.get_text())
    if not datak:
        return None
    datak = [d.replace("/", "-") for d in datak]

    kokapenak = []
    for herria in el.select(".event-place span"):
        u = udalerriak.bilatu(herria.get_text(strip=True))
        if u:
            kokapenak.append({"herria": u["izena"], "lurraldea": u["lurraldea"],
                              "lat": u["lat"], "lon": u["lon"]})
    if not kokapenak:
        return None

    kategoria = el.select_one("nav.category li")
    mota = kategoria.get_text(strip=True) if kategoria else ""
    irudia = el.select_one("img")
    url = izenburua["href"]

    return {
        "id": "eke:" + url.rstrip("/").rsplit("/", 1)[-1],
        "iturria": "EKE",
        "izenburua": izenburua.get_text(strip=True),
        "kategoria": MOTAK.get(mota.lower(), "bestelakoa"),
        "mota_jatorrizkoa": mota,
        "data_hasiera": datak[0],
        "data_amaiera": datak[-1],
        "ordua": "",
        "lekua": "",
        "prezioa": "",
        "deskribapena": "",
        "url": url,
        "irudia": irudia["src"] if irudia else "",
        "kokapenak": kokapenak,
    }
