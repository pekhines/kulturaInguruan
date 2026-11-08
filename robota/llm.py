"""
LLM bezero txikia (OpenRouter, doako ereduak).

API GAKOA: ez da INOIZ kodean gordetzen.
  - Lokalean: proiektuaren erroan `.env` fitxategia (git-ek ez du igotzen):
        OPENROUTER_API_KEY=sk-or-...
  - GitHub Actions-en: Settings → Secrets and variables → Actions → OPENROUTER_API_KEY

Ereduak: OpenRouter-en doako ereduen zerrendatik automatikoki (ikus ereduak()).
Eredu bakarra behartzeko: OPENROUTER_MODEL ingurune-aldagaia (adib. .env-en).
"""
import json
import os
import re
import time
from collections import Counter

import requests

from lagungarriak import ERROA

API = "https://openrouter.ai/api/v1/chat/completions"
EREDUEN_API = "https://openrouter.ai/api/v1/models"
# Lehentasunezko doako ereduak (ordena honetan, eskuragarri badaude). Gainerako doako ereduak
# OpenRouter-en zerrendatik automatikoki gehitzen dira, ordezko gisa.
LEHENTASUNA = ["google/gemma-4-31b-it:free", "nvidia/nemotron-3.5-super-vl:free",
               "google/gemma-4-26b-a4b-it:free"]
DEIEN_ARTEAN = 3.5  # segundo; doako mailak ~20 dei/minutu onartzen ditu
TIMEOUT = 150       # segundo dei bakoitzeko
GUTXIENEZKO_TESTUINGURUA = 32000
TXIKIEGIA = 20      # izenean "7b", "2.6b"… duten ereduak (mila milioi parametro) baztertu: emaitza txarrak


def _env_kargatu():
    env = ERROA / ".env"
    if env.exists():
        for lerroa in env.read_text(encoding="utf-8").splitlines():
            if "=" in lerroa and not lerroa.lstrip().startswith("#"):
                k, v = lerroa.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_env_kargatu()
_azken_deia = 0.0
_ereduak = None            # [(id, irudiak_onartzen_ditu)]; lehen deian kargatzen da
_atsedena = {}             # eredua → noiz arte ez erabili (time.time()); okupatuta dagoenean
_atseden_luzera = {}       # eredua → hurrengo atsedenaren luzera (bikoizten da 429 jarraian)
_baztertuak = set()        # errore iraunkorra (400, 404…): exekuzio osorako kanpoan
_geldituta = None          # kuota agortuta edo gakoa okerra: ez egin dei gehiago
_estatistika = {}          # eredua → Counter


def gakoa():
    return os.environ.get("OPENROUTER_API_KEY", "").strip()


def ereduak():
    """Erabil daitezkeen doako ereduak, OpenRouter-en zerrendatik (lehen aldian kargatzen da)."""
    global _ereduak
    if _ereduak is not None:
        return _ereduak
    if os.environ.get("OPENROUTER_MODEL"):
        _ereduak = [(os.environ["OPENROUTER_MODEL"], True)]
        return _ereduak
    try:
        r = requests.get(EREDUEN_API, timeout=30)
        r.raise_for_status()
        zerrenda = r.json()["data"]
    except (requests.RequestException, ValueError, KeyError):
        print("  OHARRA: OpenRouter-en eredu-zerrenda ezin izan da irakurri; lehentasunezkoak erabiliko dira")
        _ereduak = [(e, True) for e in LEHENTASUNA]
        return _ereduak
    egokiak = {}
    for m in zerrenda:
        id_ = m.get("id", "")
        tamaina = re.search(r"(\d+(?:\.\d+)?)b\b", id_.split("/")[-1])
        if (not id_.endswith(":free")
                or "response_format" not in (m.get("supported_parameters") or [])
                or (m.get("context_length") or 0) < GUTXIENEZKO_TESTUINGURUA
                or (tamaina and float(tamaina.group(1)) < TXIKIEGIA)):
            continue
        irudiak = "image" in ((m.get("architecture") or {}).get("input_modalities") or [])
        egokiak[id_] = (irudiak, m.get("context_length") or 0)
    ordena = [e for e in LEHENTASUNA if e in egokiak]
    ordena += sorted((e for e in egokiak if e not in ordena), key=lambda e: -egokiak[e][1])
    _ereduak = [(e, egokiak[e][0]) for e in ordena]
    print("  LLM ereduak:", ", ".join(e for e, _ in _ereduak) or "(bat ere ez)")
    return _ereduak


def _atseden(eredua, oinarria, gehienez=900):
    """Eredua denbora batez alde batera utzi; jarraian errepikatzen bada, gero eta luzeago."""
    luzera = _atseden_luzera.get(eredua, oinarria)
    _atsedena[eredua] = time.time() + luzera
    _atseden_luzera[eredua] = min(luzera * 2, gehienez)


def _kontatu(eredua, zer):
    _estatistika.setdefault(eredua, Counter())[zer] += 1


def laburpena():
    """Eredu bakoitzaren emaitzak, adib. {'google/gemma…': {'ondo': 40, '429': 12}}"""
    emaitza = {e: dict(c) for e, c in _estatistika.items()}
    if _geldituta:
        emaitza["geldituta"] = _geldituta
    return emaitza


def eskatu_json(sistema, erabiltzailea, irudia=None):
    """LLMari galdetu eta JSON objektu bat itzuli (edo None).
    irudia: aukerakoa, "data:image/jpeg;base64,…" (agenda-kartelak irakurtzeko).

    Eredu batek huts egiten badu (429 okupatuta, timeout, 5xx), berehala hurrengora pasatzen da
    eta okupatutakoa minutu batzuetan alde batera uzten da: ez da itxaroten eredu berarekin."""
    global _azken_deia, _geldituta
    hautagaiak = [e for e, irudiak in ereduak() if irudiak or not irudia]
    saiatuak = Counter()   # dei honetan eredu bakoitza gehienez bi aldiz (bigarrena atsedenaren ondoren)
    for _ in range(3 * len(hautagaiak)):
        if _geldituta:
            return None
        libreak = [e for e in hautagaiak if e not in _baztertuak and saiatuak[e] < 2]
        if not libreak:
            return None
        orain = time.time()
        prest = [e for e in libreak if _atsedena.get(e, 0) <= orain]
        if not prest:
            # Denak okupatuta: lehenengo libratzen dena itxaron (gehienez 2 minutu)
            itxaron = min(_atsedena[e] for e in libreak) - orain
            time.sleep(max(1, min(itxaron, 120)))
            continue
        eredua = min(prest, key=lambda e: saiatuak[e])  # probatu gabekoak lehenengo, lehentasun-ordenan
        saiatuak[eredua] += 1

        itxaron = DEIEN_ARTEAN - (time.time() - _azken_deia)
        if itxaron > 0:
            time.sleep(itxaron)
        _azken_deia = time.time()
        try:
            r = requests.post(API, timeout=TIMEOUT, headers={
                "Authorization": f"Bearer {gakoa()}",
                "X-Title": "Kultura inguruan",
            }, json={
                "model": eredua,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": sistema},
                             {"role": "user", "content": _edukia(erabiltzailea, irudia)}],
            })
        except requests.Timeout:
            _kontatu(eredua, "timeout")
            _atseden(eredua, 300)
            continue
        except requests.RequestException:
            _kontatu(eredua, "konexioa")
            _atseden(eredua, 60)
            continue

        if r.status_code == 429:
            _kontatu(eredua, "429")
            if "per-day" in r.text or "per day" in r.text:
                _geldituta = "eguneko kuota agortuta"
                print(f"  OHARRA: OpenRouter-en eguneko kuota agortuta ({eredua})")
                return None
            _atseden(eredua, 120)
            continue
        if r.status_code in (401, 402, 403):
            _kontatu(eredua, str(r.status_code))
            if r.status_code == 401:
                _geldituta = "gakoa okerra (401)"
                return None
            _baztertuak.add(eredua)   # 402/403: eredu honek ez du balio guretzat
            continue
        if r.status_code >= 500:
            _kontatu(eredua, "5xx")
            _atseden(eredua, 60)
            continue
        if not r.ok:
            _kontatu(eredua, str(r.status_code))
            _baztertuak.add(eredua)   # 400, 404…: eredua desagertuta edo ez du gure eskaera onartzen
            continue
        try:
            edukia = r.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError, TypeError):
            _kontatu(eredua, "erantzun_txarra")
            _atseden(eredua, 60)
            continue
        emaitza = _json_atera(edukia)
        if emaitza is None:
            _kontatu(eredua, "json_txarra")
            continue              # hurrengo ereduarekin saiatu
        _kontatu(eredua, "ondo")
        _atseden_luzera.pop(eredua, None)
        return emaitza
    return None


def _edukia(testua, irudia):
    if not irudia:
        return testua
    return [{"type": "text", "text": testua}, {"type": "image_url", "image_url": {"url": irudia}}]


def _json_atera(testua):
    testua = re.sub(r"^```(?:json)?|```$", "", testua.strip(), flags=re.M).strip()
    try:
        return json.loads(testua)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", testua, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None
