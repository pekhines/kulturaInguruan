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
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import llm
from lagungarriak import ERROA, GOIBURUAK, html_garbitu, kategoria_asmatu, udal_kokapena
from iturriak.udal_agendak import metodoak

ORRIAK = ERROA / "robota" / "agenda_orriak.json"
AGENDAK = ERROA / "robota" / "agendak.json"
CACHEA = ERROA / "robota" / "cache" / "llm.json"
PROMPT_BERTSIOA = "2"
GEHIENEZ_DEIAK = int(os.environ.get("LLM_GEHIENEZ", "150"))  # exekuzio bakoitzeko
TESTU_LUZERA = 24000
IRUDI_MUGA = 5_000_000  # byte; handiagoak ez
# Bere irakurle propioa duten udalak (iturriak/irunea.py…): LLMak ez ditu irakurri behar
IRAKURLE_PROPIOA = {"Iruñea", "Eibar"}

SISTEMA = """You extract cultural and public events from Basque Country agenda web pages.
Pages may be in Basque, Spanish or French. Return ONLY JSON:
{"ekitaldiak": [{"izenburua": str, "data_hasiera": "YYYY-MM-DD", "data_amaiera": "YYYY-MM-DD" or null,
  "ordua": "HH:MM" or "", "herria": str or "", "lekua": str or "", "mota": str, "url": str or ""}]}
Rules:
- Only events explicitly listed on the page with a concrete date. Never invent events or dates.
- Ignore news articles, past events, institutional meetings (plenos), job offers, ads, and administrative
  notices (taxes, payment deadlines, registration periods, public procedures, office hours).
- If a date has no year, choose the year that makes it closest to TODAY (events are usually upcoming).
- "herria": the town/village where the event happens, as written on the page; "" if not stated.
- "mota": short type (kontzertua, antzerkia, jaiak, azoka, dantza, zinema, bertsoak, erakusketa, hitzaldia, haurrak, tailerra, kirola…).
- "url": the event's own link if the page shows one (links appear as [text](url)), else "".
- Keep "izenburua" in the page's original language. Max 80 events.
If there are no events, return {"ekitaldiak": []}."""

saioa = requests.Session()
saioa.headers.update(GOIBURUAK)


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
    }


def ekitaldiak(udalerriak):
    cachea = json.loads(CACHEA.read_text(encoding="utf-8")) if CACHEA.exists() else {}
    berria, deiak, estatistika = {}, 0, {"cachea": 0, "llm": 0, "saltatuta": 0, "hutsak": 0}
    gakoa_badago = bool(llm.gakoa())
    if not gakoa_badago:
        print("  OHARRA: OPENROUTER_API_KEY ez dago; cacheko emaitzak bakarrik erabiliko dira.")

    gaur = date.today().isoformat()
    for izena, url, herria in orriak_zerrenda(udalerriak):
        try:
            r = saioa.get(url, timeout=30)
            r.raise_for_status()
        except requests.RequestException:
            estatistika["hutsak"] += 1
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
                continue
            edukia_hash = testua
        else:
            continue  # PDFak… ez (oraingoz)
        hash_ = hashlib.sha256(f"{PROMPT_BERTSIOA}|{url}|{edukia_hash}".encode()).hexdigest()

        if hash_ in cachea:
            emaitza = cachea[hash_]["ekitaldiak"]
            estatistika["cachea"] += 1
        elif gakoa_badago and deiak < GEHIENEZ_DEIAK:
            deiak += 1
            herri_testua = f"{herria['izena']} ({herria['lurraldea']})" if herria else "ezezaguna"
            erantzuna = llm.eskatu_json(SISTEMA, f"TODAY: {gaur}\nSOURCE: {izena}\n"
                                                 f"DEFAULT TOWN: {herri_testua}\nPAGE URL: {r.url}\n\n{testua}",
                                         irudia=irudia)
            if erantzuna is None:
                estatistika["hutsak"] += 1
                continue
            emaitza = erantzuna.get("ekitaldiak") or []
            estatistika["llm"] += 1
        else:
            estatistika["saltatuta"] += 1
            continue

        berria[hash_] = {"url": url, "data": gaur, "ekitaldiak": emaitza}
        for e in emaitza:
            ek = bihurtu(izena, r.url, herria, e, udalerriak) if isinstance(e, dict) else None
            if ek:
                yield ek

    # Gaur erabilitakoak bakarrik gorde (orri aldatuen sarrera zaharrak ezabatzen dira)
    CACHEA.parent.mkdir(exist_ok=True)
    CACHEA.write_text(json.dumps(berria, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"  orriak: {estatistika}")
