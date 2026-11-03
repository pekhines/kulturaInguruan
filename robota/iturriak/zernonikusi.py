"""
ZER NON IKUSI (Pantailak Euskaraz): euskarazko zinema-saioak aretoz areto.
https://www.zernonikusi.eus/zinema  (pantailakeuskaraz.eus/zer-non-ikusi orrian txertatuta)

Webguneak API ireki bat erabiltzen du; film bakoitzak bere saioak ditu, honela:
  "screenings": {"Bizkaia": {"Igorre": {"Igorre Aretoa Zinea": {"2026/11/8": ["17:00"]}}}}
Ekitaldi bat = film bat + areto bat + egun bat (egun bereko orduak elkarrekin: "17:00 / 19:30").
"""
from datetime import date, datetime

import requests

from lagungarriak import GOIBURUAK, html_garbitu, udal_kokapena

API = "https://www.zernonikusi.eus/api/film-screening-movies-for-sharing"
WEBGUNEA = "https://www.zernonikusi.eus"


def ekitaldiak(udalerriak):
    r = requests.get(API, headers=GOIBURUAK, timeout=30)
    r.raise_for_status()
    gaur = date.today()
    for filma in r.json().get("movies", []):
        izenburua = html_garbitu(filma.get("title", ""), 200)
        xehetasunak = " · ".join(x for x in [
            f"{filma['duration']} min" if filma.get("duration") else "", filma.get("country") or ""] if x)
        for _lurraldea, herriak in (filma.get("screenings") or {}).items():
            for herria, aretoak in herriak.items():
                u = udalerriak.bilatu(herria)
                if not u:
                    continue
                for aretoa, egunak in aretoak.items():
                    for eguna, orduak in egunak.items():
                        try:
                            d = datetime.strptime(eguna, "%Y/%m/%d").date()
                        except ValueError:
                            continue
                        if d < gaur:
                            continue
                        yield {
                            "id": f"zernonikusi:{filma['id']}:{normal_gakoa(aretoa)}:{d.isoformat()}",
                            "iturria": "Pantailak Euskaraz",
                            "izenburua": izenburua,
                            "kategoria": "zinema",
                            "hizkuntza": "eu",
                            "mota_jatorrizkoa": "zinema euskaraz",
                            "data_hasiera": d.isoformat(),
                            "data_amaiera": d.isoformat(),
                            "ordua": " / ".join(sorted(orduak)),
                            "lekua": html_garbitu(aretoa, 80),
                            "prezioa": "",
                            "deskribapena": html_garbitu(f"{xehetasunak}. {filma.get('plot') or ''}".strip(". ")),
                            "url": f"{WEBGUNEA}/zinema",
                            "irudia": WEBGUNEA + filma["cover"] if filma.get("cover") else "",
                            "kokapenak": [udal_kokapena(u)],
                        }


def normal_gakoa(testua):
    return "".join(c for c in testua.lower() if c.isalnum())[:40]
