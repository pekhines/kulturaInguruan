"""
ELKARTE ETA HEDABIDEEN AGENDAK, formatu estandarrekoak (udalenak ez direnak).

robota/agenda_orriak.json-eko sarrerek "metodoa" badute, hemen irakurtzen dira
(udal-agendetako irakurle berberekin); "metodoa" ez dutenak LLMak irakurtzen ditu.

Adibidea:
  {"izena": "Karrikiri", "herria": "Iruñea", "metodoa": "tribe",
   "url": "https://www.karrikiri.eus/wp-json/tribe/events/v1/events"}

Metodoak:
  tribe  = WordPress "The Events Calendar" (…/wp-json/tribe/events/v1/events)
  ical   = .ics egutegia
  jsonld = schema.org Event duen orria
  mec    = Modern Events Calendar (WordPress) hilabete-egutegia, hurrengo hilabeteak barne
           (adib. eibarkultura.eus/egutegia)
  plone  = Plone-ko ekitaldi-zerrenda (class="dtstart"), adib. Eibarko udalaren kultura-agenda
"herria" aukerakoa da: ekitaldiak herria adierazten ez badu, hori erabiltzen da.
"""
import json
from urllib.parse import urlparse

from lagungarriak import ERROA
from iturriak.udal_agendak import IRAKURLEAK

ORRIAK = ERROA / "robota" / "agenda_orriak.json"


def egituratuak():
    if not ORRIAK.exists():
        return []
    return [o for o in json.loads(ORRIAK.read_text(encoding="utf-8")) if o.get("metodoa")]


def ekitaldiak(udalerriak):
    for o in egituratuak():
        herria = udalerriak.bilatu(o["herria"]) if o.get("herria") else None
        # Udal-irakurleek "udala" bat espero dute: herri lehenetsia + iturriaren izena
        # ("izena" herriarena da eta ez da zapaldu behar: ekitaldiaren kokapena da)
        iturria = dict(herria or {}, id=urlparse(o["url"]).netloc, iturria=o["izena"])
        try:
            zerrenda = [e for e in IRAKURLEAK[o["metodoa"]](o["url"], iturria, udalerriak) if e]
        except Exception as e:  # noqa: BLE001 — bat hausten bada, besteekin jarraitu
            print(f"  ✗ {o['izena']}: {type(e).__name__}")
            continue
        print(f"  {o['izena']}: {len(zerrenda)}")
        yield from zerrenda
