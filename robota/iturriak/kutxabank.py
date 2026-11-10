"""
KUTXABANK TICKETS: Kutxabank-en sarrera-salmentako ekitaldiak (Bizkaia eta Gipuzkoa batez ere:
Arriaga, Euskalduna, Kursaal, herrietako antzoki eta zinemak…).
https://tickets.kutxabank.es/

Webgunea JavaScript aplikazio bat da: HTMLak ez dakar ekitaldirik. Nabigatzaileak Firestore datu-base
publiko batetik kargatzen ditu (saiorik eta gakorik gabe), eta guk ere hortik irakurtzen ditugu,
orrika (pageSize/pageToken). robots.txt-ik ez du. LLMrik ez da behar.

Erabiltzaileak baimena eman zuen iturri hau gehitzeko (2026-11-10).
"""
import time
from datetime import date, datetime

from iturriak.zarata import herria_bilatu
from lagungarriak import eskuratu, html_garbitu, kategoria_asmatu, normalizatu, udal_kokapena

ITEMAK = ("https://firestore.googleapis.com/v1/projects/jmdb-production/databases/(default)"
          "/documents/webitems/kutxabank.cms/items/")
XEHETASUNAK = "https://tickets.kutxabank.es/eu/detalle/{}/{}"
IRUDI_HUTSA = "sinImagen"

# Kutxabank-en motak → gure kategoriak (hemen ez daudenak izenburutik asmatzen dira)
MOTAK = {
    "humor": "antzerkia", "monólogo": "antzerkia", "bakarrizketa": "antzerkia",
    "familiar": "haurrak", "infantil": "haurrak", "teatro infantil": "haurrak", "cine infantil": "haurrak",
    "literatura": "hitzaldia", "podcast": "hitzaldia",
}
KANPOAN = {"bono"}  # abonamenduak (10 zinema-saio…), ez dira ekitaldiak


def _balioa(x):
    """Firestore-ren {"stringValue": "…"} / {"mapValue": …} formatua → Python."""
    if not isinstance(x, dict):
        return x
    if "mapValue" in x:
        return {k: _balioa(v) for k, v in x["mapValue"].get("fields", {}).items()}
    if "arrayValue" in x:
        return [_balioa(v) for v in x["arrayValue"].get("values", [])]
    return next(iter(x.values()), None)


def _itemak():
    tokena = None
    for _ in range(20):  # gehienez 20 × 550
        url = ITEMAK + "?pageSize=550" + (f"&pageToken={tokena}" if tokena else "")
        d = eskuratu(url).json()
        for dok in d.get("documents", []):
            yield {k: _balioa(v) for k, v in dok.get("fields", {}).items()}
        tokena = d.get("nextPageToken")
        if not tokena:
            break
        time.sleep(1)


def _data(testua):
    """'20261115170000' → (date, '17:00')"""
    try:
        d = datetime.strptime(str(testua)[:12], "%Y%m%d%H%M")
    except ValueError:
        return None, ""
    return d.date(), ("" if d.strftime("%H%M") == "0000" else d.strftime("%H:%M"))


def _prezioa(min_, max_):
    """Zentimotan: '400', '1800' → '4–18 €'."""
    try:
        a, b = int(min_) / 100, int(max_ or min_) / 100
    except (TypeError, ValueError):
        return ""
    euroak = lambda x: f"{x:.2f}".replace(".00", "").replace(".", ",")  # noqa: E731
    if not a and not b:
        return ""
    return f"{euroak(a)} €" if a == b else f"{euroak(a)}–{euroak(b)} €"


def ekitaldiak(udalerriak):
    gaur = date.today()
    for i in _itemak():
        mota = (i.get("index_tipo") or "").strip().lower()
        if i.get("tipo") != "evento" or mota in KANPOAN or "cancel" in str(i.get("eventStatus") or "").lower():
            continue
        hasiera, ordua = _data(i.get("fechaInicio"))
        amaiera, _ = _data(i.get("fechaFin"))
        amaiera = max(amaiera or hasiera, hasiera) if hasiera else None
        if not hasiera or amaiera < gaur:
            continue
        u = herria_bilatu(i.get("index_poblacion") or "", udalerriak)
        if not u:
            continue  # Euskal Herritik kanpokoak (Kordoba…)
        izenburua = html_garbitu(i.get("nombre") or i.get("index_nombre") or "", 200)
        if izenburua.isupper():
            izenburua = izenburua.capitalize()  # "LEONES EN INVIERNO" → "Leones en invierno"
        ekitaldi_id, _, aretoa = str(i.get("id", "")).partition("__")
        if not izenburua or not ekitaldi_id:
            continue
        irudia = i.get("imageUrl") or i.get("index_img") or ""
        yield {
            "id": "kutxabank:" + normalizatu(i["id"]).replace(" ", "-"),
            "iturria": "Kutxabank Tickets",
            "izenburua": izenburua,
            "kategoria": MOTAK.get(mota) or kategoria_asmatu(mota, izenburua),
            "mota_jatorrizkoa": mota,
            "data_hasiera": hasiera.isoformat(),
            "data_amaiera": amaiera.isoformat(),
            "ordua": ordua,
            "lekua": html_garbitu(i.get("index_recinto") or "", 80),
            "prezioa": _prezioa(i.get("index_precio_min"), i.get("index_precio_max")),
            "deskribapena": "",
            "url": XEHETASUNAK.format(ekitaldi_id, aretoa),
            "irudia": "" if IRUDI_HUTSA in irudia else irudia,
            "kokapenak": [udal_kokapena(u)],
        }
