"""
LLM bezero txikia (OpenRouter, doako ereduak).

API GAKOA: ez da INOIZ kodean gordetzen.
  - Lokalean: proiektuaren erroan `.env` fitxategia (git-ek ez du igotzen):
        OPENROUTER_API_KEY=sk-or-...
  - GitHub Actions-en: Settings → Secrets and variables → Actions → OPENROUTER_API_KEY

Eredua aldatzeko: OPENROUTER_MODEL ingurune-aldagaia (adib. .env-en).
"""
import json
import os
import re
import time

import requests

from lagungarriak import ERROA

API = "https://openrouter.ai/api/v1/chat/completions"
# Doako ereduak, lehentasun-ordenan (lehenengoak huts egiten badu, hurrengoa)
EREDUAK = ["google/gemma-4-31b-it:free", "nvidia/nemotron-3.5-super-vl:free"]
DEIEN_ARTEAN = 3.5  # segundo; doako mailak ~20 dei/minutu onartzen ditu


def _env_kargatu():
    env = ERROA / ".env"
    if env.exists():
        for lerroa in env.read_text(encoding="utf-8").splitlines():
            if "=" in lerroa and not lerroa.lstrip().startswith("#"):
                k, v = lerroa.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_env_kargatu()
_azken_deia = 0.0


def gakoa():
    return os.environ.get("OPENROUTER_API_KEY", "").strip()


def eskatu_json(sistema, erabiltzailea, irudia=None):
    """LLMari galdetu eta JSON objektu bat itzuli (edo None).
    irudia: aukerakoa, "data:image/jpeg;base64,…" (agenda-kartelak irakurtzeko)."""
    global _azken_deia
    ereduak = [os.environ["OPENROUTER_MODEL"]] if os.environ.get("OPENROUTER_MODEL") else EREDUAK
    for eredua in ereduak:
        for saiakera in range(3):
            itxaron = DEIEN_ARTEAN - (time.time() - _azken_deia)
            if itxaron > 0:
                time.sleep(itxaron)
            _azken_deia = time.time()
            try:
                r = requests.post(API, timeout=180, headers={
                    "Authorization": f"Bearer {gakoa()}",
                    "X-Title": "Kultura inguruan",
                }, json={
                    "model": eredua,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": sistema},
                                 {"role": "user", "content": _edukia(erabiltzailea, irudia)}],
                })
            except requests.RequestException:
                continue
            if r.status_code == 429:          # gehiegi: itxaron eta berriro
                time.sleep(20 * (saiakera + 1))
                continue
            if not r.ok:
                break                          # eredu honek ez du balio: hurrengoa
            try:
                edukia = r.json()["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, ValueError):
                break
            return _json_atera(edukia)
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
