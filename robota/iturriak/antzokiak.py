"""
ANTZOKI NAGUSIEN KARTELDEGIAK, beren webguneetatik (LLMrik gabe).

Antzoki handi gehienak (Gayarre, Baluarte, Victoria Eugenia, Arriaga, Euskalduna…) Kulturklik
eta Kutxabank Tickets bidez jasotzen dira jada. Hemen hutsuneak betetzen dira:

  - Kursaal (Donostia): webguneak Kulturklik-ek baino ekitaldi gehiago ditu (kongresuak kanpo).
    https://www.kursaal.eus/eu/agenda/  (orrikatua: …/page/2/)
  - Scène Nationale du Sud-Aquitain: Iparraldeko agertoki nagusiak (Baionako Michel Portal,
    Angeluko Quintaou, Donibane Lohizuneko Tanka, Bokaleko Apollo…), ia ezein iturrik jasotzen ez zituenak.
    https://www.scenenationale.fr/spectacles  (+ fitxa bakoitza, data, ordua eta prezioarentzat)
  - LABA (Iruñea): euskarazko kultur gunea. https://laba.eus/ekintzak/
  - Baluarte eta Gayarre (Iruñea): beren webguneetatik, Kulturklik-en ez dauden saioengatik.

Zentral (Iruñea) eta Tabakalera (Donostia) ez: AA bot guztiak blokeatzen dituzte (Anthropic barne),
eta Kulturklik bidez jasotzen dira jada.

Campos Elíseos (Bilbo) eta Hazparneko udala "tribe" APIarekin irakurtzen dira (agenda_orriak.json).
"""
import re
import time
from datetime import date

from bs4 import BeautifulSoup

from iturriak.zarata import herria_bilatu
from lagungarriak import (GOIBURUAK, HILABETE_LABURDURAK, eskuratu, html_garbitu, kategoria_asmatu,
                          normalizatu, udal_kokapena)


def _hurrengoa(hila, eguna):
    """Urterik gabeko data, karteldegi batean: gaur edo aurrerago (ez iraganean)."""
    gaur = date.today()
    for urtea in (gaur.year, gaur.year + 1):
        try:
            d = date(urtea, hila, eguna)
        except ValueError:
            continue
        if d >= gaur:
            return d
    return None


def _prezioa(prezioak):
    """[12.5, 25.0] → '12,5–25 €'"""
    if not prezioak:
        return ""
    f = lambda x: f"{x:g}".replace(".", ",")  # noqa: E731
    a, b = min(prezioak), max(prezioak)
    return f"{f(a)} €" if a == b else f"{f(a)}–{f(b)} €"


def _ekitaldia(iturria, gakoa, u, izenburua, hasiera, amaiera=None, ordua="", lekua="", url="",
               irudia="", deskribapena="", prezioa="", mota=""):
    izenburua = html_garbitu(izenburua, 200)
    if izenburua.isupper():
        izenburua = izenburua.capitalize()
    deskribapena = html_garbitu(deskribapena)
    return {
        "id": f"{normalizatu(iturria).replace(' ', '-')}:{gakoa}"[:200],
        "iturria": iturria,
        "izenburua": izenburua,
        "kategoria": kategoria_asmatu(mota, izenburua, deskribapena),
        "mota_jatorrizkoa": mota,
        "data_hasiera": hasiera.isoformat(),
        "data_amaiera": (amaiera or hasiera).isoformat(),
        "ordua": ordua,
        "lekua": html_garbitu(lekua, 80),
        "prezioa": prezioa,
        "deskribapena": deskribapena,
        "url": url,
        "irudia": irudia or "",
        "kokapenak": [udal_kokapena(u)],
    }


# ---------- Kursaal (Donostia) ----------

KURSAAL = "https://www.kursaal.eus/eu/agenda/"


def kursaal(udalerriak):
    donostia = udalerriak.bilatu("Donostia")
    ikusiak = set()
    for orria in range(1, 16):
        url = KURSAAL if orria == 1 else f"{KURSAAL}page/{orria}/"
        try:
            r = eskuratu(url, headers=GOIBURUAK)
        except Exception as e:  # noqa: BLE001
            if orria == 1:
                raise
            print(f"  ! Kursaal {orria}. orria: {type(e).__name__} (aurrekoak gorde)")
            break
        txartelak = BeautifulSoup(r.text, "html.parser").select("div.snippet_nuevo[data-id]")
        if not txartelak:
            break
        for t in txartelak:
            gakoa = t["data-id"]
            esteka = t.select_one("h2.titulo a") or t.select_one("a[href]")
            data = t.select_one("p.foto .texto")  # "03 urt"
            m = re.match(r"\s*(\d{1,2})\s+(\w{3})", data.get_text() if data else "")
            if gakoa in ikusiak or not esteka or not m:
                continue
            # Kongresu, jardunaldi eta azokek ez dute sarrera-estekarik (shop.kursaal.eus, Euskadiko
            # Orkestra, Kursaal Eszena…): kultur ekitaldiak bakarrik
            if not any("/agenda/" not in l["href"] for l in t.select("a[href]")):
                continue
            hila = HILABETE_LABURDURAK.get(m.group(2).lower())
            hasiera = _hurrengoa(hila, int(m.group(1))) if hila else None
            if not hasiera:
                continue
            ikusiak.add(gakoa)
            fecha = t.select_one("p.fecha")
            ordua = re.search(r"\b(\d{1,2}:\d{2})\b", fecha.get_text() if fecha else "")
            irudia = t.select_one("img")
            yield _ekitaldia(
                "Kursaal", gakoa, donostia, esteka.get_text(" ", strip=True), hasiera,
                ordua=ordua.group(1).zfill(5) if ordua else "", lekua="Kursaal",
                url=esteka["href"], irudia=irudia.get("src", "") if irudia else "",
            )
        time.sleep(1)


# ---------- Scène Nationale du Sud-Aquitain (Iparraldea) ----------

SN = "https://www.scenenationale.fr"
_DATA = re.compile(r"(\d{1,2})(?:\.(\d{2}))?(?:\.(\d{2}))?\b")
_ORDUA = re.compile(r"(\d{1,2})h(\d{2})?")


def _sn_saioak(bloka, udalerriak):
    """Fitxako data-blokea → [(hasiera, amaiera, ordua, herria, aretoa)].
    'jeu. 26 + ven. 27.11.26 > 20h / Anglet > Théâtre Quintaou' bezalako lerroak: data-lerroak
    pilatzen dira "Herria > Aretoa" lerro bat agertu arte (ikuskizun bera hainbat herritan izan daiteke)."""
    lerroak = [l.strip(" + ") for l in re.split(r"\n|<br\s*/?>|</p>", bloka) if l.strip()]
    lerroak = [html_garbitu(l, 300) for l in lerroak]
    saioak, datak, ordua = [], [], ""
    for lerroa in lerroak:
        zatiak = [z.strip() for z in lerroa.split(">")]
        herria = herria_bilatu(zatiak[0], udalerriak) if not _DATA.search(zatiak[0]) else None
        if herria:  # "Bayonne > Théâtre Michel Portal"
            if datak:
                # Hilabete/urterik gabeko egunek hurrengo data osoarenak hartzen dituzte
                hila = urtea = None
                osoak = []
                for eguna, h, u in reversed(datak):
                    hila, urtea = int(h) if h else hila, int(u) + 2000 if u else urtea
                    if hila and urtea:
                        try:
                            osoak.append(date(urtea, hila, int(eguna)))
                        except ValueError:
                            pass
                if osoak:
                    aretoa = zatiak[1] if len(zatiak) == 2 else ""
                    saioak.append((min(osoak), max(osoak), ordua, herria, aretoa))
            datak, ordua = [], ""
        elif _DATA.search(zatiak[0]):  # "dim. 23.05 > 11h + 15h30" edo "Du 07 au 14.02.27"
            datak += _DATA.findall(zatiak[0])
            m = _ORDUA.search(" ".join(zatiak[1:]))
            if m and not ordua:
                ordua = f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
    return saioak


def scene_nationale(udalerriak):
    gaur = date.today()
    zerrenda = BeautifulSoup(eskuratu(f"{SN}/spectacles").text, "html.parser")
    ikusiak = set()
    for a in zerrenda.select("a.spectacle[href^='/spectacle/']"):
        bidea = a["href"]
        if bidea in ikusiak:
            continue
        ikusiak.add(bidea)
        izenburua = a.select_one(".titre")
        artista = a.select_one(".artiste")
        info = a.select_one(".info")
        mota = re.sub(r"\s+", " ", info.find(string=True, recursive=False) or "").strip(" /") if info else ""
        irudia = a.select_one("img")
        time.sleep(1)
        try:
            fitxa = BeautifulSoup(eskuratu(SN + bidea).text, "html.parser")
        except Exception as e:  # noqa: BLE001 — fitxa batek huts egiten badu, besteekin jarraitu
            print(f"  ! Scène Nationale {bidea}: {type(e).__name__}")
            continue
        bloka = fitxa.select_one(".duree-seance")
        if not izenburua or not bloka:
            continue
        deskribapena = fitxa.select_one(".description")
        tarifak = [float(x.replace(",", ".")) for li in fitxa.select("li.tarif")
                   for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*€", li.get_text())]
        prezioa = _prezioa(tarifak)
        titulua = izenburua.get_text(" ", strip=True)
        if artista and artista.get_text(strip=True):
            titulua += " – " + artista.get_text(" ", strip=True)
        for i, (hasiera, amaiera, ordua, u, aretoa) in enumerate(_sn_saioak(bloka.decode_contents(), udalerriak)):
            if amaiera < gaur:
                continue
            yield _ekitaldia(
                "Scène Nationale du Sud-Aquitain", f"{bidea.rsplit('/', 1)[-1]}:{i}", u, titulua,
                hasiera, amaiera, ordua=ordua, lekua=aretoa, url=SN + bidea,
                irudia=irudia.get("src", "") if irudia else "",
                deskribapena=deskribapena.get_text(" ", strip=True) if deskribapena else "",
                prezioa=prezioa, mota=mota,
            )


# ---------- LABA (Iruñea) ----------

LABA = "https://laba.eus/ekintzak/"


def laba(udalerriak):
    """Euskarazko kultur gunea, Iruñeko Alde Zaharrean. Zerrenda kronologikoa: "Izenburua / aza. 13",
    urterik gabe eta iraganekoak barne. Urtea ordenatik: hilabetea atzera doan bakoitzean urte bat
    aurrera; azken ekitaldia gaurtik hurbilen dagoen etorkizuneko urtean kokatuta."""
    iruñea = udalerriak.bilatu("Iruñea")
    zerrenda = []
    for a in BeautifulSoup(eskuratu(LABA).text, "html.parser").select("a[href^='/ekintzak/']"):
        zatiak = [z.get_text(" ", strip=True) for z in a.find_all("span", recursive=False)]
        m = re.match(r"(\w{3})\.?\s*(\d{1,2})$", zatiak[-1]) if len(zatiak) >= 2 else None
        hila = HILABETE_LABURDURAK.get(m.group(1).lower()) if m else None
        if hila:
            zerrenda.append((zatiak[0], hila, int(m.group(2)), a["href"]))
    if not zerrenda:
        return
    # Urte-aldaketak (hilabetea atzera doanean) eta azkenaren urtea
    desplazamenduak, k = [], 0
    for i, (_, hila, eguna, _) in enumerate(zerrenda):
        if i and (hila, eguna) < zerrenda[i - 1][1:3]:
            k += 1
        desplazamenduak.append(k)
    gaur = date.today()
    _, hila, eguna, _ = zerrenda[-1]
    azken_urtea = gaur.year if (hila, eguna) >= (gaur.month, gaur.day) else gaur.year + 1
    if (date(azken_urtea, hila, min(eguna, 28)) - gaur).days > 270:
        azken_urtea -= 1  # zerrendak ez du etorkizuneko ekitaldirik
    for (izenburua, hila, eguna, bidea), d in zip(zerrenda, desplazamenduak):
        try:
            hasiera = date(azken_urtea - (k - d), hila, eguna)
        except ValueError:
            continue
        if hasiera < gaur:
            continue
        yield _ekitaldia("LABA", f"{bidea.rsplit('/', 1)[-1]}:{hasiera}", iruñea, izenburua, hasiera,
                         lekua="Laba", url="https://laba.eus" + bidea)


# ---------- Baluarte (Iruñea) ----------

BALUARTE = "https://www.baluarte.com"


def baluarte(udalerriak):
    """https://www.baluarte.com/es/agenda — kongresu eta jardunaldiak kanpo: ikuskizunek sarrera-botoia
    ("Entradas") edo "Aretoa | ordua" dute; kongresuek ordu-tartea bakarrik."""
    iruñea = udalerriak.bilatu("Iruñea")
    zerrenda = BeautifulSoup(eskuratu(f"{BALUARTE}/es/agenda").text, "html.parser")
    for t in zerrenda.select("a.bal__eventcard--evento[href]"):
        g = lambda k: t.select_one(k).get_text(" ", strip=True) if t.select_one(k) else ""  # noqa: E731
        izenburua, gehiago, botoia = g(".bal__eventcard-title"), g(".bal__eventcard-more"), g(".bal__eventcard-btn")
        if not izenburua or ("|" not in gehiago and "entradas" not in botoia.lower()):
            continue
        hila = HILABETE_LABURDURAK.get(g(".bal__eventcard-month").lower()[:3])
        egunak = [int(x) for x in re.findall(r"\d{1,2}", g(".bal__eventcard-day"))]
        if not hila or not egunak:
            continue
        # Urtea URLan egon ohi da ("…-18-19-diciembre-2026"); bestela, hurrengo data
        urtea = re.search(r"-(20\d\d)(?:$|-)", t["href"])
        try:
            hasiera = date(int(urtea.group(1)), hila, egunak[0]) if urtea else _hurrengoa(hila, egunak[0])
        except ValueError:
            continue
        if not hasiera:
            continue
        amaiera = hasiera.replace(day=egunak[-1]) if len(egunak) > 1 and egunak[-1] >= egunak[0] else hasiera
        if amaiera < date.today():
            continue
        aretoa, _, ordua = gehiago.partition("|")
        ordua = re.search(r"\d{1,2}:\d{2}", ordua)
        irudia = t.select_one("img")
        yield _ekitaldia("Baluarte", t["href"].rstrip("/").rsplit("/", 1)[-1], iruñea, izenburua, hasiera, amaiera,
                         ordua=ordua.group(0).zfill(5) if ordua else "", lekua=f"Baluarte – {aretoa.strip()}",
                         url=BALUARTE + t["href"], irudia=irudia.get("src", "") if irudia else "")


# ---------- Gayarre (Iruñea) ----------

GAYARRE = "https://teatrogayarre.com"
_ES_HILAK = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
             "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
_ES_EGUNAK = {"lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3, "viernes": 4,
              "sábado": 5, "sabado": 5, "domingo": 6}
_GAYARRE_SAIOA = re.compile(r"(" + "|".join(_ES_EGUNAK) + r"),?\s+(\d{1,2})\s+(?:de\s+)?(" + "|".join(_ES_HILAK)
                            + r")(?:\s+a\s+las\s+(\d{1,2}[:.]\d{2}))?", re.I)


def _asteko_egunarekin(asteguna, eguna, hila):
    """'domingo, 28 febrero' → asteko egunarekin bat datorren urtea (gaur.urtea-1 … +1). Iraganekoa bada: None."""
    gaur = date.today()
    for urtea in (gaur.year - 1, gaur.year, gaur.year + 1):
        try:
            d = date(urtea, hila, eguna)
        except ValueError:
            continue
        if d.weekday() == asteguna:
            return d if d >= gaur else None
    return None


def gayarre(udalerriak):
    """Ikuskizunak WordPress bidalketak dira ("programacion" kategoria), baina datak fitxan bakarrik daude
    ("Fechas y horarios: domingo, 28 febrero a las 19:00"), urterik gabe: asteko egunak ematen du urtea.
    (Sarrera-plataformak, Patronbase-k, robot guztiak debekatzen ditu: ez da erabiltzen.)"""
    iruñea = udalerriak.bilatu("Iruñea")
    kat = eskuratu(f"{GAYARRE}/wp-json/wp/v2/categories?slug=programacion").json()
    if not kat:
        return
    bidalketak = eskuratu(f"{GAYARRE}/wp-json/wp/v2/posts?categories={kat[0]['id']}&per_page=100"
                          "&_fields=id,link,title").json()
    for b in bidalketak:
        if re.search(r"funci[oó]n(es)? escolar", b["title"]["rendered"], re.I):
            continue  # ikastetxeentzako saioak, ez publikoarentzat
        time.sleep(1)
        try:
            fitxa = BeautifulSoup(eskuratu(b["link"]).text, "html.parser")
        except Exception as e:  # noqa: BLE001
            print(f"  ! Gayarre {b['link']}: {type(e).__name__}")
            continue
        testua = fitxa.get_text("\n", strip=True)
        i = testua.find("Fechas y horarios")
        if i < 0:
            continue
        zatia = testua[i:i + 1500]
        j = zatia.find("Precios")
        saioak = []
        for m in _GAYARRE_SAIOA.finditer(zatia[:j] if j > 0 else zatia):
            d = _asteko_egunarekin(_ES_EGUNAK[m.group(1).lower()], int(m.group(2)), _ES_HILAK[m.group(3).lower()])
            if d:
                saioak.append((d, (m.group(4) or "").replace(".", ":").zfill(5) if m.group(4) else ""))
        if not saioak:
            continue
        prezioak = [float(x.replace(",", ".")) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*€", zatia[j:j + 200])] \
            if j > 0 else []
        prezioa = _prezioa(prezioak)
        irudia = fitxa.select_one('meta[property="og:image"]')
        deskribapena = fitxa.select_one('meta[property="og:description"]')
        for d, ordua in sorted(set(saioak)):
            yield _ekitaldia("Gayarre", f"{b['id']}:{d}", iruñea, html_garbitu(b["title"]["rendered"], 200), d,
                             ordua=ordua, lekua="Gayarre antzokia", url=b["link"], prezioa=prezioa,
                             irudia=irudia.get("content", "") if irudia else "",
                             deskribapena=deskribapena.get("content", "") if deskribapena else "")


def ekitaldiak(udalerriak):
    for izena, irakurlea in (("Kursaal", kursaal), ("Scène Nationale", scene_nationale), ("LABA", laba),
                             ("Baluarte", baluarte), ("Gayarre", gayarre)):
        try:
            zerrenda = list(irakurlea(udalerriak))
        except Exception as e:  # noqa: BLE001 — bat hausten bada, besteekin jarraitu
            print(f"  ✗ {izena}: {type(e).__name__}: {e}")
            continue
        print(f"  {izena}: {len(zerrenda)}")
        yield from zerrenda
