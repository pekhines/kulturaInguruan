"""
CULTURA NAVARRA: Nafarroako Gobernuaren Kultura Zuzendaritzaren agenda
(liburutegiak, museoak, Kultur programa herrietan, erakusketak…).

Hilabete bakoitzak bere orria du: https://www.culturanavarra.es/es/agenda/2026-11
Ekitaldi bakoitza <div class="agenda_evento"> bat da:
  h3 = mota · span.fecha = "22/11/2026" edo "19/06/2026 - 13/12/2026" · h4 a = izenburua
  .localidad = "Tafalla - Centro Cultural / Kultur Gunea"  edo  "TUDELA"
OHARRA: webguneak bilatzaileentzako erabilera onartzen du (robots.txt: search=yes), baina ez
adimen artifiziala entrenatzeko. Horregatik HTMLa zuzenean irakurtzen dugu, LLMrik gabe,
eta beti estekatzen dugu jatorrizko orrira.
"""
import re
import time
from datetime import date, datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from lagungarriak import GOIBURUAK, herriak_testuan, html_garbitu, kategoria_asmatu, udal_kokapena

OINARRIA = "https://www.culturanavarra.es/"
HILABETEAK_AURRERA = 5
# Herririk aipatzen ez duten Iruñeko egoitza ezagunak
IRUÑEKO_EGOITZAK = ("biblioteca de navarra", "archivo real", "baluarte", "museo de navarra",
                    "palacio del condestable", "civivox", "planetario", "filmoteca de navarra")
GEHIENEZKO_IRAUPENA = 120
# Webgunearen motak (h3) → gure kategoriak; zerrendan ez badago, testutik asmatzen da
MOTAK = {
    "Conciertos": "musika", "Música": "musika", "Exposiciones": "erakusketa",
    "Arte contemporáneo": "erakusketa", "Charlas y conferencias": "hitzaldia",
    "Presentación": "hitzaldia", "Taller": "ikastaroa", "Teatro": "antzerkia",
    "Danza": "dantza", "Cine": "zinema", "Infantil": "haurrak",
}


def _data(testua):
    return datetime.strptime(testua.strip(), "%d/%m/%Y").date()


def _herria(lekua, udalerriak):
    """'Estella / Lizarra - Espacio Cultural Los Llanos' → Lizarra"""
    lehena = lekua.split(" - ")[0].strip()
    u = udalerriak.bilatu(lehena)
    if u:
        return u
    aurkituak = herriak_testuan(lekua, udalerriak)
    if aurkituak:
        return aurkituak[0]
    if any(e in lekua.lower() for e in IRUÑEKO_EGOITZAK):
        return udalerriak.bilatu("Iruña")
    return None


def hilabeteak():
    gaur = date.today()
    urtea, hila = gaur.year, gaur.month
    for _ in range(HILABETEAK_AURRERA):
        yield f"{urtea}-{hila:02d}"
        hila += 1
        if hila > 12:
            urtea, hila = urtea + 1, 1


def ekitaldiak(udalerriak):
    gaur = date.today()
    ikusiak = set()
    for hilabetea in hilabeteak():
        r = requests.get(f"{OINARRIA}es/agenda/{hilabetea}", headers=GOIBURUAK, timeout=30)
        r.raise_for_status()
        r.encoding = "iso-8859-1"
        soup = BeautifulSoup(r.text, "html.parser")
        for ev in soup.select(".agenda_evento"):
            esteka, data = ev.select_one("h4 a"), ev.select_one(".fecha")
            if not esteka or not data:
                continue
            url = urljoin(OINARRIA, esteka["href"])
            if url in ikusiak:
                continue  # hilabete batetik bestera irauten dutenak behin bakarrik
            ikusiak.add(url)
            try:
                zatiak = data.get_text().split(" - ")
                hasiera, amaiera = _data(zatiak[0]), _data(zatiak[-1])
            except ValueError:
                continue
            if amaiera < gaur or (amaiera - hasiera).days > GEHIENEZKO_IRAUPENA:
                continue
            lekua = html_garbitu(ev.select_one(".localidad").get_text(" ", strip=True) if ev.select_one(".localidad") else "", 120)
            u = _herria(lekua, udalerriak)
            if not u:
                continue
            izenburua = html_garbitu(esteka.get_text(" ", strip=True), 200)
            mota = ev.select_one("h3").get_text(strip=True) if ev.select_one("h3") else ""
            sarrera = ev.select_one(".entradilla")
            sarrera = html_garbitu(sarrera.get_text(" ", strip=True) if sarrera else "")
            yield {
                "id": "culturanavarra:" + url.rsplit("/agenda/", 1)[-1],
                "iturria": "Cultura Navarra",
                "izenburua": izenburua,
                "kategoria": MOTAK.get(mota) or kategoria_asmatu(izenburua + " " + mota, sarrera),
                "mota_jatorrizkoa": mota,
                "data_hasiera": hasiera.isoformat(),
                "data_amaiera": amaiera.isoformat(),
                "ordua": "",
                "lekua": re.sub(r"^[^-]*-\s*", "", lekua) if " - " in lekua else "",
                "prezioa": "",
                "deskribapena": sarrera,
                "url": url,
                "irudia": "",
                "kokapenak": [udal_kokapena(u)],
            }
        time.sleep(1)
