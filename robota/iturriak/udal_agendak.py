"""
UDAL AGENDAK: udal bakoitzaren webguneko agenda irakurtzen du.

Zein udal eta nola: robota/agendak.json (robota/agendak_aurkitu.py-k sortua).
Udal bakoitzerako metodorik onena erabiltzen da, ordena honetan:

  1. WordPress "The Events Calendar" APIa (JSON egituratua)
  2. iCal jarioa (.ics)
  3. schema.org Event datuak orrian (JSON-LD)
  4. IZFE agenda (Gipuzkoako udal askoren plataforma: div.agenda)

Metodo hauetako bat ere ez duten udalak LLM bidezko irakurleak landuko ditu (hurrengo fasea).
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from icalendar import Calendar

from lagungarriak import (ERROA, GOIBURUAK, HILABETE_LABURDURAK, html_garbitu,
                          kategoria_asmatu, udal_kokapena, urtea_asmatu)

AGENDAK = ERROA / "robota" / "agendak.json"
HORIZONTEA = timedelta(days=365)  # urtebete baino urrunago dauden ekitaldiak ez

saioa = requests.Session()
saioa.headers.update(GOIBURUAK)


def eskuratu(url, **kw):
    r = saioa.get(url, timeout=30, **kw)
    r.raise_for_status()
    return r


def ekitaldia(udala, udalerriak, metodoa, gakoa, izenburua, hasiera, amaiera=None,
              ordua="", url="", lekua="", deskribapena="", irudia="", herria=None):
    """Ekitaldi bateratua sortu. 'herria' emanez gero (adib. tokiaren herria), hori erabili."""
    izenburua = html_garbitu(izenburua, 200)
    if not izenburua or not hasiera:
        return None
    gaur = date.today()
    amaiera = amaiera or hasiera
    if amaiera < gaur or hasiera > gaur + HORIZONTEA:
        return None
    u = (udalerriak.bilatu(herria) if herria else None) or udala
    if u.get("lat") is None:
        return None  # herririk gabe (elkarte-agenda bat, herri lehenetsirik gabe): ezin da mapan jarri
    deskribapena = html_garbitu(deskribapena)
    # 'iturria' badu, ez da udal bat (elkarte edo hedabide baten agenda da; ikus elkarte_agendak.py)
    aurrizkia, iturria = ("orria", udala["iturria"]) if udala.get("iturria") else ("udala", f"{udala['izena']} (udala)")
    return {
        "id": f"{aurrizkia}:{udala['id']}:{gakoa}"[:200],
        "iturria": iturria,
        "izenburua": izenburua,
        "kategoria": kategoria_asmatu(izenburua, deskribapena),
        "mota_jatorrizkoa": metodoa,
        "data_hasiera": hasiera.isoformat(),
        "data_amaiera": amaiera.isoformat(),
        "ordua": ordua,
        "lekua": html_garbitu(lekua, 80),
        "prezioa": "",
        "deskribapena": deskribapena,
        "url": url,
        "irudia": irudia or "",
        "kokapenak": [udal_kokapena(u)],
    }


# ---------- 1. The Events Calendar (WordPress) ----------

def tribe(api, udala, udalerriak):
    url = f"{api}?per_page=50&start_date={date.today().isoformat()}"
    for _ in range(10):  # gehienez 500 ekitaldi
        d = eskuratu(url).json()
        for e in d.get("events", []):
            hasiera = datetime.fromisoformat(e["start_date"])
            amaiera = datetime.fromisoformat(e["end_date"]) if e.get("end_date") else hasiera
            venue = e.get("venue") or {}
            if isinstance(venue, list):
                venue = venue[0] if venue else {}
            yield ekitaldia(
                udala, udalerriak, "tribe", e["id"], e.get("title", ""),
                hasiera.date(), amaiera.date(),
                ordua="" if e.get("all_day") else hasiera.strftime("%H:%M"),
                url=e.get("url", ""), lekua=venue.get("venue", ""),
                deskribapena=e.get("description", ""),
                irudia=(e.get("image") or {}).get("url", "") if isinstance(e.get("image"), dict) else "",
                herria=venue.get("city"),
            )
        url = d.get("next_rest_url")
        if not url:
            break
        time.sleep(1)


# ---------- 2. iCal ----------

def ical(jarioa, udala, udalerriak):
    jarioa = jarioa.replace("webcal://", "https://")
    cal = Calendar.from_ical(eskuratu(jarioa).content)
    for e in cal.walk("VEVENT"):
        hasi = e.get("DTSTART")
        if not hasi:
            continue
        hasi = hasi.dt
        amai = e.get("DTEND").dt if e.get("DTEND") else hasi
        ordua = hasi.strftime("%H:%M") if isinstance(hasi, datetime) else ""
        hasiera = hasi.date() if isinstance(hasi, datetime) else hasi
        amaiera = amai.date() if isinstance(amai, datetime) else amai
        if not isinstance(amai, datetime) and amaiera > hasiera:
            amaiera -= timedelta(days=1)  # iCal-en egun osoko DTEND esklusiboa da
        yield ekitaldia(
            udala, udalerriak, "ical", str(e.get("UID") or f"{hasiera}-{e.get('SUMMARY')}"),
            str(e.get("SUMMARY", "")), hasiera, amaiera, ordua=ordua,
            url=str(e.get("URL", "")), lekua=str(e.get("LOCATION", "")).split(",")[0],
            deskribapena=str(e.get("DESCRIPTION", "")),
        )


# ---------- 3. schema.org JSON-LD ----------

def _jsonld_ekitaldiak(datuak):
    if isinstance(datuak, list):
        for d in datuak:
            yield from _jsonld_ekitaldiak(d)
    elif isinstance(datuak, dict):
        if "@graph" in datuak:
            yield from _jsonld_ekitaldiak(datuak["@graph"])
        mota = datuak.get("@type", "")
        motak = mota if isinstance(mota, list) else [mota]
        if any(str(m).endswith("Event") or m == "Festival" for m in motak):
            yield datuak


def _data(testua):
    if not testua:
        return None, ""
    try:
        d = datetime.fromisoformat(str(testua).replace("Z", "+00:00"))
        return d.date(), (d.strftime("%H:%M") if "T" in str(testua) and d.strftime("%H:%M") != "00:00" else "")
    except ValueError:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(testua))
        return (date(*map(int, m.groups())), "") if m else (None, "")


def jsonld(orria, udala, udalerriak):
    soup = BeautifulSoup(eskuratu(orria).text, "html.parser")
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            datuak = json.loads(s.string or "")
        except json.JSONDecodeError:
            continue
        for e in _jsonld_ekitaldiak(datuak):
            hasiera, ordua = _data(e.get("startDate"))
            amaiera, _ = _data(e.get("endDate"))
            lekua = e.get("location") or {}
            if isinstance(lekua, list):
                lekua = lekua[0] if lekua else {}
            helbidea = lekua.get("address") or {} if isinstance(lekua, dict) else {}
            irudia = e.get("image")
            if isinstance(irudia, list):
                irudia = irudia[0] if irudia else ""
            if isinstance(irudia, dict):
                irudia = irudia.get("url", "")
            yield ekitaldia(
                udala, udalerriak, "jsonld", e.get("url") or f"{hasiera}-{e.get('name')}",
                e.get("name", ""), hasiera, amaiera, ordua=ordua, url=e.get("url", orria),
                lekua=lekua.get("name", "") if isinstance(lekua, dict) else "",
                deskribapena=e.get("description", ""), irudia=irudia,
                herria=helbidea.get("addressLocality") if isinstance(helbidea, dict) else None,
            )


# ---------- 4. IZFE (Gipuzkoa) ----------

def izfe(orria, udala, udalerriak):
    soup = BeautifulSoup(eskuratu(orria).text, "html.parser")
    for el in soup.select("div.agendas div.agenda"):
        datak = []
        for f in el.select(".fecha_wrapper"):
            eguna = f.select_one(".dia")
            hila = f.select_one(".mes")
            if not eguna or not hila:
                continue
            hilabetea = HILABETE_LABURDURAK.get(hila.get_text(strip=True).lower()[:3])
            if hilabetea and eguna.get_text(strip=True).isdigit():
                datak.append((hilabetea, int(eguna.get_text(strip=True))))
        a = el.select_one(".titulo a")
        if not datak or not a:
            continue
        hasiera = urtea_asmatu(*datak[0])
        amaiera = urtea_asmatu(*datak[-1]) if len(datak) > 1 else hasiera
        if hasiera and amaiera and amaiera < hasiera:  # urte-aldaketa (abendua → urtarrila)
            amaiera = amaiera.replace(year=amaiera.year + 1)
        desk = el.select_one(".descripcion")
        url = urljoin(orria, a["href"])
        yield ekitaldia(udala, udalerriak, "izfe", url.rsplit("/", 1)[-1], a.get_text(strip=True),
                        hasiera, amaiera, url=url,
                        deskribapena=desk.get_text(" ", strip=True) if desk else "")


# ---------- Udal bakoitzerako metodoa aukeratu ----------

def metodoak(t):
    """agendak.json-eko txosten batetik, erabil daitezkeen metodoak (lehentasun-ordenan)."""
    emaitza = []
    if t.get("tribe_api"):
        emaitza.append(("tribe", t["tribe_api"]))
    ag = t.get("agenda") or {}
    for j in ag.get("jarioak", []) + t.get("jarioak_hasieran", []):
        u = j["url"]
        if re.search(r"ical=1|\.ics\b|/icalendar/|^webcal:", u, re.I) and \
                not re.search(r"google\.com|outlook\.|shortcode|outlook-ical", u):
            emaitza.append(("ical", u))
            break
    if ag.get("jsonld_ekitaldiak") and ag.get("url"):
        emaitza.append(("jsonld", ag["url"]))
    if "izfe" in t.get("plataforma", []) and t.get("webgunea"):
        oinarria = f"{urlparse(t['webgunea']).scheme}://{urlparse(t['webgunea']).netloc}"
        hizkuntza = "es" if "/es/" in t["webgunea"] else "eu"
        emaitza.append(("izfe", f"{oinarria}/{hizkuntza}/agenda"))
    return emaitza


# ---------- 5. Plone (Eibar, Dantzan.eus…) ----------

def plone(orria, udala, udalerriak):
    """Plone-ko ekitaldi-zerrendak: <… class="dtstart" title="2026-11-08T12:45:00+01:00">.
    Ekitaldi bakoitzaren blokea: dtstart duen elementutik gora, izenburu-esteka (h2/h3/h4 a) duen
    lehen elementua. Orrikatuta badago (?b_start:int=20), hurrengo orriak ere bai."""
    url, ikusiak = orria, set()
    for _ in range(10):  # gehienez 10 orri
        soup = BeautifulSoup(eskuratu(url).text, "html.parser")
        for hasi in soup.select(".dtstart[title]"):
            blokea = hasi
            while blokea and not blokea.select_one("h2 a, h3 a, h4 a"):
                blokea = blokea.parent
            if not blokea:
                continue
            esteka = blokea.select_one("h2 a, h3 a, h4 a")
            gakoa = (esteka.get("href"), hasi["title"])
            if gakoa in ikusiak:
                continue
            ikusiak.add(gakoa)
            try:
                h = datetime.fromisoformat(hasi["title"])
                amai = blokea.select_one(".dtend[title]")
                a = datetime.fromisoformat(amai["title"]) if amai else h
            except ValueError:
                continue
            lekua = blokea.select_one(".event-place, [itemprop=location], .location")
            mota = blokea.select_one(".subject")
            yield ekitaldia(
                udala, udalerriak, "plone", f"{esteka.get('href', '').rstrip('/').rsplit('/', 1)[-1]}:{h.date()}",
                esteka.get_text(" ", strip=True), h.date(), a.date(),
                ordua=h.strftime("%H:%M") if h.strftime("%H:%M") != "00:00" else "",
                url=urljoin(url, esteka.get("href", "")),
                lekua=lekua.get_text(" ", strip=True) if lekua else "",
                deskribapena=mota.get_text(" ", strip=True) if mota else "",
            )
        hurrengoa = soup.select_one('a[href*="b_start"].next, .pagination .next a, a.next[href*="b_start"], '
                                    'li.next a[href*="b_start"]')
        if not hurrengoa:
            break
        url = urljoin(url, hurrengoa["href"])
        time.sleep(1)


IRAKURLEAK = {"tribe": tribe, "ical": ical, "jsonld": jsonld, "izfe": izfe, "plone": plone}


def udal_bat(t, udalerriak):
    udala = next((u for u in udalerriak.zerrenda if u["id"] == t["id"]), None)
    if not udala:
        return [], None
    for metodoa, url in metodoak(t):
        try:
            emaitza = [e for e in IRAKURLEAK[metodoa](url, udala, udalerriak) if e]
            return emaitza, f"{metodoa}: {len(emaitza)}"
        except Exception as e:  # noqa: BLE001 — metodo bat hausten bada, hurrengoa probatu
            last = f"{metodoa} errorea: {type(e).__name__}"
            continue
    return [], (last if metodoak(t) else None)


def ekitaldiak(udalerriak):
    txostenak = json.loads(AGENDAK.read_text(encoding="utf-8"))
    lanak = [t for t in txostenak if metodoak(t)]
    egoera = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for t, (emaitza, oharra) in zip(lanak, ex.map(lambda t: udal_bat(t, udalerriak), lanak)):
            egoera[t["izena"]] = oharra
            yield from emaitza
    ondo = {k: v for k, v in egoera.items() if v and "errorea" not in v and not v.endswith(": 0")}
    print(f"  {len(lanak)} udal irakurgarri; {len(ondo)}k ekitaldiak eman dituzte")
    hutsak = {k: v for k, v in egoera.items() if v and "errorea" in v}
    if hutsak:
        print("  Erroreak:", hutsak)
