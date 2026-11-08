"""
MUSIKA ZUZENEAN: euskal musikaren kontzertu-agenda, Euskal Herri osoa (gaztetxeak, tabernak,
kultur etxeak, jaialdiak…). Taldeek eta antolatzaileek beraiek igotzen dituzte kontzertuak.
https://musikazuzenean.eus/  (orrikatzea: /page/2/, /page/3/…)

Zerrenda kronologikoa da, data-blokeetan:
    <div class="events__date"> Igandea GAUR 08 Aza </div>
    <div class="event__card">
        .event__bands  → taldeak ("Añube")
        .event__where  → "ABADIÑO (BIZKAIA)"
        .event__info   → lekua ("Amaraun Arte Fabrika")
Orduak fitxan bakarrik daude (ez dira irakurtzen, eskaera gehiegi lirateke). LLMrik ez da behar.
"""
import re
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from iturriak.zarata import herria_bilatu
from lagungarriak import GOIBURUAK, HILABETE_LABURDURAK, html_garbitu, normalizatu, udal_kokapena

URL = "https://musikazuzenean.eus/"
GEHIENEZ_ORRIAK = 25
HORIZONTEA = timedelta(days=365)
IRUDIA = re.compile(r"url\((['\"]?)(.+?)\1\)")


def orria(n):
    r = requests.get(URL if n == 1 else f"{URL}page/{n}/", headers=GOIBURUAK, timeout=30)
    if r.status_code == 404:
        return None  # orririk ez: amaiera
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def herria_atera(testua, udalerriak):
    """'ERRENTERIA/ORERETA (GIPUZKOA)' → Errenteria. Izen elebidunetan, zati bakoitza probatu."""
    izena = re.sub(r"\s*\(.*?\)\s*$", "", testua or "").strip()
    for zatia in [izena] + [z.strip() for z in re.split(r"[/-]", izena) if z.strip()]:
        u = herria_bilatu(zatia.title(), udalerriak)
        if u:
            return u
    return None


def ekitaldiak(udalerriak):
    gaur = date.today()
    urtea, aurreko_hila = gaur.year, gaur.month
    ikusiak = set()
    for n in range(1, GEHIENEZ_ORRIAK + 1):
        soup = orria(n)
        if soup is None:
            break
        blokeak = [d.parent for d in soup.select(".events__date")]
        if not blokeak:
            break
        for blokea in blokeak:
            eguna = blokea.select_one(".events__date-calendar-day")
            hila = blokea.select_one(".events__date-calendar-month")
            hilabetea = HILABETE_LABURDURAK.get(normalizatu(hila.get_text())[:3]) if hila else None
            if hila and normalizatu(hila.get_text()).startswith("abn"):
                hilabetea = 12  # "Abn" = abendua
            if not eguna or not hilabetea or not eguna.get_text(strip=True).isdigit():
                continue
            # Zerrenda kronologikoa da: hilabeteak atzera egiten badu, urte berria
            if hilabetea < aurreko_hila:
                urtea += 1
            aurreko_hila = hilabetea
            try:
                data = date(urtea, hilabetea, int(eguna.get_text(strip=True)))
            except ValueError:
                continue
            if data > gaur + HORIZONTEA:
                return
            if data < gaur:
                continue
            for txartela in blokea.select(".event__card"):
                e = bihurtu(txartela, data, udalerriak)
                if e and e["id"] not in ikusiak:
                    ikusiak.add(e["id"])
                    yield e
        time.sleep(1)


def bihurtu(txartela, data, udalerriak):
    taldeak = txartela.select_one(".event__bands")
    esteka = txartela.select_one(".event__bands a[href]") or txartela.select_one("a[href]")
    if not taldeak or not esteka:
        return None
    izenburua = html_garbitu(taldeak.get_text(" ", strip=True), 200)
    lekua_el = txartela.select_one(".event__info")
    lekua = re.sub(r"\s+", " ", lekua_el.get_text(" ", strip=True)) if lekua_el else ""
    where = txartela.select_one(".event__where")
    u = herria_atera(where.get_text(" ", strip=True) if where else "", udalerriak)
    if not u or not izenburua:
        return None
    irudia = ""
    irudi_el = txartela.select_one("[data-bg-image]")
    if irudi_el:
        m = IRUDIA.search(irudi_el["data-bg-image"])
        irudia = m.group(2) if m else ""
    url = esteka["href"]
    return {
        "id": "musikazuzenean:" + url.rstrip("/").rsplit("/", 1)[-1],
        "iturria": "Musika Zuzenean",
        "izenburua": izenburua,
        "kategoria": "musika",
        "data_hasiera": data.isoformat(),
        "data_amaiera": data.isoformat(),
        "ordua": "",
        "lekua": html_garbitu(lekua, 80),
        "prezioa": "",
        "deskribapena": "",
        "url": url,
        "irudia": irudia,
        "kokapenak": [udal_kokapena(u)],
    }
