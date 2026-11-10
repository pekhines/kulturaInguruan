"""
ANTZOKIEN AURKITZAILEA: Euskal Herriko antzokien zerrendak bildu eta bakoitzaren webgunean agenda
non dagoen eta nola irakur daitekeen aztertzen du (agendak_aurkitu.py-ren antzera, udalen ordez antzokiak).

    python robota/antzokiak_aurkitu.py

Zerrendak (zuzenean irakurrita, beti eguneratuta):
  - EAE: Sarea, Euskadiko Antzokien Sarea (~70)        https://www.sarea.euskadi.eus
  - Iparraldea: Euskal Kultur Erakundearen direktorioa (aretoak, antzokiak, kontzertu-aretoak)
  - Nafarroa: ez da behar; Nafarroako Antzoki Sareak agenda bateratua du (iturriak/antzokiak.py)

Kanpoan: udalaren webgunera bidaltzen dutenak (udal_agendak-ek irakurtzen ditu jada) eta beste iturri
batek jasotzen dituenak (agenda_orriak.json, antzokiak.py, Destination Biarritz…).

Emaitza: robota/antzoki_orriak.json — agenda_orriak.json-en formatu berean:
  {"izena", "herria", "url", "metodoa"?}  ("metodoa" gabe → LLM bidez; ikus llm_agendak.py)
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from agendak_aurkitu import agenda_estekak, eskuratu, jarioak, jsonld_ekitaldiak, plataforma, saioa  # noqa: E402
from lagungarriak import ERROA, robots_baimena  # noqa: E402

IRTEERA = ERROA / "robota" / "antzoki_orriak.json"
SAREA = ("https://www.sarea.euskadi.eus/webkklik02-shtealis/eu/aa58aPublicoWar/integracion/"
         "listadoTeatrosFiltro?portal=2&locale=eu")
EKE = "https://www.eke.eus/fr/repertoire-artistes-acteurs-basques/"
EKE_KATEGORIAK = [
    "cat/equipements-lieux-culturels/salles-spectacle/lieux-representations-spectacles",
    "cat/antzerkia/ikusgarriak/aretoak/salles-theatre-lieux-representation-spectacles",
    "cat/musika/ikusgarriak/aretoak/salles-de-concerts-lieux-de-representations-de-spectacles",
    "cat/dantza/ikusgarriak/aretoak/treevocabularyterm.2014-04-03.8593203156",
]
# Beste iturri batek jasotzen dituen domeinuak (iturriak/antzokiak.py, biarritz.py, kutxabank…)
BESTE_ITURRIAK = {"scenenationale.fr", "destination-biarritz.fr", "biarritz.fr", "kursaal.eus", "baluarte.com",
                  "teatrogayarre.com", "teatrocampos.com", "laba.eus", "donostiakultura.eus",
                  "eibarkultura.eus", "eibar.eus", "kafeantzokia.eus"}


# Aurkitzaileak agenda-orri okerra hautatzen duenean (ekitaldi jakin bat…): eskuzko zuzenketa
ESKUZKOAK = {
    "atabal-biarritz.fr": "https://www.atabal-biarritz.fr/agenda/",
    "sarrerakzornotzaaretoa.com": "https://sarrerakzornotzaaretoa.com/",
}


def domeinua(url):
    return urlparse(url).netloc.lower().removeprefix("www.")


def sarea():
    r, err = eskuratu(SAREA)
    if not r:
        print("  ✗ Sarea:", err)
        return []
    s = BeautifulSoup(r.text, "html.parser")
    emaitza = []
    for a in s.find_all("a"):
        if a.get_text(strip=True) != "Webgunera jo" or not a.get("href"):
            continue
        aurrekoak = [t.strip() for t in a.find_all_previous(string=True, limit=12) if t.strip()]
        herria = next((t for t in aurrekoak if t.startswith("[")), "")
        izena = aurrekoak[aurrekoak.index(herria) + 1] if herria in aurrekoak else aurrekoak[0]
        herria = re.sub(r"\s*\(\d+\)|\[|\]", "", herria).strip()
        emaitza.append({"izena": izena, "herria": herria, "web": a["href"], "zerrenda": "Sarea"})
    return emaitza


def eke():
    fitxak = set()
    for kat in EKE_KATEGORIAK:
        r, _ = eskuratu(EKE + kat)
        if r:
            for url, izena in re.findall(r'href="(' + re.escape(EKE) + r'([^"/#?]+))"', r.text):
                if izena not in ("aiec", "cat") and not izena.startswith("repertoire"):
                    fitxak.add(url)
        time.sleep(1)
    emaitza = []
    for url in sorted(fitxak):
        r, _ = eskuratu(url)
        time.sleep(1)
        if not r:
            continue
        s = BeautifulSoup(r.text, "html.parser")
        izena = (s.select_one("h1") or s.title).get_text(" ", strip=True)
        dt = next((d for d in s.select("dt") if "Site web" in d.get_text()), None)
        web = dt.find_next("dd").a["href"] if dt and dt.find_next("dd") and dt.find_next("dd").a else ""
        herria = s.select_one('dd a[href*="/la-culture-basque-dans-les-communes"]')
        emaitza.append({"izena": izena, "herria": herria.get_text(strip=True) if herria else "",
                        "web": web, "zerrenda": "EKE"})
    return emaitza


def udal_domeinuak():
    """agendak.json-eko udal webguneen domeinuak (udal_agendak-ek irakurtzen ditu)."""
    domeinuak = set()
    for t in json.loads((ERROA / "robota" / "agendak.json").read_text(encoding="utf-8")):
        for u in [t.get("webgunea"), (t.get("agenda") or {}).get("url")]:
            if u:
                domeinuak.add(domeinua(u))
    for o in json.loads((ERROA / "robota" / "agenda_orriak.json").read_text(encoding="utf-8")):
        domeinuak.add(domeinua(o["url"]))
    return domeinuak


def aztertu(lekua, udalenak=frozenset()):
    """Antzokiaren webgunean agenda eta metodo egituratua bilatu."""
    txostena = dict(lekua)
    r, err = None, None
    for saiakera in range(2):  # sare-akats iragankorrak
        r, err = eskuratu(lekua["web"])
        if r or not err or err.startswith(("HTTP", "robots")):
            break
        time.sleep(5)
    if not r:
        txostena["errorea"] = err
        return txostena
    if domeinua(r.url) in udalenak:  # udal webgunera birbideratzen du: udal_agendak-ek irakurtzen du
        txostena["errorea"] = "udalaren webgunea"
        return txostena
    oinarria = f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}"
    txostena["webgunea"] = r.url
    soup = BeautifulSoup(r.text, "html.parser")
    txostena["plataforma"] = plataforma(r.text)
    # Agenda orokorra, ez ekitaldi jakin bat: bide laburrena lehenengo
    estekak = sorted((e for e in agenda_estekak(soup, r.url) if not e["kanpokoa"]),
                     key=lambda e: len(urlparse(e["url"]).path.strip("/").split("/")))
    agenda_url, agenda_html = r.url, r.text
    if estekak:
        time.sleep(1)
        ra, _ = eskuratu(estekak[0]["url"])
        if ra:
            agenda_url, agenda_html = ra.url, ra.text
    sa = BeautifulSoup(agenda_html, "html.parser")
    txostena["agenda"] = agenda_url
    # Metodo egituratuak, lehentasun-ordenan (robots.txt-ek benetan eskatuko den URLa baimentzen badu)
    api = oinarria + "/wp-json/tribe/events/v1/events"
    if "wordpress" in txostena["plataforma"] and robots_baimena(api + "?per_page=50"):
        try:
            ar = saioa.get(api + "?per_page=1", timeout=20)
            if ar.ok and '"events"' in ar.text and ar.json().get("total", 0):
                txostena["metodoa"], txostena["url"] = "tribe", api
                return txostena
        except (ValueError, Exception):  # noqa: BLE001
            pass
    if "mec-wrap" in agenda_html and "mecMonthlyView" in agenda_html:
        txostena["metodoa"], txostena["url"] = "mec", agenda_url
        return txostena
    if jsonld_ekitaldiak(sa) >= 2:
        txostena["metodoa"], txostena["url"] = "jsonld", agenda_url
        return txostena
    ical = next((j["url"] for j in jarioak(sa, agenda_url) + jarioak(soup, r.url)
                 if re.search(r"ical=1|\.ics\b|webcal:", j["url"], re.I)
                 and not re.search(r"google\.com|outlook", j["url"])
                 and robots_baimena(re.sub(r"^webcal://", "https://", j["url"]))), None)
    if ical:
        txostena["metodoa"], txostena["url"] = "ical", ical
        return txostena
    txostena["url"] = ESKUZKOAK.get(domeinua(agenda_url), agenda_url)  # LLM bidez
    return txostena


def main():
    lekuak = sarea() + eke()
    print(f"{len(lekuak)} antzoki/areto zerrendetan")
    udalenak = udal_domeinuak()
    aztertzeko, saltatuak = [], {"webgunerik ez": 0, "udalaren webgunea": 0, "beste iturri bat": 0}
    ikusiak = set()
    for l in lekuak:
        d = domeinua(l["web"]) if l["web"] else ""
        if not d:
            saltatuak["webgunerik ez"] += 1
        elif any(d == b or d.endswith("." + b) for b in BESTE_ITURRIAK):
            saltatuak["beste iturri bat"] += 1
        elif d in udalenak:
            saltatuak["udalaren webgunea"] += 1
        elif d not in ikusiak:
            ikusiak.add(d)
            aztertzeko.append(l)
    print("Saltatuak:", saltatuak, f"→ {len(aztertzeko)} aztertzeko")
    with ThreadPoolExecutor(max_workers=6) as ex:
        txostenak = list(ex.map(lambda l: aztertu(l, frozenset(udalenak)), aztertzeko))
    orriak = []
    for t in txostenak:
        egoera = t.get("errorea") or t.get("metodoa") or "LLM"
        print(f"  {t['izena'][:40]:40} {t['herria'][:20]:20} {egoera:12} {t.get('url', t['web'])}")
        if not t.get("errorea") and t.get("url"):
            o = {"izena": t["izena"], "herria": t["herria"], "url": t["url"]}
            if t.get("metodoa"):
                o["metodoa"] = t["metodoa"]
            orriak.append(o)
    IRTEERA.write_text(json.dumps(orriak, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(orriak)} orri → {IRTEERA.relative_to(ERROA)}")


if __name__ == "__main__":
    main()
