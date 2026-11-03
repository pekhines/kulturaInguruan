"""
VISIT NAVARRA: Nafarroako turismoaren "jai eta ekitaldien agenda" (jai handiak, feriak, azokak…).
https://www.visitnavarra.es/es/agenda — orri bakarra, ekitaldi nabarmenak bakarrik.

Txartel bakoitza div.card-plan bat da:
  a[href] · p.fecha ("28 nov - 29 nov", urterik gabe) · p.calendas-title-small · p.location
"""
import re
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from lagungarriak import (GOIBURUAK, HILABETE_LABURDURAK, herria_helbidetik, html_garbitu, kategoria_asmatu,
                          udal_kokapena, urtea_asmatu)

URL = "https://www.visitnavarra.es/es/agenda"


def data_irakurri(testua):
    """'28 nov' → date (urtea gaurtik hurbilena)"""
    m = re.match(r"(\d{1,2})\s+([a-zé]{3})", testua.strip().lower())
    if not m or m.group(2) not in HILABETE_LABURDURAK:
        return None
    return urtea_asmatu(HILABETE_LABURDURAK[m.group(2)], int(m.group(1)))


def ekitaldiak(udalerriak):
    r = requests.get(URL, headers=GOIBURUAK, timeout=30)
    r.raise_for_status()
    gaur = date.today()
    for txartela in BeautifulSoup(r.text, "html.parser").select(".card-plan"):
        esteka = txartela.select_one("a[href]")
        izenburua = txartela.select_one(".calendas-title-small")
        fecha = txartela.select_one(".fecha")
        lekua = txartela.select_one(".location")
        if not (esteka and izenburua and fecha and lekua):
            continue
        zatiak = fecha.get_text(" ", strip=True).split(" - ")
        hasiera, amaiera = data_irakurri(zatiak[0]), data_irakurri(zatiak[-1])
        if not hasiera:
            continue
        if not amaiera or amaiera < hasiera:
            amaiera = hasiera
        if amaiera < gaur or (amaiera - hasiera) > timedelta(days=120):
            continue
        # "Estella-Lizarra"  edo  "Ayuntamiento de Pamplona, Pamplona, Iglesia de San Saturnino"
        lekua = lekua.get_text(" ", strip=True)
        u = udalerriak.bilatu(lekua) or herria_helbidetik(lekua, udalerriak)
        if not u:
            continue
        izena = html_garbitu(izenburua.get_text(" ", strip=True), 200)
        url = esteka["href"].split("?")[0]
        yield {
            "id": "visitnavarra:" + url.rstrip("/").rsplit("/", 1)[-1],
            "iturria": "Visit Navarra",
            "izenburua": izena,
            "kategoria": kategoria_asmatu(izena),
            "mota_jatorrizkoa": "",
            "data_hasiera": hasiera.isoformat(),
            "data_amaiera": amaiera.isoformat(),
            "ordua": "",
            "lekua": "",
            "prezioa": "",
            "deskribapena": "",
            "url": url,
            "irudia": "",
            "kokapenak": [udal_kokapena(u)],
        }
