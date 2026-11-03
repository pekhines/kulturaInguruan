"""
WEBGUNEAK ASMATU: Wikidatan webgunerik ez duten udalentzat, ohiko domeinuak probatu.

Adibidez Baztan → baztan.eus, baztan.es… Domeinu bat onartzen da baldin eta:
  - orria irekitzen bada (HTML), eta
  - izenburuan edo goiburuan herriaren izena agertzen bada, eta
  - udal bat dela adierazten duen hitzen bat badu (udala, ayuntamiento, mairie, commune…).

Aurkitutakoak robota/udal_webguneak.json-en gehitzen dira; gero agendak_aurkitu.py-k aztertzen ditu.
Exekutatu:  .venv/bin/python robota/webguneak_asmatu.py
"""
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from lagungarriak import GOIBURUAK, UDALERRIAK_FITXATEGIA, normalizatu
from udalerriak_sortu import WEBGUNEAK

IPARRALDEA = {"Lapurdi", "Nafarroa Beherea", "Zuberoa"}
# Udal-webgunea dela adierazten duten hitzak, lurraldearen arabera
# (Iparraldeko udal batek "mairie" behar du: horrela ez dugu Nafarroako izen bereko herria hartzen)
UDAL_HITZAK_HEGOA = re.compile(r"udal|ayuntamiento|ayto|concejo|kontzeju", re.I)
UDAL_HITZAK_IPAR = re.compile(r"mairie|commune|ville de|herriko etxea", re.I)
DOAKO_ZERBITZUAK = ("wordpress.com", "blogspot.", "wixsite.", "jimdo", "webnode")


def domeinu_izena(izena):
    """'Donibane Garazi' → ['donibanegarazi', 'donibane-garazi']"""
    t = unicodedata.normalize("NFKD", izena.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9 -]", "", t).strip()
    return list(dict.fromkeys([re.sub(r"[ -]", "", t), re.sub(r"[ ]+", "-", t)]))


def hautagaiak(u):
    luzapenak = [".fr", ".eus", ".com"] if u["lurraldea"] in IPARRALDEA else [".eus", ".es", ".net", ".org", ".com"]
    for izena in u["izenak"]:
        for d in domeinu_izena(izena):
            if len(d) >= 4:
                for l in luzapenak:
                    yield f"https://www.{d}{l}/"


def egiaztatu(url, u):
    try:
        r = requests.get(url, headers=GOIBURUAK, timeout=10)
    except requests.RequestException:
        return None
    if not r.ok or "html" not in r.headers.get("content-type", ""):
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    goiburua = " ".join(x.get_text(" ", strip=True) for x in soup.select("title, h1, header")[:5])
    izenak = [normalizatu(i) for i in u["izenak"]]
    if not any(i and i in normalizatu(goiburua) for i in izenak):
        return None
    hitzak = UDAL_HITZAK_IPAR if u["lurraldea"] in IPARRALDEA else UDAL_HITZAK_HEGOA
    if not hitzak.search(goiburua + " " + soup.get_text(" ")[:5000]):
        return None
    if any(z in r.url for z in DOAKO_ZERBITZUAK):
        return None  # blogak: beste herri batena izan daiteke
    return r.url


def domeinua(url):
    return urlparse(url).netloc.lower().removeprefix("www.")


def udal_bat(u, hartuak):
    for url in hautagaiak(u):
        aurkitua = egiaztatu(url, u)
        if not aurkitua:
            continue
        # Birbideratu bada beste domeinu batera (adib. beste herri bateko blog batera), ez
        if not any(d.split("-")[0] in domeinua(aurkitua) for i in u["izenak"] for d in domeinu_izena(i)):
            continue
        # Beste udal batek domeinu hori badu (adib. bi Lekunberri), ez
        if domeinua(aurkitua) in hartuak:
            continue
        return u, aurkitua
    return u, None


def main():
    webguneak = json.loads(WEBGUNEAK.read_text(encoding="utf-8"))
    udalerriak = [u for u in json.loads(UDALERRIAK_FITXATEGIA.read_text(encoding="utf-8"))
                  if u.get("mota") == "udalerria" and not webguneak.get(u["id"])]
    print(f"{len(udalerriak)} udal webgunerik gabe; domeinuak probatzen…")
    hartuak = {domeinua(url) for urlak in webguneak.values() for url in urlak}
    aurkituak = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        for u, url in ex.map(lambda u: udal_bat(u, hartuak), udalerriak):
            if url:
                webguneak[u["id"]] = [url]
                aurkituak += 1
                print(f"  {u['izena']} ({u['lurraldea']}): {url}")
    WEBGUNEAK.write_text(json.dumps(webguneak, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{aurkituak} webgune berri gordeta → {WEBGUNEAK.name}")


if __name__ == "__main__":
    main()
