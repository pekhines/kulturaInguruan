"""
LLM AGENDAK: egiturarik gabeko agenda-orriak LLM batekin irakurtzen ditu.

Orriak bi tokitatik datoz:
  1. robota/agenda_orriak.json — eskuz gehitutako orriak (hedabideak, elkarteak…)
  2. robota/agendak.json — beste metodorik ez duten udal-agendak (aurkitzaileak topatuak)

Orri bakoitza testu bihurtzen da eta LLMari ekitaldiak JSON gisa ateratzeko eskatzen zaio.
CACHEA: orriaren testua aldatu ez bada, aurreko emaitza erabiltzen da (LLM deirik gabe).
Gakorik ez badago, cachean dagoena bakarrik erabiltzen da.
"""
import base64
import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import llm
from lagungarriak import ERROA, HIZKUNTZAK, GOIBURUAK, html_garbitu, kategoria_asmatu, udal_kokapena
from iturriak.udal_agendak import metodoak

ORRIAK = ERROA / "robota" / "agenda_orriak.json"
AGENDAK = ERROA / "robota" / "agendak.json"
CACHEA = ERROA / "robota" / "cache" / "llm.json"
PROMPT_BERTSIOA = "2"
GEHIENEZ_DEIAK = int(os.environ.get("LLM_GEHIENEZ", "150"))  # exekuzio bakoitzeko
# Robotaren hasiera (modulua bildu.py abiatzean kargatzen da): LLM_MINUTUAK hemendik kontatzen da,
# ez LLM zatiaren hasieratik, aurreko iturriak motel badoaz ere GitHub-eko muga ez gainditzeko.
HASIERA = time.monotonic()
TESTU_LUZERA = 24000
IRUDI_MUGA = 5_000_000  # byte; handiagoak ez
# Bere irakurle propioa duten udalak (iturriak/irunea.py…): LLMak ez ditu irakurri behar
IRAKURLE_PROPIOA = {"Iruñea", "Eibar"}

SISTEMA = """You extract cultural and public events from Basque Country agenda web pages.
Pages may be in Basque, Spanish or French. Return ONLY JSON:
{"ekitaldiak": [{"izenburua": str, "data_hasiera": "YYYY-MM-DD", "data_amaiera": "YYYY-MM-DD" or null,
  "ordua": "HH:MM" or "", "herria": str or "", "lekua": str or "", "mota": str, "url": str or "",
  "hizkuntza": "eu" | "es" | "fr" | "bi" | ""}]}
Rules:
- Only events explicitly listed on the page with a concrete date. Never invent events or dates.
- Ignore news articles, past events, institutional meetings (plenos), job offers, ads, and administrative
  notices (taxes, payment deadlines, registration periods, public procedures, office hours).
- If a date has no year, choose the year that makes it closest to TODAY (events are usually upcoming).
- "herria": the town/village where the event happens, as written on the page; "" if not stated.
- "mota": short type (kontzertua, antzerkia, jaiak, azoka, dantza, zinema, bertsoak, erakusketa, hitzaldia, haurrak, tailerra, kirola…).
- "url": the event's own link if the page shows one (links appear as [text](url)), else "".
- "hizkuntza": language of the EVENT itself (eu=Basque, es=Spanish, fr=French, bi=bilingual), ONLY if the page
  says it explicitly (e.g. "euskaraz", "en castellano", "elebiduna"); otherwise "". The language the page is
  written in does NOT count.
- Keep "izenburua" in the page's original language. Max 80 events.
If there are no events, return {"ekitaldiak": []}."""

def orria_testura(html, oinarria):
    """HTMLa testu garbi bihurtu, estekak [testua](url) gisa mantenduz."""
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.select("script, style, noscript, svg, nav, header, footer, aside, form, iframe"):
        el.decompose()
    for el in soup.select('[class*="cookie"], [id*="cookie"], [class*="menu"], [id*="menu"]'):
        el.decompose()
    gorputza = soup.select_one("main") or soup.select_one("#content, .content, article") or soup.body or soup
    for a in gorputza.select("a[href]"):
        href = urljoin(oinarria, a["href"])
        testua = a.get_text(" ", strip=True)
        if testua and href.startswith("http") and len(testua) > 3:
            a.replace_with(f"[{testua}]({href})")
    testua = gorputza.get_text("\n")
    testua = re.sub(r"[ \t]+", " ", testua)
    testua = re.sub(r"\n\s*\n+", "\n", testua).strip()
    return testua[:TESTU_LUZERA]


def orriak_zerrenda(udalerriak):
    """[(izena, url, herri_lehenetsia)]"""
    emaitza = []
    if ORRIAK.exists():
        for o in json.loads(ORRIAK.read_text(encoding="utf-8")):
            if o.get("metodoa"):
                continue  # formatu estandarrekoa: elkarte_agendak.py-k irakurtzen du
            herria = udalerriak.bilatu(o["herria"]) if o.get("herria") else None
            emaitza.append((o["izena"], o["url"], herria))
    if AGENDAK.exists():
        ids = {u["id"]: u for u in udalerriak.zerrenda}
        for t in json.loads(AGENDAK.read_text(encoding="utf-8")):
            ag = t.get("agenda") or {}
            if ag.get("url") and not ag.get("errorea") and not metodoak(t) and t["id"] in ids \
                    and t["izena"] not in IRAKURLE_PROPIOA:
                emaitza.append((f"{t['izena']} (udala)", ag["url"], ids[t["id"]]))
    # URL bera behin bakarrik (eskuzko zerrendakoak lehentasuna)
    ikusiak, garbiak = set(), []
    for o in emaitza:
        gakoa = o[1].rstrip("/").split("://", 1)[-1].removeprefix("www.")
        if gakoa not in ikusiak:
            ikusiak.add(gakoa)
            garbiak.append(o)
    return garbiak


def _data(testua):
    try:
        return date.fromisoformat(str(testua)[:10])
    except (TypeError, ValueError):
        return None


def bihurtu(izena, orri_url, herri_lehenetsia, e, udalerriak):
    gaur = date.today()
    hasiera, amaiera = _data(e.get("data_hasiera")), _data(e.get("data_amaiera"))
    izenburua = html_garbitu(e.get("izenburua", ""), 200)
    if not izenburua or not hasiera:
        return None
    amaiera = amaiera if amaiera and amaiera >= hasiera else hasiera
    if amaiera < gaur or hasiera > gaur + timedelta(days=365) or (amaiera - hasiera).days > 120:
        return None
    u = udalerriak.bilatu(e["herria"]) if e.get("herria") else None
    u = u or herri_lehenetsia
    if not u:
        return None
    url = e.get("url") or ""
    if not url.startswith("http"):
        url = orri_url
    ordua = e.get("ordua") or ""
    ordua = ordua if re.fullmatch(r"\d{1,2}:\d{2}", ordua) else ""
    gakoa = hashlib.sha1(f"{orri_url}|{izenburua}|{hasiera}".encode()).hexdigest()[:16]
    return {
        "id": f"llm:{urlparse(orri_url).netloc}:{gakoa}",
        "iturria": izena,
        "izenburua": izenburua,
        "kategoria": kategoria_asmatu(f"{izenburua} {e.get('mota', '')}"),
        "mota_jatorrizkoa": html_garbitu(e.get("mota", ""), 40),
        "data_hasiera": hasiera.isoformat(),
        "data_amaiera": amaiera.isoformat(),
        "ordua": ordua,
        "lekua": html_garbitu(e.get("lekua", ""), 80),
        "prezioa": "",
        "deskribapena": "",
        "url": url,
        "irudia": "",
        "kokapenak": [udal_kokapena(u)],
        "hizkuntza": e.get("hizkuntza") if e.get("hizkuntza") in HIZKUNTZAK else "",
    }


def ekitaldiak(udalerriak):
    cachea = json.loads(CACHEA.read_text(encoding="utf-8")) if CACHEA.exists() else {}
    azkenak = {}  # url → azken emaitza: saltatutako orrien ekitaldiak ez galtzeko
    for v in sorted(cachea.values(), key=lambda v: v.get("data", "")):
        azkenak[v.get("url")] = v
    berria, ikusiak, deiak = {}, set(), 0
    estatistika = {"cachea": 0, "llm": 0, "saltatuta": 0, "hutsak": 0}
    gakoa_badago = bool(llm.gakoa())
    if not gakoa_badago:
        print("  OHARRA: OPENROUTER_API_KEY ez dago; cacheko emaitzak bakarrik erabiliko dira.")
    # GitHub-en lanak 150 minutu ditu gehienez: robota abiatu eta LLM_MINUTUAK igarota ez da dei berririk egiten.
    # Saltatutako orriek aurreko emaitzak mantentzen dituzte, eta hurrengo exekuzioan jarraitzen da.
    minutuak = float(os.environ.get("LLM_MINUTUAK") or 0)
    muga = HASIERA + minutuak * 60 if minutuak else None

    gaur = date.today().isoformat()
    orriak = orriak_zerrenda(udalerriak)
    oraingoak = {url for _, url, _ in orriak}
    # Orriak aldi berean jaitsi (gehienak webgune desberdinak dira); LLM deiak sekuentzialak dira
    with ThreadPoolExecutor(max_workers=8) as exekutorea:
        erantzunak = exekutorea.map(_orria_jaitsi, [url for _, url, _ in orriak])
        for (izena, url, herria), r in zip(orriak, erantzunak):
            if r is None:
                estatistika["hutsak"] += 1
                ikusiak.add(url)
                continue
            mota = r.headers.get("Content-Type", "html")
            irudia = None
            if mota.startswith("image/") and len(r.content) < IRUDI_MUGA:
                # Agenda kartel bat (adib. Lesakako hileko agenda JPEG gisa): irudia bera bidali
                irudia = f"data:{mota.split(';')[0]};base64," + base64.b64encode(r.content).decode()
                testua = "(The agenda is in the attached image.)"
                edukia_hash = hashlib.sha256(r.content).hexdigest()
            elif "html" in mota:
                testua = orria_testura(r.text, r.url)
                if len(testua) < 200:
                    ikusiak.add(url)
                    continue
                edukia_hash = testua
            else:
                ikusiak.add(url)
                continue  # PDFak… ez (oraingoz)
            hash_ = hashlib.sha256(f"{PROMPT_BERTSIOA}|{url}|{edukia_hash}".encode()).hexdigest()

            if hash_ in cachea:
                emaitza = cachea[hash_]["ekitaldiak"]
                estatistika["cachea"] += 1
            elif gakoa_badago and deiak < GEHIENEZ_DEIAK and (muga is None or time.monotonic() < muga):
                deiak += 1
                herri_testua = f"{herria['izena']} ({herria['lurraldea']})" if herria else "ezezaguna"
                erantzuna = llm.eskatu_json(SISTEMA, f"TODAY: {gaur}\nSOURCE: {izena}\n"
                                                     f"DEFAULT TOWN: {herri_testua}\nPAGE URL: {r.url}\n\n{testua}",
                                             irudia=irudia)
                if erantzuna is None:
                    estatistika["hutsak"] += 1
                    ikusiak.add(url)
                    continue
                emaitza = erantzuna.get("ekitaldiak") or []
                estatistika["llm"] += 1
                if deiak % 10 == 0:  # tarteka gorde: exekuzioa hilda ere, egindako lana ez galtzeko
                    _cachea_gorde(berria, cachea, ikusiak, oraingoak)
            else:
                # Dei-muga edo denbora-muga: orri honen aurreko emaitza (badago) mantendu
                estatistika["saltatuta"] += 1
                zaharra = azkenak.get(url)
                for e in (zaharra or {}).get("ekitaldiak", []):
                    ek = bihurtu(izena, zaharra.get("orri_url", url), herria, e, udalerriak) \
                        if isinstance(e, dict) else None
                    if ek:
                        yield ek
                continue

            ikusiak.add(url)
            berria[hash_] = {"url": url, "orri_url": r.url, "data": gaur, "ekitaldiak": emaitza}
            for e in emaitza:
                ek = bihurtu(izena, r.url, herria, e, udalerriak) if isinstance(e, dict) else None
                if ek:
                    yield ek

    _cachea_gorde(berria, cachea, ikusiak, oraingoak)
    print(f"  orriak: {estatistika}")
    if deiak:
        print(f"  ereduak: {llm.laburpena()}")
    # Denbora- edo dei-mugagatik orriak geratu badira, GitHub-eko workflow-ak exekuzio berri bat
    # abiarazten du egun berean (cacheari esker, utzitako lekutik jarraitzen du).
    # Dei on bakar bat ere ez bada egin (kuota agortuta, gakorik ez…), ez jarraitu: begizta litzateke.
    if estatistika["saltatuta"] and estatistika["llm"]:
        print(f"  {estatistika['saltatuta']} orri aztertu gabe: hurrengo exekuzioak jarraituko du")
        irteera = os.environ.get("GITHUB_OUTPUT")
        if irteera:
            with open(irteera, "a", encoding="utf-8") as f:
                f.write("llm_amaitu_gabe=true\n")


def _orria_jaitsi(url):
    try:
        # Saio partekaturik ez: hari askotan erabiltzeko seguruagoa
        r = requests.get(url, headers=GOIBURUAK, timeout=30)
        r.raise_for_status()
        return r
    except requests.RequestException:
        return None


def _cachea_gorde(berria, zaharra, ikusiak, oraingoak):
    """Gaurko sarrerak + oraindik ikusi gabeko orrien sarrera zaharrak (saltatuak). Ikusitako orri
    aldatuen eta zerrendatik kendutako orrien sarrera zaharrak ezabatzen dira."""
    gorde = {h: v for h, v in zaharra.items() if v.get("url") in oraingoak and v.get("url") not in ikusiak}
    gorde.update(berria)
    CACHEA.parent.mkdir(exist_ok=True)
    CACHEA.write_text(json.dumps(gorde, ensure_ascii=False, indent=0), encoding="utf-8")
