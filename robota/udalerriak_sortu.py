"""
Euskal Herriko 7 lurraldeetako udalerrien zerrenda sortzen du, koordenatuekin.

Behin bakarrik exekutatu behar da (edo udalerriak aldatzen direnean):
    python robota/udalerriak_sortu.py

Iturriak:
  - Hegoaldea (Araba, Bizkaia, Gipuzkoa, Nafarroa Garaia): Wikidata
  - Iparraldea (Lapurdi, Nafarroa Beherea, Zuberoa): Frantziako geo APIa
    (Euskal Hirigune Elkargoa) + Wikidata (euskarazko izenak eta lurraldea)

Emaitza: docs/datuak/udalerriak.json
"""
import json
from pathlib import Path

import requests

ERROA = Path(__file__).resolve().parent.parent
IRTEERA = ERROA / "docs" / "datuak" / "udalerriak.json"
WEBGUNEAK = ERROA / "robota" / "udal_webguneak.json"

WIKIDATA = "https://query.wikidata.org/sparql"
GOIBURUAK = {"User-Agent": "kulturaInguruan/0.1 (Euskal Herriko kultur agenda)"}

# Wikidata identifikadoreak
LURRALDEAK_WD = {
    "Q671023": "Lapurdi",
    "Q638503": "Nafarroa Beherea",
    "Q673040": "Zuberoa",
}
EUSKAL_HIRIGUNE_ELKARGOA = "200067106"  # Frantziako SIREN kodea

# Wikidatan lurralderik gabe edo bikoiztuta daudenak, eskuz zuzenduta
IPAR_ZUZENKETAK = {
    "64125": "Lapurdi",  # Bidarte
    "64140": "Lapurdi",  # Bokale
    "64483": "Lapurdi",  # Donibane Lohizune
    "64441": "Zuberoa",  # Pagola
}

# Iturrietan agertzen diren izen ohikoak, Wikidatan ez daudenak
# (adib. Nafarroako iturriek "Iruña" idazten dute Iruñea esateko)
IZEN_GEHIGARRIAK = {
    "Iruñea": ["Iruña", "Pamplona/Iruña", "Pamplona-Iruña"],
}


def izenak_gehitu(udalerriak):
    for u in udalerriak:
        if u["izena"] in IZEN_GEHIGARRIAK and u.get("mota", "udalerria") == "udalerria":
            u["izenak"] = sorted(set(u["izenak"]) | set(IZEN_GEHIGARRIAK[u["izena"]]))


def sparql(galdera):
    r = requests.post(  # POST: galdera luzeak (ehunka udalerri) URLan ez dira sartzen
        WIKIDATA,
        data={"query": galdera},
        headers={**GOIBURUAK, "Accept": "application/sparql-results+json"},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def puntua(wkt):
    # "Point(-2.92 43.25)" -> (lat, lon)
    lon, lat = wkt.replace("Point(", "").replace(")", "").split()
    return round(float(lat), 5), round(float(lon), 5)


HEGO_GALDERA = """
SELECT ?item ?eu ?es ?coord WHERE {
  %s
  ?item wdt:P625 ?coord.
  OPTIONAL { ?item rdfs:label ?eu FILTER(lang(?eu)="eu") }
  OPTIONAL { ?item rdfs:label ?es FILTER(lang(?es)="es") }
}"""

# Lurralde bakoitzeko udalerriak nola aukeratu Wikidatan
HEGO_LURRALDEAK = [
    ("Araba", "?item wdt:P31 wd:Q2074737; wdt:P131+ wd:Q81801."),
    ("Bizkaia", "?item wdt:P31 wd:Q2074737; wdt:P131+ wd:Q93366."),
    ("Gipuzkoa", "?item wdt:P31 wd:Q2074737; wdt:P131+ wd:Q95010."),
    ("Nafarroa Garaia", "?item wdt:P31 wd:Q2074737; wdt:P131+ wd:Q4018."),
    # Trebiñu eta Argantzon: Arabaren barruan dagoen enklabea
    ("Araba", "VALUES ?item { wd:Q946251 wd:Q1634743 }"),
]


def hegoaldea():
    emaitza = {}
    for lurraldea, baldintza in HEGO_LURRALDEAK:
        for b in sparql(HEGO_GALDERA % baldintza):
            qid = b["item"]["value"].rsplit("/", 1)[1]
            if qid in emaitza:
                continue  # koordenatu bat baino gehiago: lehenengoa nahikoa
            lat, lon = puntua(b["coord"]["value"])
            es = b.get("es", {}).get("value", "")
            eu = b.get("eu", {}).get("value", es)
            emaitza[qid] = {
                "id": qid,
                "izena": eu,
                "izenak": sorted({eu, es} - {""}),
                "lurraldea": lurraldea,
                "lat": lat,
                "lon": lon,
            }
    return list(emaitza.values())


def iparraldea():
    r = requests.get(
        f"https://geo.api.gouv.fr/epcis/{EUSKAL_HIRIGUNE_ELKARGOA}/communes",
        params={"fields": "nom,code,centre"},
        headers=GOIBURUAK,
        timeout=60,
    )
    r.raise_for_status()
    herriak = {c["code"]: c for c in r.json()}

    kodeak = " ".join(f'"{k}"' for k in herriak)
    galdera = f"""
    SELECT ?insee ?eu ?lurraldea WHERE {{
      VALUES ?insee {{ {kodeak} }}
      ?item wdt:P374 ?insee.
      OPTIONAL {{ ?item rdfs:label ?eu FILTER(lang(?eu)="eu") }}
      OPTIONAL {{ VALUES ?lurraldea {{ wd:Q671023 wd:Q638503 wd:Q673040 }}
                 ?item wdt:P131 ?lurraldea. }}
    }}"""
    eu_izenak, lurraldeak = {}, {}
    for b in sparql(galdera):
        k = b["insee"]["value"]
        if "eu" in b:
            eu_izenak[k] = b["eu"]["value"]
        if "lurraldea" in b:
            lurraldeak[k] = LURRALDEAK_WD[b["lurraldea"]["value"].rsplit("/", 1)[1]]
    lurraldeak.update(IPAR_ZUZENKETAK)

    emaitza = []
    for k, c in herriak.items():
        lon, lat = c["centre"]["coordinates"]
        eu = eu_izenak.get(k, c["nom"])
        emaitza.append({
            "id": f"FR{k}",
            "izena": eu,
            "izenak": sorted({eu, c["nom"]}),
            "lurraldea": lurraldeak.get(k, "Lapurdi"),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
        })
    return emaitza


# Udalerri barruko herri motak (Wikidata): kontzejuak, biztanle-guneak, auzoak…
HERRI_MOTAK = {
    "Q2989421",    # Nafarroako kontzejua
    "Q16543169",   # Arabako kontzejua
    "Q12254025",   # toki-entitate txikia (EATIM)
    "Q3055118",    # biztanle-gunea (entidad singular de población)
    "Q121289819",  # udalerriburua
    "Q13526752",   # "lugar" (Baztango herriak: Elizondo, Arizkun…)
    "Q3257686",    # herria / localidad
    "Q486972",     # gizakien kokalekua
    "Q123705",     # auzoa
}
PROBINTZIAK = {"Q81801": "Araba", "Q93366": "Bizkaia", "Q95010": "Gipuzkoa", "Q4018": "Nafarroa Garaia"}


def herriak(udalerriak):
    """Hegoaldeko udalerrien barruko herriak (Elizondo, Arizkun, Armentia, Otxarkoaga…).

    Wikidatan herri batzuk udalerriari lotuta daude, eta beste batzuk eskualdeari
    (adib. Arabako kontzejuak kuadrillari). Bi urratsetan egiten da, P131+ motelegia delako.
    """
    hego = {u["id"]: u for u in udalerriak if u["id"].startswith("Q")}

    # 1. Eskualdeak: udalerrien gurasoak Wikidatan (kuadrillak, merinaldeak, eskualdeak)
    gurasoak = {qid: u["lurraldea"] for qid, u in hego.items()}
    for b in sparql("SELECT ?u ?g WHERE { VALUES ?u { %s } ?u wdt:P131 ?g }"
                    % " ".join("wd:" + q for q in hego)):
        g = b["g"]["value"].rsplit("/", 1)[1]
        if g not in PROBINTZIAK:
            gurasoak.setdefault(g, hego[b["u"]["value"].rsplit("/", 1)[1]]["lurraldea"])

    # 2. Udalerri edo eskualde horiei lotutako herriak (zatika, Wikidata ez gainkargatzeko)
    galdera = """
    SELECT ?item ?guraso ?eu ?es ?coord WHERE {
      VALUES ?guraso { %s }
      VALUES ?mota { %s }
      ?item wdt:P131 ?guraso; wdt:P31 ?mota; wdt:P625 ?coord.
      FILTER NOT EXISTS { ?item wdt:P31 wd:Q350895 }   # herri hustuak ez
      FILTER NOT EXISTS { ?item wdt:P31 wd:Q2074737 }  # udalerriak ez (badaude)
      OPTIONAL { ?item rdfs:label ?eu FILTER(lang(?eu)="eu") }
      OPTIONAL { ?item rdfs:label ?es FILTER(lang(?es)="es") }
    }"""
    motak = " ".join("wd:" + m for m in HERRI_MOTAK)
    zerrenda = list(gurasoak)
    erantzunak = []
    for i in range(0, len(zerrenda), 100):
        zatia = " ".join("wd:" + q for q in zerrenda[i:i + 100])
        erantzunak += sparql(galdera % (zatia, motak))

    emaitza = {}
    for b in erantzunak:
        qid = b["item"]["value"].rsplit("/", 1)[1]
        if qid in emaitza or qid in hego:
            continue
        guraso = b["guraso"]["value"].rsplit("/", 1)[1]
        udalerria = hego.get(guraso)  # None bada, eskualde bati lotuta dago
        es = b.get("es", {}).get("value", "")
        eu = b.get("eu", {}).get("value", es)
        if not eu or (udalerria and normal(eu) in {normal(i) for i in udalerria["izenak"]}):
            continue  # udalerriaren izen bera duen gunea (adib. Eibar Eibarren barruan)
        lat, lon = puntua(b["coord"]["value"])
        herria = {
            "id": qid,
            "izena": eu,
            "izenak": sorted({eu, es} - {""}),
            "lurraldea": gurasoak[guraso],
            "lat": lat,
            "lon": lon,
        }
        if udalerria:
            herria["udalerria"] = udalerria["izena"]
        emaitza[qid] = herria
    return list(emaitza.values())


def normal(t):
    return " ".join(t.lower().replace("-", " ").split())


def webguneak(udalerriak):
    """Udalen webgune ofizialak (Wikidata P856), robotak agendak bilatzeko."""
    hego = [u["id"] for u in udalerriak if u["id"].startswith("Q")]
    ipar = [u["id"][2:] for u in udalerriak if u["id"].startswith("FR")]
    emaitza = {}
    for b in sparql("SELECT ?i ?w WHERE { VALUES ?i { %s } ?i wdt:P856 ?w }"
                    % " ".join("wd:" + q for q in hego)):
        emaitza.setdefault(b["i"]["value"].rsplit("/", 1)[1], []).append(b["w"]["value"])
    for b in sparql('SELECT ?c ?w WHERE { VALUES ?c { %s } ?i wdt:P374 ?c; wdt:P856 ?w }'
                    % " ".join(f'"{k}"' for k in ipar)):
        emaitza.setdefault("FR" + b["c"]["value"], []).append(b["w"]["value"])
    return emaitza


def main():
    from collections import Counter

    udalerriak = hegoaldea() + iparraldea()
    barrukoak = herriak(udalerriak)
    for u in udalerriak:
        u["mota"] = "udalerria"
    izenak_gehitu(udalerriak)
    for h in barrukoak:
        h["mota"] = "herria"
    guztiak = sorted(udalerriak + barrukoak, key=lambda u: u["izena"])
    IRTEERA.parent.mkdir(parents=True, exist_ok=True)
    IRTEERA.write_text(json.dumps(guztiak, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"{len(udalerriak)} udalerri + {len(barrukoak)} herri gordeta: {IRTEERA}")
    for lurraldea, n in Counter(u["lurraldea"] for u in udalerriak).most_common():
        print(f"  {lurraldea}: {n} udalerri")

    webak = webguneak(udalerriak)
    WEBGUNEAK.write_text(json.dumps(webak, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(webak)} udal webgune gordeta: {WEBGUNEAK}")


if __name__ == "__main__":
    main()
