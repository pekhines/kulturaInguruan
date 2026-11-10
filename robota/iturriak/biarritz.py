"""
DESTINATION BIARRITZ: Biarritzeko turismo bulegoaren agenda osoa (Gare du Midi, Colisée, Casinoko
antzokia, Atabal, Cité de l'Océan…). https://www.destination-biarritz.fr/agenda/  (…/page/2/ …)

Txartel bakoitza egun bateko saio bat da: "Le 14 novembre 2026 · 20h00 · Titulua · Aretoa · BIARRITZ".
Ekitaldi bera egun askotan badago (erakusketak), tarte bakarrean biltzen da.

robots.txt: "Content-Signal: ai-train=no" → LLMrik gabe irakurtzen da (Cultura Navarra bezala).
"""
import re
import time
from datetime import date

from bs4 import BeautifulSoup

from iturriak.zarata import herria_bilatu
from lagungarriak import eskuratu, html_garbitu, kategoria_asmatu, udal_kokapena

AGENDA = "https://www.destination-biarritz.fr/agenda/"
HILABETEAK = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
              "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
              "décembre": 12, "decembre": 12}
DATA = re.compile(r"(\d{1,2})\s+(" + "|".join(HILABETEAK) + r")\s+(\d{4})", re.I)
ORDUA = re.compile(r"^(\d{1,2})h(\d{2})$")
# Kultur ekitaldiak ez direnak
KANPOAN = re.compile(r"^march[ée]s?\b|aquarium|num[ée]ro de neptune|carte fid[ée]lit[ée]|bon cadeau|"
                     r"^abonnements?\b|vide.?grenier|braderie|salon professionnel|horesta|^visite guid[ée]e", re.I)
TARTEA_GUTXIENEZ = 4  # egun hauetan edo gehiagotan errepikatzen bada, tarte bakar gisa


def _txartelak(udalerriak):
    for orria in range(1, 60):
        url = AGENDA if orria == 1 else f"{AGENDA}page/{orria}/"
        try:
            html = eskuratu(url).text
        except Exception as e:  # noqa: BLE001
            if orria == 1:
                raise
            print(f"  ! Destination Biarritz {orria}. orria: {type(e).__name__} (aurrekoak gorde)")
            return
        estekak = BeautifulSoup(html, "html.parser").select("h2.iris-card__content__title a[href]")
        if not estekak:
            return
        for a in estekak:
            txartela = next((p for p in a.parents if "iris-card" in (p.get("class") or [])), None)
            if txartela is None:
                continue
            testuak = [t for t in txartela.stripped_strings if "carnet" not in t and "©" not in t]
            m = DATA.search(" ".join(testuak))
            if not m:
                continue
            try:
                eguna = date(int(m.group(3)), HILABETEAK[m.group(2).lower()], int(m.group(1)))
            except ValueError:
                continue
            ordua = next((f"{int(o.group(1)):02d}:{o.group(2)}" for t in testuak if (o := ORDUA.match(t))), "")
            izenburua = a.get_text(" ", strip=True)
            # Izenburuaren ondoren: aretoa eta herria
            i = testuak.index(izenburua) if izenburua in testuak else -1
            ondorengoak = testuak[i + 1:] if i >= 0 else []
            herria = herria_bilatu(ondorengoak[-1].title(), udalerriak) if ondorengoak else None
            aretoa = ondorengoak[0] if len(ondorengoak) >= 2 else ""
            irudia = txartela.select_one("img")
            yield {
                "url": a["href"], "eguna": eguna, "ordua": ordua, "izenburua": izenburua,
                "aretoa": aretoa, "herria": herria or udalerriak.bilatu("Biarritz"),
                "irudia": (irudia.get("data-src") or irudia.get("src") or "") if irudia else "",
            }
        time.sleep(1)


def ekitaldiak(udalerriak):
    gaur = date.today()
    taldeak = {}
    for t in _txartelak(udalerriak):
        if t["eguna"] >= gaur and not KANPOAN.search(t["izenburua"]):
            # Saio bakoitzak bere URLa du (…/occ/3/): ekitaldi bera
            taldeak.setdefault(re.sub(r"occ/\d+/?$", "", t["url"]), []).append(t)
    for url, saioak in taldeak.items():
        saioak.sort(key=lambda s: (s["eguna"], s["ordua"]))
        egunak = {s["eguna"] for s in saioak}
        if len(egunak) >= TARTEA_GUTXIENEZ:  # erakusketa, ikuskizun luzea…: tarte bakarra
            saioak = [dict(saioak[0], amaiera=max(egunak), ordua="")]
        for s in saioak:
            izenburua = html_garbitu(s["izenburua"], 200)
            if izenburua.isupper():
                izenburua = izenburua.capitalize()
            yield {
                "id": f"biarritz:{url.rstrip('/').rsplit('/', 1)[-1]}:{s['eguna']}"[:200],
                "iturria": "Destination Biarritz",
                "izenburua": izenburua,
                "kategoria": kategoria_asmatu(izenburua, s["aretoa"]),
                "data_hasiera": s["eguna"].isoformat(),
                "data_amaiera": s.get("amaiera", s["eguna"]).isoformat(),
                "ordua": s["ordua"],
                "lekua": html_garbitu(s["aretoa"], 80),
                "prezioa": "",
                "deskribapena": "",
                "url": url,
                "irudia": s["irudia"],
                "kokapenak": [udal_kokapena(s["herria"])],
            }
