"""
Bikoiztuak bateratu: herri berean, egun berean eta ordu berean, izen antzekoa duten ekitaldiak
ekitaldi bakarra dira (adib. Kulturklik-eko «"Kandida" (Leioa)» eta Hiruka-ko «"Kandida" antzezlana»).

Nola erabakitzen da "izen antzekoa"?
  - Izenburuak hitzetan zatitzen dira; hitz bakoitzaren lehen 5 letrak bakarrik ("Horregoren" = "Horrego").
  - Herriaren izena, urteak, hilabeteak eta "sarrerak" bezalako hitzak ez dira kontuan hartzen.
  - Hitz bakoitzak pisu bat du: zenbat eta ekitaldi gutxiagotan agertu, orduan eta bereizgarriagoa
    (IDF). Horrela, "Mapamunditarrak 2026: Ad hoc" eta "Mapamunditarrak 2026: Anbuloa" ez dira
    nahasten (jaialdiaren izena askotan agertzen da, obraren izena ez).
  - Iturri desberdinetakoak: izenburu laburrenaren hitz bereizgarriak luzean egon behar dira
    (iturri batek jaialdiaren izena gehitzen du sarri: "Antzerkiño 2026: "43º13'44''N"").
  - Iturri berekoak: ordu bera izan behar dute, eta bi izenburuek elkarren antzekoak izan behar dute
    bi noranzkoetan (jaialdi bateko ekitaldi desberdinak ez nahasteko).

Ekitaldi nagusia iturrien ordenaren araberakoa da (bildu.py-ko ITURRIAK). Besteen datuak
(ordua, lekua, prezioa, irudia…) falta direnean osatzeko erabiltzen dira, eta haien estekak
"beste_iturriak"-en gordetzen dira.
"""
import math
import re
from collections import Counter, defaultdict

from lagungarriak import normalizatu

# Ezer bereizten ez duten hitzak (5 letrara moztuta konparatzen dira)
HUTSAK = {
    # euskara
    "eta", "edo", "bat", "da", "dira", "ere", "ko", "en", "ren", "de", "la", "el", "los", "las", "del",
    "y", "a", "al", "con", "por", "para", "et", "le", "les", "du", "des", "au", "aux", "un", "une",
    "en", "sur", "avec", "the", "of", "and", "in", "vs",
    "sarrerak", "entradas", "billets",
    # hilabeteak eta egunak (Kulturklik: "(azaroak 28 - Bilbo)")
    "urtarrilak", "otsailak", "martxoak", "apirilak", "maiatzak", "ekainak", "uztailak", "abuztuak",
    "irailak", "urriak", "azaroak", "abenduak", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre", "janvier", "fevrier", "mars",
    "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre",
}
ERROA = 5             # hitzen lehen 5 letrak ("mutxiko" = "mutxikoak")
ATALASEA_BESTE = 0.75  # iturri desberdinak: laburrenaren pisuaren %75 luzean
ATALASEA_BERA = 0.85   # iturri bera: bi noranzkoetan %85
ATALASEA_ORDURIK_GABE = 0.85  # batek ordurik ez badu, zorrotzago


def ordua_normalizatu(ordua):
    """'9:00-11:00' → '09:00'; '19:30-21:30 (gutxi gorabehera)' → '19:30'; 'Ordutegia…' → ''."""
    m = re.search(r"\b(\d{1,2})[:.h](\d{2})\b", ordua or "")
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else ""


def hitzak(izenburua, herria):
    herri_hitzak = set(normalizatu(herria).split())
    emaitza = set()
    for h in normalizatu(izenburua).split():
        if h in HUTSAK or h in herri_hitzak or re.fullmatch(r"(19|20)\d\d", h):
            continue
        emaitza.add(h[:ERROA])
    return emaitza


def antzekotasuna(a, b, pisua):
    """a-ren hitzen pisuaren zein zati dagoen b-n (0-1)."""
    guztira = sum(pisua(h) for h in a)
    return sum(pisua(h) for h in a & b) / guztira if guztira else 0.0


def berdinak(x, y, pisua):
    """Ekitaldi bera badira, bien arteko antzekotasun simetrikoa (0-1); bestela None."""
    if x["ordua"] and y["ordua"] and x["ordua"] != y["ordua"]:
        return None
    a, b = x["hitzak"], y["hitzak"]
    if not a or not b:
        return None
    ab, ba = antzekotasuna(a, b, pisua), antzekotasuna(b, a, pisua)
    if x["e"]["iturria"] == y["e"]["iturria"]:
        if not (x["ordua"] and y["ordua"]):
            return None  # iturri berean, ordua ezinbestekoa
        atalasea = ATALASEA_BERA
        balioa = min(ab, ba)
    else:
        atalasea = ATALASEA_BESTE
        # izenburu laburrena (hitz gutxien) luzean egon behar da
        balioa = ab if len(a) < len(b) else ba if len(b) < len(a) else max(ab, ba)
    if not (x["ordua"] and y["ordua"]):
        atalasea = max(atalasea, ATALASEA_ORDURIK_GABE)
    return min(ab, ba) if balioa >= atalasea else None


def kontrakoak(x, y, pisua):
    """Talde berean egon ezin direnak: ordu desberdinak, edo iturri bereko bi ekitaldi desberdin."""
    if x["ordua"] and y["ordua"] and x["ordua"] != y["ordua"]:
        return True
    return x["e"]["iturria"] == y["e"]["iturria"] and berdinak(x, y, pisua) is None


OSATZEKO = ("ordua", "lekua", "prezioa", "deskribapena", "irudia", "url", "hizkuntza")


def batu(nagusia, besteak):
    e = {k: v for k, v in nagusia.items() if k not in ("beste_iturriak", "taldeak")}
    for b in besteak:
        for eremua in OSATZEKO:
            if not e.get(eremua) and b.get(eremua):
                e[eremua] = b[eremua]
        if e.get("kategoria") == "bestelakoa" and b.get("kategoria") not in (None, "bestelakoa"):
            e["kategoria"] = b["kategoria"]
        if b.get("data_amaiera", "") > e.get("data_amaiera", ""):
            e["data_amaiera"] = b["data_amaiera"]
    beste_iturriak, ikusiak = [], {(e["iturria"], e.get("url"))}
    for b in besteak:
        gakoa = (b["iturria"], b.get("url"))
        if gakoa not in ikusiak:
            ikusiak.add(gakoa)
            beste_iturriak.append({"iturria": b["iturria"], "url": b.get("url") or "", "bilduma": b.get("bilduma")})
    if beste_iturriak:
        e["beste_iturriak"] = beste_iturriak
    return e


def bateratu(ekitaldiak):
    """Ekitaldiak lehentasun-ordenan jaso behar dira (lehenengoa = nagusia)."""
    # Hitzen pisua: zenbat eta ekitaldi gutxiagotan, orduan eta bereizgarriago
    datuak = [{"e": e, "ordua": ordua_normalizatu(e.get("ordua")),
               "hitzak": hitzak(e["izenburua"], e["kokapenak"][0]["herria"])} for e in ekitaldiak]
    df = Counter(h for d in datuak for h in d["hitzak"])
    n = len(datuak)

    def pisua(h):
        return math.log((n + 1) / (df[h] + 1)) + 1

    taldeak = defaultdict(list)
    for i, d in enumerate(datuak):
        taldeak[(d["e"]["kokapenak"][0]["herria"], d["e"]["data_hasiera"])].append(i)

    # Bikote antzekoenak lehenengo. Bi multzo batzen dira kide guztiak bateragarriak badira
    # bakarrik: horrela "Azaroan Lore 2026" (jaialdi osoa) ez da jaialdiko hitzaldi batekin batzen,
    # iturri berak hitzaldia bereizita ere badakarrelako.
    multzoa = list(range(n))            # ekitaldia → multzoaren gakoa
    kideak = {i: [i] for i in range(n)}  # multzoaren gakoa → ekitaldiak
    for indizeak in taldeak.values():
        bikoteak = []
        for ii, i in enumerate(indizeak):
            for j in indizeak[ii + 1:]:
                balioa = berdinak(datuak[i], datuak[j], pisua)
                if balioa is not None:
                    bikoteak.append((-balioa, i, j))
        for _, i, j in sorted(bikoteak):
            mi, mj = multzoa[i], multzoa[j]
            if mi == mj or any(kontrakoak(datuak[x], datuak[y], pisua) for x in kideak[mi] for y in kideak[mj]):
                continue
            berria, zaharra = min(mi, mj), max(mi, mj)
            for k in kideak.pop(zaharra):
                multzoa[k] = berria
                kideak[berria].append(k)

    multzoak = kideak
    emaitza = []
    for i in sorted(multzoak):
        kideak = [datuak[k]["e"] for k in sorted(multzoak[i])]
        # bildu.py-ko bikoiztuak_kendu()-k jada kendutako izen berdin-berdinekoak
        zehatzak = [b for k in kideak for b in k.pop("_bikoiztuak", [])]
        besteak = kideak[1:] + zehatzak
        emaitza.append(batu(kideak[0], besteak) if besteak else kideak[0])
    return emaitza
