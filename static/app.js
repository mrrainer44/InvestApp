/* GPW Tracker – interfejs */
"use strict";

const api = async (url, opts = {}) => {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
};
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const toast = (msg) => { const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove("show"), 2200); };
const debounce = (fn, ms) => { let h; return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), ms); }; };

const nf = (d) => new Intl.NumberFormat("pl-PL", { minimumFractionDigits: d, maximumFractionDigits: d });
const F = { 0: nf(0), 1: nf(1), 2: nf(2) };
const fmtNum = (v, d = 2) => v == null || v === "" || isNaN(v) ? "" : F[d].format(v);
const fmtMoney = (v) => {
  if (v == null) return "";
  const a = Math.abs(v);
  if (a >= 1e9) return `${F[2].format(v / 1e9)} mld`;
  if (a >= 1e6) return `${F[1].format(v / 1e6)} mln`;
  if (a >= 1e3) return `${F[0].format(v / 1e3)} tys.`;
  return F[0].format(v);
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const espiHref = (url) => /^https:\/\//.test(url || "") ? url : `https://www.biznesradar.pl${url || ""}`;

/* ---------- formatery komórek ---------- */
const pct = (cell) => { const v = cell.getValue(); if (v == null) return "";
  return `<span class="${v > 0 ? "up" : v < 0 ? "down" : ""}">${v > 0 ? "+" : ""}${fmtNum(v, 2)}%</span>`; };
const num2 = (cell) => fmtNum(cell.getValue(), 2);
const money = (cell) => fmtMoney(cell.getValue());
const ratio = (cell) => { const v = cell.getValue(); if (v == null) return "";
  return v < 0 ? `<span class="dim">${fmtNum(v, 1)}</span>` : fmtNum(v, 1); };
const yesno = (cell) => cell.getValue() ? "tak" : `<span class="dim">nie</span>`;
const tickerFmt = (cell) => `<a class="tk" href="#" data-t="${esc(cell.getValue())}">${esc(cell.getValue())}</a>`;

let flowScale = 1;
const flowBar = (v, scale) => {
  if (v == null) return "";
  const w = Math.min(100, Math.sqrt(Math.abs(v) / (scale || 1)) * 100);
  const bar = v >= 0 ? `<span></span><i class="pos" style="width:${w}%"></i>` : `<i class="neg" style="width:${w}%"></i><span></span>`;
  return `<div class="flow-cell"><div class="flow">${bar}</div><span class="v ${v >= 0 ? "up" : "down"}">${v > 0 ? "+" : ""}${fmtMoney(v)}</span></div>`;
};
const flowFmt = (cell) => flowBar(cell.getValue(), flowScale);
const numSort = (a, b) => (a ?? -Infinity) - (b ?? -Infinity);

/* ---------- kolumny listy spółek ---------- */
const GROUPS = {
  base: "Podstawowe", quote: "Notowania", ret: "Stopy zwrotu", val: "Wycena",
  div: "Dywidendy", own: "Akcjonariat i przepływy", press: "Presja kupujących", af: "Analiza fundamentalna",
  custom: "Moje kolumny",
};
const cmfFmt = (cell) => { const v = cell.getValue(); if (v == null) return `<span class="dim">–</span>`;
  const p = v * 100; return `<span class="${p > 10 ? "up" : p < -10 ? "down" : ""}">${p > 0 ? "+" : ""}${fmtNum(p, 0)}%</span>`; };
const CMF_TIP = "Przewaga kupujących w obrocie (Chaikin Money Flow): +100% = sesje kończyły się na maksimum dnia, −100% = na minimum. Powyżej +10% akumulacja, poniżej −10% dystrybucja.";
const afFmt = (cell) => cell.getValue()
  ? `<span class="af-yes" title="Analiz: ${cell.getRow().getData().af_count}">✓ ${esc(cell.getValue())}</span>` : `<span class="dim">–</span>`;
const BUILTIN = [
  { field: "ticker", title: "Ticker", group: "base", frozen: true, formatter: tickerFmt, headerFilter: "input", width: 86 },
  { field: "name", title: "Spółka", group: "base", headerFilter: "input", width: 190 },
  { field: "market", title: "Rynek", group: "base", headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true }, width: 80 },
  { field: "sector", title: "Branża", group: "base", headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true }, width: 160 },
  { field: "price", title: "Kurs", group: "quote", hozAlign: "right", formatter: num2, sorter: numSort },
  { field: "change_pct", title: "Zmiana dzienna", group: "quote", hozAlign: "right", formatter: pct, sorter: numSort },
  { field: "turnover", title: "Obrót dziś", group: "quote", hozAlign: "right", formatter: money, sorter: numSort },
  { field: "avg_turnover_30d", title: "Śr. obrót 30 dni", group: "quote", hozAlign: "right", formatter: money, sorter: numSort },
  { field: "mcap", title: "Kapitalizacja", group: "quote", hozAlign: "right", formatter: money, sorter: numSort },
  { field: "volume", title: "Wolumen", group: "quote", hozAlign: "right", formatter: (c) => fmtNum(c.getValue(), 0), sorter: numSort, visible: false },
  { field: "r1w", title: "1 tydz.", group: "ret", hozAlign: "right", formatter: pct, sorter: numSort },
  { field: "r1m", title: "1 mies.", group: "ret", hozAlign: "right", formatter: pct, sorter: numSort },
  { field: "r3m", title: "3 mies.", group: "ret", hozAlign: "right", formatter: pct, sorter: numSort, visible: false },
  { field: "r6m", title: "6 mies.", group: "ret", hozAlign: "right", formatter: pct, sorter: numSort, visible: false },
  { field: "ytd", title: "Od początku roku", group: "ret", hozAlign: "right", formatter: pct, sorter: numSort },
  { field: "r12m", title: "12 mies.", group: "ret", hozAlign: "right", formatter: pct, sorter: numSort },
  { field: "cz", title: "C/Z", group: "val", hozAlign: "right", formatter: ratio, sorter: numSort },
  { field: "cwk", title: "C/WK", group: "val", hozAlign: "right", formatter: ratio, sorter: numSort },
  { field: "evebitda", title: "EV/EBITDA", group: "val", hozAlign: "right", formatter: ratio, sorter: numSort },
  { field: "cp", title: "C/P", group: "val", hozAlign: "right", formatter: ratio, sorter: numSort, visible: false },
  { field: "report", title: "Ostatni raport", group: "val", visible: false },
  { field: "div_has", title: "Dywidenda", group: "div", formatter: yesno, headerFilter: "tickCross", headerFilterParams: { tristate: true }, hozAlign: "center" },
  { field: "div_yield", title: "Stopa dyw. 12 mies.", group: "div", hozAlign: "right", formatter: (c) => c.getValue() == null ? "" : fmtNum(c.getValue(), 2) + "%", sorter: numSort },
  { field: "div_dps12", title: "Dyw. na akcję 12 mies.", group: "div", hozAlign: "right", formatter: num2, sorter: numSort, visible: false },
  { field: "div_next_day", title: "Ostatni dzień z prawem", group: "div" },
  { field: "div_next_dps", title: "Najbliższa dywidenda", group: "div", hozAlign: "right", formatter: num2, sorter: numSort, visible: false },
  { field: "top_holders", title: "Główni akcjonariusze", group: "own", width: 260, tooltip: true, visible: false },
  { field: "free_float", title: "Free float (szac.)", group: "own", hozAlign: "right", formatter: (c) => c.getValue() == null ? "" : fmtNum(c.getValue(), 1) + "%", sorter: numSort, visible: false },
  { field: "funds_pct", title: "Udział OFE/TFI", group: "own", hozAlign: "right", formatter: (c) => c.getValue() == null ? "" : fmtNum(c.getValue(), 1) + "%", sorter: numSort },
  { field: "last_art69", title: "Ostatnie zawiadomienie", group: "own", width: 240, tooltip: true },
  { field: "flow_30d", title: "Przepływ 30 dni", group: "own", formatter: flowFmt, sorter: numSort, width: 190 },
  { field: "cmf63", title: "Presja 90 dni", group: "press", hozAlign: "right", formatter: cmfFmt, sorter: numSort, headerTooltip: CMF_TIP },
  { field: "cmf21", title: "Presja 30 dni", group: "press", hozAlign: "right", formatter: cmfFmt, sorter: numSort, headerTooltip: CMF_TIP, visible: false },
  { field: "af_date", title: "AF", group: "af", formatter: afFmt, width: 118, headerTooltip: "Data najnowszej analizy fundamentalnej (plik w OneDrive)",
    headerFilter: "tickCross", headerFilterParams: { tristate: true }, headerFilterFunc: (h, v) => h === null || h === !!v },
];
const DEFAULT_VISIBLE = Object.fromEntries(BUILTIN.map((c) => [c.field, c.visible !== false]));
const GROUP_OF = Object.fromEntries(BUILTIN.map((c) => [c.field, c.group]));
const CUSTOM_OF = {};

let customCols = [];
const customDef = (c) => {
  const def = { field: `c_${c.key}`, title: c.label, editable: true, cssClass: "custom-col" };
  GROUP_OF[def.field] = "custom"; CUSTOM_OF[def.field] = c.key;
  const opts = JSON.parse(c.options || "[]");
  if (c.type === "number") Object.assign(def, { editor: "number", hozAlign: "right", sorter: (a, b) => (+a || 0) - (+b || 0), formatter: (cell) => fmtNum(+cell.getValue(), 2), headerFilter: "input" });
  else if (c.type === "bool") Object.assign(def, { editor: "tickCross", formatter: (cell) => cell.getValue() === "true" || cell.getValue() === true ? "tak" : "", hozAlign: "center", headerFilter: "tickCross", headerFilterParams: { tristate: true }, headerFilterFunc: (h, v) => h === null || (h === (v === "true" || v === true)) });
  else if (c.type === "date") Object.assign(def, { editor: "date", sorter: "string" });
  else if (c.type === "list") Object.assign(def, { editor: "list", editorParams: { values: ["", ...opts], clearable: true }, headerFilter: "list", headerFilterParams: { values: opts, clearable: true } });
  else Object.assign(def, { editor: "input", headerFilter: "input", tooltip: true });
  return def;
};

/* ---------- tabela spółek ---------- */
let tblCompanies, market = "", views = {};
const layoutKey = "companies_layout";
const saveLayout = debounce(() => {
  if (!tblCompanies) return;
  const layout = tblCompanies.getColumnLayout().map(({ field, width, visible }) => ({ field, width, visible }));
  const sort = tblCompanies.getSorters().map((s) => ({ column: s.field, dir: s.dir }));
  api(`/api/settings/${layoutKey}`, { method: "PUT", body: { layout, sort } }).catch(() => {});
}, 600);

function applyLayout(saved) {
  if (!saved || !saved.layout) return;
  const byField = Object.fromEntries(tblCompanies.getColumns().map((c) => [c.getField(), c]));
  // kolejność
  let prev = null;
  for (const l of saved.layout) {
    const col = byField[l.field];
    if (!col) continue;
    if (l.visible === false) col.hide(); else col.show();
    if (l.width) col.setWidth(l.width);
    if (prev && byField[prev]) tblCompanies.moveColumn(l.field, prev, true);
    prev = l.field;
  }
  if (saved.sort && saved.sort.length) tblCompanies.setSort(saved.sort.filter((s) => byField[s.column]));
}

async function loadCompanies() {
  const [data, cols, saved, savedViews] = await Promise.all([
    api("/api/companies"), api("/api/columns"), api(`/api/settings/${layoutKey}`), api("/api/settings/views")]);
  customCols = cols;
  views = savedViews || {};
  renderViewSelect();
  const flows = data.map((d) => Math.abs(d.flow_30d || 0)).filter(Boolean).sort((a, b) => b - a);
  flowScale = flows[Math.min(5, flows.length - 1)] || 1;
  const columns = [...BUILTIN.map(({ group, ...c }) => c), ...customCols.map(customDef)];
  if (tblCompanies) tblCompanies.destroy();
  tblCompanies = new Tabulator("#tblCompanies", {
    data, columns, index: "ticker", height: "calc(100vh - 190px)", layout: "fitData",
    movableColumns: true, placeholder: "Brak danych. Uruchom pierwsze pobranie w zakładce „Dane i ustawienia”.",
    initialSort: [{ column: "mcap", dir: "desc" }], columnDefaults: { headerTooltip: true, resizable: true },
  });
  tblCompanies.on("tableBuilt", () => { applyLayout(saved); applyFilters();
    ["columnMoved", "columnResized", "columnVisibilityChanged", "dataSorted"].forEach((e) => tblCompanies.on(e, saveLayout)); });
  tblCompanies.on("cellEdited", async (cell) => {
    const key = CUSTOM_OF[cell.getField()];
    if (!key) return;
    let v = cell.getValue();
    if (v === false) v = "";
    await api("/api/values", { method: "PUT", body: { ticker: cell.getRow().getIndex(), key, value: v } });
    toast("Zapisano");
  });
}

function applyFilters() {
  const q = $("#q").value.trim().toLowerCase();
  tblCompanies.setFilter((d) => (!market || d.market === market) &&
    (!q || [d.ticker, d.name, d.short, d.sector].some((x) => (x || "").toLowerCase().includes(q))));
}

function renderViewSelect() {
  const sel = $("#viewSel");
  sel.innerHTML = `<option value="">Widok: bieżący</option>` +
    Object.keys(views).map((n) => `<option>${esc(n)}</option>`).join("") +
    (Object.keys(views).length ? `<option value="__del">Usuń wybrany widok…</option>` : "");
}

$("#viewSel").addEventListener("change", async (e) => {
  const v = e.target.value;
  if (v === "__del") {
    const name = prompt("Nazwa widoku do usunięcia:", Object.keys(views)[0] || "");
    if (name && views[name]) { delete views[name]; await api("/api/settings/views", { method: "PUT", body: views }); toast("Usunięto widok"); }
    renderViewSelect(); return;
  }
  if (views[v]) { applyLayout(views[v]); saveLayout(); toast(`Widok „${v}”`); }
});
$("#btnSaveView").addEventListener("click", async () => {
  const name = prompt("Nazwa widoku (np. Dywidendowe, Skaner insiderów):");
  if (!name) return;
  views[name] = { layout: tblCompanies.getColumnLayout().map(({ field, width, visible }) => ({ field, width, visible })),
    sort: tblCompanies.getSorters().map((s) => ({ column: s.field, dir: s.dir })) };
  await api("/api/settings/views", { method: "PUT", body: views });
  renderViewSelect(); $("#viewSel").value = name; toast("Zapisano widok");
});

$("#q").addEventListener("input", debounce(applyFilters, 150));
$$("[data-mkt]").forEach((b) => b.addEventListener("click", () => {
  market = b.dataset.mkt; $$("[data-mkt]").forEach((x) => x.setAttribute("aria-pressed", x === b)); applyFilters(); }));
$("#btnCsv").addEventListener("click", () => tblCompanies.download("csv", `gpw_spolki_${new Date().toISOString().slice(0, 10)}.csv`, { delimiter: ";", bom: true }));

/* wybór kolumn */
$("#btnCols").addEventListener("click", () => {
  const list = $("#colList");
  const cols = tblCompanies.getColumns();
  const byGroup = {};
  cols.forEach((c) => { (byGroup[GROUP_OF[c.getField()] || "base"] ||= []).push(c); });
  list.innerHTML = Object.entries(GROUPS).filter(([g]) => byGroup[g]).map(([g, label]) => `<fieldset><legend>${label}</legend>` +
    byGroup[g].map((c) => { const d = c.getDefinition();
      return `<label><input type="checkbox" data-f="${esc(d.field)}" ${c.isVisible() ? "checked" : ""} ${d.field === "ticker" ? "disabled" : ""}> ${esc(d.title)}` +
        (CUSTOM_OF[d.field] ? ` <button class="del" data-del="${esc(CUSTOM_OF[d.field])}" title="Usuń kolumnę i jej wartości">usuń</button>` : "") + `</label>`; }).join("") + `</fieldset>`).join("");
  $("#dlgCols").showModal();
});
$("#colList").addEventListener("change", (e) => {
  const f = e.target.dataset.f; if (!f) return;
  const col = tblCompanies.getColumn(f); e.target.checked ? col.show() : col.hide();
});
$("#colList").addEventListener("click", async (e) => {
  const key = e.target.dataset.del; if (!key) return;
  e.preventDefault();
  if (!confirm("Usunąć kolumnę razem ze wszystkimi wpisanymi w niej wartościami?")) return;
  await api(`/api/columns/${key}`, { method: "DELETE" });
  $("#dlgCols").close(); await loadCompanies(); toast("Usunięto kolumnę");
});
$("#colsReset").addEventListener("click", () => {
  tblCompanies.getColumns().forEach((c) => { const f = c.getField(); (DEFAULT_VISIBLE[f] ?? true) ? c.show() : c.hide(); });
  $("#dlgCols").close();
});
$$("dialog [data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));

/* nowa kolumna */
$("#btnAddCol").addEventListener("click", () => { $("#formAdd").reset(); $("#optWrap").hidden = true; $("#dlgAdd").showModal(); $("#newLabel").focus(); });
$("#newType").addEventListener("change", (e) => { $("#optWrap").hidden = e.target.value !== "list"; });
$("#dlgAdd").addEventListener("close", async () => {
  if ($("#dlgAdd").returnValue !== "ok") return;
  const label = $("#newLabel").value.trim(); if (!label) return;
  const options = $("#newOpts").value.split(",").map((s) => s.trim()).filter(Boolean);
  await api("/api/columns", { method: "POST", body: { label, type: $("#newType").value, options } });
  await loadCompanies(); toast(`Dodano kolumnę „${label}”`);
});

/* ---------- panel spółki ---------- */
document.addEventListener("click", (e) => {
  const a = e.target.closest("a.tk"); if (!a) return;
  e.preventDefault(); openCompany(a.dataset.t);
});
$("#drawerClose").addEventListener("click", () => { $("#drawer").classList.remove("open"); $("#drawer").setAttribute("aria-hidden", "true"); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#drawerClose").click(); });

/* --- wskaźniki z objaśnieniem: co to jest i jak czytać obecny odczyt (progi orientacyjne) --- */
// każda ocena: [poziom, tekst]; poziomy: good (na korzyść), neutral, warn (ostrożnie), bad (na niekorzyść), none
const FACT_INFO = {
  price: ["Kurs", "Ostatnia cena zamknięcia akcji (notowania z ok. 15-minutowym opóźnieniem). Ikona pokazuje trend z ostatnich 3 miesięcy.",
    (v, r) => r == null ? ["none", "Brak danych o zmianie kursu z 3 miesięcy."]
      : r > 5 ? ["good", `Trend wzrostowy - ${fmtNum(r, 1)}% w 3 miesiące.`]
        : r < -5 ? ["bad", `Trend spadkowy - ${fmtNum(r, 1)}% w 3 miesiące.`]
          : ["neutral", `Kurs stabilny - ${r > 0 ? "+" : ""}${fmtNum(r, 1)}% w 3 miesiące.`]],
  mcap: ["Kapitalizacja", "Kurs × liczba akcji, czyli wartość całej spółki według giełdy.",
    (v) => v == null ? ["none", "Brak danych."] : v >= 10e9 ? ["good", "Duża spółka - zwykle stabilniejsza i łatwiej kupić czy sprzedać akcje."]
      : v >= 1e9 ? ["neutral", "Średnia spółka."] : ["warn", "Mała spółka - większy potencjał, ale też większe ryzyko i słabsza płynność."]],
  cz: ["C/Z (cena / zysk)", "Ile złotych płacisz za 1 zł rocznego zysku spółki (ostatnie 4 kwartały), czyli po ilu latach zyski „zwrócą” cenę akcji.",
    (v) => v == null ? ["none", "Brak danych - spółka mogła nie mieć zysku albo wyników."] : v < 0 ? ["bad", "Ujemne - spółka ma stratę."]
      : v < 8 ? ["good", "Nisko - tanio względem zysków, ale sprawdź, czy zysk nie był jednorazowy."]
        : v <= 20 ? ["neutral", "W typowym przedziale dla GPW (ok. 10-15)."] : ["bad", "Wysoko - drogo względem zysków; ma sens tylko przy szybkim wzroście."]],
  cwk: ["C/WK (cena / wartość księgowa)", "Ile płacisz za 1 zł majątku netto spółki (kapitału własnego).",
    (v) => v == null ? ["none", "Brak danych."] : v < 0 ? ["bad", "Ujemny kapitał własny - sygnał ostrzegawczy."]
      : v < 1 ? ["good", "Poniżej 1 - giełda wycenia spółkę taniej niż jej majątek, choć bywa to też sygnałem kłopotów."]
        : v <= 3 ? ["neutral", "Umiarkowanie."] : ["warn", "Wysoko - normalne w IT i markach, dla banków czy przemysłu to drogo."]],
  dy: ["Stopa dywidendy", "Dywidendy wypłacone w ostatnich 12 miesiącach w stosunku do obecnego kursu.",
    (v) => !v ? ["neutral", "Brak dywidendy w ostatnich 12 miesiącach."] : v < 3 ? ["neutral", "Niska."]
      : v <= 7 ? ["good", "Dobra - regularny dochód gotówkowy."] : ["warn", "Bardzo wysoka - sprawdź, czy nie jednorazowa i czy spółkę na nią stać."]],
  press: ["Presja kupujących (90 dni)", "Czy na sesjach przeważają kupujący: przewaga w obrocie z ostatnich ok. 63 sesji (CMF). Liczona z notowań, więc obejmuje cały rynek, także inwestorów, którzy niczego nie zgłaszają.",
    (v, v30) => {
      const s30 = v30 == null ? "" : ` 30 dni: ${v30 > 0 ? "+" : ""}${fmtNum(v30 * 100, 0)}%.`;
      return v == null ? ["none", "Za mało sesji w historii notowań (potrzeba ok. 3 tygodni)."]
        : v > 0.1 ? ["good", `Akumulacja - sesje częściej kończyły się blisko maksimum dnia przy dużych obrotach: przeważali kupujący.${s30}`]
          : v < -0.1 ? ["bad", `Dystrybucja - sesje częściej kończyły się blisko minimum: przeważali sprzedający.${s30}`]
            : ["neutral", `Równowaga kupujących i sprzedających.${s30}`];
    }],
  flow: ["Przepływ 30 dni", "Saldo zakupów minus sprzedaży zgłoszonych przez dużych inwestorów (zawiadomienia art. 69, insiderzy, fundusze) z ostatnich 30 dni. Nie obejmuje inwestorów, którzy nie muszą się ujawniać, więc nie jest to cały ruch na akcjach.",
    (v) => !v ? ["neutral", "Brak zarejestrowanych ruchów w ostatnich 30 dniach."] : v > 0 ? ["good", "Dodatni - duzi gracze dokupowali."]
      : ["bad", "Ujemny - duzi gracze sprzedawali."]],
};
const LEVEL = { good: "Na korzyść", neutral: "Neutralnie", warn: "Ostrożnie", bad: "Na niekorzyść", none: "Brak oceny" };
// różne kształty, nie tylko kolory: kółko z ✓, kółko z –, trójkąt z !, kółko z ✕
const LEVEL_ICON = {
  good: `<circle cx="8" cy="8" r="7" class="bg"/><path d="M4.6 8.2l2.3 2.3 4.5-4.6" class="g"/>`,
  neutral: `<circle cx="8" cy="8" r="7" class="bg"/><path d="M5 8h6" class="g"/>`,
  warn: `<path d="M8 1.2l7.1 12.6H.9z" class="bg"/><path d="M8 5.6v4.1M8 11.6v.1" class="g"/>`,
  bad: `<circle cx="8" cy="8" r="7" class="bg"/><path d="M5.4 5.4l5.2 5.2M10.6 5.4l-5.2 5.2" class="g"/>`,
};
const levelIcon = (lvl) => lvl === "none" ? "" :
  `<svg class="lvl lvl-${lvl}" viewBox="0 0 16 16" width="15" height="15" role="img" aria-label="Ocena: ${LEVEL[lvl]}"><title>${LEVEL[lvl]}</title>${LEVEL_ICON[lvl]}</svg>`;
function fact(key, value, ...raw) {
  const [label, what, read] = FACT_INFO[key];
  const [lvl, text] = read(...raw);
  return `<div class="fact" tabindex="0" aria-describedby="tip-${key}"><b>${value}${levelIcon(lvl)}</b>
    <span>${esc(label)} <i class="info" aria-hidden="true">i</i></span>
    <div class="tip" id="tip-${key}" role="tooltip"><strong>${esc(label)}</strong> ${esc(what)}
      <em>Ten odczyt: ${esc(LEVEL[lvl].toLowerCase())}</em> ${esc(text)}</div></div>`;
}

/* --- przepływ kapitału dzień po dniu: słupki = saldo dnia, linia = saldo narastające w okresie --- */
const FLOW_SOURCES = ["art69", "mar", "fundusze", "akcjonariat"];
const PERIODS = [7, 30, 180, 365];
const chartPref = (() => { try { return JSON.parse(localStorage.getItem("gpwt_chart") || "{}"); } catch { return {}; } })();
const saveChartPref = () => { try { localStorage.setItem("gpwt_chart", JSON.stringify(chartPref)); } catch { /* brak dostępu do pamięci */ } };
let drawerData = null;

function dailyFlows(changes, startIso) {
  const by = new Map();
  for (const x of changes) {
    if (x.excluded || x.value == null || !FLOW_SOURCES.includes(x.source) || x.date < startIso) continue;
    const d = x.date.slice(0, 10);
    const g = by.get(d) || { date: d, net: 0, buy: 0, sell: 0, items: [] };
    g.net += x.value; if (x.value >= 0) g.buy += x.value; else g.sell -= x.value;
    g.items.push(x); by.set(d, g);
  }
  return [...by.values()].sort((a, b) => a.date.localeCompare(b.date));
}

function niceStep(span) {
  const raw = span / 4, p = 10 ** Math.floor(Math.log10(raw || 1)), m = raw / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p;
}

function flowChart(days, start, end) {
  if (!days.length) return `<p class="dim chart-empty">Brak zarejestrowanych przepływów w tym okresie.</p>`;
  const W = 700, H = 180, L = 64, R = 70, T = 12, B = 24, day = 864e5;
  const t0 = start.getTime(), t1 = end.getTime(), x = (iso) => L + ((Date.parse(iso) - t0) / (t1 - t0)) * (W - L - R);
  let cum = 0;
  const pts = days.map((g) => ({ ...g, cum: (cum += g.net) }));
  const vals = [0, ...pts.map((g) => g.net), ...pts.map((g) => g.cum)];
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const step = niceStep(hi - lo || Math.abs(hi) || 1);
  lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
  if (hi === lo) hi = lo + step;
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const bw = Math.max(4, Math.min(24, ((W - L - R) / ((t1 - t0) / day)) * 0.7));
  const grid = [];
  for (let v = lo; v <= hi + step / 2; v += step) {
    grid.push(`<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="${v === 0 ? "zero" : "gl"}"/>
      <text x="${L - 6}" y="${y(v) + 4}" class="yl">${v > 0 ? "+" : ""}${fmtMoney(v)}</text>`);
  }
  const bar = (g, i) => {
    const cx = x(g.date), y0 = y(0), y1 = y(g.net), h = Math.abs(y1 - y0), r = Math.min(4, bw / 2, h);
    const l = cx - bw / 2, rgt = cx + bw / 2, up = g.net >= 0;
    const d = up ? `M${l},${y0} V${y1 + r} Q${l},${y1} ${l + r},${y1} H${rgt - r} Q${rgt},${y1} ${rgt},${y1 + r} V${y0} Z`
      : `M${l},${y0} V${y1 - r} Q${l},${y1} ${l + r},${y1} H${rgt - r} Q${rgt},${y1} ${rgt},${y1 - r} V${y0} Z`;
    return `<path d="${h < 0.5 ? `M${l},${y0}h${bw}` : d}" class="${up ? "bar-in" : "bar-out"}" data-i="${i}"/>`;
  };
  let line = `M${L},${y(0)}`, prev = 0;
  for (const g of pts) { line += ` H${x(g.date)} V${y(g.cum)}`; prev = g.cum; }
  line += ` H${W - R}`;
  const hits = pts.map((g, i) => {
    const w = Math.max(bw + 6, 14);
    return `<rect class="hit" x="${x(g.date) - w / 2}" y="${T}" width="${w}" height="${H - T - B}" data-i="${i}" tabindex="0"
      aria-label="${g.date}: saldo ${fmtMoney(g.net)}"/>`;
  }).join("");
  const fmtD = (dt) => dt.toISOString().slice(0, 10);
  return `<div class="chart-wrap"><svg class="flowchart" viewBox="0 0 ${W} ${H}" role="img"
      aria-label="Dzienne saldo przepływów kapitału od ${fmtD(start)} do ${fmtD(end)}">
      ${grid.join("")}<path d="${line}" class="cum"/>${pts.map(bar).join("")}
      <circle cx="${W - R}" cy="${y(prev)}" r="4" class="cum-dot"/>
      <text x="${W - R + 8}" y="${y(prev) + 4}" class="endl">${prev > 0 ? "+" : ""}${fmtMoney(prev)}</text>
      <text x="${L}" y="${H - 6}" class="xl">${fmtD(start)}</text>
      <text x="${W - R}" y="${H - 6}" class="xl" text-anchor="end">${fmtD(end)}</text>
      ${hits}</svg><div class="chart-tip" role="status" hidden></div></div>`;
}

function bindFlowTips(root, days) {
  const tip = root.querySelector(".chart-tip"), svg = root.querySelector(".flowchart");
  if (!tip || !svg) return;
  let cum = 0;
  const pts = days.map((g) => ({ ...g, cum: (cum += g.net) }));
  const show = (el) => {
    const g = pts[+el.dataset.i];
    tip.replaceChildren();
    const add = (cls, text) => { const s = document.createElement("div"); s.className = cls; s.textContent = text; tip.append(s); };
    add("tv", `${g.net > 0 ? "+" : ""}${fmtMoney(g.net)}`);
    add("tl", `saldo dnia ${g.date}`);
    add("tr", `kupno ${fmtMoney(g.buy)} · sprzedaż ${fmtMoney(g.sell)}`);
    add("tr", `saldo narastające ${g.cum > 0 ? "+" : ""}${fmtMoney(g.cum)}`);
    g.items.slice().sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, 3)
      .forEach((it) => add("ti", `${it.value > 0 ? "+" : ""}${fmtMoney(it.value)}  ${it.investor}`));
    if (g.items.length > 3) add("ti", `i jeszcze ${g.items.length - 3}…`);
    svg.querySelectorAll(`[data-i]`).forEach((n) => n.classList.toggle("hl", n.dataset.i === el.dataset.i));
    tip.hidden = false;
    const box = root.getBoundingClientRect(), r = el.getBoundingClientRect();
    const left = Math.min(Math.max(0, r.left - box.left + r.width / 2 - 120), box.width - 240);
    tip.style.left = `${left}px`;
  };
  const hide = () => { tip.hidden = true; svg.querySelectorAll(".hl").forEach((n) => n.classList.remove("hl")); };
  svg.querySelectorAll(".hit").forEach((h) => {
    h.addEventListener("pointerenter", () => show(h)); h.addEventListener("focus", () => show(h));
    h.addEventListener("pointerleave", hide); h.addEventListener("blur", hide);
  });
}

/* --- presja kupujących: kurs (góra) i linia akumulacji/dystrybucji (dół), wspólna oś sesji --- */
function pressPoints(rows) {
  let ad = 0;
  return rows.map((r) => {
    const h = r.high, l = r.low, c = r.close;
    const k = h != null && l != null && h > l ? ((c - l) - (h - c)) / (h - l) : 0;
    const mf = k * (r.turnover || 0);
    ad += mf;
    return { ...r, clv: k, mf, ad };
  });
}

function pressChart(pts) {
  if (pts.length < 2) return `<p class="dim chart-empty">Za mało sesji w tym okresie - historia notowań tej spółki dopiero się zbiera.</p>`;
  const W = 700, L = 64, R = 74, T = 18, PH = 92, GAP = 34, B = 22, H = T + PH + GAP + PH + B, n = pts.length;
  const x = (i) => L + (i / (n - 1)) * (W - L - R);
  const scale = (vals, top, withZero) => {
    let lo = Math.min(...vals, ...(withZero ? [0] : [])), hi = Math.max(...vals, ...(withZero ? [0] : []));
    if (hi === lo) { hi += 1; lo -= 1; }
    const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
    return { lo, hi, y: (v) => top + (1 - (v - lo) / (hi - lo)) * PH };
  };
  const ps = scale(pts.map((p) => p.close), T, false), as = scale(pts.map((p) => p.ad), T + PH + GAP, true);
  const line = (s, key) => pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${s.y(p[key]).toFixed(1)}`).join(" ");
  const last = pts[n - 1];
  const yTop2 = T + PH + GAP;
  const hitW = (W - L - R) / (n - 1);
  const hits = pts.map((p, i) => `<rect class="hit" x="${x(i) - hitW / 2}" y="${T}" width="${hitW}" height="${H - T - B}" data-i="${i}"
      tabindex="${i === n - 1 ? 0 : -1}" aria-label="${p.date}: kurs ${fmtNum(p.close)}"/>`).join("");
  return `<div class="chart-wrap"><svg class="flowchart presschart" viewBox="0 0 ${W} ${H}" role="img"
      aria-label="Kurs i linia akumulacji/dystrybucji od ${pts[0].date} do ${last.date}">
      <text x="${L}" y="${T - 6}" class="pl">Kurs</text>
      <line x1="${L}" x2="${W - R}" y1="${T + PH}" y2="${T + PH}" class="gl"/>
      <text x="${L - 6}" y="${ps.y(ps.hi) + 10}" class="yl">${fmtNum(ps.hi)}</text>
      <text x="${L - 6}" y="${T + PH}" class="yl">${fmtNum(ps.lo)}</text>
      <path d="${line(ps, "close")}" class="price-line"/>
      <circle cx="${x(n - 1)}" cy="${ps.y(last.close)}" r="4" class="price-dot"/>
      <text x="${x(n - 1) + 8}" y="${ps.y(last.close) + 4}" class="endl">${fmtNum(last.close)}</text>
      <text x="${L}" y="${yTop2 - 6}" class="pl">Linia akumulacji/dystrybucji (napływ pieniądza)</text>
      <line x1="${L}" x2="${W - R}" y1="${as.y(0)}" y2="${as.y(0)}" class="zero"/>
      <text x="${L - 6}" y="${as.y(0) + 4}" class="yl">0</text>
      <path d="${line(as, "ad")}" class="cum"/>
      <circle cx="${x(n - 1)}" cy="${as.y(last.ad)}" r="4" class="cum-dot"/>
      <text x="${x(n - 1) + 8}" y="${as.y(last.ad) + 4}" class="endl">${last.ad > 0 ? "+" : ""}${fmtMoney(last.ad)}</text>
      <text x="${L}" y="${H - 6}" class="xl">${pts[0].date}</text>
      <text x="${W - R}" y="${H - 6}" class="xl" text-anchor="end">${last.date}</text>
      <line class="xh" x1="0" x2="0" y1="${T}" y2="${H - B}" visibility="hidden"/>
      ${hits}</svg><div class="chart-tip" role="status" hidden></div></div>`;
}

function bindPressTips(root, pts) {
  const tip = root.querySelector(".chart-tip"), svg = root.querySelector(".presschart");
  if (!tip || !svg) return;
  const xh = svg.querySelector(".xh");
  const show = (el) => {
    const p = pts[+el.dataset.i];
    tip.replaceChildren();
    const add = (cls, text) => { const s = document.createElement("div"); s.className = cls; s.textContent = text; tip.append(s); };
    add("tv", `${fmtNum(p.close)} zł`);
    add("tl", `sesja ${p.date}`);
    add("tr", `zamknięcie ${p.clv > 0.3 ? "blisko maksimum" : p.clv < -0.3 ? "blisko minimum" : "w środku"} dnia (${fmtNum(p.low)}–${fmtNum(p.high)})`);
    add("tr", `obrót ${fmtMoney(p.turnover)} · napływ dnia ${p.mf > 0 ? "+" : ""}${fmtMoney(p.mf)}`);
    add("tr", `od początku okresu ${p.ad > 0 ? "+" : ""}${fmtMoney(p.ad)}`);
    const cx = +el.getAttribute("x") + +el.getAttribute("width") / 2;
    xh.setAttribute("x1", cx); xh.setAttribute("x2", cx); xh.setAttribute("visibility", "visible");
    tip.hidden = false;
    const box = root.getBoundingClientRect(), r = el.getBoundingClientRect();
    tip.style.left = `${Math.min(Math.max(0, r.left - box.left + r.width / 2 - 120), box.width - 240)}px`;
  };
  const hide = () => { tip.hidden = true; xh.setAttribute("visibility", "hidden"); };
  svg.querySelectorAll(".hit").forEach((h) => {
    h.addEventListener("pointerenter", () => show(h)); h.addEventListener("focus", () => show(h));
    h.addEventListener("pointerleave", hide); h.addEventListener("blur", hide);
  });
}

function renderPress(body, startIso) {
  const rows = (drawerData.ohlc || []).filter((r) => r.date >= startIso);
  const pts = pressPoints(rows);
  const tot = pts.reduce((s, p) => s + (p.turnover || 0), 0), mf = pts.reduce((s, p) => s + p.mf, 0);
  const cmfP = pts.length >= 15 && tot ? mf / tot : null;
  const recent = (drawerData.ohlc || []).slice(-31, -1), avg = recent.length ? recent.reduce((s, p) => s + (p.turnover || 0), 0) / recent.length : null;
  const lastT = (drawerData.ohlc || []).at(-1);
  const rel = avg && lastT ? lastT.turnover / avg : null;
  const lvl = cmfP == null ? "none" : cmfP > 0.1 ? "good" : cmfP < -0.1 ? "bad" : "neutral";
  body.innerHTML = `
    <div class="chart-sum">
      <span>presja w okresie <b>${cmfP == null ? "–" : (cmfP > 0 ? "+" : "") + fmtNum(cmfP * 100, 0) + "%"}</b> ${levelIcon(lvl)}</span>
      <span>sesji <b>${pts.length}</b></span>
      <span>obrót ostatniej sesji <b>${rel == null ? "–" : fmtNum(rel, 1) + "×"}</b> średniej z 30 sesji</span>
    </div>
    ${pressChart(pts)}
    <p class="dim chart-note">Linia akumulacji/dystrybucji rośnie, gdy sesje kończą się blisko maksimum dnia przy dużym obrocie (przeważają kupujący),
      a spada, gdy blisko minimum. Najciekawsze są rozbieżności z kursem: kurs stoi albo spada, a linia rośnie, to ciche skupowanie
      (akumulacja); kurs rośnie, a linia spada, to wzrost bez kupujących. Dane obejmują cały rynek, ale nie mówią, kto kupuje.</p>`;
  bindPressTips(body, pts);
}

function renderChart() {
  const host = $("#companyChart");
  if (!host || !drawerData) return;
  const mode = chartPref.mode || "flow", days = chartPref.days || 365;
  const end = new Date(), start = new Date(end.getTime() - days * 864e5), startIso = start.toISOString().slice(0, 10);
  const flows = dailyFlows(drawerData.changes, startIso);
  const sum = (k) => flows.reduce((s, g) => s + g[k], 0);
  const net = sum("net");
  host.querySelector(".chart-ctl").innerHTML = `
    <div class="seg" role="group" aria-label="Rodzaj wykresu">
      ${[["flow", "Przepływy"], ["press", "Presja"], ["price", "Kurs"]].map(([k, l]) => `<button data-mode="${k}" aria-pressed="${mode === k}">${l}</button>`).join("")}</div>
    <div class="seg" role="group" aria-label="Okres">
      ${PERIODS.map((p) => `<button data-days="${p}" aria-pressed="${days === p}">${p} dni</button>`).join("")}</div>`;
  const body = host.querySelector(".chart-body");
  if (mode === "price") {
    body.innerHTML = sparkline(drawerData.prices.filter((p) => p.date >= startIso));
    return;
  }
  if (mode === "press") {
    renderPress(body, startIso);
    return;
  }
  body.innerHTML = `
    <div class="chart-sum">
      <span><i class="key in"></i>napływ <b>${sum("buy") ? "+" : ""}${fmtMoney(sum("buy"))}</b></span>
      <span><i class="key out"></i>odpływ <b>${sum("sell") ? "−" : ""}${fmtMoney(sum("sell"))}</b></span>
      <span><i class="key cum"></i>saldo narastające <b>${net > 0 ? "+" : ""}${fmtMoney(net)}</b></span>
    </div>
    ${flowChart(flows, start, end)}
    <p class="dim chart-note">Słupek nad osią = zgłoszeni duzi inwestorzy więcej kupili, pod osią = więcej sprzedali. To tylko transakcje,
      które musiały zostać ujawnione (przekroczenie progów 5%, 10%…, insiderzy, sprawozdania funduszy), a nie cały rynek: każdą sprzedaż
      ktoś kupił, często niezgłaszający inwestor (fundusz poniżej 5%, zagraniczny, indywidualny). Zmiany w portfelach OFE mają datę sprawozdania
      (30.06 i 31.12). Szczegóły w tabeli „Zmiany stanu posiadania” niżej.</p>`;
  bindFlowTips(body, flows);
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("#companyChart [data-mode], #companyChart [data-days]");
  if (!b) return;
  if (b.dataset.mode) chartPref.mode = b.dataset.mode;
  if (b.dataset.days) chartPref.days = +b.dataset.days;
  saveChartPref(); renderChart();
});

/* --- akcjonariat w grupach z rozwijaniem --- */
function holderGroups(groups) {
  if (!groups.length) return `<p class="dim">Akcjonariat pobiera się raz w tygodniu.</p>`;
  const when = (g) => !g.date_to ? "–" : g.date_from === g.date_to ? esc(g.date_to)
    : `<span title="Dane z różnych dat: ${esc(g.date_from)} – ${esc(g.date_to)}">do ${esc(g.date_to)}</span>`;
  const row = (m) => `<div class="hg-row${m.computed ? " computed" : ""}"><span>${esc(m.holder)}</span>
    <span class="n">${fmtNum(m.pct, 2)}%</span><span class="n">${m.shares == null ? "–" : fmtNum(m.shares, 0)}</span>
    <span>${m.date_upd ? esc(m.date_upd) : "–"}</span></div>`;
  return `<div class="hgroups">
    <div class="hg-row hg-head"><span>Grupa</span><span class="n">Udział</span><span class="n">Akcje</span><span>Stan na</span></div>
    ${groups.map((g) => `<details class="hg ${g.key}"><summary class="hg-row">
        <span class="hg-name">${esc(g.label)} <small class="dim">(${g.members.length})</small></span>
        <span class="n"><b>${fmtNum(g.pct, 2)}%</b></span><span class="n">${g.shares == null ? "–" : fmtNum(g.shares, 0)}</span>
        <span>${when(g)}</span></summary>
        <div class="hg-members">${g.members.map(row).join("")}</div></details>`).join("")}
    <p class="dim chart-note">Udziały pochodzą z różnych dat (fundusze raportują co pół roku), więc sumy są przybliżone.
      Akcjonariat rozproszony to 100% minus wszystkie znane udziały.</p></div>`;
}

function sparkline(prices) {
  if (prices.length < 2) return `<p class="dim">Wykres pojawi się po kilku dniach zbierania notowań.</p>`;
  const v = prices.map((p) => p.close), mn = Math.min(...v), mx = Math.max(...v), W = 700, H = 90;
  const pts = v.map((y, i) => `${(i / (v.length - 1)) * W},${H - 6 - ((y - mn) / (mx - mn || 1)) * (H - 12)}`).join(" ");
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Kurs od ${prices[0].date} do ${prices.at(-1).date}">
    <polyline fill="none" stroke="var(--accent)" stroke-width="1.6" points="${pts}"/></svg>
    <div class="dim" style="display:flex;justify-content:space-between;font-size:12px"><span>${prices[0].date} · ${fmtNum(v[0])}</span><span>${prices.at(-1).date} · ${fmtNum(v.at(-1))}</span></div>`;
}

async function openCompany(t) {
  const d = await api(`/api/company/${encodeURIComponent(t)}`);
  const row = tblCompanies?.getRow(t)?.getData() || {};
  const c = d.company;
  drawerData = d;
  $("#drawerBody").innerHTML = `
    <h2>${esc(c.ticker)} · ${esc(c.full_name || c.short_name)}</h2>
    <div class="dim">${esc(c.market === "NC" ? "NewConnect" : "GPW")}${c.sector ? " · " + esc(c.sector) : ""}${c.isin ? " · " + esc(c.isin) : ""}
      ${c.slug ? `· <a href="https://www.biznesradar.pl/notowania/${encodeURIComponent(c.slug)}" target="_blank" rel="noopener">profil w Biznesradar</a>` : "· wycofana z obrotu (brak w Biznesradar)"}</div>
    <div class="facts">
      ${fact("price", fmtNum(row.price), row.price, row.r3m)}
      ${fact("mcap", fmtMoney(row.mcap), row.mcap)}
      ${fact("cz", row.cz == null ? "–" : fmtNum(row.cz, 1), row.cz)}
      ${fact("cwk", row.cwk == null ? "–" : fmtNum(row.cwk, 1), row.cwk)}
      ${fact("dy", row.div_yield == null ? "–" : fmtNum(row.div_yield, 2) + "%", row.div_yield)}
      ${fact("flow", row.flow_30d == null ? "–" : (row.flow_30d > 0 ? "+" : "") + fmtMoney(row.flow_30d), row.flow_30d)}
      ${fact("press", row.cmf63 == null ? "–" : (row.cmf63 > 0 ? "+" : "") + fmtNum(row.cmf63 * 100, 0) + "%", row.cmf63, row.cmf21)}
    </div>
    <p class="dim chart-note lvl-legend">${["good", "neutral", "warn", "bad"].map((l) => `${levelIcon(l)} ${LEVEL[l].toLowerCase()}`).join(" · ")}
      - najedź na wskaźnik, żeby zobaczyć objaśnienie. Progi są orientacyjne, to nie rekomendacja.</p>
    <section id="companyChart" aria-label="Wykres"><div class="chart-ctl"></div><div class="chart-body"></div></section>
    <h3>Analiza fundamentalna ${row.c_ocena_af ? `<span class="af-rating">${esc(row.c_ocena_af)}</span>` : ""}</h3>
    ${d.analyses.length ? `<table>${d.analyses.map((a) => `<tr><td style="white-space:nowrap">${esc(a.date)}</td>
        <td><a href="/af/${a.file.split("/").map(encodeURIComponent).join("/")}" target="_blank" rel="noopener">${esc(a.name)}</a></td>
        <td class="n dim">${fmtNum(a.size / 1024, 0)} KB</td></tr>`).join("")}</table>`
      : `<p class="dim">Brak analizy. Zapisz plik w folderze „Analizy fundamentalne” w OneDrive z tickerem w nazwie
          (np. ${esc(c.ticker)}_analiza.pdf) - pojawi się tu po synchronizacji (co 15 minut).</p>`}
    <p class="dim chart-note">Ocenę (Warto / Obserwuj / Nie warto) ustawisz w kolumnie „Ocena AF” w tabeli spółek.</p>
    <h3>Akcjonariat (ostatni odczyt)</h3>
    ${holderGroups(d.holder_groups || [])}
    <h3>Zmiany stanu posiadania</h3>
    ${d.changes.length ? `<table><tr><th>Data</th><th>Inwestor</th><th class="n">Zmiana akcji</th><th class="n">Wartość</th><th>Źródło</th></tr>
      ${d.changes.slice(0, 40).map((x) => `<tr${x.excluded ? ' class="dim"' : ""}><td>${esc(x.date)}</td><td>${esc(x.investor)}</td>
        <td class="n ${x.delta > 0 ? "up" : "down"}">${x.delta > 0 ? "+" : ""}${fmtNum(x.delta, 0)}</td><td class="n">${fmtMoney(x.value)}</td><td><span class="tag ${x.source}">${esc(x.source)}</span></td></tr>`).join("")}</table>`
      : `<p class="dim">Brak zarejestrowanych zmian.</p>`}
    <h3>Dywidendy</h3>
    ${d.dividends.length ? `<table><tr><th>Za rok</th><th>Ostatni dzień z prawem</th><th>Wypłata</th><th class="n">Na akcję</th><th>Status</th></tr>
      ${d.dividends.map((x) => `<tr><td>${esc(x.year_for)}</td><td>${esc(x.last_day)}</td><td>${esc(x.pay_day)}</td><td class="n">${fmtNum(x.dps)}</td><td>${esc(x.status)}</td></tr>`).join("")}</table>`
      : `<p class="dim">Brak dywidend w ostatnich latach.</p>`}
    <h3>Komunikaty</h3>
    ${d.espi.length ? `<table>${d.espi.slice(0, 25).map((x) => `<tr><td style="white-space:nowrap">${esc(x.ts.slice(0, 10))}</td><td><span class="tag ${x.category}">${esc(catLabel[x.category] || x.category)}</span></td>
      <td><a href="${esc(espiHref(x.url))}" target="_blank" rel="noopener">${esc(x.title)}</a></td></tr>`).join("")}</table>` : `<p class="dim">Brak komunikatów w bazie.</p>`}`;
  $("#drawer").classList.add("open"); $("#drawer").setAttribute("aria-hidden", "false");
  renderChart();
  // dymek wskaźnika przy prawej krawędzi panelu otwiera się w lewo, żeby nie wychodził poza panel
  const facts = $("#drawerBody .facts");
  $$(".fact", facts).forEach((f) => f.classList.toggle("edge", f.offsetLeft + 300 > facts.clientWidth));
}

/* ---------- inwestorzy ---------- */
const SOURCES = { art69: "Zawiadomienia art. 69", mar: "Insiderzy (MAR)", fundusze: "Portfele OFE/TFI", akcjonariat: "Główni akcjonariusze", wz: "Walne zgromadzenia" };
const DEFAULT_SOURCES = ["art69", "mar", "fundusze", "akcjonariat"];
let period = "week", tblInv;
$("#srcChips").innerHTML = Object.entries(SOURCES).map(([k, v]) => `<label class="chip"><input type="checkbox" value="${k}" ${DEFAULT_SOURCES.includes(k) ? "checked" : ""}>${v}</label>`).join("");
// od 1 stycznia poprzedniego roku - obejmuje półroczne i roczne struktury portfeli OFE
$("#invFrom").value = `${new Date().getFullYear() - 1}-01-01`;

async function loadInvestors() {
  const src = $$("#srcChips input:checked").map((i) => i.value).join(",");
  const qs = new URLSearchParams({ period, sources: src, from: $("#invFrom").value, to: $("#invTo").value });
  const data = await api(`/api/flows?${qs}`);
  const scale = data.map((d) => Math.abs(d.net)).sort((a, b) => b - a)[Math.min(3, data.length - 1)] || 1;
  const cols = [
    { field: "period", title: period === "week" ? "Tydzień" : "Miesiąc", width: 100, headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true } },
    { field: "investor", title: "Inwestor", width: 300, headerFilter: "input", formatter: (c) => `<a href="#" class="inv">${esc(c.getValue())}</a>` },
    { field: "net", title: "Saldo (kupno − sprzedaż)", width: 240, formatter: (c) => flowBar(c.getValue(), scale), sorter: numSort },
    { field: "buy", title: "Kupno", hozAlign: "right", formatter: money, sorter: numSort },
    { field: "sell", title: "Sprzedaż", hozAlign: "right", formatter: money, sorter: numSort },
    { field: "n", title: "Zmian", hozAlign: "right" },
    { field: "tickers", title: "Spółki", width: 220, tooltip: true, headerFilter: "input", formatter: (c) => esc(c.getValue()).split(", ").map((t) => `<a class="tk" href="#" data-t="${t}">${t}</a>`).join(" ") },
    { field: "sources", title: "Źródła", headerFilter: "input" },
    { field: "unpriced", title: "Bez wyceny", hozAlign: "right", headerTooltip: "Zmiany, dla których nie znaleziono kursu – nie są wliczone do kwot" },
  ];
  if (tblInv) tblInv.destroy();
  tblInv = new Tabulator("#tblInvestors", { data, columns: cols, layout: "fitData", height: "calc(100vh - 190px)",
    movableColumns: true,
    placeholder: "Brak zmian w wybranym okresie i źródłach.", groupBy: "period", groupStartOpen: (v, count, data, g) => true,
    groupHeader: (v, count, rows) => { const net = rows.reduce((s, r) => s + (r.net || 0), 0);
      return `${esc(v)} <span class="dim">· ${count} inwestorów · saldo ${fmtMoney(net)}</span>`; } });
  tblInv.on("cellClick", (e, cell) => { if (e.target.classList.contains("inv")) { e.preventDefault();
    showView("changes"); $("#chQ").value = cell.getRow().getData().investor; filterChanges(); } });
  tblInv.on("tableBuilt", () => filterInv());
}
const filterInv = () => { const q = $("#invQ").value.trim().toLowerCase(); tblInv?.setFilter((d) => !q || d.investor.toLowerCase().includes(q)); };
$("#invQ").addEventListener("input", debounce(filterInv, 150));
$$("[data-period]").forEach((b) => b.addEventListener("click", () => { period = b.dataset.period;
  $$("[data-period]").forEach((x) => x.setAttribute("aria-pressed", x === b)); loadInvestors(); }));
["#invFrom", "#invTo"].forEach((s) => $(s).addEventListener("change", loadInvestors));
$("#srcChips").addEventListener("change", loadInvestors);

/* ---------- zmiany (edytowalne) ---------- */
let tblCh;
async function loadChanges() {
  const data = await api("/api/changes");
  const intEd = { editor: "number", hozAlign: "right", formatter: (c) => fmtNum(c.getValue(), 0), sorter: numSort };
  if (tblCh) tblCh.destroy();
  tblCh = new Tabulator("#tblChanges", { data, index: "id", layout: "fitData", height: "calc(100vh - 190px)",
    movableColumns: true,
    placeholder: "Brak zmian. Pojawią się po pierwszym pobraniu komunikatów i akcjonariatu.",
    columns: [
      { field: "date", title: "Data", editor: "input", width: 100, headerFilter: "input",
        headerTooltip: "Data transakcji lub zmiany stanu posiadania (z formularza)" },
      { field: "report_ts", title: "Opublikowano", width: 130, headerFilter: "input",
        headerTooltip: "Kiedy spółka opublikowała raport ESPI/EBI z tą informacją" },
      { field: "ticker", title: "Ticker", formatter: tickerFmt, width: 80, headerFilter: "input" },
      { field: "investor", title: "Inwestor", editor: "input", width: 260, tooltip: true, headerFilter: "input" },
      { field: "shares_before", title: "Akcje przed", ...intEd },
      { field: "shares_after", title: "Akcje po", ...intEd },
      { field: "delta", title: "Zmiana", ...intEd, formatter: (c) => { const v = c.getValue(); return v == null ? "" : `<span class="${v > 0 ? "up" : "down"}">${v > 0 ? "+" : ""}${fmtNum(v, 0)}</span>`; } },
      { field: "price", title: "Cena", editor: "number", hozAlign: "right", formatter: num2, sorter: numSort },
      { field: "value", title: "Wartość", hozAlign: "right", formatter: money, sorter: numSort },
      { field: "source", title: "Źródło", formatter: (c) => `<span class="tag ${c.getValue()}">${esc(SOURCES[c.getValue()] || c.getValue())}</span>`,
        headerFilter: "list", headerFilterParams: { values: SOURCES, clearable: true } },
      { field: "verified", title: "Sprawdzone", editor: "tickCross", formatter: "tickCross", hozAlign: "center", width: 100,
        headerFilter: "tickCross", headerFilterParams: { tristate: true }, headerFilterFunc: (h, v) => h === null || h === !!v },
      { field: "excluded", title: "Wyklucz z sum", editor: "tickCross", formatter: "tickCross", hozAlign: "center", width: 110,
        headerFilter: "tickCross", headerFilterParams: { tristate: true }, headerFilterFunc: (h, v) => h === null || h === !!v },
      { field: "note", title: "Uwagi", editor: "input", width: 240, tooltip: true, headerFilter: "input" },
      { field: "espi_id", title: "Raport", formatter: (c) => { const u = c.getRow().getData().espi_url;
        return u ? `<a href="${esc(espiHref(u))}" target="_blank" rel="noopener">otwórz</a>` : ""; } },
    ] });
  tblCh.on("cellEdited", async (cell) => {
    const f = cell.getField(); let v = cell.getValue();
    if (f === "verified" || f === "excluded") v = v ? 1 : 0;
    const row = await api(`/api/changes/${cell.getRow().getIndex()}`, { method: "PATCH", body: { [f]: v } });
    cell.getRow().update(row); toast("Zapisano poprawkę");
  });
  tblCh.on("tableBuilt", filterChanges);
}
function filterChanges() {
  const q = $("#chQ").value.trim().toLowerCase(), src = $("#chSrc").value, unv = $("#chUnverified").checked;
  tblCh?.setFilter((d) => (!src || d.source === src) && (!unv || !d.verified) &&
    (!q || (d.ticker || "").toLowerCase() === q || (d.investor || "").toLowerCase().includes(q) || (d.investor_display || "").toLowerCase().includes(q)));
}
$("#chQ").addEventListener("input", debounce(filterChanges, 150));
["#chSrc", "#chUnverified"].forEach((s) => $(s).addEventListener("change", filterChanges));
$("#chClear").addEventListener("click", () => { $("#chQ").value = ""; $("#chSrc").value = ""; $("#chUnverified").checked = false; filterChanges(); tblCh?.clearHeaderFilter(); });

/* ---------- ESPI ---------- */
const catLabel = { art69: "Zmiana udziału", mar: "Insider", wezwanie: "Wezwanie", wz_lista: "Lista z WZ", skup: "Skup akcji", other: "Inne" };
$("#espiChips").innerHTML = Object.entries(catLabel).map(([k, v]) => `<label class="chip"><input type="checkbox" value="${k}" ${k !== "other" ? "checked" : ""}>${v}</label>`).join("");
let tblEspi;
const parsedSummary = (cat, p) => {
  try { p = JSON.parse(p || "{}"); } catch { return ""; }
  if (p.forms) return p.forms.map((f) => [f.investor, f.delta != null ? `${f.delta > 0 ? "+" : ""}${fmtNum(f.delta, 0)} akcji` : null,
    f.pct_after != null ? `${fmtNum(f.pct_before, 2)}% → ${fmtNum(f.pct_after, 2)}%` : null, f.price ? `po ${fmtNum(f.price)} zł` : null].filter(Boolean).join(", ")).join(" | ");
  if (p.holders) return p.holders.map((h) => `${h.holder} ${h.pct_total != null ? fmtNum(h.pct_total, 2) + "%" : ""}`).join("; ");
  return "";
};
async function loadEspi() {
  const cats = $$("#espiChips input:checked").map((i) => i.value).join(",");
  const data = await api(`/api/espi?days=${$("#espiDays").value}&categories=${cats}`);
  if (tblEspi) tblEspi.destroy();
  tblEspi = new Tabulator("#tblEspi", { data, index: "id", layout: "fitData", height: "calc(100vh - 190px)",
    movableColumns: true,
    placeholder: "Brak komunikatów w tym zakresie.",
    columns: [
      { field: "ts", title: "Czas", width: 140, headerFilter: "input" },
      { field: "ticker", title: "Ticker", formatter: (c) => c.getValue() ? tickerFmt(c) : `<span class="dim" title="Kliknij, aby przypisać ticker">przypisz</span>`, editor: "input", width: 90, headerFilter: "input" },
      { field: "category", title: "Rodzaj", formatter: (c) => `<span class="tag ${c.getValue()}">${esc(catLabel[c.getValue()] || c.getValue())}</span>`, width: 130,
        headerFilter: "list", headerFilterParams: { values: catLabel, clearable: true } },
      { field: "title", title: "Tytuł", width: 520, formatter: (c) => `<a href="${esc(espiHref(c.getRow().getData().url))}" target="_blank" rel="noopener">${esc(c.getValue())}</a>`, tooltip: true, headerFilter: "input" },
      { field: "parsed", title: "Odczytane dane", width: 420, formatter: (c) => esc(parsedSummary(c.getRow().getData().category, c.getValue())), tooltip: true },
    ] });
  tblEspi.on("cellEdited", async (cell) => { if (cell.getField() !== "ticker") return;
    await api(`/api/espi/${cell.getRow().getIndex()}/ticker`, { method: "POST", body: { ticker: cell.getValue() } }); toast("Przypisano spółkę"); });
  tblEspi.on("tableBuilt", filterEspi);
}
const filterEspi = () => { const q = $("#espiQ").value.trim().toLowerCase(); tblEspi?.setFilter((d) => !q || d.title.toLowerCase().includes(q) || (d.ticker || "").toLowerCase() === q); };
$("#espiChips").addEventListener("change", loadEspi);
$("#espiDays").addEventListener("change", loadEspi);
$("#espiQ").addEventListener("input", debounce(filterEspi, 150));

/* ---------- ustawienia ---------- */
let tblRuns, tblAl;
async function loadSettings() {
  const s = await api("/api/status");
  const labels = { companies: "spółek", quotes: "notowań dziennych", espi: "komunikatów", changes: "zmian stanu posiadania", holdings_snap: "odczytów akcjonariatu", dividends: "dywidend" };
  $("#counts").innerHTML = Object.entries(s.counts).map(([k, v]) => `<div><b>${fmtNum(v, 0)}</b><span>${labels[k]}</span></div>`).join("");
  const af = await api("/api/analyses");
  $("#afStatus").innerHTML = `Przypisane: <b>${af.assigned}</b> plików do <b>${af.companies}</b> spółek
    · ostatnia synchronizacja z OneDrive: <b>${af.last_sync ? esc(af.last_sync.replace("T", " ").slice(0, 16)) : "jeszcze nie było"}</b>
    ${af.unassigned.length ? `<br>Nie udało się przypisać do spółki (dodaj ticker do nazwy pliku, np. CDR_analiza.pdf):
      <ul>${af.unassigned.map((a) => `<li>${esc(a.name)}</li>`).join("")}</ul>` : ""}`;
  $("#runState").textContent = s.job_running ? "Pobieranie trwa…" : "";
  const runs = s.runs.map((r) => ({ ...r, summaryText: summarize(r.summary) }));
  if (tblRuns) tblRuns.destroy();
  tblRuns = new Tabulator("#tblRuns", { data: runs, layout: "fitData", maxHeight: 300, movableColumns: true, placeholder: "Jeszcze nic nie pobrano.",
    columns: [{ field: "started", title: "Start" }, { field: "finished", title: "Koniec" }, { field: "kind", title: "Rodzaj", formatter: (c) => c.getValue() === "weekly" ? "pełne" : "dzienne" },
      { field: "status", title: "Wynik", formatter: (c) => c.getValue() === "ok" ? `<span class="up">udane</span>` : c.getValue() === "error" ? `<span class="down">błąd</span>` : "w toku" },
      { field: "summaryText", title: "Podsumowanie", width: 640, tooltip: true }] });
  const inv = await api("/api/investors");
  if (tblAl) tblAl.destroy();
  tblAl = new Tabulator("#tblAliases", { data: inv, index: "investor_norm", layout: "fitData", maxHeight: 420, movableColumns: true, placeholder: "Inwestorzy pojawią się po pierwszych zmianach.",
    columns: [{ field: "investor", title: "Nazwa w danych", width: 340, headerFilter: "input" }, { field: "n", title: "Zmian", hozAlign: "right" },
      { field: "canonical", title: "Pokazuj jako", editor: "input", width: 280 }, { field: "investor_norm", title: "Klucz", cssClass: "dim", width: 260 }] });
  tblAl.on("cellEdited", async (cell) => { await api("/api/aliases", { method: "POST", body: { alias_norm: cell.getRow().getIndex(), canonical: cell.getValue() } }); toast("Zapisano nazwę"); });
}
function summarize(js) {
  try { const s = JSON.parse(js || "{}");
    if (s.error) return `Błąd: ${s.error}`;
    const parts = [];
    if (s.quotes_GPW != null) parts.push(`notowania GPW ${s.quotes_GPW}, NC ${s.quotes_NC ?? 0}`);
    if (s.espi_new != null) parts.push(`nowe komunikaty ${s.espi_new} (odczytane ${s.espi_parsed ?? 0}/${s.espi_details ?? 0})`);
    if (s.companies_profiles) parts.push(`akcjonariat ${s.companies_profiles} spółek`);
    if (s.prices_filled != null) parts.push(`wycenione zmiany ${s.prices_filled}`);
    return parts.join("; ");
  } catch { return js || ""; }
}
async function startRun(weekly) {
  const r = await api("/api/collect", { method: "POST", body: { weekly } });
  toast(r.started ? "Rozpoczęto pobieranie – potrwa kilka minut" : r.msg);
  pollStatus();
}
const pollStatus = async () => { const s = await api("/api/status"); updateFoot(s);
  if (s.job_running) { $("#runState").textContent = "Pobieranie trwa…"; setTimeout(pollStatus, 5000); }
  else { $("#runState").textContent = ""; if (pollStatus.was) { toast("Pobieranie zakończone"); refreshCurrent(); } }
  pollStatus.was = s.job_running; };
$("#btnRun").addEventListener("click", () => startRun(false));
$("#btnRunWeekly").addEventListener("click", () => startRun(true));
function updateFoot(s) { const r = s.runs.find((x) => x.finished);
  $("#lastRun").textContent = r ? `Ostatnie pobranie: ${r.finished.replace("T", " ").slice(0, 16)} (${r.status === "ok" ? "udane" : "błąd"})` : "Jeszcze nic nie pobrano"; }

/* ---------- nawigacja ---------- */
const loaders = { companies: loadCompanies, investors: loadInvestors, changes: loadChanges, espi: loadEspi, settings: loadSettings };
const loaded = {};
let current = "companies";
function showView(v) {
  current = v;
  $$(".rail [data-view]").forEach((b) => b.dataset.view === v ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current"));
  $$("main > section").forEach((s) => { s.hidden = s.id !== `view-${v}`; });
  if (!loaded[v]) { loaded[v] = true; loaders[v]().catch((e) => toast("Błąd: " + e.message)); }
  else if (v === "settings") loadSettings();
  history.replaceState(null, "", `#${v}`);
}
function refreshCurrent() { Object.keys(loaded).forEach((k) => delete loaded[k]); showView(current); }
$$(".rail [data-view]").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));
const startView = location.hash.slice(1);
showView(startView in loaders ? startView : "companies");
api("/api/status").then((s) => { updateFoot(s); if (s.job_running) pollStatus(); }).catch(() => {});
