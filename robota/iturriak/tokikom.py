"""
TOKIKOM: euskarazko tokiko hedabideen agendak (Goiena, Anboto, Alea, Guka, Euskalerria Irratia…).

Hedabide hauek plataforma bera erabiltzen dute: /agenda/ orrian datozen egunak, eta
/agenda/eguna-YYYY-MM-DD/ orrietan egun bakoitzekoak. Ekitaldi bakoitzak schema.org
microdata du (startDate, endDate, url…) eta "Lekua, Herria | Mota" sinadura.

HEDABIDE BERRI bat gehitzeko: bere helbidea HEDABIDEAK zerrendan jarri
(egiaztatu lehenago /agenda/ orrian "tk-agendaindex" agertzen dela).
"""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from lagungarriak import GOIBURUAK, herria_helbidetik, html_garbitu, kategoria_asmatu, udal_kokapena

# Egiaztatuta 2026-11-02an (redirect-ak jarraituta, bikoiztuak kenduta)
HEDABIDEAK = {
    "Aiaraldea": "https://aiaraldea.eus",
    "Aikor": "https://aikor.eus",
    "Aiurri": "https://aiurri.eus",
    "Alea": "https://alea.eus",
    "Amezti": "https://amezti.eus",
    "Anboto": "https://anboto.org",
    "Ataria": "https://ataria.eus",
    "Barrena": "https://barrena.eus",
    "Begitu": "https://begitu.eus",
    "Erran": "https://erran.eus",
    "Euskalerria Irratia": "https://euskalerriairratia.eus",
    "Goiena": "https://goiena.eus",
    "Guaixe": "https://guaixe.eus",
    "Guka": "https://guka.eus",
    "Azkoitia Guka": "https://azkoitiaguka.eus",
    "Azpeitia Guka": "https://azpeitiaguka.eus",
    "Zarautz Guka": "https://zarautzguka.eus",
    "Zumaia Guka": "https://zumaiaguka.eus",
    "Hiruka": "https://hiruka.eus",
    "Kronika": "https://kronika.eus",
    "Mailope": "https://mailope.eus",
    "Orio Guka": "https://orioguka.eus",
    "Noaua": "https://noaua.eus",
    "Txintxarri": "https://txintxarri.eus",
}
EGUNAK_AURRERA = 30

saioa = requests.Session()
saioa.headers.update(GOIBURUAK)


def orria_irakurri(url, oinarria, izena, udalerriak):
    r = saioa.get(url, timeout=30)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    emaitza = []
    for wrapper in soup.select('[itemtype="http://schema.org/Event"]'):
        e = ekitaldia(wrapper, oinarria, izena, udalerriak)
        if e:
            emaitza.append(e)
    return emaitza


def ekitaldia(wrapper, oinarria, izena, udalerriak):
    def prop(p, attr="content"):
        el = wrapper.select_one(f'[itemprop="{p}"]')
        if not el:
            return ""
        return el.get(attr) or el.get_text(" ", strip=True)

    izenburua = html_garbitu(prop("name", attr=None) or prop("name"), 200)
    try:
        hasi = datetime.strptime(prop("startDate")[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    try:
        amai = datetime.strptime(prop("endDate")[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        amai = hasi
    if amai.date() < date.today():
        return None

    # Sinadura ("Foruen plaza, Oñati | Elkarretaratzea") ekitaldiaren blokean dago
    blokea = wrapper.find_parent("div", class_="mb-3") or wrapper.parent
    sinadura = blokea.select_one(".signature") if blokea else None
    lekua_herria, _, mota = (sinadura.get_text(" ", strip=True) if sinadura else "").partition("|")
    u = herria_helbidetik(lekua_herria, udalerriak)
    if not u:  # sinadura hutsik: microdata-ko lekua probatu
        kokapena = wrapper.select_one('[itemprop="location"]')
        u = herria_helbidetik(kokapena.get_text(", ", strip=True), udalerriak) if kokapena else None
    if not u:
        return None
    deskribapena = blokea.select_one("p") if blokea else None
    deskribapena = html_garbitu(deskribapena.get_text(" ", strip=True) if deskribapena else "")
    url = urljoin(oinarria, prop("url"))
    lekua = wrapper.select_one('[itemprop="location"] [itemprop="name"]')

    return {
        "id": "tokikom:" + url.split("://", 1)[-1][:180],
        "iturria": izena,
        "izenburua": izenburua,
        "kategoria": kategoria_asmatu(izenburua + " " + mota, deskribapena),
        "mota_jatorrizkoa": mota.strip(),
        "data_hasiera": hasi.date().isoformat(),
        "data_amaiera": amai.date().isoformat(),
        "ordua": hasi.strftime("%H:%M") if hasi.strftime("%H:%M") != "00:00" else "",
        "lekua": html_garbitu(lekua.get_text(strip=True) if lekua else "", 80),
        "prezioa": "",
        "deskribapena": deskribapena,
        "url": url,
        "irudia": prop("image"),
        "kokapenak": [udal_kokapena(u)],
    }


def hedabide_bat(izena, oinarria, udalerriak):
    emaitza, ikusiak = [], set()
    gaur = date.today()
    urlak = [f"{oinarria}/agenda/"] + [
        f"{oinarria}/agenda/eguna-{(gaur + timedelta(days=i)).isoformat()}/" for i in range(1, EGUNAK_AURRERA)
    ]
    for url in urlak:
        try:
            for e in orria_irakurri(url, oinarria, izena, udalerriak):
                if e["id"] not in ikusiak:
                    ikusiak.add(e["id"])
                    emaitza.append(e)
        except requests.RequestException:
            pass  # egun bateko orria huts eginda ere, jarraitu
        time.sleep(1)  # zerbitzaria ez kargatzeko
    return emaitza


def ekitaldiak(udalerriak):
    with ThreadPoolExecutor(max_workers=8) as ex:
        emaitzak = ex.map(lambda kv: (kv[0], hedabide_bat(kv[0], kv[1], udalerriak)), HEDABIDEAK.items())
        for izena, zerrenda in emaitzak:
            print(f"  {izena}: {len(zerrenda)}")
            yield from zerrenda
