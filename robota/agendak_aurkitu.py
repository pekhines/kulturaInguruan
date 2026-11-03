"""
AURKITZAILEA: udal bakoitzaren webgunean agenda non dagoen eta nola irakur daitekeen aztertzen du.

    python robota/agendak_aurkitu.py

Udal bakoitzerako:
  1. Webgunearen hasiera-orria ireki (robots.txt errespetatuz)
  2. Agendarako estekak bilatu ("agenda", "ekitaldiak", "egitaraua", "événements"…)
  3. Agenda-orrian datu egituratuak bilatu: RSS/Atom, iCal, schema.org Event (JSON-LD),
     WordPress-en "The Events Calendar" APIa…
  4. Plataforma identifikatu (CMS-aren hatz-marka), irakurleak plataformaka idazteko

Emaitza: robota/agendak.json (robota/bildu.py-ko "udal_agendak" iturriak erabiltzen du)
"""
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from lagungarriak import ERROA, GOIBURUAK, UDALERRIAK_FITXATEGIA  # noqa: E402

WEBGUNEAK = ERROA / "robota" / "udal_webguneak.json"
IRTEERA = ERROA / "robota" / "agendak.json"

AGENDA_HITZAK = re.compile(
    r"\b(agenda|ekitaldi|egitarau|kultur[ae]? ?agenda|jaiak|programazio|programación|"
    r"eventos?|actividades|événements|evenements|agenda culturel|manifestations|sortir)\b",
    re.I,
)
# Agenda hitza dute baina ez dira ekitaldi-agendak
EZ_DIRA = re.compile(r"(agenda[ _-]?(21|2030|politic|institu|del alcalde|de alcald)|alkate|alcald|pleno|"
                     r"osoko bilkura|agenda-local|tokiko agenda|agenda escolar|eskola agenda)", re.I)

# CMS edo plataformen hatz-markak (HTMLaren barruan)
PLATAFORMAK = {
    "wordpress": r"wp-content|wp-json",
    "tribe-events": r"tribe-events|/wp-json/tribe/",
    "drupal": r"Drupal|/sites/default/files",
    "joomla": r"Joomla|/media/jui/",
    "liferay": r"Liferay|/o/frontend-|/combo\?",
    "plone": r"Plone|plone\.app",
    "izfe": r"izfe|gipuzkoa\.eus/o/",
    "animsa": r"animsa",
    "lantik": r"lantik",
    "opencms": r"OpenCms|/export/sites/",
    "typo3": r"TYPO3|typo3conf",
    "wix": r"wix\.com|_wixCssImports",
    "jimdo": r"jimdo",
    "google-sites": r"sites\.google\.com",
    "ayuntamiento-panel": r"panelmunicipal|cuadrodemando",
}

saioa = requests.Session()
saioa.headers.update(GOIBURUAK)
robots_cache = {}


def baimena(url):
    """robots.txt-ek uzten digu?"""
    host = urlparse(url).scheme + "://" + urlparse(url).netloc
    if host not in robots_cache:
        rp = RobotFileParser()
        try:
            r = saioa.get(host + "/robots.txt", timeout=15)
            rp.parse(r.text.splitlines() if r.ok else [])
        except requests.RequestException:
            rp.parse([])
        robots_cache[host] = rp
    return robots_cache[host].can_fetch(GOIBURUAK["User-Agent"], url)


def eskuratu(url):
    if not baimena(url):
        return None, "robots.txt-ek debekatuta"
    try:
        r = saioa.get(url, timeout=25, allow_redirects=True)
    except requests.RequestException as e:
        return None, type(e).__name__
    if not r.ok:
        return None, f"HTTP {r.status_code}"
    if "html" not in r.headers.get("content-type", ""):
        return None, "ez da HTML"
    r.encoding = r.apparent_encoding if not r.encoding or r.encoding.lower() == "iso-8859-1" else r.encoding
    return r, None


def plataforma(html):
    return sorted(k for k, patroia in PLATAFORMAK.items() if re.search(patroia, html, re.I))


def jarioak(soup, oinarria):
    """RSS, Atom eta iCal estekak."""
    emaitza = []
    for link in soup.select('link[rel="alternate"][href]'):
        mota = (link.get("type") or "").lower()
        if "rss" in mota or "atom" in mota or "calendar" in mota:
            emaitza.append({"mota": mota, "url": urljoin(oinarria, link["href"])})
    for a in soup.select("a[href]"):
        href = a["href"]
        if re.search(r"(\.ics\b|ical|webcal:|/feed/?$|rss)", href, re.I):
            emaitza.append({"mota": "esteka", "url": urljoin(oinarria, href)})
    # bikoiztuak kendu
    ikusiak, garbiak = set(), []
    for j in emaitza:
        if j["url"] not in ikusiak:
            ikusiak.add(j["url"])
            garbiak.append(j)
    return garbiak[:10]


def jsonld_ekitaldiak(soup):
    n = 0
    for s in soup.select('script[type="application/ld+json"]'):
        if re.search(r'"@type"\s*:\s*"(\w*Event)"', s.string or ""):
            n += len(re.findall(r'"@type"\s*:\s*"\w*Event"', s.string or ""))
    return n


# Egun edo hilabete jakin bateko agendak ("/eventos/fecha/02-11-2026/", "/agenda/2026-11/") → agenda orokorra
DATA_ZATIA = re.compile(r"/(fecha|date|eguna|data)?/?\d{1,4}[-/]\d{1,2}([-/]\d{2,4})?/?$", re.I)


def data_gabe(url):
    return DATA_ZATIA.sub("/", url)


def agenda_estekak(soup, oinarria):
    hautagaiak = []
    domeinua = urlparse(oinarria).netloc.removeprefix("www.")
    for a in soup.select("a[href]"):
        testua = " ".join(a.get_text(" ").split())[:80]
        href = data_gabe(urljoin(oinarria, a["href"]))
        if not href.startswith("http"):
            continue
        if EZ_DIRA.search(testua) or EZ_DIRA.search(href):
            continue
        if AGENDA_HITZAK.search(testua) or re.search(r"/(agenda|ekitaldiak|eventos|evenements|agenda-culturel)", href, re.I):
            kanpokoa = domeinua not in urlparse(href).netloc
            hautagaiak.append({"testua": testua, "url": href, "kanpokoa": kanpokoa})
    # barnekoak lehenengo, eta URLan "agenda" dutenak
    hautagaiak.sort(key=lambda h: (h["kanpokoa"], "agenda" not in h["url"].lower()))
    ikusiak, emaitza = set(), []
    for h in hautagaiak:
        if h["url"] not in ikusiak:
            ikusiak.add(h["url"])
            emaitza.append(h)
    return emaitza[:6]


def aztertu(udalerria, webak):
    txostena = {"id": udalerria["id"], "izena": udalerria["izena"], "lurraldea": udalerria["lurraldea"],
                "webgunea": None, "errorea": None}
    r, errorea = None, "webgunerik ez"
    for web in webak:
        r, errorea = eskuratu(web)
        if r:
            break
    if not r:
        txostena["errorea"] = errorea
        return txostena

    txostena["webgunea"] = r.url
    soup = BeautifulSoup(r.text, "html.parser")
    txostena["plataforma"] = plataforma(r.text)
    txostena["jarioak_hasieran"] = jarioak(soup, r.url)
    estekak = agenda_estekak(soup, r.url)
    txostena["agenda_estekak"] = estekak

    # Lehen agenda-esteka barnekoa aztertu
    barnekoa = next((e for e in estekak if not e["kanpokoa"]), None)
    if barnekoa:
        time.sleep(1)
        ra, err = eskuratu(barnekoa["url"])
        if ra:
            sa = BeautifulSoup(ra.text, "html.parser")
            txostena["agenda"] = {
                "url": ra.url,
                "jarioak": jarioak(sa, ra.url),
                "jsonld_ekitaldiak": jsonld_ekitaldiak(sa),
                "plataforma": plataforma(ra.text),
                "tamaina": len(ra.text),
            }
        else:
            txostena["agenda"] = {"url": barnekoa["url"], "errorea": err}

    # WordPress + The Events Calendar: API egituratua du
    if "wordpress" in txostena["plataforma"]:
        oinarria = f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}"
        api = oinarria + "/wp-json/tribe/events/v1/events?per_page=1"
        if baimena(api):
            try:
                ar = saioa.get(api, timeout=20)
                if ar.ok and "events" in ar.text:
                    txostena["tribe_api"] = oinarria + "/wp-json/tribe/events/v1/events"
            except requests.RequestException:
                pass
    return txostena


def main():
    udalerriak = [u for u in json.loads(UDALERRIAK_FITXATEGIA.read_text(encoding="utf-8"))
                  if u.get("mota") == "udalerria"]
    webguneak = json.loads(WEBGUNEAK.read_text(encoding="utf-8"))

    lanak = [(u, webguneak.get(u["id"], [])) for u in udalerriak]
    emaitzak = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, t in enumerate(ex.map(lambda l: aztertu(*l), lanak), 1):
            emaitzak.append(t)
            if i % 50 == 0:
                print(f"  {i}/{len(lanak)}…", flush=True)

    IRTEERA.write_text(json.dumps(emaitzak, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{len(emaitzak)} udalerri aztertuta → {IRTEERA.relative_to(ERROA)}")
    print("Webgunea irekita:", sum(1 for t in emaitzak if t["webgunea"]))
    print("Agenda-esteka aurkituta:", sum(1 for t in emaitzak if t.get("agenda_estekak")))
    print("Agendan RSS/iCal:", sum(1 for t in emaitzak if t.get("agenda", {}).get("jarioak")))
    print("Agendan schema.org Event:", sum(1 for t in emaitzak if t.get("agenda", {}).get("jsonld_ekitaldiak")))
    print("WordPress ekitaldi-APIa:", sum(1 for t in emaitzak if t.get("tribe_api")))
    print("Erroreak:", Counter(t["errorea"] for t in emaitzak if t["errorea"]).most_common(8))
    print("Plataformak:", Counter(p for t in emaitzak for p in t.get("plataforma", [])).most_common(15))


if __name__ == "__main__":
    main()
