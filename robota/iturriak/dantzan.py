"""
DANTZAN.EUS: euskal dantzaren agenda (ikuskizunak, dantza-plazak, topaketak, erakusketak…).

Agenda osoa orri bakarrean dago: https://dantzan.eus/agenda
Ekitaldi bakoitza <article class="event-item"> bat da:
  - izenburua eta esteka:  h2 a
  - hasiera / amaiera:     abbr.dtstart / abbr.dtend  (title="2026-11-04T18:30:00+01:00")
  - lekua:                 [itemprop=location]  →  "Herria, Lekua"
(robots.txt-ek iCal esportazioa debekatzen du; horregatik HTML orria irakurtzen dugu.)
"""
from datetime import date, datetime

from bs4 import BeautifulSoup

from lagungarriak import eskuratu, html_garbitu, kategoria_asmatu, udal_kokapena

URL = "https://dantzan.eus/agenda"
GEHIENEZKO_IRAUPENA = 120  # egunak; luzeagoak (urte osoko zikloak…) ez ditugu sartzen


def _data(abbr):
    try:
        return datetime.fromisoformat(abbr["title"]) if abbr and abbr.get("title") else None
    except ValueError:
        return None


def ekitaldiak(udalerriak):
    r = eskuratu(URL)  # 429 (eskaera gehiegi) bada, itxaron eta berriz saiatzen da
    soup = BeautifulSoup(r.text, "html.parser")
    gaur = date.today()

    for art in soup.select("article.event-item"):
        esteka = art.select_one("h2 a")
        hasi = _data(art.select_one(".dtstart"))
        if not esteka or not hasi:
            continue
        amai = _data(art.select_one(".dtend")) or hasi
        if amai.date() < gaur or (amai.date() - hasi.date()).days > GEHIENEZKO_IRAUPENA:
            continue

        # "Elgoibar, Kultur Etxeko hitzaldi-gela" → herria = Elgoibar, lekua = gainerakoa
        non = art.select_one('[itemprop="location"]')
        herria, _, lekua = (non.get_text(" ", strip=True) if non else "").partition(",")
        u = udalerriak.bilatu(herria.strip()) if herria.strip() else None
        if not u:
            continue  # lekurik gabe ezin dugu mapan jarri

        izenburua = html_garbitu(esteka.get_text(" ", strip=True), 200)
        kategoria = kategoria_asmatu(izenburua)
        if kategoria == "bestelakoa":
            kategoria = "dantza"  # dantza-agenda bat da: zalantzan, dantza

        yield {
            "id": "dantzan:" + esteka["href"].rstrip("/").rsplit("/", 1)[-1] + ":" + hasi.date().isoformat(),
            "iturria": "Dantzan.eus",
            "izenburua": izenburua,
            "kategoria": kategoria,
            "mota_jatorrizkoa": "dantza",
            "data_hasiera": hasi.date().isoformat(),
            "data_amaiera": amai.date().isoformat(),
            "ordua": hasi.strftime("%H:%M") if hasi.strftime("%H:%M") != "00:00" else "",
            "lekua": html_garbitu(lekua.strip(), 80),
            "prezioa": "",
            "deskribapena": "",
            "url": esteka["href"],
            "irudia": "",
            "kokapenak": [udal_kokapena(u)],
        }
