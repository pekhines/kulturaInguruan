"""
IPARRALDEKO TURISMO BULEGOA (Office de Tourisme Pays Basque): en-pays-basque.fr
Lapurdi, Nafarroa Beherea eta Zuberoa osoko agenda: kontzertuak, ikuskizunak, jaiak, azokak…

Agenda orria data-tarte batekin eskatzen da (?dr_du=…&dr_au=…) eta orrikatuta dago (/page/N/).
Txartel bakoitza (a.card-agenda) EGUN BATEKO agerraldi bat da:
  data-id (ekitaldiaren kodea) · data-lat / data-lng · h3.title-card · span.cat (motak)
  time[datetime] · <strong>ordua</strong> · span.location (herria, frantsesez eta maiuskulaz)
Egun jarraian errepikatzen diren agerraldiak (erakusketak…) tarte bakar batean biltzen ditugu;
astero errepikatzen direnak (azokak…) bereizita uzten dira.
"""
import time
from collections import defaultdict
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from lagungarriak import GOIBURUAK, html_garbitu, kategoria_asmatu, udal_kokapena

URL = "https://www.en-pays-basque.fr/votre-sejour/tout-lagenda/"
EGUNAK_AURRERA = 28   # 4 aste
GEHIENEZ_ORRIAK = 80   # segurtasunerako muga
GEHIENEZKO_IRAUPENA = 120


def orria_eskuratu(url, parametroak):
    """Orri bat eskuratu; zerbitzaria motela denean, behin berriro saiatu."""
    for saiakera in range(2):
        try:
            r = requests.get(url, params=parametroak, headers=GOIBURUAK, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.text
        except requests.RequestException:
            if saiakera == 1:
                raise
            time.sleep(10)


def agerraldiak():
    """Txartel guztiak irakurri, astez aste (kontsulta txikiagoak, zerbitzariarentzat arinagoak).
    Emaitza: {data-id: [txartel-datuak, …]}"""
    gaur = date.today()
    taldeak = defaultdict(list)
    for astea in range(0, EGUNAK_AURRERA, 7):
        hasi = gaur + timedelta(days=astea)
        parametroak = {"dr_du": hasi.isoformat(), "dr_au": (hasi + timedelta(days=6)).isoformat()}
        for orria in range(1, GEHIENEZ_ORRIAK + 1):
            url = URL if orria == 1 else f"{URL}page/{orria}/"
            try:
                html = orria_eskuratu(url, parametroak)
            except requests.RequestException:
                print(f"  ✗ ezin izan da {parametroak['dr_du']} asteko {orria}. orria irakurri; hurrengo astera")
                break
            txartelak = BeautifulSoup(html, "html.parser").select("a.card-agenda") if html else []
            if not txartelak:
                break
            for t in txartelak:
                datuak = txartela(t)
                if datuak:
                    taldeak[t["data-id"]].append(datuak)
            time.sleep(1)  # zerbitzaria ez kargatzeko
    return taldeak


def txartela(t):
    denbora = t.select_one("time[datetime]")
    izenburua = t.select_one(".title-card")
    if not denbora or not izenburua or not t.get("data-id"):
        return None
    orduak = [s.get_text(strip=True) for s in denbora.select("strong")]
    return {
        "data": date.fromisoformat(denbora["datetime"][:10]),
        "ordua": orduak[0] if orduak else "",
        "izenburua": izenburua.get_text(" ", strip=True),
        "motak": t.select_one(".cat").get_text(" ", strip=True) if t.select_one(".cat") else "",
        "herria": t.select_one(".location").get_text(" ", strip=True) if t.select_one(".location") else "",
        "lat": float(t["data-lat"]) if t.get("data-lat") else None,
        "lon": float(t["data-lng"]) if t.get("data-lng") else None,
        "url": t.get("href", ""),
        "irudia": (t.select_one("img") or {}).get("data-src", ""),
    }


def tarteak(datak):
    """[3, 4, 5, 12] azaroa → [(3, 5), (12, 12)]: egun jarraiak tarte bakarrean."""
    datak = sorted(set(datak))
    emaitza = [[datak[0], datak[0]]]
    for d in datak[1:]:
        if d - emaitza[-1][1] == timedelta(days=1):
            emaitza[-1][1] = d
        else:
            emaitza.append([d, d])
    return emaitza


def ekitaldiak(udalerriak):
    for kodea, zerrenda in agerraldiak().items():
        e = zerrenda[0]
        u = udalerriak.bilatu(e["herria"], e["lat"], e["lon"])
        if not u:
            continue
        izenburua = html_garbitu(e["izenburua"], 200)
        ordua = e["ordua"] if e["ordua"] not in ("00:00", "09:00") else ""
        for hasiera, amaiera in tarteak([x["data"] for x in zerrenda]):
            if (amaiera - hasiera).days > GEHIENEZKO_IRAUPENA:
                continue
            yield {
                "id": f"enpaysbasque:{kodea}:{hasiera.isoformat()}",
                "iturria": "Pays Basque turismo bulegoa",
                "izenburua": izenburua,
                "kategoria": kategoria_asmatu(izenburua, e["motak"]),
                "mota_jatorrizkoa": html_garbitu(e["motak"], 80),
                "data_hasiera": hasiera.isoformat(),
                "data_amaiera": amaiera.isoformat(),
                "ordua": ordua if hasiera == amaiera else "",
                "lekua": "",
                "prezioa": "",
                "deskribapena": "",
                "url": e["url"],
                "irudia": e["irudia"],
                "kokapenak": [udal_kokapena(u)],
            }
