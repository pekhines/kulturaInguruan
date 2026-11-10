# Kultura inguruan

Euskal Herriko (7 lurraldeak) kultur agenda: herri bat aukeratu, distantzia zehaztu,
eta inguruko kontzertuak, antzerkia, zinema, dantza, bertsolaritza, jaiak… ikusi.

## Nola dabil

```
 ┌────────────────────┐      ┌──────────────────┐      ┌───────────────────────┐
 │ ITURRIAK           │      │ ROBOTA (Python)  │      │ WEBGUNEA (docs/)      │
 │ Kulturklik (APIa)  │ ───▶ │ robota/bildu.py  │ ───▶ │ index.html + app.js   │
 │ EKE (HTMLa)        │      │ SQLite + JSON    │      │ ekitaldiak.json irak. │
 └────────────────────┘      └──────────────────┘      └───────────────────────┘
                              egunero, GitHub Actions     GitHub Pages (doan)
```

- **`robota/`**: iturrietatik ekitaldiak bildu eta `docs/datuak/ekitaldiak.json` sortzen du.
- **`docs/`**: webgunea. Zerbitzaririk ez du behar; nabigatzaileak egiten ditu
  distantzia-kalkuluak eta iragazkiak.
- **`docs/datuak/udalerriak.json`**: 7 lurraldeetako 684 udalerriak eta haien barruko
  2.151 herri (kontzejuak, auzoak, herrixkak), koordenatuekin eta izen guztiekin
  (Baiona/Bayonne, Iruñea/Pamplona, Elizondo (Baztan)…).

## Ordenagailuan probatzeko

```bash
# Behin bakarrik
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt

# LLM gakoa (aukerakoa): sortu `.env` fitxategia erroan, lerro honekin.
# .env ez da inoiz GitHub-era igotzen (.gitignore-n dago).
#   OPENROUTER_API_KEY=sk-or-...

# Robota exekutatu (≈5 minutu; LLMarekin lehen aldian 20-40 minutu, gero cachea)
.venv/bin/python robota/bildu.py

# Iturri bat edo batzuk bakarrik (besteen datuak ez dira ukitzen)
.venv/bin/python robota/bildu.py Dantzan.eus EKE

# Udal webguneetan agendak bilatu (hilean behin nahikoa)
.venv/bin/python robota/agendak_aurkitu.py

# Wikidatan webgunerik ez duten udalentzat webgunea asmatu (baztan.eus…), gero aurkitzailea berriro
.venv/bin/python robota/webguneak_asmatu.py

# Webgunea ikusi: ireki http://localhost:8000
cd docs && python3 -m http.server 8000
```

## Internetera argitaratzeko (GitHub, doan)

1. GitHub-en biltegi berri bat sortu eta karpeta hau igo.
2. *Settings → Pages*: "Deploy from a branch", `main` adarra, `/docs` karpeta.
3. *Settings → Actions → General*: "Read and write permissions" gaitu.
4. *Settings → Secrets and variables → Actions → New repository secret*:
   izena `OPENROUTER_API_KEY`, balioa zure gakoa. (Gakoa ez da inoiz kodean idazten.)
5. Kitto. Robota egunero 04:00etan (UTC) exekutatuko da (`.github/workflows/egunero.yml`)
   eta webgunea bakarrik eguneratuko da. *Actions* fitxatik eskuz ere exekutatu daiteke.
   - **Egunero**: iturri egituratuak (LLMrik gabe, ~15 minutu).
   - **Astearteetan**: gainera, udal webguneak eta agendak berriro bilatzen dira.
   - **Ostegunetan** (eta eskuz exekutatzean): gainera, LLM agendak (~30-60 minutu).

Iturri bat hausten bada (webgunea aldatu dutelako, adibidez), robotak aurreko datuak
mantentzen ditu, besteekin jarraitzen du, eta GitHub-ek posta bidez abisatzen dizu.

## Iturri berri bat gehitzeko

**Erraza (programatu gabe)**: agenda-orri baten helbidea `robota/agenda_orriak.json`-en
gehitu. LLMak irakurriko du:

```json
{"izena": "Herriko euskara elkartea", "url": "https://…/agenda", "herria": "Elgoibar"}
```

**Agendak formatu estandarra badu** (WordPress "The Events Calendar", iCal edo schema.org),
gehitu `"metodoa"` eremua eta ez da LLMrik behar:

```json
{"izena": "Karrikiri", "herria": "Iruñea", "metodoa": "tribe",
 "url": "https://www.karrikiri.eus/wp-json/tribe/events/v1/events"}
```

**Tokiko hedabide bat Tokikom plataforman** badago (`/agenda/` orrian "tk-agendaindex"):
gehitu `robota/iturriak/tokikom.py`-ko `HEDABIDEAK` zerrendara.

**Iturri berezi bat (programatuz)**:

1. Sortu `robota/iturriak/nire_iturria.py` fitxategia, `ekitaldiak(udalerriak)`
   funtzio batekin. Funtzio horrek ekitaldiak itzultzen ditu (`yield`), `eke.py`-k
   egiten duen formatu berean.
2. Herriaren izena koordenatu bihurtzeko: `udalerriak.bilatu("Elgoibar")`.
3. Gehitu `robota/bildu.py`-ko `ITURRIAK` zerrendara.

Ekitaldi baten formatua:

```json
{
  "id": "iturria:identifikadore-bakarra",
  "iturria": "Iturriaren izena",
  "izenburua": "…",
  "kategoria": "musika | antzerkia | dantza | zinema | bertsolaritza | jaiak | jaialdia | erakusketa | hitzaldia | haurrak | ikastaroa | bestelakoa",
  "data_hasiera": "2026-11-07", "data_amaiera": "2026-11-07",
  "ordua": "20:30", "lekua": "…", "prezioa": "…", "deskribapena": "…",
  "url": "https://…", "irudia": "https://…",
  "kokapenak": [{"herria": "…", "lurraldea": "…", "lat": 43.1, "lon": -2.4}]
}
```

## Bikoiztuak

Ekitaldi bera iturri askotan agertzen da sarri (Kulturklik, udala, tokiko hedabidea…).
`robota/bateratu.py`-k bakar bihurtzen ditu: **herri bera + egun bera + ordu bera** (edo batek ordurik ez)
eta **izen antzekoa**. Izenburuen hitz bereizgarriak alderatzen dira; jaialdien izenak bezalako hitz
arruntek ("Mapamunditarrak 2026: …") pisu txikia dute, eta iturri bereko bi ekitaldi desberdin ez dira
inoiz batzen. Lehentasun handieneko iturriarena gordetzen da, besteen datuekin osatuta, eta webguneak
iturri guztien estekak erakusten ditu ("Kulturklik · Hiruka").

## Hizkuntza

Ekitaldi bakoitzak `hizkuntza` eremua du: `eu`, `es`, `fr`, `bi` (elebiduna) edo hutsik (zehaztugabea).
Testuak **argi esaten duenean bakarrik** jartzen da ("euskaraz", "en castellano", "en français",
"elebiduna", "euskaraz eta gazteleraz"…), `robota/lagungarriak.py`-ko `hizkuntza_asmatu()` funtzioarekin.
Izenburua zein hizkuntzatan idatzita dagoen ez da kontuan hartzen. Salbuespenak: Pantailak Euskaraz-en
saioak eta bertsolaritza beti euskaraz; LLMari ere orriak argi esaten duenean bakarrik eskatzen zaio.

## Iturriak

| Iturria | Lurraldeak | Nola |
|---|---|---|
| [Kulturklik](https://www.kulturklik.euskadi.eus) | 7ak (EAE batez ere) | API irekia (JSON) |
| Tokiko hedabideak (Tokikom): Goiena, Anboto, Alea, Guka, Euskalerria Irratia… (22) | Hegoaldea | schema.org microdata |
| Udal agendak (aurkitzaileak topatuak) | 7ak | WordPress APIa, iCal, schema.org, IZFE |
| [Euskal Kultur Erakundea](https://www.eke.eus/eu/agenda) | Iparraldea | HTMLa irakurrita |
| [Dantzan.eus](https://dantzan.eus/agenda) | 7ak (dantza) | HTMLa irakurrita |
| [Pays Basque turismo bulegoa](https://www.en-pays-basque.fr/votre-sejour/tout-lagenda/) | Iparraldea (hiru lurraldeak) | HTMLa irakurrita |
| [Cultura Navarra](https://www.culturanavarra.es/es/agenda) (Nafarroako Gobernua) | Nafarroa Garaia | HTMLa irakurrita (LLMrik gabe: webguneak ez du AA erabilera onartzen) |
| [Iruñeko udala](https://www.pamplona.es/eu/gaurkotasuna/ekitaldiak) | Iruñea | HTMLa irakurrita |
| [Visit Navarra](https://www.visitnavarra.es/es/agenda) | Nafarroa Garaia (jai eta feria handiak) | HTMLa irakurrita |
| Elkarteen agendak (Karrikiri…) eta Eibarko udala ([eibarkultura.eus](https://eibarkultura.eus/egutegia/) barne) | 7ak | `agenda_orriak.json`, formatu estandarrak (WordPress, iCal, schema.org, Modern Events Calendar, Plone) |
| [Kutxabank Tickets](https://tickets.kutxabank.es/) | Bizkaia, Gipuzkoa (antzoki, auditorio, herrietako zinemak) | Webguneak berak erabiltzen duen Firestore datu-base publikoa (JSON) |
| [Zarata (MondoSonoro)](https://www.mondosonoro.com/agenda-zarata/) | 7ak (kontzertuak; Errioxakoak ez) | WordPress APIa, testua irakurrita (LLMrik gabe) |
| [Pantailak Euskaraz / Zer non ikusi](https://www.zernonikusi.eus/zinema) | Hegoaldea | Euskarazko zinema-saioak, API irekia (JSON) |
| [Euskadiko Agenda Turistikoa](https://turismo.euskadi.eus/agenda-turistica-de-euskadi/webtur00-recursostop/es/) | EAE (jaiak, azokak) | Datu irekiak (JSON) |
| Beste agenda-orriak (udalak, hedabideak) | 7ak | LLM (OpenRouter, doako eredua) + cachea |

## Hurrengo pausoak (ideiak)

- **Nafarroa**: euskara elkarte gehiago; Ttipi-ttapa eta Xorroxin-ek ez dute agenda irakurgarririk.
- **Baiona**: udalaren webguneak robotak blokeatzen ditu (HTTP 418); turismo bulegotik datoz ekitaldiak.
- **NAIZ-en agenda**: RSS jarioak ez du herria ez estekarik; LLMarekin irakur daiteke.
- **Webgunerik gabeko udalak**: `webguneak_asmatu.py`-k 80 aurkitu zituen; gainerakoak eskuz.
- **PDF agendak eta kartelak** (Animsa-ko Nafarroako udalek horrela argitaratzen dute):
  LLM irakurlea PDFetara eta irudietara zabaldu.
- **JavaScript bidez kargatzen diren agendak** (Berria, Hitza-ren edizioak): haien APIa bilatu.
- **Argia eta EITB**: ez dute agenda-orri publikorik aurkitu; berrietatik atera daiteke.
- **Iturriekiko errespetua**: `robots.txt` errespetatu, eskaeren artean pausa egin,
  eta beti jatorrizko iturrira estekatu.

Udalerrien zerrenda berriro sortzeko (gutxitan behar da): `python robota/udalerriak_sortu.py`
