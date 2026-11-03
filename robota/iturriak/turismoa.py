"""
Euskadiko Agenda Turistikoa (Eusko Jaurlaritza, datu irekiak, CC BY 4.0).
https://turismo.euskadi.eus/agenda-turistica-de-euskadi/webtur00-recursostop/es/

Kulturklik-ek ez dituen gauzak ditu: herriko jaiak, azokak, gastronomia-egunak…
Ekitaldi batek udalerri bat baino gehiago izan ditzake.
"""
from datetime import date, datetime

import requests

from lagungarriak import GOIBURUAK, herriak_testuan, html_garbitu, kategoria_asmatu, udal_kokapena

URLA = "https://turismo.euskadi.eus/contenidos/ds_eventos/eventos_turisticos/opendata/agenda.json"
GEHIENEZKO_IRAUPENA = 120  # egunak; luzeagoak "iraunkorrak" dira (merkatuak, museoak…), ez ekitaldiak


def ekitaldiak(udalerriak):
    r = requests.get(URLA, headers=GOIBURUAK, timeout=60)
    r.raise_for_status()
    gaur = date.today()
    for e in r.json():
        try:
            hasiera = datetime.strptime(e["eventSearchDate1"], "%Y%m%d").date()
            amaiera = datetime.strptime(e["eventSearchDate2"], "%Y%m%d").date()
        except (KeyError, ValueError):
            continue
        if amaiera < gaur or (amaiera - hasiera).days > GEHIENEZKO_IRAUPENA:
            continue

        kokapenak = [udal_kokapena(u) for u in herriak_testuan(e.get("municipality", ""), udalerriak)]
        if not kokapenak and e.get("latwgs84") and e.get("lonwgs84"):
            u = udalerriak.bilatu("", float(e["latwgs84"]), float(e["lonwgs84"]))
            if u:
                kokapenak = [udal_kokapena(u)]
        if not kokapenak:
            continue

        izenburua = html_garbitu(e.get("documentName", ""), 200)
        deskribapena = html_garbitu(e.get("documentDescription", ""))
        yield {
            "id": "turismoa:" + (e.get("friendlyUrl") or izenburua).rstrip("/").rsplit("/", 1)[-1][:120],
            "iturria": "Euskadiko Agenda Turistikoa",
            "izenburua": izenburua,
            "kategoria": kategoria_asmatu(izenburua, deskribapena),
            "mota_jatorrizkoa": e.get("eventType", ""),
            "data_hasiera": hasiera.isoformat(),
            "data_amaiera": amaiera.isoformat(),
            "ordua": html_garbitu(e.get("eventTimeTable", ""), 40),
            "lekua": html_garbitu(e.get("placename", ""), 80),
            "prezioa": html_garbitu(e.get("eventPrice", ""), 60),
            "deskribapena": deskribapena,
            "url": e.get("friendlyUrl") or e.get("eventSourceUrl") or e.get("webpage", ""),
            "irudia": e.get("eventImageUrl", ""),
            "kokapenak": kokapenak,
        }
