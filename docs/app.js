// Kultura inguruan — frontenda
// Datuak: datuak/udalerriak.json eta datuak/ekitaldiak.json (robotak sortuak)

const KATEGORIAK = {
  musika: "Musika",
  antzerkia: "Antzerkia",
  dantza: "Dantza",
  zinema: "Zinema",
  bertsolaritza: "Bertsolaritza",
  jaiak: "Jaiak",
  azoka: "Azokak",
  jaialdia: "Jaialdiak",
  erakusketa: "Erakusketak",
  hitzaldia: "Hitzaldiak",
  haurrak: "Haurrentzat",
  ikastaroa: "Ikastaroak",
  bestelakoa: "Bestelakoak",
};
// Iturri-taldeak (robotak ekitaldi bakoitzari "taldea" jartzen dio; ikus robota/bildu.py).
// [izena, azalpena (sagua gainean jartzean)]
const ITURRIAK = {
  kulturklik: ["Kulturklik", "Eusko Jaurlaritzaren kultur agenda"],
  hedabideak: ["Tokiko hedabideak", "Goiena, Anboto, Alea, Guka, Barrena, Erran, Euskalerria Irratia… (Tokikom)"],
  udalak: ["Udalak", "Udalen webguneetako agendak"],
  elkarteak: ["Elkarteak eta hedabideak", "Karrikiri, Herria, Geuria eta beste agenda batzuk"],
  pantailak: ["Pantailak Euskaraz", "Euskarazko zinema-saioak aretoz areto"],
  dantzan: ["Dantzan.eus", "Euskal dantzaren agenda"],
  eke: ["EKE", "Euskal Kultur Erakundea (Iparraldea)"],
  culturanavarra: ["Cultura Navarra", "Nafarroako Gobernuaren kultur agenda"],
  zarata: ["Zarata", "MondoSonoro-ren kontzertu-agenda (Zarata edizioa)"],
  musikazuzenean: ["Musika Zuzenean", "Euskal musikaren kontzertu-agenda: taldeek eta antolatzaileek igotakoak, gaztetxeak barne"],
  metaleuskadi: ["Metal Euskadi", "Metal eta rock kontzertuak lurraldeka, gaztetxeak barne"],
  antzokiak: ["Antzokiak", "Antzokien karteldegiak: Kursaal, Campos Elíseos, LABA, Scène Nationale (Baiona, Angelu, Donibane Lohizune, Bokale)"],
  kutxabank: ["Kutxabank Tickets", "Kutxabank-en sarrera-salmenta: antzoki, auditorio eta herrietako zinemak"],
  turismoa: ["Turismo bulegoak", "Pays Basque turismo bulegoa, Visit Navarra, Euskadiko Agenda Turistikoa"],
};
// Ekitaldiaren hizkuntza (robotak "hizkuntza" jartzen du testuak argi esaten duenean; bestela zehaztugabea)
const HIZKUNTZAK = {
  eu: ["Euskaraz", "Ekitaldia euskaraz da"],
  es: ["Gazteleraz", "Ekitaldia gazteleraz da"],
  fr: ["Frantsesez", "Ekitaldia frantsesez da"],
  bi: ["Elebiduna", "Bi hizkuntzatan"],
  zehaztugabea: ["Zehaztugabea", "Iturriak ez du hizkuntza zehazten (kontzertu, erakusketa askotan ez du axola)"],
};
const HIZKUNTZA_ETIKETAK = { eu: "euskaraz", es: "gazteleraz", fr: "frantsesez", bi: "elebiduna" };
const hizkuntza = (e) => (e.hizkuntza in HIZKUNTZA_ETIKETAK ? e.hizkuntza : "zehaztugabea");

const ASTEGUNAK = ["igandea", "astelehena", "asteartea", "asteazkena", "osteguna", "ostirala", "larunbata"];
const HILABETEAK = ["urtarrilak", "otsailak", "martxoak", "apirilak", "maiatzak", "ekainak",
  "uztailak", "abuztuak", "irailak", "urriak", "azaroak", "abenduak"];
const EGUN_ASKOTAKOA = 7; // egun hauek baino gehiago irauten dutenak bereizita erakusten dira

const egoera = {
  udalerriak: [],
  ekitaldiak: [],
  zentroa: null,          // {izena, lat, lon}
  km: 20,
  noiz: "astea",
  tartea: null,           // [hasiera, amaiera] "YYYY-MM-DD"
  kategoriak: new Set(Object.keys(KATEGORIAK)),
  iturriak: new Set(Object.keys(ITURRIAK)),
  hizkuntzak: new Set(Object.keys(HIZKUNTZAK)),
};

const $ = (id) => document.getElementById(id);

// ---------- Lagungarriak ----------

function normalizatu(t) {
  return (t || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9ñ]+/g, " ").trim();
}

function ihes(t) {
  // Kanpoko testua HTMLan seguru sartzeko
  return String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function distantzia(lat1, lon1, lat2, lon2) {
  const r = 6371, rad = Math.PI / 180;
  const dp = (lat2 - lat1) * rad, dl = (lon2 - lon1) * rad;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}

function isoData(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function gehituEgunak(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
function dataIrakurri(s) { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); }
function egunKopurua(a, b) { return Math.round((dataIrakurri(b) - dataIrakurri(a)) / 86400000); }

function dataTestua(s) {
  const d = dataIrakurri(s);
  const t = `${ASTEGUNAK[d.getDay()]}, ${HILABETEAK[d.getMonth()]} ${d.getDate()}`;
  return t[0].toUpperCase() + t.slice(1);
}
function dataLaburra(s) {
  const d = dataIrakurri(s);
  return `${HILABETEAK[d.getMonth()]} ${d.getDate()}`;
}

// "Eibar (Gipuzkoa)", "Elizondo (Baztan)", "Armentia (Araba)"
function herriEtiketa(u) { return `${u.izena} (${u.udalerria || u.lurraldea})`; }

// ---------- Noiz ----------

function tarteaKalkulatu(noiz) {
  const gaur = new Date();
  switch (noiz) {
    case "gaur": return [isoData(gaur), isoData(gaur)];
    case "bihar": { const b = gehituEgunak(gaur, 1); return [isoData(b), isoData(b)]; }
    case "asteburua": {
      // ostiraletik igandera; asteburuan bagaude, gaurtik igandera
      const eguna = gaur.getDay(); // 0 = igandea
      const igandera = (7 - eguna) % 7;
      const hasiera = eguna === 0 || eguna >= 5 ? gaur : gehituEgunak(gaur, 5 - eguna);
      return [isoData(hasiera), isoData(gehituEgunak(gaur, igandera))];
    }
    case "hilabetea": return [isoData(gaur), isoData(gehituEgunak(gaur, 30))];
    case "astea":
    default: return [isoData(gaur), isoData(gehituEgunak(gaur, 6))];
  }
}

// ---------- Herria ----------

function herriaBilatu(testua) {
  const n = normalizatu(testua);
  if (!n) return null;
  // 1) "Izena (Lurraldea)" zehatza
  const zehatza = egoera.udalerriak.find((u) => normalizatu(herriEtiketa(u)) === n);
  if (zehatza) return zehatza;
  // 2) izen ofizial edo alternatiboa (Baiona / Bayonne); udalerriak herrien aurretik
  const izenez = egoera.udalerriak.find((u) => u.mota === "udalerria" && u.izenak.some((i) => normalizatu(i) === n))
    || egoera.udalerriak.find((u) => u.izenak.some((i) => normalizatu(i) === n));
  if (izenez) return izenez;
  // 3) hasiera berdina
  return egoera.udalerriak.find((u) => u.izenak.some((i) => normalizatu(i).startsWith(n))) || null;
}

// Izen bereko herri bat baino gehiago (adib. Elizondo Baztanen eta Lemoan): denak itzuli
function izenBerekoak(testua) {
  const n = normalizatu(testua);
  if (!n) return [];
  return egoera.udalerriak.filter((u) => u.izenak.some((i) => normalizatu(i) === n));
}

// "Zein Elizondo?": aukerak botoi gisa erakutsi, erabiltzaileak aukeratzeko
function aukerakErakutsi(hautatua, aukerak) {
  const kutxa = $("aukerak");
  const besteak = aukerak.filter((u) => u.id !== hautatua.id);
  if (!besteak.length) { kutxa.hidden = true; return; }
  kutxa.innerHTML = "Beste hau esan nahi zenuen? " + besteak.map((u) =>
    `<button type="button" data-id="${ihes(u.id)}">${ihes(herriEtiketa(u))}</button>`).join(" ");
  kutxa.hidden = false;
}

function zentroaEzarri(u) {
  egoera.zentroa = u ? { id: u.id, izena: u.izena, lat: u.lat, lon: u.lon } : null;
  if (u && u.id) localStorage.setItem("azken-herria", u.id);
  eguneratu();
}

// ---------- Iragazkia ----------

function iragazi() {
  const [hasiera, amaiera] = egoera.tartea;
  const z = egoera.zentroa;
  const emaitza = [];
  for (const e of egoera.ekitaldiak) {
    if (!egoera.kategoriak.has(e.kategoria)) continue;
    // Batutako ekitaldiek talde bat baino gehiago izan dezakete (iturri bat baino gehiagotan agertzen da)
    if (e.taldea && !(e.taldeak || [e.taldea]).some((t) => egoera.iturriak.has(t))) continue;
    if (!egoera.hizkuntzak.has(hizkuntza(e))) continue;
    if (e.data_hasiera > amaiera || e.data_amaiera < hasiera) continue;
    let km = null, herria = e.kokapenak[0];
    if (z) {
      for (const k of e.kokapenak) {
        const d = distantzia(z.lat, z.lon, k.lat, k.lon);
        if (km === null || d < km) { km = d; herria = k; }
      }
      if (km > egoera.km) continue;
    }
    emaitza.push({ e, km, herria });
  }
  return emaitza;
}

// ---------- Zerrenda ----------

function ekitaldiaHTML({ e, km, herria }, egunAskotakoa) {
  // "Ordutegia kontsultatu" bezalako testuak ez dira orduaren zutabean erakusten
  const ordua = !egunAskotakoa && /\d/.test(e.ordua || "") ? ihes(e.ordua) : "";
  const tartea = egunAskotakoa ? `${dataLaburra(e.data_hasiera)} – ${dataLaburra(e.data_amaiera)}` : "";
  const besteHerriak = e.kokapenak.length > 1 ? ` <span class="xehetasunak">(+${e.kokapenak.length - 1} herri)</span>` : "";
  const xehetasunak = [tartea, e.lekua, e.prezioa].filter(Boolean).map(ihes).join(" · ");
  const izenburua = e.url
    ? `<a href="${ihes(e.url)}" target="_blank" rel="noopener">${ihes(e.izenburua)}</a>`
    : ihes(e.izenburua);
  return `
    <article class="ekitaldia" data-herria="${ihes(herria.herria)}">
      <div class="ordua">${ordua}</div>
      <div>
        <h3>${izenburua}</h3>
        <div class="non">
          <span class="etiketa">${ihes(KATEGORIAK[e.kategoria] || e.kategoria)}</span>${
            HIZKUNTZA_ETIKETAK[e.hizkuntza] ? ` <span class="etiketa hizkuntza-etiketa">${HIZKUNTZA_ETIKETAK[e.hizkuntza]}</span>` : ""}
          <strong>${ihes(herria.herria)}</strong>${km !== null ? ` · <span class="km-etiketa">${km < 1 ? "<1" : Math.round(km)} km</span>` : ""}${besteHerriak}
        </div>
        ${xehetasunak ? `<div class="xehetasunak">${xehetasunak}</div>` : ""}
        <div class="xehetasunak">${iturriakHTML(e)}</div>
      </div>
    </article>`;
}

// "Kulturklik · Hiruka": bikoiztuak bateratzean, beste iturrien estekak ere bai
function iturriakHTML(e) {
  const beste = (e.beste_iturriak || []).map((b) => b.url
    ? `<a href="${ihes(b.url)}" target="_blank" rel="noopener">${ihes(b.iturria)}</a>`
    : ihes(b.iturria));
  return [ihes(e.iturria), ...beste].join(" · ");
}

function zerrendaMargotu(emaitzak) {
  const [hasiera] = egoera.tartea;
  const laburrak = [], luzeak = [];
  for (const r of emaitzak) {
    (egunKopurua(r.e.data_hasiera, r.e.data_amaiera) > EGUN_ASKOTAKOA ? luzeak : laburrak).push(r);
  }

  // Egunaren arabera multzokatu (dagoeneko hasita daudenak tartearen lehen egunean)
  const egunak = new Map();
  for (const r of laburrak) {
    const eguna = r.e.data_hasiera < hasiera ? hasiera : r.e.data_hasiera;
    if (!egunak.has(eguna)) egunak.set(eguna, []);
    egunak.get(eguna).push(r);
  }
  const ordenatu = (a, b) => (a.e.ordua || "99").localeCompare(b.e.ordua || "99") || (a.km ?? 0) - (b.km ?? 0);

  let html = "";
  for (const eguna of [...egunak.keys()].sort()) {
    html += `<h2 class="eguna">${dataTestua(eguna)}</h2>`;
    html += egunak.get(eguna).sort(ordenatu).map((r) => ekitaldiaHTML(r, false)).join("");
  }
  if (luzeak.length) {
    html += `<h2 class="eguna">Egun askotan zehar (erakusketak, zikloak…)</h2>`;
    html += luzeak.sort((a, b) => (a.km ?? 0) - (b.km ?? 0)).map((r) => ekitaldiaHTML(r, true)).join("");
  }
  $("zerrenda").innerHTML = html || `<p class="hutsik">Ez dago ekitaldirik iragazki hauekin. Probatu distantzia handitzen edo data-tartea zabaltzen.</p>`;

  const non = !egoera.zentroa ? "Euskal Herri osoan"
    : egoera.zentroa.id ? `${ihes(egoera.zentroa.izena)} inguruan (${egoera.km} km)`
    : `zure inguruan (${egoera.km} km)`;
  $("laburpena").innerHTML = `<strong>${emaitzak.length}</strong> ekitaldi · ${non} · ${dataLaburra(egoera.tartea[0])}–${dataLaburra(egoera.tartea[1])}`;
}

// ---------- Mapa ----------

let mapa, geruza, zirkulua;

function mapaHasieratu() {
  mapa = L.map("mapa").setView([43.1, -1.9], 8);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(mapa);
  geruza = L.layerGroup().addTo(mapa);
}

function mapaMargotu(emaitzak) {
  geruza.clearLayers();
  if (zirkulua) { zirkulua.remove(); zirkulua = null; }

  // Herri bakoitzeko markatzaile bat
  const herriak = new Map();
  for (const r of emaitzak) {
    const k = r.herria;
    const gakoa = `${k.lat},${k.lon}`;
    if (!herriak.has(gakoa)) herriak.set(gakoa, { k, zerrenda: [] });
    herriak.get(gakoa).zerrenda.push(r.e);
  }
  for (const { k, zerrenda } of herriak.values()) {
    const erradioa = Math.min(6 + Math.sqrt(zerrenda.length) * 2.5, 22);
    const popup = `<strong>${ihes(k.herria)}</strong> (${zerrenda.length})<br>` +
      zerrenda.slice(0, 8).map((e) => `· ${ihes(e.izenburua)}`).join("<br>") +
      (zerrenda.length > 8 ? `<br>… eta ${zerrenda.length - 8} gehiago` : "");
    L.circleMarker([k.lat, k.lon], { radius: erradioa, color: "#c8102e", weight: 1, fillOpacity: 0.55 })
      .bindPopup(popup).addTo(geruza);
  }

  if (egoera.zentroa) {
    const z = egoera.zentroa;
    zirkulua = L.circle([z.lat, z.lon], { radius: egoera.km * 1000, color: "#1f2328", weight: 1, fill: false, dashArray: "4 4" }).addTo(mapa);
    L.marker([z.lat, z.lon]).bindTooltip(z.izena).addTo(geruza);
    mapa.fitBounds(zirkulua.getBounds(), { padding: [10, 10] });
  }
}

// ---------- Egoera eta URLa ----------

function urlaEguneratu() {
  const p = new URLSearchParams();
  if (egoera.zentroa?.id) p.set("herria", egoera.zentroa.id);
  p.set("km", egoera.km);
  p.set("noiz", egoera.noiz === "tartea" ? egoera.tartea.join("_") : egoera.noiz);
  if (egoera.kategoriak.size !== Object.keys(KATEGORIAK).length) p.set("mota", [...egoera.kategoriak].join(","));
  if (egoera.iturriak.size !== Object.keys(ITURRIAK).length) p.set("iturri", [...egoera.iturriak].join(","));
  if (egoera.hizkuntzak.size !== Object.keys(HIZKUNTZAK).length) p.set("hizk", [...egoera.hizkuntzak].join(","));
  history.replaceState(null, "", "#" + p.toString());
}

function urlaIrakurri() {
  const p = new URLSearchParams(location.hash.slice(1));
  const herriId = p.get("herria") || localStorage.getItem("azken-herria");
  const u = egoera.udalerriak.find((x) => x.id === herriId);
  if (u) { egoera.zentroa = { id: u.id, izena: u.izena, lat: u.lat, lon: u.lon }; $("herria").value = herriEtiketa(u); }
  if (p.get("km")) egoera.km = Math.max(2, Math.min(100, Number(p.get("km")) || 20));
  const noiz = p.get("noiz");
  if (noiz && noiz.includes("_")) { egoera.noiz = "tartea"; egoera.tartea = noiz.split("_"); }
  else if (noiz) egoera.noiz = noiz;
  if (p.get("mota")) egoera.kategoriak = new Set(p.get("mota").split(",").filter((k) => k in KATEGORIAK));
  if (p.get("iturri")) egoera.iturriak = new Set(p.get("iturri").split(",").filter((k) => k in ITURRIAK));
  if (!egoera.kategoriak.size) egoera.kategoriak = new Set(Object.keys(KATEGORIAK));
  if (!egoera.iturriak.size) egoera.iturriak = new Set(Object.keys(ITURRIAK));
  if (p.get("hizk")) egoera.hizkuntzak = new Set(p.get("hizk").split(",").filter((k) => k in HIZKUNTZAK));
  if (!egoera.hizkuntzak.size) egoera.hizkuntzak = new Set(Object.keys(HIZKUNTZAK));
}

function eguneratu() {
  if (egoera.noiz !== "tartea") egoera.tartea = tarteaKalkulatu(egoera.noiz);
  $("km-balioa").textContent = egoera.km;
  $("km").value = egoera.km;
  $("data-noiz").value = egoera.tartea[0];
  $("data-arte").value = egoera.tartea[1];
  document.querySelectorAll("[data-noiz]").forEach((b) => b.classList.toggle("aktiboa", b.dataset.noiz === egoera.noiz));
  document.querySelectorAll("[data-kategoria]").forEach((b) => b.classList.toggle("aktiboa", egoera.kategoriak.has(b.dataset.kategoria)));
  document.querySelectorAll("[data-iturria]").forEach((b) => b.classList.toggle("aktiboa", egoera.iturriak.has(b.dataset.iturria)));
  document.querySelectorAll("[data-hizkuntza]").forEach((b) => b.classList.toggle("aktiboa", egoera.hizkuntzak.has(b.dataset.hizkuntza)));

  const emaitzak = iragazi();
  zerrendaMargotu(emaitzak);
  mapaMargotu(emaitzak);
  urlaEguneratu();
}

// ---------- Hasiera ----------

function kontrolakLotu() {
  $("herria").addEventListener("change", (ev) => {
    const u = herriaBilatu(ev.target.value);
    const aukerak = u ? izenBerekoak(u.izena) : [];
    if (u) ev.target.value = herriEtiketa(u);
    if (u && aukerak.length > 1) aukerakErakutsi(u, aukerak); else $("aukerak").hidden = true;
    zentroaEzarri(u);
  });
  $("aukerak").addEventListener("click", (ev) => {
    const id = ev.target.dataset && ev.target.dataset.id;
    const u = id && egoera.udalerriak.find((x) => x.id === id);
    if (!u) return;
    $("herria").value = herriEtiketa(u);
    $("aukerak").hidden = true;
    zentroaEzarri(u);
  });
  $("herria").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") ev.target.dispatchEvent(new Event("change"));
  });

  $("kokapena").addEventListener("click", () => {
    if (!navigator.geolocation) return alert("Zure nabigatzaileak ez du kokapena ematen.");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        $("herria").value = "📍 Nire kokapena";
        egoera.zentroa = { id: null, izena: "Zure kokapena", lat: pos.coords.latitude, lon: pos.coords.longitude };
        eguneratu();
      },
      () => alert("Ezin izan da kokapena lortu."),
    );
  });

  let kmTimer;
  $("km").addEventListener("input", (ev) => {
    egoera.km = Number(ev.target.value);
    $("km-balioa").textContent = egoera.km;
    clearTimeout(kmTimer);
    kmTimer = setTimeout(eguneratu, 120);
  });

  document.querySelectorAll("[data-noiz]").forEach((b) =>
    b.addEventListener("click", () => { egoera.noiz = b.dataset.noiz; eguneratu(); }));

  const tarteaAldatu = () => {
    let [a, b] = [$("data-noiz").value, $("data-arte").value];
    if (!a || !b) return;
    if (a > b) [a, b] = [b, a];
    egoera.noiz = "tartea";
    egoera.tartea = [a, b];
    eguneratu();
  };
  $("data-noiz").addEventListener("change", tarteaAldatu);
  $("data-arte").addEventListener("change", tarteaAldatu);

  txipak($("kategoriak"), KATEGORIAK, "kategoriak", "kategoria");
  txipak($("iturriak"), ITURRIAK, "iturriak", "iturria");
  txipak($("hizkuntzak"), HIZKUNTZAK, "hizkuntzak", "hizkuntza");
}

// Txip-botoiak (kategoriak, iturriak): lehen klikak bakarra aukeratzen du; gero gehitu/kendu;
// "Guztiak"-ek denak berreskuratzen ditu.
function txipak(edukiontzia, aukerak, gakoa, atributua) {
  const denak = () => new Set(Object.keys(aukerak));
  edukiontzia.insertAdjacentHTML("beforeend",
    `<button type="button" data-guztiak>Guztiak</button>` +
    Object.entries(aukerak).map(([k, balioa]) => {
      const [izena, azalpena] = Array.isArray(balioa) ? balioa : [balioa, ""];
      return `<button type="button" data-${atributua}="${k}" title="${ihes(azalpena)}">${ihes(izena)}</button>`;
    }).join(""));
  edukiontzia.querySelector("[data-guztiak]").addEventListener("click", () => {
    egoera[gakoa] = denak();
    eguneratu();
  });
  edukiontzia.querySelectorAll(`[data-${atributua}]`).forEach((b) => b.addEventListener("click", () => {
    const k = b.dataset[atributua];
    const multzoa = egoera[gakoa];
    if (multzoa.size === Object.keys(aukerak).length) egoera[gakoa] = new Set([k]);  // lehen klika: hau bakarrik
    else if (multzoa.has(k)) multzoa.delete(k);
    else multzoa.add(k);
    if (egoera[gakoa].size === 0) egoera[gakoa] = denak();
    eguneratu();
  }));
}

async function hasi() {
  mapaHasieratu();
  kontrolakLotu();
  try {
    const [udalerriak, datuak] = await Promise.all([
      fetch("datuak/udalerriak.json").then((r) => r.json()),
      fetch("datuak/ekitaldiak.json").then((r) => r.json()),
    ]);
    egoera.udalerriak = udalerriak;
    egoera.ekitaldiak = datuak.ekitaldiak;
    $("herri-zerrenda").innerHTML = udalerriak.map((u) => `<option value="${ihes(herriEtiketa(u))}">`).join("");
    const eguneratua = new Date(datuak.sortua);
    $("eguneratua").textContent = `Datuak eguneratuta: ${isoData(eguneratua)} ${eguneratua.toTimeString().slice(0, 5)}`;
  } catch (err) {
    $("laburpena").textContent = "Errorea datuak kargatzean. Saiatu berriro geroago.";
    console.error(err);
    return;
  }
  urlaIrakurri();
  eguneratu();
}

hasi();
