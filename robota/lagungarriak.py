"""Iturri guztiek erabiltzen dituzten funtzio txikiak."""
import html
import json
import math
import re
import unicodedata
from pathlib import Path

ERROA = Path(__file__).resolve().parent.parent
UDALERRIAK_FITXATEGIA = ERROA / "docs" / "datuak" / "udalerriak.json"

# Oharra: Kulturklik-ek User-Agent luzeak (parentesiekin) baztertzen ditu
GOIBURUAK = {"User-Agent": "kulturaInguruan/0.1"}

# Kategoria bateratuak: iturri bakoitzaren motak hauetako batera eramaten dira
KATEGORIAK = [
    "musika", "antzerkia", "dantza", "zinema", "bertsolaritza",
    "jaiak", "azoka", "jaialdia", "erakusketa", "hitzaldia", "haurrak",
    "ikastaroa", "bestelakoa",
]

# Izenburutik kategoria asmatzeko gako-hitzak (euskara, gaztelania, frantsesa).
# Ordena garrantzitsua da: lehenengo bat datorrena aukeratzen da.
KATEGORIA_HITZAK = [
    ("jaiak", r"\bjai(ak|etako|en)?\b|\bfest(a|ak|ak?etako)\b|fiestas?\b|\bf[eê]tes?\b|txupinazo|kalejira|"
              r"inauteri|carnaval|sanjuan|san juan|olentzero|santa ?ager|aratost|erromeria|romer[ií]a|"
              r"maskarada|pastorala|herri ?bazkari"),
    ("azoka", r"azoka|\bferias?\b|merkatu|mercad(o|illo)|march[eé]|foire|braderie|vide-?grenier|rastro"),
    ("bertsolaritza", r"bertso"),
    ("dantza", r"dantza|danza|danse|mutxiko|soka-?dantza|ezpata-?dantza|ballet|fandango"),
    ("zinema", r"zinem|\bcine|film|pel[ií]cula|dokumental|documental|projection"),
    ("antzerkia", r"antzerk|antzezlan|teatro|th[eé][aâ]tre|ikuskizun|espect[aá]culo|spectacle|bakarrizketa|mon[oó]logo|magia|zirk[ou]|circo|cirque"),
    ("musika", r"kontzertu|concierto|concert|musika|m[uú]sica|musique|abesbatza|koru|coral|chorale|"
               r"txaranga|banda|orkestra|orquesta|orchestre|dj\b|jazz|rock|trikiti|bertso-?kantari|\bop[eé]ra\b|chant\b|chorale"),
    ("erakusketa", r"erakusketa|exposici[oó]n|exposition|expo\b"),
    ("haurrak", r"haur|umeentzat|infantil|ni[nñ]os|enfants?\b|jeune public|ipuin|cuentacuentos|\bcontes?\b|pailazo|payas|clown|txotx\b"),
    ("ikastaroa", r"ikastaro|tailer|taller|curso|atelier|formakuntza|formaci[oó]n|stage\b"),
    ("hitzaldia", r"hitzaldi|conferencia|confer[eê]nce|charla|mahai-?inguru|aurkezpen|presentaci[oó]n|"
                  r"pr[eé]sentation|solasaldi|tertulia|liburu|libro|livre|rencontre|irakurketa"),
    ("jaialdia", r"jaialdi|festival"),
]


def kategoria_asmatu(*testuak):
    """Izenburu eta deskribapenetik kategoria asmatu. Izenburuak lehentasuna du."""
    for testua in testuak:
        t = (testua or "").lower()
        for kategoria, patroia in KATEGORIA_HITZAK:
            if re.search(patroia, t):
                return kategoria
    return "bestelakoa"


def urtea_asmatu(hilabetea, eguna, gaur=None):
    """Urterik gabeko data batentzat (adib. "12 ABU"), gaurtik hurbilen dagoen urtea.
    Berdinketan, etorkizuna."""
    from datetime import date
    gaur = gaur or date.today()
    hautagaiak = []
    for urtea in (gaur.year - 1, gaur.year, gaur.year + 1):
        try:
            d = date(urtea, hilabetea, eguna)
        except ValueError:
            continue
        hautagaiak.append((abs((d - gaur).days), d < gaur, d))
    return min(hautagaiak)[2] if hautagaiak else None


HILABETE_LABURDURAK = {
    # euskara
    "urt": 1, "ots": 2, "mar": 3, "api": 4, "mai": 5, "eka": 6, "uzt": 7, "abu": 8,
    "ira": 9, "urr": 10, "aza": 11, "abe": 12,
    # gaztelania
    "ene": 1, "feb": 2, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9,
    "set": 9, "oct": 10, "nov": 11, "dic": 12,
    # frantsesa
    "jan": 1, "fév": 2, "fev": 2, "avr": 4, "mai.": 5, "jui": 7, "aoû": 8, "aou": 8,
    "déc": 12, "dec": 12,
}


def udal_kokapena(u):
    """Udalerri edo herri bat ekitaldiaren 'kokapenak' formatura."""
    return {"herria": u["izena"], "lurraldea": u["lurraldea"], "lat": u["lat"], "lon": u["lon"]}


def normalizatu(testua):
    """'Donibane-Lohizune' -> 'donibane lohizune' (azentu eta ikurrik gabe)."""
    t = unicodedata.normalize("NFKD", testua or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9ñ]+", " ", t).strip()


def html_garbitu(testua, luzera=300):
    """HTMLa testu arrunt bihurtu eta moztu."""
    t = re.sub(r"<[^>]+>", " ", testua or "")
    t = re.sub(r"\s+", " ", html.unescape(t)).strip()
    if len(t) > luzera:
        t = t[:luzera].rsplit(" ", 1)[0] + "…"
    return t


def distantzia_km(lat1, lon1, lat2, lon2):
    """Bi punturen arteko distantzia (haversine formula)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class Udalerriak:
    """Herri baten izena (edozein hizkuntzatan) udalerri ezagun batekin lotzen du."""

    def __init__(self):
        self.zerrenda = json.loads(UDALERRIAK_FITXATEGIA.read_text(encoding="utf-8"))
        self.izenez = {}
        # Udalerriak lehenengo: izen bera badute, udalerriak lehentasuna du herriaren aurrean
        self.zerrenda.sort(key=lambda u: u.get("mota") != "udalerria")
        for u in self.zerrenda:
            for izena in u["izenak"]:
                self._gehitu(izena, u)
                # "Pamplona/Iruña" bezalako izen bikoitzak
                for zatia in re.split(r"[/]", izena):
                    self._gehitu(zatia, u)

    def _gehitu(self, izena, u):
        gakoa = normalizatu(izena)
        if gakoa:
            self.izenez.setdefault(gakoa, []).append(u)

    def bilatu(self, izena, lat=None, lon=None):
        """Izenaz bilatu; izen bera duten bi badaude, koordenatuek erabakitzen dute.
        Izenak ez badu ezer ematen, koordenatuetatik hurbilena (10 km barruan)."""
        hautagaiak = []
        for zatia in [izena] + re.split(r"[/()]| - |-", izena or ""):  # "Estella-Lizarra" → "Estella"
            hautagaiak = self.izenez.get(normalizatu(zatia), [])
            if hautagaiak:
                break
        if len(hautagaiak) == 1:
            return hautagaiak[0]
        if lat is None or lon is None:
            return hautagaiak[0] if hautagaiak else None
        multzoa = hautagaiak or self.zerrenda
        hurbilena = min(multzoa, key=lambda u: distantzia_km(lat, lon, u["lat"], u["lon"]))
        if hautagaiak or distantzia_km(lat, lon, hurbilena["lat"], hurbilena["lon"]) < 10:
            return hurbilena
        return None


def herriak_testuan(testua, udalerriak):
    """'Hernani Lasarte-Oria Donostia / San Sebastián Urnieta' -> 4 udalerri."""
    t = f" {normalizatu(testua)} "
    aurkituak = []
    # izen luzeenak lehenengo ("lasarte oria" "oria"-ren aurretik)
    for gakoa in sorted(udalerriak.izenez, key=len, reverse=True):
        if len(gakoa) < 3 or f" {gakoa} " not in t:
            continue
        u = udalerriak.izenez[gakoa][0]
        if u.get("mota") == "udalerria" and u not in aurkituak:
            aurkituak.append(u)
        t = t.replace(f" {gakoa} ", " | ")
    return aurkituak


# Helbideen bukaeran agertzen diren eskualde/estatu izenak (ez dira herriak)
EZ_HERRIAK = {"espainia", "espana", "frantzia", "france", "navarra", "nafarroa", "gipuzkoa", "bizkaia",
              "araba", "alava", "euskal herria", "euskadi", "pyrenees atlantiques", "lapurdi"}


def herria_helbidetik(helbidea, udalerriak):
    """Helbidean herria bilatu, eskuinetik ezkerrera:
    'Foruen plaza, Oñati'                                              → Oñati
    'Civivox Condestable, C. Mayor, 2, 31001 Pamplona, Navarra, Espainia,' → Iruñea"""
    zatiak = [z.strip() for z in helbidea.split(",") if z.strip()]
    for zatia in reversed(zatiak):
        zatia = re.sub(r"^\d{5}\s*", "", zatia)  # posta-kodea kendu
        if not zatia or normalizatu(zatia) in EZ_HERRIAK:
            continue
        u = udalerriak.bilatu(zatia)
        if u:
            return u
    return herria_deklinatuta(helbidea, udalerriak)


# Leku-izenei itsatsitako atzizkiak, luzeenak lehenengo ("Lesakako" → "Lesaka")
ATZIZKIAK = ("ako", "eko", "ko", "ean", "an", "en", "n", "ra", "rako", "tik")


def herria_deklinatuta(testua, udalerriak):
    """'Lesakako Arkupe elkartea' → Lesaka; 'Arantzako eskolako gimnasioan' → Arantza.
    Letra larriz hasten diren hitzak eta udalerriak bakarrik (ez herrixkak: "Plazan" → Plaza auzoa ez)."""
    for hitza in re.findall(r"\b[A-ZÁÉÍÓÚÑ][\wáéíóúñ-]{2,}", testua):
        for atzizkia in ("",) + ATZIZKIAK:
            if atzizkia and not hitza.lower().endswith(atzizkia):
                continue
            erroa = hitza[: len(hitza) - len(atzizkia)] if atzizkia else hitza
            if len(erroa) >= 3:
                u = udalerriak.bilatu(erroa)
                if u and u.get("mota") == "udalerria":
                    return u
    return None


# ---------- Hizkuntza ----------
# Ekitaldiaren hizkuntza, testuak ARGI esaten duenean bakarrik ("euskaraz", "en castellano"…).
# Izenburua zein hizkuntzatan idatzita dagoen ez da kontuan hartzen (ez du ezer esan nahi).
HIZKUNTZAK = ("eu", "es", "fr", "bi")   # bi = elebiduna; "" = zehaztugabea
HIZKUNTZA_HITZAK = {
    "bi": r"elebidun|bil[ií]ng[üu]e|euskaraz eta (gaztelaniaz|gazteleraz|frantsesez)|(gaztelaniaz|gazteleraz|frantsesez) eta euskaraz|"
          r"en euskera y (en )?castellano|en castellano y (en )?euskera|en basque et (en )?fran[cç]ais|"
          r"en fran[cç]ais et (en )?basque",
    "eu": r"\beuskaraz\b|en euskera\b|\ben basque\b|en langue basque|euskarazko (emanaldi|bertsio|saio|"
          r"antzezlan|ikuskizun|filma|pelikula)",
    "es": r"\bgaztelaniaz\b|\bgazteleraz\b|en castellano\b|en español\b",
    "fr": r"\bfrantsesez\b|en fran[cç]ais\b|en franc[eé]s\b",
}


def hizkuntza_asmatu(*testuak):
    """'eu' | 'es' | 'fr' | 'bi' | '' (zehaztugabea)."""
    t = " ".join(x or "" for x in testuak).lower()
    if re.search(HIZKUNTZA_HITZAK["bi"], t):
        return "bi"
    aurkituak = [h for h in ("eu", "es", "fr") if re.search(HIZKUNTZA_HITZAK[h], t)]
    if len(aurkituak) > 1:
        return "bi"
    return aurkituak[0] if aurkituak else ""
