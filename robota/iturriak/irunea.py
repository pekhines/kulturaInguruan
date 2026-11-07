"""
IRUÑEKO UDALA: udalaren ekitaldi-zerrenda (Drupal), euskaraz.
https://www.pamplona.es/eu/gaurkotasuna/ekitaldiak?page=0,1,2…

Ekitaldi bakoitza "layout__region--first" bloke bat da:
  h3 a (izenburua) · time[datetime] bat edo bi (hasiera / amaiera)
  field-event-info (lekua) · field-theme (gaia: Kultura, Kirola…)
"""
import time
from datetime import date, datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from lagungarriak import eskuratu, html_garbitu, kategoria_asmatu, udal_kokapena

URL = "https://www.pamplona.es/eu/gaurkotasuna/ekitaldiak"
GEHIENEZ_ORRIAK = 30
GEHIENEZKO_IRAUPENA = 120
# Webguneak ausaz 502 ematen du (eskaeren erdiak inoiz, 2026-11-07): saiakera asko, itxaronaldi laburrak
SAIAKERAK = 6
HUTSEN_MUGA = 3  # jarraian huts egiten duten orriak: webgunea benetan erorita dago


def ekitaldiak(udalerriak):
    irunea = udalerriak.bilatu("Iruñea")
    gaur = date.today()
    ikusiak = set()
    hutsak_jarraian = 0
    for orria in range(GEHIENEZ_ORRIAK):
        try:
            r = eskuratu(URL, params={"page": orria}, saiakerak=SAIAKERAK, itxaronaldia=2)
        except requests.HTTPError as errorea:
            if errorea.response is None or errorea.response.status_code < 500:
                raise
            hutsak_jarraian += 1
            if hutsak_jarraian >= HUTSEN_MUGA:
                raise
            print(f"  ! Iruñea: {orria}. orria saltatuta ({errorea.response.status_code})", flush=True)
            continue
        hutsak_jarraian = 0
        blokeak = [b for b in BeautifulSoup(r.text, "html.parser").select(".layout__region--first")
                   if b.select_one("h3 a") and b.select_one("time[datetime]")]
        if not blokeak:
            break
        berriak = 0
        for b in blokeak:
            esteka = b.select_one("h3 a")
            url = urljoin(URL, esteka["href"])
            if url in ikusiak:
                continue
            ikusiak.add(url)
            berriak += 1
            datak = [datetime.fromisoformat(t["datetime"].replace("Z", "+00:00")).date()
                     for t in b.select("time[datetime]")]
            hasiera, amaiera = datak[0], datak[-1]
            if amaiera < gaur or (amaiera - hasiera).days > GEHIENEZKO_IRAUPENA:
                continue
            lekua = b.select_one(".field--name-field-event-info .field--item")
            gaia = b.select_one(".field--name-field-theme")
            gaia = gaia.get_text(" ", strip=True) if gaia else ""
            if gaia and "Kultura" not in gaia and "Jaiak" not in gaia and "Gazteria" not in gaia:
                continue  # kirol-lehiaketak, osasun-kanpainak… ez
            izenburua = html_garbitu(esteka.get_text(" ", strip=True), 200)
            if izenburua.isupper():
                izenburua = izenburua.capitalize()  # "ANTZERKI AROA" → "Antzerki aroa"
            yield {
                "id": "irunea:" + url.rstrip("/").rsplit("/", 1)[-1],
                "iturria": "Iruñea (udala)",
                "izenburua": izenburua,
                "kategoria": kategoria_asmatu(izenburua),
                "mota_jatorrizkoa": gaia,
                "data_hasiera": hasiera.isoformat(),
                "data_amaiera": amaiera.isoformat(),
                "ordua": "",
                "lekua": html_garbitu(lekua.get_text(" ", strip=True) if lekua else "", 80),
                "prezioa": "",
                "deskribapena": "",
                "url": url,
                "irudia": "",
                "kokapenak": [udal_kokapena(irunea)],
            }
        if not berriak:
            break  # orri berbera errepikatzen bada (azken orritik aurrera), gelditu
        time.sleep(1)
