"""
Kulturklik: Eusko Jaurlaritzaren kultur agenda, datu ireki gisa.
API dokumentazioa: https://opendata.euskadi.eus  (culture/events)

Zazpi lurraldeetako ekitaldiak ditu (Iparraldekoak eta Nafarroakoak gutxiago).
Ekitaldi bakoitzak udalerriaren koordenatuak ditu.
"""
import time

import requests

from lagungarriak import GOIBURUAK, hizkuntza_asmatu, html_garbitu

API = "https://api.euskadi.eus/culture/events/v1.0/events/upcoming"
ORRIKO = 500

# Kulturklik-en motak -> gure kategoriak
MOTAK = {
    1: "musika",         # Kontzertua
    2: "antzerkia",      # Antzerkia
    3: "erakusketa",     # Erakusketa
    4: "dantza",         # Dantza
    5: "hitzaldia",      # Aurkezpena
    6: "hitzaldia",      # Hitzaldia
    7: "bertsolaritza",  # Bertsolaritza
    8: "azoka",          # Azoka
    9: "zinema",         # Zinema eta ikus-entzunezkoak
    10: "bestelakoa",    # Ekitaldiak/jardunaldiak
    11: "ikastaroa",     # Formakuntza
    12: "bestelakoa",    # Lehiaketa
    13: "jaialdia",      # Jaialdia
    14: "haurrak",       # Haur jarduera
    15: "bestelakoa",    # Bestelakoa
    16: "jaiak",         # Jaiak
}


def eu(item, eremua):
    """Euskarazko eremua, edo gaztelaniazkoa euskarazkorik ez badago."""
    return (item.get(eremua + "Eu") or item.get(eremua + "Es") or "").strip()


def ekitaldiak(udalerriak):
    orria, orriak = 1, 1
    while orria <= orriak:
        r = requests.get(API, params={"_elements": ORRIKO, "_page": orria},
                         headers=GOIBURUAK, timeout=60)
        r.raise_for_status()
        datuak = r.json()
        orriak = datuak["totalPages"]
        for item in datuak["items"]:
            ekitaldia = bihurtu(item, udalerriak)
            if ekitaldia:
                yield ekitaldia
        orria += 1
        time.sleep(1)  # zerbitzaria ez kargatzeko


def bihurtu(item, udalerriak):
    try:
        lat = float(item["municipalityLatitude"])
        lon = float(item["municipalityLongitude"])
    except (KeyError, TypeError, ValueError):
        return None  # kokapenik gabe ezin dugu distantziaz bilatu

    herri_izena = eu(item, "municipality")
    udalerria = udalerriak.bilatu(herri_izena, lat, lon)
    irudiak = item.get("images") or []

    return {
        "id": f"kulturklik:{item['id']}",
        "iturria": "Kulturklik",
        "izenburua": html_garbitu(eu(item, "name"), 200),
        "kategoria": MOTAK.get(item.get("type"), "bestelakoa"),
        "mota_jatorrizkoa": eu(item, "type"),
        "data_hasiera": item["startDate"][:10],
        "data_amaiera": (item.get("endDate") or item["startDate"])[:10],
        "ordua": eu(item, "openingHours")[:40],
        "lekua": eu(item, "establishment"),
        "prezioa": eu(item, "price")[:60],
        "deskribapena": html_garbitu(eu(item, "description")),
        "url": eu(item, "sourceUrl") or eu(item, "urlEvent") or eu(item, "purchaseUrl"),
        "irudia": irudiak[0]["imageUrl"] if irudiak else "",
        # Hizkuntza: izen eta deskribapen osoetan (bi hizkuntzetan) argi esaten badu
        "hizkuntza": hizkuntza_asmatu(*(item.get(k) for k in ("nameEu", "nameEs", "descriptionEu", "descriptionEs"))),
        # Herria ezaguna bada, gure koordenatuak erabiltzen ditugu
        # (Kulturklik-en batzuk okerrak dira, adib. Uztaritze)
        "kokapenak": [{
            "herria": udalerria["izena"] if udalerria else herri_izena,
            "lurraldea": udalerria["lurraldea"] if udalerria else "",
            "lat": udalerria["lat"] if udalerria else lat,
            "lon": udalerria["lon"] if udalerria else lon,
        }],
    }
