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
const F = { 0: nf(0), 1: nf(1), 2: nf(2), 3: nf(3), 4: nf(4) };
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
const WARN_SHORT = { emisja: "emisja", sprzedaz: "sprzedaż po wzroście", raport: "brak raportu", raport_opozniony: "opóźniony raport", skrajne: "NC: skrajne" };
const warnRank = (v) => (v || []).reduce((s, w) => s + (w.level === "warn" ? 10 : 1), 0);
const warnFmt = (cell) => { const v = cell.getValue() || []; if (!v.length) return "";
  const main = v.filter((w) => w.level === "warn"), tip = esc(v.map((w) => "• " + w.text).join("\n"));
  return main.length ? `<span class="sig warn" title="${tip}">⚠ ${esc(WARN_SHORT[main[0].kind] || main[0].kind)}${main.length > 1 ? " +" + (main.length - 1) : ""}</span>`
    : `<span class="sig" title="${tip}">${esc(WARN_SHORT[v[0].kind] || v[0].kind)}</span>`; };
const pfColFmt = (cell) => { const v = cell.getValue(), q = cell.getRow().getData().pf_qty;
  return v ? v.split(", ").map((n) => `<span class="pf-tag" title="${fmtNum(q, 0)} akcji w portfelach">${esc(n)}</span>`).join(" ") : ""; };
const tickerFmt = (cell) => `<a class="tk" href="#" data-t="${esc(cell.getValue())}">${esc(cell.getValue())}</a>`;

const chgFmt = (cell) => {
  const d = cell.getRow().getData(), base = pct(cell);
  if (!d.exdiv_today || d.price == null || d.change_pct == null) return base;
  const prev = d.price / (1 + d.change_pct / 100), adj = ((d.price + d.exdiv_today) / prev - 1) * 100;
  return `${base} <span class="badge" title="Dzień odcięcia dywidendy ${fmtNum(d.exdiv_today, 2)} zł (${fmtNum(d.exdiv_today / prev * 100, 1)}%). Po doliczeniu dywidendy: ${adj > 0 ? "+" : ""}${fmtNum(adj, 2)}%">D</span>`;
};
const divYieldFmt = (cell) => {
  const v = cell.getValue(), d = cell.getRow().getData();
  if (v == null) return "";
  const warn = d.div_payout > 100 ? ` <span class="warn" title="Dywidendy z 12 mies. to ${fmtNum(d.div_payout, 0)}% zysku na akcję – wypłata ponad zysk, trudna do powtórzenia">⚠</span>` : "";
  const one = cell.getField() === "div_yield" && d.div_oneoff12 ? ` <span class="badge" title="W tym wypłata jednorazowa ${fmtNum(d.div_oneoff12, 2)} zł na akcję">J</span>` : "";
  return `${fmtNum(v, 2)}%${one}${cell.getField() === "div_yield_regular" ? warn : ""}`;
};

const pctPlain = (c) => c.getValue() == null ? "" : `<span class="${c.getValue() < 0 ? "down" : ""}">${fmtNum(c.getValue(), 1)}%</span>`;
const qualFmt = (c) => { const v = c.getValue(); if (v == null) return "";
  return `<span class="qbadge ${v >= 70 ? "good" : v >= 45 ? "mid" : "bad"}">${v}</span>`; };
const ndFmt = (c) => { const d = c.getRow().getData(); if (d.net_cash) return `<span class="up">gotówka netto</span>`;
  const v = c.getValue(); return v == null ? "" : `<span class="${v > 3 ? "down" : v < 2 ? "" : "warn"}">${fmtNum(v, 1)}</span>`; };
const czMedFmt = (c) => { const v = c.getValue(); if (v == null) return "";
  return `<span class="${v < -15 ? "up" : v > 25 ? "down" : ""}" title="Mediana C/Z z 5 lat: ${fmtNum(c.getRow().getData().cz_med5, 1)}">${v > 0 ? "+" : ""}${fmtNum(v, 0)}%</span>`; };
const trendFmt = (c) => c.getValue() == null ? "" : c.getValue() ? `<span class="up">▲ wzrost.</span>` : `<span class="down">▼ spadk.</span>`;
const ppFmt = (c) => { const v = c.getValue(); return v == null ? "" : `<span class="${v > 0 ? "up" : v < 0 ? "down" : ""}">${v > 0 ? "+" : ""}${fmtNum(v, 1)} pp</span>`; };

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
  tech: "Trend i siła względna", fin: "Wyniki i jakość", div: "Dywidendy", own: "Akcjonariat i przepływy", press: "Presja kupujących", af: "Analiza fundamentalna",
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
  { field: "warnings", title: "Ostrzeżenia", group: "base", width: 120, formatter: warnFmt, sorter: (a, b) => warnRank(a) - warnRank(b),
    headerTooltip: "Nie dotykaj bez sprawdzenia: emisja akcji (60 dni), sprzedaż dużych akcjonariuszy lub insiderów po dużym wzroście, brak lub opóźnienie raportu okresowego, a na NewConnect skrajne wskaźniki (C/WK > 20, ujemna EBITDA, kapitalizacja < 20 mln zł). Szczegóły w dymku.",
    headerFilter: "list", headerFilterParams: { values: { warn: "ważne ostrzeżenia", any: "dowolne", none: "bez ostrzeżeń" }, clearable: true },
    headerFilterFunc: (h, v) => h === "none" ? !v : h === "any" ? !!v : (v || []).some((w) => w.level === "warn") },
  { field: "pf", title: "W portfelu", group: "base", width: 130, formatter: pfColFmt, sorter: "string",
    headerTooltip: "Spółka ma otwartą pozycję w zakładce Moje spółki (nazwa portfela). Aktualizuje się po każdym zakupie i sprzedaży.",
    headerFilter: "tickCross", headerFilterParams: { tristate: true }, headerFilterFunc: (h, v) => h === null || h === !!v },
  { field: "market", title: "Rynek", group: "base", headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true }, width: 80 },
  { field: "sector", title: "Branża", group: "base", headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true }, width: 160 },
  { field: "price", title: "Kurs", group: "quote", hozAlign: "right", formatter: num2, sorter: numSort },
  { field: "change_pct", title: "Zmiana dzienna", group: "quote", hozAlign: "right", formatter: chgFmt, sorter: numSort },
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
  { field: "trend", title: "Trend", group: "tech", hozAlign: "center", width: 96, formatter: trendFmt,
    headerTooltip: "Wzrostowy: średnia z 50 sesji nad średnią z 200 sesji (spadkowy - odwrotnie). Puste: za krótka historia notowań.",
    headerFilter: "list", headerFilterParams: { values: { true: "wzrostowy", false: "spadkowy" }, clearable: true },
    headerFilterFunc: (h, v) => String(v) === String(h) },
  { field: "vs200", title: "vs SMA200", group: "tech", hozAlign: "right", formatter: pct, sorter: numSort,
    headerTooltip: "Odległość kursu od średniej z 200 sesji (%)." },
  { field: "rs_1m", title: "Siła 1 mies.", group: "tech", hozAlign: "right", formatter: ppFmt, sorter: numSort, visible: false,
    headerTooltip: "Zmiana kursu z 21 sesji minus zmiana WIG w tym samym czasie (punkty procentowe)." },
  { field: "rs_3m", title: "Siła 3 mies.", group: "tech", hozAlign: "right", formatter: ppFmt, sorter: numSort,
    headerTooltip: "Zmiana kursu z 63 sesji minus zmiana WIG w tym samym czasie (punkty procentowe)." },
  { field: "mom", title: "Momentum 3–6 mies.", group: "tech", hozAlign: "right", formatter: pct, sorter: numSort,
    headerTooltip: "Średnia zmiana kursu z 3 i 6 miesięcy (63 i 126 sesji). Ranking w zakładce Trendy." },
  { field: "new_high52", title: "52 tyg.", group: "tech", hozAlign: "center", width: 80, sorter: "boolean",
    formatter: (c) => c.getValue() ? `<span class="sig up">maks.</span>` : c.getRow().getData().new_low52 ? `<span class="sig down">min.</span>` : "",
    headerTooltip: "Dziś nowe maksimum (lub minimum) z 52 tygodni." },
  { field: "cz", title: "C/Z", group: "val", hozAlign: "right", formatter: ratio, sorter: numSort },
  { field: "cwk", title: "C/WK", group: "val", hozAlign: "right", formatter: ratio, sorter: numSort },
  { field: "evebitda", title: "EV/EBITDA", group: "val", hozAlign: "right", formatter: ratio, sorter: numSort },
  { field: "cp", title: "C/P", group: "val", hozAlign: "right", formatter: ratio, sorter: numSort, visible: false },
  { field: "report", title: "Ostatni raport", group: "val", visible: false },
  { field: "quality", title: "Jakość", group: "fin", hozAlign: "right", sorter: numSort, formatter: qualFmt, width: 84,
    headerTooltip: "Ocena jakości biznesu 0–100: F-Score Piotroskiego (do 25 pkt), ROE co najmniej 10% w każdym z ostatnich lat (20), stabilna marża netto (10), dług netto / EBITDA poniżej 2 (15), dodatni wolny przepływ gotówki w 4 z 5 lat (15), Altman EM-Score ≥ 5,5 (15). Szczegóły w panelu spółki." },
  { field: "rev_ttm_yoy", title: "Przychody r/r", group: "fin", hozAlign: "right", formatter: pct, sorter: numSort,
    headerTooltip: "Przychody z 4 ostatnich kwartałów wobec 4 kwartałów rok wcześniej (banki: wynik odsetkowy + prowizyjny)." },
  { field: "np_ttm_yoy", title: "Zysk netto r/r", group: "fin", hozAlign: "right", formatter: pct, sorter: numSort,
    headerTooltip: "Zysk netto z 4 ostatnich kwartałów wobec roku wcześniej. Puste, gdy rok wcześniej była strata." },
  { field: "roe", title: "ROE", group: "fin", hozAlign: "right", formatter: pctPlain, sorter: numSort,
    headerTooltip: "Zysk netto z 4 kwartałów / średni kapitał własny." },
  { field: "net_margin", title: "Marża netto", group: "fin", hozAlign: "right", formatter: pctPlain, sorter: numSort, visible: false },
  { field: "nd_ebitda", title: "Dług netto / EBITDA", group: "fin", hozAlign: "right", sorter: numSort, formatter: ndFmt,
    headerTooltip: "Dług netto (kredyty, obligacje, leasing minus gotówka i inwestycje krótkoterminowe) / EBITDA z 4 kwartałów. Poniżej 2 bezpiecznie." },
  { field: "fcf_ttm", title: "FCF 4 kw.", group: "fin", hozAlign: "right", sorter: numSort, visible: false,
    formatter: (c) => c.getValue() == null ? "" : `<span class="${c.getValue() < 0 ? "down" : ""}">${fmtMoney(c.getValue() * 1000)}</span>`,
    headerTooltip: "Wolny przepływ gotówki z 4 kwartałów: przepływy operacyjne minus CAPEX." },
  { field: "fscore", title: "F-Score", group: "fin", hozAlign: "center", sorter: numSort, width: 78,
    formatter: (c) => c.getValue() == null ? "" : `<span class="${c.getValue() >= 7 ? "up" : c.getValue() <= 3 ? "down" : ""}">${c.getValue()}/9</span>`,
    headerTooltip: "Piotroski F-Score (Biznesradar): 9 kryteriów zyskowności, zadłużenia i efektywności. 7–9 mocno, 0–3 słabo." },
  { field: "altman_rating", title: "Altman", group: "fin", hozAlign: "center", visible: false, width: 74,
    headerTooltip: "Rating z Altman EM-Score (Biznesradar): AAA najlepszy, poniżej BB+ podwyższone ryzyko upadłości." },
  { field: "cz_vs_med", title: "C/Z vs 5 lat", group: "fin", hozAlign: "right", sorter: numSort, formatter: czMedFmt,
    headerTooltip: "Obecne C/Z na tle mediany C/Z spółki z ostatnich 5 lat (20 kwartałów). Ujemne = taniej niż zwykle." },
  { field: "shares_3y", title: "Liczba akcji 3 lata", group: "fin", hozAlign: "right", formatter: pct, sorter: numSort, visible: false,
    headerTooltip: "Zmiana liczby akcji w 3 lata: wzrost = rozwodnienie (emisje), spadek = skup akcji." },
  { field: "div_has", title: "Dywidenda 12 mies.", headerTooltip: "Tak = dywidenda wypłacona w ostatnich 12 miesiącach albo już zapowiedziana (z ustalonym dniem prawa). Wcześniejsze wypłaty są w panelu spółki.", group: "div", formatter: yesno, headerFilter: "tickCross", headerFilterParams: { tristate: true }, hozAlign: "center" },
  { field: "div_streak", title: "Lata dywidendy z rzędu", group: "div", hozAlign: "right", sorter: numSort,
    formatter: (c) => c.getValue() ? fmtNum(c.getValue(), 0) : "", headerTooltip: "Ile lat z rzędu spółka wypłacała dywidendę (z przepływów pieniężnych)." },
  { field: "div_yield", title: "Stopa dyw. 12 mies.", group: "div", hozAlign: "right", formatter: divYieldFmt, sorter: numSort,
    headerTooltip: "Wszystkie dywidendy z dniem odcięcia w ostatnich 12 miesiącach, w relacji do kursu." },
  { field: "div_yield_regular", title: "Stopa dyw. regularna", group: "div", hozAlign: "right", formatter: divYieldFmt, sorter: numSort,
    headerTooltip: "Stopa z 12 miesięcy bez wypłat jednorazowych (ponad 2× wyższych od mediany innych wypłat spółki). ⚠ = wypłata wyższa niż zysk na akcję – trudna do powtórzenia." },
  { field: "div_payout", title: "Wypłata / zysk", group: "div", hozAlign: "right", sorter: numSort, visible: false,
    formatter: (c) => c.getValue() == null ? "" : `<span class="${c.getValue() > 100 ? "down" : ""}">${fmtNum(c.getValue(), 0)}%</span>`,
    headerTooltip: "Dywidendy z 12 miesięcy jako % zysku na akcję z 4 ostatnich kwartałów (kurs / C/Z). Ponad 100% = spółka wypłaca więcej, niż zarabia." },
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

/* ---------- okienko pytania (zamiast prompt/confirm przeglądarki) ---------- */
// ask({title, text, input: {value, placeholder, list}, select: [opcje], ok, danger}) -> Promise: tekst / true / null
function ask(o) {
  return new Promise((resolve) => {
    const dlg = $("#askDlg"), f = $("#askForm");
    f.innerHTML = `<h2>${esc(o.title)}</h2>${o.text ? `<p class="dim">${esc(o.text)}</p>` : ""}
      ${o.input ? `<label class="fld"><span>${esc(o.input.label || "")}</span><input name="v" required maxlength="60" value="${esc(o.input.value || "")}"
        placeholder="${esc(o.input.placeholder || "")}" ${o.input.list ? 'list="askList"' : ""} autofocus></label>
        ${o.input.list ? `<datalist id="askList">${o.input.list.map((x) => `<option value="${esc(x)}">`).join("")}</datalist>` : ""}` : ""}
      ${o.select ? `<label class="fld"><span>${esc(o.selectLabel || "")}</span><select name="v">${o.select.map((x) => `<option ${x === o.selectValue ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></label>` : ""}
      <div class="dlg-actions"><button class="btn" value="cancel" formnovalidate>Anuluj</button>
        <button class="btn ${o.danger ? "danger" : "primary"}" value="ok">${esc(o.ok || "OK")}</button></div>`;
    let answered = false;
    f.onsubmit = (e) => {
      e.preventDefault();
      answered = true;
      const val = e.submitter?.value === "ok" ? (o.input || o.select ? (new FormData(f).get("v") || "").trim() || null : true) : null;
      dlg.close(); resolve(val);
    };
    dlg.onclose = () => { if (!answered) resolve(null); };
    dlg.showModal();
  });
}

/* ---------- tabela spółek ---------- */
let tblCompanies, market = "", views = {};
// "Widok: bieżący" to własny układ użytkownika (companies_layout) - zapisywany na bieżąco, ale tylko gdy
// wybrany jest właśnie on. Zapisany widok tylko się wyświetla; zmiany w nim utrwala przycisk "Zapisz widok".
let activeView = "", workingLayout = null, defaultLayout = null;
const layoutKey = "companies_layout";
const currentLayout = () => ({
  layout: tblCompanies.getColumnLayout().map(({ field, width, visible }) => ({ field, width, visible })),
  sort: tblCompanies.getSorters().map((s) => ({ column: s.field, dir: s.dir })),
  // filtry pod nagłówkami, rynek i wyszukiwanie - widok "Portfel" to zwykle filtr "W portfelu = tak"
  filters: tblCompanies.getHeaderFilters().map((f) => ({ field: f.field, value: f.value })),
  market, q: $("#q").value,
});
function storeWorking() {
  if (!tblCompanies || activeView) return;
  // widok bieżący pamięta kolumny, sortowanie i własne filtry (także po odświeżeniu strony); filtry zapisanego widoku
  // do niego nie przechodzą, a przy zapisie nowego widoku jego filtry przechodzą do tego widoku (patrz Zapisz widok)
  workingLayout = currentLayout();
  api(`/api/settings/${layoutKey}`, { method: "PUT", body: workingLayout }).catch(() => {});
}
const saveLayout = debounce(storeWorking, 600);
function setActiveView(name) {
  activeView = name;
  $("#viewSel").value = name;
  api("/api/settings/companies_active_view", { method: "PUT", body: { name } }).catch(() => {});
}

// isView: zapisany widok - kolumny dodane do aplikacji po jego zapisaniu są w nim ukryte (widok wygląda tak,
// jak go zapisano); w widoku bieżącym nowe kolumny pokazują się, żeby było je widać
function applyLayout(saved, isView = false) {
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
  // kolumny dodane w nowszej wersji (nie ma ich w zapisanym układzie): obok sąsiada z domyślnej kolejności
  const known = new Set(saved.layout.map((l) => l.field));
  BUILTIN.forEach((c, i) => {
    if (known.has(c.field) || !byField[c.field] || i === 0) return;
    tblCompanies.moveColumn(c.field, BUILTIN[i - 1].field, true);
    if (isView) byField[c.field].hide();
  });
  if (saved.sort && saved.sort.length) tblCompanies.setSort(saved.sort.filter((s) => byField[s.column]));
  if (saved.filters) {  // widoki zapisane przed tą wersją nie mają filtrów - zostawiamy bieżące
    tblCompanies.clearHeaderFilter();
    saved.filters.filter((f) => byField[f.field]).forEach((f) => tblCompanies.setHeaderFilterValue(f.field, f.value));
    market = saved.market || "";
    $$("[data-mkt]").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.mkt === market)));
    $("#q").value = saved.q || "";
    applyFilters();
  }
}

async function loadCompanies() {
  const [data, cols, saved, savedViews, active] = await Promise.all([
    api("/api/companies"), api("/api/columns"), api(`/api/settings/${layoutKey}`), api("/api/settings/views"),
    api("/api/settings/companies_active_view")]);
  customCols = cols;
  views = savedViews || {};
  workingLayout = saved;
  activeView = active && views[active.name] ? active.name : "";
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
  tblCompanies.on("tableBuilt", () => { defaultLayout = currentLayout();
    applyLayout(activeView ? views[activeView] : saved, !!activeView); applyFilters();
    ["columnMoved", "columnResized", "columnVisibilityChanged", "dataSorted", "dataFiltered"].forEach((e) => tblCompanies.on(e, saveLayout)); });
  tblCompanies.on("cellEdited", async (cell) => {
    const key = CUSTOM_OF[cell.getField()];
    if (!key) return;
    let v = cell.getValue();
    if (v === false) v = "";
    await api("/api/values", { method: "PUT", body: { ticker: cell.getRow().getIndex(), key, value: v } });
    if (key === "ocena_af") syncAfRating(cell.getRow().getIndex(), key, v || "");
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
  sel.value = activeView;
}

$("#viewSel").addEventListener("change", async (e) => {
  const v = e.target.value;
  if (v === "__del") {
    renderViewSelect();
    const name = await ask({ title: "Usuń zapisany widok", select: Object.keys(views), selectLabel: "Widok",
      selectValue: activeView || Object.keys(views)[0], ok: "Usuń", danger: true });
    if (name && views[name]) {
      try {
        const rest = { ...views }; delete rest[name];
        await api("/api/settings/views", { method: "PUT", body: rest });
        views = rest;
        if (name === activeView) { setActiveView(""); applyLayout(workingLayout || defaultLayout); }
        toast(`Usunięto widok „${name}”`);
      } catch (err) { toast("Nie udało się usunąć widoku: " + err.message); }
    }
    renderViewSelect(); return;
  }
  if (!activeView) storeWorking();  // zmiany z ostatnich chwil, zanim przełączymy na zapisany widok
  setActiveView(views[v] ? v : "");
  applyLayout(activeView ? views[activeView] : (workingLayout || defaultLayout), !!activeView);
  if (!activeView && !(workingLayout || {}).filters) {  // układ ze starszej wersji (bez filtrów) - bez filtrów widoku
    tblCompanies.clearHeaderFilter(); market = ""; $("#q").value = "";
    $$("[data-mkt]").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.mkt === ""))); applyFilters();
  }
  toast(activeView ? `Widok „${activeView}”` : "Widok bieżący");
});
$("#btnSaveView").addEventListener("click", async () => {
  const name = await ask({ title: "Zapisz widok", ok: "Zapisz",
    text: "Zapisują się kolumny, ich kolejność i szerokość, sortowanie, filtry pod nagłówkami, rynek i wyszukiwanie. Wpisz istniejącą nazwę, żeby ją nadpisać.",
    input: { label: "Nazwa widoku", value: activeView || "", placeholder: "np. Obserwowane, Dywidendowe", list: Object.keys(views) } });
  if (!name) return;
  if (views[name] && name !== activeView && !await ask({ title: `Nadpisać widok „${name}”?`, ok: "Nadpisz", danger: true })) return;
  const fromWorking = !activeView, layout = currentLayout();
  try {
    await api("/api/settings/views", { method: "PUT", body: { ...views, [name]: layout } });
  } catch (err) { toast("Nie udało się zapisać widoku: " + err.message); return; }
  views[name] = layout;
  if (fromWorking) {  // filtry przeszły do nowego widoku - widok bieżący wraca do wszystkich spółek
    workingLayout = { ...layout, filters: [], market: "", q: "" };
    api(`/api/settings/${layoutKey}`, { method: "PUT", body: workingLayout }).catch(() => {});
  }
  setActiveView(name); renderViewSelect(); toast(`Zapisano widok „${name}”`);
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
  if (!await ask({ title: "Usunąć kolumnę?", text: "Kolumna zniknie razem ze wszystkimi wpisanymi w niej wartościami.", ok: "Usuń", danger: true })) return;
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
$("#drawerClose").addEventListener("click", () => { drawerTicker = null; $("#drawer").classList.remove("open"); $("#drawer").setAttribute("aria-hidden", "true"); });
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

/* wyniki finansowe i jakość biznesu (długi termin) */
const QUAL_DESC = "Ocena 0–100 z kryteriów: F-Score Piotroskiego (do 25 pkt), ROE co najmniej 10% w każdym z ostatnich lat (20), stabilna marża netto (10), dług netto / EBITDA poniżej 2 (15), dodatni wolny przepływ gotówki w 4 z 5 lat (15), Altman EM-Score ≥ 5,5 (15). Liczona z kryteriów dostępnych dla spółki.";
function qualityBlock(d) {
  const q = d.quality, qs = d.quarters;
  if (!q || !q.period) return `<h3>Wyniki i jakość</h3><p class="dim">Brak danych finansowych (pojawią się po tygodniowym pobraniu sprawozdań).</p>`;
  const k = (v, d = 1, suf = "%") => v == null ? `<span class="dim">–</span>` : `${fmtNum(v, d)}${suf}`;
  const yoy = (v) => v == null ? `<span class="dim">–</span>` : signed(v, 0);
  const th = (x) => x == null ? `<span class="dim">–</span>` : fmtMoney(x * 1000);
  const tbl = qs && qs.rows.length ? `<table><tr><th>Kwartał</th><th class="n">${qs.bank ? "Wynik odsetk. + prowiz." : "Przychody"}</th><th class="n">r/r</th>
      ${qs.bank ? "" : `<th class="n">EBITDA</th><th class="n">r/r</th>`}<th class="n">Zysk netto</th><th class="n">r/r</th></tr>
      ${qs.rows.map((r) => `<tr><td>${esc(r.period.replace("/", " "))}</td><td class="n">${th(r.rev)}</td><td class="n">${yoy(r.rev_yoy)}</td>
        ${qs.bank ? "" : `<td class="n">${th(r.ebitda)}</td><td class="n">${yoy(r.ebitda_yoy)}</td>`}
        <td class="n ${r.np < 0 ? "down" : ""}">${th(r.np)}</td><td class="n">${yoy(r.np_yoy)}</td></tr>`).join("")}</table>` : "";
  const parts = (q.quality_parts || []).map((p) => `<li><b>${fmtNum(p.points, 0)}/${p.of}</b> ${esc(p.name)} <span class="dim">– ${esc(p.text)}</span></li>`).join("");
  const fs = (q.fscore_items || []).length ? `<details><summary>F-Score ${q.fscore}/9 – kryteria</summary><ul class="fs">${q.fscore_items.map((i) =>
      `<li class="${i.ok ? "up" : "down"}">${i.ok ? "✓" : "✗"} ${esc(i.name)} <span class="dim">${esc(i.value)}</span></li>`).join("")}</ul></details>` : "";
  const roeH = Object.entries(q.roe_hist || {}).map(([y, v]) => `${y}: ${fmtNum(v, 1)}%`).join(" · ");
  return `<h3>Wyniki i jakość <span class="dim">(dane za ${esc(q.period.replace("/", " "))})</span></h3>
    <div class="qhead">${q.quality == null ? "" : `<div class="qscore ${q.quality >= 70 ? "good" : q.quality >= 45 ? "mid" : "bad"}" title="${esc(QUAL_DESC)}">${q.quality}<small>/100</small></div>`}
      <ul class="qparts">${parts}</ul></div>
    <div class="facts qfacts">
      <div><b>${yoy(q.rev_ttm_yoy)}</b><span>${q.bank ? "Wynik odsetk.+prowiz." : "Przychody"} r/r (4 kw.)</span></div>
      <div><b>${yoy(q.np_ttm_yoy)}${q.np_turnaround ? ` <span class="sig up">z straty na zysk</span>` : ""}</b><span>Zysk netto r/r (4 kw.)</span></div>
      <div><b>${k(q.roe)}</b><span title="${esc(roeH)}">ROE${roeH ? " (najniższe 5 lat: " + k(q.roe_min5) + ")" : ""}</span></div>
      ${q.bank ? "" : `<div><b>${k(q.roic)}</b><span>ROIC</span></div>`}
      <div><b>${k(q.net_margin)}</b><span>Marża netto${q.margin_std5 != null ? ` (wahania ${fmtNum(q.margin_std5, 1)} pp)` : ""}</span></div>
      ${q.bank ? "" : `<div><b>${q.net_cash ? `<span class="up">gotówka netto</span>` : k(q.nd_ebitda, 1, "")}</b><span>Dług netto / EBITDA</span></div>
      <div><b class="${q.fcf_ttm < 0 ? "down" : ""}">${th(q.fcf_ttm)}</b><span>FCF 4 kw. (dodatni w ${q.fcf_pos_years}/${q.fcf_years} lat)</span></div>`}
      <div><b>${q.div_streak || 0}</b><span>Lat dywidendy z rzędu${q.payout != null ? ` · wypłata ${fmtNum(q.payout, 0)}% zysku${q.payout > 80 ? " ⚠" : ""}` : ""}</span></div>
      <div><b>${q.cz_vs_med == null ? `<span class="dim">–</span>` : signed(q.cz_vs_med, 0)}</b><span>C/Z na tle 5 lat (mediana ${k(q.cz_med5, 1, "")})</span></div>
      <div><b>${q.shares_3y == null ? `<span class="dim">–</span>` : signed(q.shares_3y, 1)}</b><span>Liczba akcji w 3 lata</span></div>
      ${q.altman != null ? `<div><b>${esc(q.altman_rating || "")}</b><span>Altman EM-Score ${fmtNum(q.altman, 1)}</span></div>` : ""}
    </div>${fs}${tbl}
    <p class="dim chart-note">Sprawozdania kwartalne z Biznesradar (tys. zł, przeliczone na zł). EBITDA = EBIT + amortyzacja, FCF = przepływy operacyjne − CAPEX. „Niespodzianki” względem oczekiwań analityków nie pokazujemy – konsensusy nie są dostępne bezpłatnie.</p>`;
}

/* ocena analizy fundamentalnej - ta sama wartość co w kolumnie "Ocena AF" tabeli spółek */
let drawerTicker = null;
const AF_TONE = { "Warto": "up", "Obserwuj": "info", "Nie warto": "down" };
function afRatingControl(d) {
  const col = d.af_column;
  if (!col) return `<p class="dim chart-note">Kolumna „Ocena AF” została usunięta – dodaj kolumnę typu lista o tej nazwie, żeby oceniać analizy.</p>`;
  const cur = d.custom?.[col.key] || "";
  return `<div class="af-rate" role="radiogroup" aria-label="${esc(col.label)}" data-key="${esc(col.key)}">
      <span class="dim">${esc(col.label)}:</span>
      ${[...col.options, ""].map((o) => `<button type="button" role="radio" aria-checked="${o === cur}" data-v="${esc(o)}"
        class="${o ? AF_TONE[o] || "" : "none"}">${o ? esc(o) : "brak oceny"}</button>`).join("")}
    </div>`;
}
function syncAfRating(ticker, key, value) {
  if (drawerTicker === ticker) $$(`#drawerBody .af-rate[data-key="${key}"] button`).forEach((b) => b.setAttribute("aria-checked", String(b.dataset.v === value)));
  const r = tblCompanies?.getRow(ticker);
  if (r && r.getData()[`c_${key}`] !== value) r.update({ [`c_${key}`]: value });
}
document.addEventListener("click", async (e) => {
  const b = e.target.closest(".af-rate button"); if (!b || !drawerTicker) return;
  const key = b.closest(".af-rate").dataset.key, value = b.dataset.v, t = drawerTicker;
  await api("/api/values", { method: "PUT", body: { ticker: t, key, value } });
  syncAfRating(t, key, value);
  toast(value ? `Ocena: ${value}` : "Usunięto ocenę");
});

// wiersz z tabeli Spółki (kurs, wskaźniki); gdy tabela nie była jeszcze otwarta - z serwera (raz, potem z pamięci)
let companiesCache = null;
async function companyRow(t) {
  const r = tblCompanies?.getRow(t)?.getData();
  if (r) return r;
  if (!companiesCache || Date.now() - companiesCache.at > 5 * 60 * 1000) {
    companiesCache = { at: Date.now(), rows: Object.fromEntries((await api("/api/companies")).map((x) => [x.ticker, x])) };
  }
  return companiesCache.rows[t] || {};
}

async function openCompany(t) {
  drawerTicker = t;
  const [d, row] = await Promise.all([api(`/api/company/${encodeURIComponent(t)}`), companyRow(t)]);
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
    ${qualityBlock(d)}
    <h3>Analiza fundamentalna</h3>
    ${afRatingControl(d)}
    ${d.analyses.length ? `<table>${d.analyses.map((a) => `<tr><td style="white-space:nowrap">${esc(a.date)}</td>
        <td><a href="/af/${a.file.split("/").map(encodeURIComponent).join("/")}" target="_blank" rel="noopener">${esc(a.name)}</a></td>
        <td class="n dim">${fmtNum(a.size / 1024, 0)} KB</td></tr>`).join("")}</table>`
      : `<p class="dim">Brak analizy. Zapisz plik w folderze „Analizy fundamentalne” w OneDrive z tickerem w nazwie
          (np. ${esc(c.ticker)}_analiza.pdf) - pojawi się tu po synchronizacji (co 15 minut).</p>`}
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

/* ---------- kontekst rynku ---------- */
let mktData = null;
const BREADTH_TXT = (p) => p == null ? "" : p >= 60 ? "większość spółek w trendzie wzrostowym – szeroka hossa"
  : p >= 40 ? "rynek mieszany – trend wzrostowy ma tylko część spółek" : "większość spółek pod średnią 200 sesji – słaby rynek lub korekta";
const smaTag = (v, n) => v == null ? "" : `<span class="sig ${v >= 0 ? "up" : "down"}" title="${v >= 0 ? "Nad" : "Pod"} średnią z ${n} sesji o ${fmtNum(Math.abs(v), 1)}%">${v >= 0 ? "▲" : "▼"} SMA${n}</span>`;
const macroVal = (m) => m.key.startsWith("FX_") ? fmtNum(m.value, 4) : m.key === "GOLD" ? fmtNum(m.value, 2) : fmtNum(m.value, m.value >= 1000 ? 0 : 2);

async function loadMarket() { mktData = await api("/api/market"); return mktData; }
function renderMarketStrip(el, m) {
  if (!m || !m.indices.length) { el.innerHTML = ""; return; }
  const b = m.breadth;
  el.innerHTML = `${m.indices.filter((i) => i.key !== "WIG").map((i) => `<div class="mchip" title="${esc(i.name)} ${fmtNum(i.value, 2)} · ${i.live ? "bieżące notowanie " + esc(i.as_of.slice(11)) : "zamknięcie " + dd(i.as_of)}
SMA50 ${fmtNum(i.sma50, 0)} (${i.vs50 == null ? "–" : (i.vs50 > 0 ? "+" : "") + fmtNum(i.vs50, 1) + "%"}), SMA200 ${fmtNum(i.sma200, 0)} (${i.vs200 == null ? "–" : (i.vs200 > 0 ? "+" : "") + fmtNum(i.vs200, 1) + "%"})">
      <b>${esc(i.name)}</b> ${signed(i.change_pct)} ${smaTag(i.vs50, 50)}${smaTag(i.vs200, 200)}</div>`).join("")}
    ${b ? `<div class="mchip" title="Odsetek spółek GPW z kursem nad średnią z 200 sesji. ${BREADTH_TXT(b.pct200)}"><b>nad SMA200</b> ${fmtNum(b.pct200, 0)}% spółek</div>
      <div class="mchip" title="Spółki GPW na nowym maksimum / minimum z 52 tygodni"><b>52 tyg.</b> <span class="up">${b.highs.length} maks.</span> / <span class="down">${b.lows.length} min.</span></div>` : ""}
    ${m.macro.filter((x) => ["FX_USD", "FX_EUR", "ROPA", "MIEDZ"].includes(x.key)).map((x) => `<div class="mchip" title="${esc(x.name)} · ${esc(x.source)}, ${dd(x.date)}${x.change_1m == null ? "" : " · 1 mies.: " + (x.change_1m > 0 ? "+" : "") + fmtNum(x.change_1m, 1) + "%"}">
      <b>${esc(x.name.split(" (")[0])}</b> ${macroVal(x)} ${signed(x.change_pct)}</div>`).join("")}`;
}
function marketCard(m) {
  if (!m || !m.indices.length) return "";
  const b = m.breadth;
  const idx = `<table class="stable"><thead><tr><th>Indeks</th><th class="n">Wartość</th><th class="n">Dziś</th>
      <th class="n" title="Odległość od średniej z 50 sesji">vs SMA50</th><th class="n" title="Odległość od średniej z 200 sesji">vs SMA200</th>
      <th title="Średnia 50 sesji nad średnią 200 sesji = trend wzrostowy">Trend</th><th class="n">Zakres 52 tyg.</th><th>Stan na</th></tr></thead><tbody>
    ${m.indices.map((i) => { const pos = i.max52 && i.min52 && i.max52 > i.min52 ? (i.value - i.min52) / (i.max52 - i.min52) * 100 : null;
      return `<tr><td><b>${esc(i.name)}</b></td><td class="n">${fmtNum(i.value, 2)}</td><td class="n">${signed(i.change_pct)}</td>
      <td class="n">${signed(i.vs50, 1)}</td><td class="n">${signed(i.vs200, 1)}</td>
      <td>${i.golden == null ? `<span class="dim">–</span>` : i.golden ? `<span class="up">wzrostowy</span>` : `<span class="down">spadkowy</span>`}</td>
      <td class="n">${pos == null ? `<span class="dim">–</span>` : `<span class="range" title="Minimum ${fmtNum(i.min52, 0)}, maksimum ${fmtNum(i.max52, 0)}"><i style="left:${Math.max(0, Math.min(100, pos))}%"></i></span> ${fmtNum(pos, 0)}%`}</td>
      <td class="dim">${i.live ? "teraz " + esc(i.as_of.slice(11)) : dd(i.as_of)}</td></tr>`; }).join("")}</tbody></table>`;
  const gauge = (p, label) => `<div class="gauge"><div class="gauge-l"><span>${label}</span><b>${fmtNum(p, 0)}%</b></div>
      <div class="bbar"><i class="up" style="flex:${p || 0.001}"></i><i class="down" style="flex:${100 - (p || 0) || 0.001}"></i></div></div>`;
  const hl = (arr, cls) => arr.length ? arr.map((h) => `<a class="tk" href="#" data-t="${esc(h.ticker)}" title="${esc(h.name)} ${fmtNum(h.close, 2)}">${esc(h.ticker)}</a>`).join(" ") : `<span class="dim">brak</span>`;
  const br = b ? `<div class="mcols"><div>${gauge(b.pct200, "Spółki GPW nad SMA200")}${gauge(b.pct50, "Spółki GPW nad SMA50")}
      <p class="small">${esc(BREADTH_TXT(b.pct200))}. <span class="dim">Orientacyjnie: powyżej 60% szeroka hossa, poniżej 40% słabość rynku. Liczone dla ${b.n200} spółek GPW z co najmniej 200 sesjami historii.</span></p></div>
      <div><p><b class="up">Nowe maksima 52 tyg. (${b.highs.length})</b><br>${hl(b.highs)}</p>
      <p><b class="down">Nowe minima 52 tyg. (${b.lows.length})</b><br>${hl(b.lows)}</p>
      <p class="dim small">Kurs (lub maksimum/minimum dnia) przebił najwyższy/najniższy poziom z ostatnich 250 sesji.</p></div></div>` : "";
  const mac = m.macro.length ? `<table class="stable"><thead><tr><th>Wskaźnik</th><th class="n">Wartość</th><th class="n">Zmiana</th><th class="n">1 mies.</th><th>Data</th><th>Źródło</th></tr></thead><tbody>
      ${m.macro.map((x) => `<tr><td>${esc(x.name)}</td><td class="n">${macroVal(x)}</td><td class="n">${signed(x.change_pct)}</td><td class="n">${signed(x.change_1m, 1)}</td>
        <td class="dim">${x.ts ? esc(dd(x.ts.slice(0, 10)) + " " + x.ts.slice(11, 16)) : dd(x.date)}</td><td class="dim">${esc(x.source)}</td></tr>`).join("")}</tbody></table>
      <p class="dim small">Kursy walut NBP to kursy średnie z fixingu ok. 11:45 (zmiana względem poprzedniego fixingu). Rentowności polskich obligacji nie mają darmowego źródła dziennego, które wolno pobierać automatycznie – nie są pokazywane.</p>` : "";
  return `<div class="scard"><h2>Kontekst rynku</h2>${idx}${br}<h3 class="sub">Waluty i surowce</h3>${mac}</div>`;
}

/* ---------- moje spółki (portfele) ---------- */
let pfData = null;
let pfPid = (() => { try { return +localStorage.getItem("gpwt_pf") || null; } catch { return null; } })();
const setPfPid = (v) => { pfPid = v || null; try { localStorage.setItem("gpwt_pf", pfPid || ""); } catch { /* brak pamięci */ } };
const HORIZONS = ["krótki (dni–tygodnie)", "średni (miesiące)", "długi (1–5 lat)"];
const ALERT_LVL = { critical: "bad", warn: "warn", info: "neutral" };
const signed = (v, d = 2, suf = "%") => v == null ? `<span class="dim">–</span>`
  : `<span class="${v > 0 ? "up" : v < 0 ? "down" : ""}">${v > 0 ? "+" : ""}${fmtNum(v, d)}${suf}</span>`;
// kwoty portfela dokładnie (do grosza, jak u brokera), miliony skrótem
const fmtPLN = (v) => v == null ? "" : Math.abs(v) >= 1e6 ? `${fmtNum(v / 1e6, 2)} mln zł` : `${fmtNum(v, 2)} zł`;
const signedMoney = (v) => v == null ? `<span class="dim">–</span>`
  : `<span class="${v > 0 ? "up" : v < 0 ? "down" : ""}">${v > 0 ? "+" : ""}${fmtPLN(v)}</span>`;
const tk = (t) => `<a class="tk" href="#" data-t="${esc(t)}">${esc(t)}</a>`;
const dd = (d) => d ? d.split("-").reverse().join(".") : "";
const pfTag = (name) => name ? `<span class="pf-tag">${esc(name)}</span>` : "";

// tabela Spółki: kolumna "W portfelu" nadąża za zakupami i sprzedażą bez przeładowania całej tabeli
async function syncCompaniesPortfolio() {
  if (!tblCompanies) return;
  const all = pfPid ? await api("/api/portfolio") : pfData, held = {};
  for (const p of all.positions) {
    const h = held[p.ticker] ||= { names: [], qty: 0 };
    if (!h.names.includes(p.portfolio)) h.names.push(p.portfolio);
    h.qty += p.qty;
  }
  const upd = tblCompanies.getData().filter((r) => (r.pf || null) !== (held[r.ticker]?.names.join(", ") || null) || (held[r.ticker] && r.pf_qty !== held[r.ticker].qty))
    .map((r) => ({ ticker: r.ticker, pf: held[r.ticker]?.names.join(", ") || null, pf_qty: held[r.ticker]?.qty ?? null }));
  if (upd.length) tblCompanies.updateData(upd);
}

async function loadPortfolio() {
  pfData = await api(`/api/portfolio?pid=${pfPid || ""}`);
  syncCompaniesPortfolio().catch(() => {});
  if (pfPid && !pfData.portfolios.some((p) => p.id === pfPid)) { setPfPid(null); return loadPortfolio(); }
  renderPortfolio(pfData);
  if (!$("#tickerList").children.length) {
    const cos = await api("/api/companies");
    $("#tickerList").innerHTML = cos.map((c) => `<option value="${esc(c.ticker)}">${esc(c.name)}</option>`).join("");
  }
}

function pfTabs(d) {
  const cur = d.portfolios.find((p) => p.id === pfPid);
  return `<div class="pf-tabs"><div class="seg" role="group" aria-label="Portfel">
      ${d.portfolios.length > 1 || !d.portfolios.length ? `<button data-pftab="" aria-pressed="${!pfPid}">Wszystkie</button>` : ""}
      ${d.portfolios.map((p) => `<button data-pftab="${p.id}" aria-pressed="${p.id === pfPid || (d.portfolios.length === 1 && !pfPid)}">${esc(p.name)}</button>`).join("")}
    </div>
    <button class="btn sm" data-pfnew>+ Nowy portfel</button>
    ${cur || d.portfolios.length === 1 ? `<button class="btn sm" data-pfrename="${(cur || d.portfolios[0]).id}">Zmień nazwę</button>
      <button class="btn sm danger" data-pfdel="${(cur || d.portfolios[0]).id}">Usuń portfel</button>` : ""}</div>`;
}

function renderPortfolio(d) {
  $("#pfAsOf").textContent = d.as_of ? `wycena po ostatniej transakcji z ${d.as_of.replace("T", " ").slice(0, 16)}` : "";
  const T = d.totals, all = !pfPid && d.portfolios.length > 1;
  const cur = d.portfolios.find((p) => p.id === pfPid);
  if (!d.positions.length && !d.closed.length) {
    $("#pfBody").innerHTML = `${pfTabs(d)}<div class="scard"><h2>${cur ? `Portfel „${esc(cur.name)}” jest pusty` : "Zacznij od pierwszego zakupu"}</h2>
      <p>Kliknij <b>Dodaj zakup</b> i wpisz spółkę, datę, liczbę akcji i cenę. Od razu zapisz plan: dlaczego kupujesz,
      przy jakim kursie wychodzisz na stracie, jaki jest cel i horyzont. Masz kilka rachunków (np. IKE i zwykły)?
      Utwórz osobne portfele przyciskiem <b>+ Nowy portfel</b> – wyniki liczą się osobno i łącznie.</p></div>`;
    return;
  }
  const title = cur ? `portfela „${esc(cur.name)}”` : all ? "wszystkich portfeli" : "portfela";
  const kpi = `<div class="kpis pf">
    <div class="kpi"><h3>Wartość ${title}</h3><div class="big">${fmtPLN(T.value)}</div>
      <p class="dim small">${T.n} ${T.n === 1 ? "pozycja" : T.n < 5 ? "pozycje" : "pozycji"} · koszt zakupu ${fmtPLN(T.cost)}</p></div>
    <div class="kpi"><h3>Wynik niezrealizowany</h3><div class="big">${signedMoney(T.pnl)}</div>
      <p class="dim small">${signed(T.pnl_pct)} od zakupu</p></div>
    <div class="kpi"><h3>Dziś</h3><div class="big">${signedMoney(T.today_pnl)}</div><p class="dim small">${signed(T.today_pct)}</p></div>
    <div class="kpi"><h3 title="Wynik minus zmiana WIG od dat Twoich zakupów (ważona kosztem pozycji)">Na tle WIG</h3>
      <div class="big">${signed(T.vs_wig, 1, " pp")}</div>
      <p class="dim small">${T.wig_pct == null ? "Brak aktualnych notowań WIG – pojawią się po wieczornym pobraniu." : `WIG od Twoich zakupów: ${signed(T.wig_pct, 1)} (${d.wig_live ? `bieżący, ${dd(d.wig_date.slice(0, 10))} ${d.wig_date.slice(11, 16)}` : `zamknięcie ${dd(d.wig_date)}`})`}</p></div>
    <div class="kpi"><h3>Zrealizowany wynik</h3><div class="big">${signedMoney(T.realized)}</div>
      <p class="dim small">ze sprzedanych pozycji</p></div>
  </div>`;

  const breakdown = all ? `<div class="scard"><h2>Portfele</h2><table class="stable"><thead><tr><th>Portfel</th><th class="n">Wartość</th>
      <th class="n">Udział</th><th class="n">Wynik</th><th class="n">Wynik %</th><th class="n">Dziś</th><th class="n">vs WIG</th>
      <th class="n">Zrealizowany</th><th class="n">Pozycje</th></tr></thead><tbody>
      ${d.portfolios.map((p) => `<tr><td><a href="#" class="tk" data-pftab="${p.id}">${esc(p.name)}</a></td><td class="n">${fmtPLN(p.value)}</td>
        <td class="n">${p.share == null ? "" : fmtNum(p.share, 1) + "%"}</td><td class="n">${signedMoney(p.cost ? p.pnl : null)}</td>
        <td class="n">${signed(p.pnl_pct)}</td><td class="n">${signedMoney(p.cost ? p.today_pnl : null)}</td>
        <td class="n">${signed(p.vs_wig, 1, " pp")}</td><td class="n">${signedMoney(p.realized || null)}</td><td class="n">${p.n}</td></tr>`).join("")}
      </tbody></table></div>` : "";

  const alerts = d.alerts.length ? `<ul class="alerts">${d.alerts.map((a) => `<li class="al-${a.level}">${levelIcon(ALERT_LVL[a.level])}
      ${tk(a.ticker)} ${all ? pfTag(a.portfolio) : ""} ${esc(a.text)} ${a.ts ? `<span class="dim">${esc(dd(a.ts.slice(0, 10)))} ${esc(a.ts.slice(11, 16))}</span>` : ""}</li>`).join("")}</ul>`
    : `<p class="dim">Brak alertów – nic nie przebiło poziomów z planu, brak nowych komunikatów i transakcji insiderów.</p>`;

  const rows = sortPositions(d.positions).map((p) => {
    const pl = p.plan || {}, toStop = pl.stop && p.close ? (p.close / pl.stop - 1) * 100 : null;
    const toTarget = pl.target && p.close ? (pl.target / p.close - 1) * 100 : null;
    const lvl = p.alerts.some((a) => a.level === "critical") ? "down" : p.alerts.some((a) => a.level === "warn") ? "warn" : "info";
    return `<tr class="pf-row" data-t="${esc(p.ticker)}" data-pid="${p.portfolio_id}">
      <td>${tk(p.ticker)} <span class="dim nm">${esc(p.name)}</span>${p.alerts.length ? ` <span class="sig ${lvl}" title="${esc(p.alerts.map((a) => a.text).join("\n"))}">${p.alerts.length} ${p.alerts.length === 1 ? "alert" : "alerty"}</span>` : ""}</td>
      ${all ? `<td>${pfTag(p.portfolio)}</td>` : ""}
      <td class="n">${fmtNum(p.qty, 0)}</td><td class="n">${fmtNum(p.avg_price, p.avg_price < 10 ? 4 : 2)}</td><td class="n" title="Ostatnia transakcja na GPW z pobrania ${esc((d.as_of || "").replace("T", " ").slice(0, 16))}">${fmtNum(p.close, p.close < 10 ? 3 : 2)}</td>
      <td class="n">${signed(p.chg)}</td><td class="n">${fmtPLN(p.value)}</td><td class="n">${p.weight == null ? "" : fmtNum(p.weight, 1) + "%"}</td>
      <td class="n">${signedMoney(p.pnl)}</td><td class="n">${signed(p.pnl_pct)}</td>
      <td class="n" title="Wynik pozycji minus zmiana WIG od daty zakupu (WIG ${p.wig_pct == null ? "–" : fmtNum(p.wig_pct, 1) + "%"})">${signed(p.vs_wig, 1, " pp")}</td>
      <td class="n">${pl.stop ? `${fmtNum(pl.stop, 2)} <span class="dim">(${toStop > 0 ? "+" : ""}${fmtNum(toStop, 1)}%)</span>` : `<span class="dim">–</span>`}</td>
      <td class="n">${pl.target ? `${fmtNum(pl.target, 2)} <span class="dim">(${toTarget > 0 ? "+" : ""}${fmtNum(toTarget, 1)}%)</span>` : `<span class="dim">–</span>`}</td>
      <td class="n" title="Ile dni sprzedawałbyś całą pozycję, biorąc 20% średniego dziennego obrotu">${p.exit_days == null ? `<span class="dim">–</span>` : p.exit_days < 0.1 ? "<0,1" : fmtNum(p.exit_days, 1)}</td>
      <td class="act"><button class="btn sm" data-pf="plan">Plan</button><button class="btn sm" data-pf="buy">Dokup</button><button class="btn sm" data-pf="sell">Sprzedaj</button></td>
    </tr>
    <tr class="pf-detail" hidden><td colspan="${all ? 15 : 14}">${planBlock(p)}</td></tr>`;
  }).join("");
  const table = d.positions.length ? `<table class="stable pf-table"><thead><tr>${sth("ticker", "Spółka", "")}${all ? sth("portfolio", "Portfel", "") : ""}${sth("qty", "Akcje")}
    ${sth("avg_price", "Śr. cena")}${sth("close", "Kurs")}${sth("chg", "Dziś")}${sth("value", "Wartość")}${sth("weight", "Udział", "n", `Udział w ${all ? "wszystkich portfelach" : "portfelu"}`)}
    ${sth("pnl", "Wynik")}${sth("pnl_pct", "Wynik %")}${sth("vs_wig", "vs WIG")}${sth("to_stop", "Wyjście", "n", "Sortuje po odległości kursu od poziomu wyjścia")}${sth("to_target", "Cel", "n", "Sortuje po odległości do celu")}
    ${sth("exit_days", "Dni wyjścia", "n", "Dni potrzebne na sprzedaż całej pozycji przy 20% średniego obrotu")}<th></th></tr></thead>
    <tbody>${rows}</tbody></table><p class="dim small">Kliknij wiersz, żeby zobaczyć plan i partie zakupu.</p>`
    : `<p class="dim">Nie masz otwartych pozycji.</p>`;

  const divs = d.dividends.length ? `<table class="stable"><thead><tr><th>Spółka</th>${all ? "<th>Portfele</th>" : ""}<th>Za rok</th><th>Ostatni dzień z prawem</th>
      <th>Wypłata</th><th class="n">Na akcję</th><th class="n">Stopa</th><th class="n">Dla Ciebie (brutto)</th><th>Status</th></tr></thead><tbody>
      ${d.dividends.map((v) => `<tr><td>${tk(v.ticker)}</td>${all ? `<td>${v.portfolios.map(pfTag).join(" ")}</td>` : ""}<td>${esc(v.year_for)}</td><td>${dd(v.last_day)}</td><td>${dd(v.pay_day)}</td>
        <td class="n">${fmtNum(v.dps, 2)} zł</td><td class="n">${v.yield == null ? "" : fmtNum(v.yield, 1) + "%"}</td>
        <td class="n"><b>${fmtNum(v.amount, 0)} zł</b></td><td class="dim">${esc(v.status || "")}</td></tr>`).join("")}</tbody></table>
      <p class="dim small">Kwota przy obecnej liczbie akcji. Prawo do dywidendy mają akcje kupione najpóźniej w ostatnim dniu z prawem.</p>`
    : `<p class="dim">Brak zapowiedzianych dywidend Twoich spółek.</p>`;

  const closed = d.closed.length ? `<details><summary>Sprzedane pozycje (${d.closed.length})</summary>
      <table class="stable"><thead><tr><th>Spółka</th>${all ? "<th>Portfel</th>" : ""}<th>Kupno</th><th>Sprzedaż</th><th class="n">Akcje</th><th class="n">Cena kupna</th>
      <th class="n">Cena sprzedaży</th><th class="n">Wynik</th><th class="n">Wynik %</th><th></th></tr></thead><tbody>
      ${d.closed.map((c) => `<tr><td>${tk(c.ticker)}</td>${all ? `<td>${pfTag(c.portfolio)}</td>` : ""}<td>${dd(c.opened)}</td><td>${dd(c.closed)}</td><td class="n">${fmtNum(c.qty, 0)}</td>
        <td class="n">${fmtNum(c.price, 2)}</td><td class="n">${fmtNum(c.close_price, 2)}</td><td class="n">${signedMoney(c.pnl)}</td>
        <td class="n">${signed(c.pnl_pct)}</td><td><button class="btn sm danger" data-lotdel="${c.id}" title="Usuń wpis z historii">Usuń</button></td></tr>`).join("")}
      </tbody></table></details>` : "";

  $("#pfBody").innerHTML = `${pfTabs(d)}${kpi}${breakdown}
    <div class="scard"><h2>Alerty</h2>${alerts}</div>
    <div class="scard"><h2>Pozycje</h2>${table}</div>
    ${calendarCard({ from: today(), to: new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10), events: d.events || [], schedules: 0, rpp_year_known: true }, 30, { onlyHeld: true, title: "Wydarzenia Twoich spółek – 30 dni" })}
    <div class="scard"><h2>Kalendarz dywidend</h2>${divs}</div>
    ${closed ? `<div class="scard">${closed}</div>` : ""}`;
}

// sortowanie tabeli Pozycje: klik w nagłówek, drugi klik odwraca; zapamiętane w przeglądarce
let pfSort = (() => { try { return JSON.parse(localStorage.getItem("gpwt_pf_sort") || "null") || { key: "value", dir: -1 }; } catch { return { key: "value", dir: -1 }; } })();
const PF_SORT_VAL = {
  to_stop: (p) => p.plan?.stop && p.close ? (p.close / p.plan.stop - 1) * 100 : null,
  to_target: (p) => p.plan?.target && p.close ? (p.plan.target / p.close - 1) * 100 : null,
};
function sortPositions(rows) {
  const val = PF_SORT_VAL[pfSort.key] || ((p) => p[pfSort.key]);
  return [...rows].sort((a, b) => {
    const x = val(a), y = val(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;  // puste zawsze na końcu
    if (y == null) return -1;
    return (typeof x === "string" ? x.localeCompare(y, "pl") : x - y) * pfSort.dir;
  });
}
const sth = (key, label, cls = "n", title = "") => `<th class="${cls} sortable${pfSort.key === key ? " sorted" : ""}" data-pfsort="${key}"${title ? ` title="${esc(title)}"` : ""}>${label}${pfSort.key === key ? (pfSort.dir > 0 ? " ▲" : " ▼") : ""}</th>`;

function planBlock(p) {
  const pl = p.plan || {};
  const line = (label, v) => `<div><span class="dim">${label}</span><div>${v ? esc(v).replace(/\n/g, "<br>") : `<span class="dim">–</span>`}</div></div>`;
  return `<div class="plan">
      ${line("Dlaczego kupiłem", pl.thesis)}
      <div class="plan-grid">${line("Poziom wyjścia na stracie", pl.stop ? fmtNum(pl.stop, 2) + " zł" : "")}
        ${line("Cel", pl.target ? fmtNum(pl.target, 2) + " zł" : "")}${line("Horyzont", pl.horizon)}
        ${line("Przegląd planu", dd(pl.review))}</div>
      ${line("Notatki", pl.notes)}
    </div>
    <table class="stable lots"><thead><tr><th>Partia</th><th class="n">Akcje</th><th class="n">Cena</th><th class="n">Prowizja</th><th></th></tr></thead><tbody>
      ${p.lots.map((l) => `<tr><td>${dd(l.opened)}</td><td class="n">${fmtNum(l.qty, 0)}</td><td class="n">${fmtNum(l.price, l.price < 10 ? 4 : 2)}</td>
        <td class="n">${fmtNum(l.fees || 0, 2)}</td><td><button class="btn sm" data-lotedit="${l.id}">Popraw</button>
        <button class="btn sm danger" data-lotdel="${l.id}">Usuń</button></td></tr>`).join("")}</tbody></table>`;
}

/* formularze: zakup (z planem), plan, sprzedaż, poprawka partii, portfel */
function pfDialog(html, onSubmit) {
  const dlg = $("#pfDlg");
  $("#pfForm").innerHTML = `${html}<div class="dlg-actions"><button class="btn" value="cancel" formnovalidate>Anuluj</button>
    <button class="btn primary" value="ok">Zapisz</button></div><p class="dlg-err down" hidden></p>`;
  $("#pfForm").onsubmit = async (e) => {
    if (e.submitter?.value !== "ok") return;
    e.preventDefault();
    const f = Object.fromEntries(new FormData($("#pfForm")).entries());
    try {
      const r = await fetch(onSubmit.url, { method: onSubmit.method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(onSubmit.body(f)) });
      const j = await r.json();
      if (!r.ok || j.ok === false) throw new Error(j.msg || r.statusText);
      dlg.close(); toast(onSubmit.done); if (onSubmit.after) onSubmit.after(j); loadPortfolio();
    } catch (err) { const p = $("#pfForm .dlg-err"); p.textContent = err.message; p.hidden = false; }
  };
  dlg.showModal();
}
const fld = (name, label, attrs = "", val = "") => `<label class="fld"><span>${label}</span><input name="${name}" ${attrs} value="${esc(val ?? "")}"></label>`;
const pfSelect = (sel) => pfData.portfolios.length ? `<label class="fld"><span>Portfel</span><select name="portfolio_id">${pfData.portfolios.map((p) =>
  `<option value="${p.id}" ${p.id === (sel || pfPid || pfData.portfolios[0].id) ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></label>` : "";
const planFields = (pl = {}) => `
  <label class="fld wide"><span>Dlaczego kupuję</span><textarea name="thesis" rows="3" placeholder="np. wzrost wyników, dywidenda, zakupy zarządu">${esc(pl.thesis || "")}</textarea></label>
  ${fld("stop", "Poziom wyjścia na stracie (zł)", 'type="number" step="any" min="0"', pl.stop)}
  ${fld("target", "Cel (zł)", 'type="number" step="any" min="0"', pl.target)}
  <label class="fld"><span>Horyzont</span><select name="horizon"><option value=""></option>${HORIZONS.map((h) => `<option ${pl.horizon === h ? "selected" : ""}>${h}</option>`).join("")}</select></label>
  ${fld("review", "Przegląd planu (data)", 'type="date"', pl.review)}
  <label class="fld wide"><span>Notatki</span><textarea name="notes" rows="2">${esc(pl.notes || "")}</textarea></label>`;
const today = () => new Date().toISOString().slice(0, 10);
const findPos = (t, pid) => pfData?.positions.find((p) => p.ticker === t && p.portfolio_id === pid);

function addLotDialog(ticker = "", pid = null) {
  const pos = ticker && findPos(ticker, pid);
  pfDialog(`<h2>${ticker ? `Dokup ${esc(ticker)}` : "Dodaj zakup"}</h2><div class="fgrid">
      ${fld("ticker", "Spółka (ticker)", `list="tickerList" required ${ticker ? "readonly" : "autofocus"}`, ticker)}
      ${pos ? `<input type="hidden" name="portfolio_id" value="${pid}">` : pfSelect(pid)}
      ${fld("opened", "Data zakupu", 'type="date" required', today())}
      ${fld("qty", "Liczba akcji", 'type="number" step="any" min="0" required')}
      ${fld("price", "Cena za akcję (zł)", 'type="number" step="any" min="0" required')}
      ${fld("fees", "Prowizja (zł)", 'type="number" step="any" min="0"')}
      ${pos ? `<p class="dim wide">Plan pozycji zmienisz przyciskiem „Plan”.</p>` : `<h3 class="wide">Plan</h3>${planFields()}`}
    </div>`, { url: "/api/positions", method: "POST", done: "Zapisano zakup", body: (f) => ({ ...f, ticker: f.ticker.trim().toUpperCase() }) });
}
function planDialog(t, pid) {
  const p = findPos(t, pid);
  pfDialog(`<h2>Plan: ${esc(t)} ${pfTag(p?.portfolio)}</h2><div class="fgrid">${planFields(p?.plan)}</div>`,
    { url: `/api/plans/${pid}/${encodeURIComponent(t)}`, method: "PUT", done: "Zapisano plan", body: (f) => f });
}
function sellDialog(t = "", pid = null) {
  if (!pfData.positions.length) { toast("Nie masz otwartych pozycji"); return; }
  const many = pfData.portfolios.length > 1;
  const opts = pfData.positions.map((p) => `<option value="${p.portfolio_id}|${esc(p.ticker)}" ${p.ticker === t && p.portfolio_id === pid ? "selected" : ""}>${esc(p.ticker)}${many ? ` (${esc(p.portfolio)})` : ""} – ${fmtNum(p.qty, 0)} akcji</option>`).join("");
  const p = findPos(t, pid) || pfData.positions[0];
  pfDialog(`<h2>Sprzedaż</h2><div class="fgrid">
      <label class="fld"><span>Pozycja</span><select name="pos">${opts}</select></label>
      ${fld("date", "Data sprzedaży", 'type="date" required', today())}
      ${fld("qty", "Liczba akcji", 'type="number" step="any" min="0" required', p.qty)}
      ${fld("price", "Cena za akcję (zł)", 'type="number" step="any" min="0" required', p.close)}
      ${fld("fees", "Prowizja (zł)", 'type="number" step="any" min="0"')}
      <p class="dim wide">Sprzedaż zamyka najstarsze partie w tym portfelu jako pierwsze (FIFO); wynik trafi do „Sprzedane pozycje”.</p></div>`,
    { url: "/api/positions/sell", method: "POST", done: "Zapisano sprzedaż",
      body: (f) => { const [portfolio_id, ticker] = f.pos.split("|"); return { ...f, portfolio_id, ticker }; } });
}
function lotEditDialog(id) {
  const lot = pfData.positions.flatMap((p) => p.lots.map((l) => ({ ...l, ticker: p.ticker, pid: p.portfolio_id }))).find((l) => l.id === id);
  pfDialog(`<h2>Popraw partię ${esc(lot.ticker)}</h2><div class="fgrid">
      ${fld("opened", "Data zakupu", 'type="date" required', lot.opened)}${fld("qty", "Liczba akcji", 'type="number" step="any" min="0" required', lot.qty)}
      ${fld("price", "Cena (zł)", 'type="number" step="any" min="0" required', lot.price)}${fld("fees", "Prowizja (zł)", 'type="number" step="any" min="0"', lot.fees)}
      ${pfData.portfolios.length > 1 ? pfSelect(lot.pid) + `<p class="dim wide">Zmiana portfela przenosi tę partię (plan pozycji zostaje w starym portfelu).</p>` : ""}</div>`,
    { url: `/api/positions/${id}`, method: "PATCH", done: "Poprawiono partię", body: (f) => f });
}
function portfolioDialog(p = null) {
  pfDialog(`<h2>${p ? "Zmień nazwę portfela" : "Nowy portfel"}</h2><div class="fgrid">
      ${fld("name", "Nazwa (np. IKE, IKZE, konto maklerskie)", 'required autofocus maxlength="40"', p?.name || "")}</div>`,
    { url: p ? `/api/portfolios/${p.id}` : "/api/portfolios", method: p ? "PATCH" : "POST",
      done: p ? "Zmieniono nazwę" : "Utworzono portfel", body: (f) => f, after: (j) => { if (!p && j.id) setPfPid(j.id); } });
}
$("#pfAdd").addEventListener("click", () => addLotDialog());
$("#pfSell").addEventListener("click", () => pfData && sellDialog());
$("#pfBody").addEventListener("click", async (e) => {
  const srt = e.target.closest("[data-pfsort]");
  if (srt) {
    const k = srt.dataset.pfsort;
    // pierwszy klik: liczby malejąco (najlepszy wynik na górze), teksty rosnąco
    pfSort = pfSort.key === k ? { key: k, dir: -pfSort.dir } : { key: k, dir: ["ticker", "portfolio"].includes(k) ? 1 : -1 };
    try { localStorage.setItem("gpwt_pf_sort", JSON.stringify(pfSort)); } catch { /* brak pamięci */ }
    renderPortfolio(pfData); return;
  }
  const tab = e.target.closest("[data-pftab]");
  if (tab) { e.preventDefault(); setPfPid(+tab.dataset.pftab || null); loadPortfolio(); return; }
  const b = e.target.closest("button");
  if (b?.dataset.pfnew !== undefined && b) { portfolioDialog(); return; }
  if (b?.dataset.pfrename) { portfolioDialog(pfData.portfolios.find((p) => p.id === +b.dataset.pfrename)); return; }
  if (b?.dataset.pfdel) {
    const p = pfData.portfolios.find((x) => x.id === +b.dataset.pfdel);
    if (!await ask({ title: `Usunąć portfel „${p.name}”?`, text: "Da się usunąć tylko pusty portfel (bez pozycji i historii sprzedaży).", ok: "Usuń", danger: true })) return;
    try { await api(`/api/portfolios/${p.id}`, { method: "DELETE" }); setPfPid(null); toast("Usunięto portfel"); loadPortfolio(); }
    catch (err) { toast(JSON.parse(err.message.replace(/^\d+ /, "") || "{}").msg || err.message); }
    return;
  }
  if (b?.dataset.pf) {
    const tr = b.closest("tr"), t = tr.dataset.t, pid = +tr.dataset.pid;
    ({ plan: planDialog, buy: addLotDialog, sell: sellDialog })[b.dataset.pf](t, pid); return;
  }
  if (b?.dataset.lotedit) { lotEditDialog(+b.dataset.lotedit); return; }
  if (b?.dataset.lotdel) {
    if (!await ask({ title: "Usunąć tę partię z portfela?", text: "Tego nie da się cofnąć.", ok: "Usuń", danger: true })) return;
    await api(`/api/positions/${b.dataset.lotdel}`, { method: "DELETE" }); toast("Usunięto"); loadPortfolio(); return;
  }
  const row = e.target.closest("tr.pf-row");
  if (row && !e.target.closest("a")) { const det = row.nextElementSibling; det.hidden = !det.hidden; row.classList.toggle("open", !det.hidden); }
});

/* ---------- sesja dziś ---------- */
let sesPref = { min: 100000, min_nc: 30000, market: "", watch: "", sessions: 1 }, sesTimer = null;
const SIG_LABEL = { insider_buy: "kupno", insider_sell: "sprzedaż", wezwanie: "wezwanie", skup: "skup", exdiv: "dywidenda",
  move_up: "wzrost", move_down: "spadek", volume: "obrót", press_up: "akumulacja", press_down: "dystrybucja", transfer: "przesunięcie",
  breakout: "wybicie", gap_up: "luka ▲", gap_down: "luka ▼", rs: "siła vs WIG", espi_umowa: "umowa", espi_wyniki: "wyniki", espi_emisja: "emisja",
  warn_emisja: "⚠ emisja", warn_sprzedaz: "⚠ sprzedaż po wzroście", warn_raport: "⚠ brak raportu", warn_raport_opozniony: "⚠ opóźniony raport" };
const SIG_TONE = { insider_buy: "up", move_up: "up", press_up: "up", insider_sell: "down", move_down: "down", press_down: "down",
  wezwanie: "warn", volume: "warn", exdiv: "info", skup: "info", transfer: "info", breakout: "up", gap_up: "up", gap_down: "down",
  rs: "up", espi_umowa: "info", espi_wyniki: "info", espi_emisja: "warn",
  warn_emisja: "down", warn_sprzedaz: "down", warn_raport: "down", warn_raport_opozniony: "down" };
// definicje sygnałów (te same progi co w gpwt/session.py) - pokazywane w dymku pod konkretnym opisem
const SIG_HELP = {
  move_up: "Wzrost: zmiana kursu co najmniej +5% (w dniu odcięcia dywidendy - po jej doliczeniu) przy obrocie co najmniej 2× wyższym od średniej z 20 sesji.",
  move_down: "Spadek: zmiana kursu co najmniej −5% (po doliczeniu dywidendy) przy obrocie co najmniej 2× wyższym od średniej z 20 sesji.",
  volume: "Obrót: co najmniej 3× wyższy od średniej z 20 sesji (i min. 20 tys. zł), bez dużej zmiany kursu - ktoś buduje lub zamyka pozycję.",
  press_up: "Akumulacja: presja kupujących (Chaikin Money Flow) z 21 sesji co najmniej +0,25 - sesje kończyły się zwykle blisko dziennego maksimum, liczone z wagą obrotu.",
  press_down: "Dystrybucja: presja kupujących (CMF) z 21 sesji co najwyżej −0,25 - sesje kończyły się zwykle blisko dziennego minimum przy dużych obrotach.",
  insider_buy: "Kupno: insider (zarząd, rada lub osoba blisko związana, art. 19 MAR) albo akcjonariusz z ponad 5% (art. 69) zgłosił zakup w wybranym oknie sesji.",
  insider_sell: "Sprzedaż: insider (art. 19 MAR) albo akcjonariusz z ponad 5% (art. 69) zgłosił sprzedaż w wybranym oknie sesji.",
  exdiv: "Dywidenda: dziś dzień odcięcia - kurs spada o wartość dywidendy technicznie, zmianę liczymy po jej doliczeniu.",
  wezwanie: "Wezwanie do zapisywania się na sprzedaż akcji - zwykle po stałej cenie, często z premią.",
  skup: "Skup akcji własnych przez spółkę.",
  transfer: "Przesunięcie: kupno i sprzedaż między powiązanymi podmiotami (np. do fundacji rodzinnej) - saldo ok. zera.",
  breakout: "Wybicie: kurs (lub maksimum dnia) powyżej najwyższego poziomu z 52 tygodni albo z 3 miesięcy, przy obrocie co najmniej 2× wyższym od średniej z 20 sesji. Jeden z niewielu krótkoterminowych sygnałów, które statystycznie mają znaczenie.",
  gap_up: "Luka wzrostowa: otwarcie co najmniej 1% powyżej maksimum poprzedniej sesji. Domknięta = kurs w trakcie dnia wrócił do poziomu wczorajszego maksimum (słabszy sygnał).",
  gap_down: "Luka spadkowa: otwarcie co najmniej 1% poniżej minimum poprzedniej sesji. Domknięta = kurs w trakcie dnia wrócił do wczorajszego minimum.",
  rs: "Siła względna: spółka rośnie co najmniej 2%, gdy WIG spada o 0,5% lub więcej - popyt niezależny od rynku.",
  espi_umowa: "Komunikat o umowie, kontrakcie, zamówieniu lub porozumieniu (słowa kluczowe w tytule).",
  espi_wyniki: "Komunikat z szacunkowymi lub wstępnymi wynikami albo prognozą (słowa kluczowe w tytule).",
  espi_emisja: "Komunikat o emisji akcji, ofercie publicznej lub podwyższeniu kapitału - możliwe rozwodnienie.",
  warn_emisja: "Nie dotykaj bez sprawdzenia: emisja akcji lub podwyższenie kapitału w ostatnich 60 dniach - nowe akcje rozwadniają udział i często trafiają na rynek.",
  warn_sprzedaz: "Nie dotykaj bez sprawdzenia: duży akcjonariusz (art. 69) lub insider sprzedaje w ostatnich 30 dniach po wzroście kursu (3 mies. ≥ +30% albo miesiąc ≥ +20%).",
  warn_raport: "Nie dotykaj bez sprawdzenia: minął ustawowy termin raportu, a najnowsze dane finansowe są o co najmniej 2 kwartały starsze i w komunikatach nie widać nowego raportu.",
  warn_raport_opozniony: "Nie dotykaj bez sprawdzenia: minęła data raportu z harmonogramu spółki, a raportu nie widać w komunikatach (NewConnect).",
};
const sigTitle = (s) => `${s.text}${SIG_HELP[s.kind] ? "\n\n" + SIG_HELP[s.kind] : ""}`;
const sigChips = (sigs) => (sigs || []).map((s) =>
  `<span class="sig ${SIG_TONE[s.kind] || ""}" title="${esc(sigTitle(s))}">${SIG_LABEL[s.kind] || s.kind}</span>`).join(" ");
const sigList = (sigs) => (sigs || []).length
  ? `<ul class="siglist">${sigs.map((s) => `<li><span class="sig ${SIG_TONE[s.kind] || ""}" title="${esc(SIG_HELP[s.kind] || "")}">${SIG_LABEL[s.kind] || s.kind}</span> ${esc(s.text)}</li>`).join("")}</ul>`
  : `<span class="dim">bez sygnałów</span>`;
const chgCell = (x) => {
  const v = x.chg_eff, cls = v > 0 ? "up" : v < 0 ? "down" : "";
  const raw = x.exdiv ? `<div class="dim" title="Zmiana kursu bez doliczenia dywidendy">kurs ${x.chg > 0 ? "+" : ""}${fmtNum(x.chg, 2)}%</div>` : "";
  return `<span class="${cls}">${v > 0 ? "+" : ""}${fmtNum(v, 2)}%</span>${x.exdiv ? ` <span class="badge" title="Dzień odcięcia dywidendy ${fmtNum(x.exdiv.dps, 2)} zł – zmiana po jej doliczeniu">D</span>` : ""}${raw}`;
};
const ratioCell = (r) => r == null ? `<span class="dim">–</span>` : `${r >= 3 ? "<b>" : ""}${fmtNum(r, 1)}×${r >= 3 ? "</b>" : ""}`;

function moversTable(rows, empty) {
  if (!rows.length) return `<p class="dim">${empty}</p>`;
  return `<table class="stable"><thead><tr><th>Spółka</th><th class="n">Zmiana</th><th class="n">Obrót</th>
    <th class="n" title="Obrót dziś do średniej z 20 sesji">× śr.</th><th>Sygnały</th></tr></thead><tbody>
    ${rows.map((x) => `<tr><td><a class="tk" href="#" data-t="${esc(x.ticker)}">${esc(x.ticker)}</a> <span class="dim nm">${esc(x.name)}</span></td>
      <td class="n">${chgCell(x)}</td><td class="n">${fmtMoney(x.turnover)}</td><td class="n">${ratioCell(x.ratio)}</td>
      <td>${sigChips(x.signals)}</td></tr>`).join("")}</tbody></table>`;
}

function breadthBar(b) {
  const tot = b.up + b.flat + b.down || 1;
  const seg = (n, cls, label) => n ? `<i class="${cls}" style="flex:${n}" title="${label}: ${n}"></i>` : "";
  return `<div class="bbar" role="img" aria-label="Rośnie ${b.up}, bez zmian ${b.flat}, spada ${b.down}">
      ${seg(b.up, "up", "Rośnie")}${seg(b.flat, "flat", "Bez zmian")}${seg(b.down, "down", "Spada")}</div>
    <div class="blegend"><span><i class="up"></i>rośnie <b>${b.up}</b> (${fmtNum(b.up / tot * 100, 0)}%)</span>
      <span><i class="flat"></i>bez zmian <b>${b.flat}</b></span>
      <span><i class="down"></i>spada <b>${b.down}</b> (${fmtNum(b.down / tot * 100, 0)}%)</span></div>`;
}

function renderSession(d) {
  if (!d.date) { $("#sesBody").innerHTML = `<p class="dim">Brak notowań – uruchom pobieranie w zakładce „Dane i ustawienia”.</p>`; return; }
  $("#sesDate").textContent = d.date.split("-").reverse().join(".");
  $("#sesAsOf").textContent = d.as_of ? `stan danych: ${d.as_of.replace("T", " ").slice(0, 16)}` : "";
  const L = d.breadth.liquid, A = d.breadth.all, ut = L.up_turnover + L.down_turnover || 1;
  const c = d.espi.counts, ins = (c.mar || 0) + (c.art69 || 0);
  const kpi = `<div class="kpis">
    <div class="kpi wide"><h3>Szerokość rynku – płynne spółki (${L.up + L.flat + L.down}; GPW od ${fmtMoney(d.min_turnover)} zł, NC od ${fmtMoney(d.min_nc)} zł)</h3>${breadthBar(L)}
      <p class="dim small">Wszystkie notowane: rośnie ${A.up}, spada ${A.down}, bez zmian ${A.flat}, bez handlu ${A.none}. Mediana zmiany płynnych: <b class="${L.median_change > 0 ? "up" : L.median_change < 0 ? "down" : ""}">${L.median_change == null ? "–" : (L.median_change > 0 ? "+" : "") + fmtNum(L.median_change, 2) + "%"}</b></p></div>
    <div class="kpi"><h3>Obrót płynnych spółek</h3>
      <div class="bbar"><i class="up" style="flex:${L.up_turnover || 0.0001}"></i><i class="down" style="flex:${L.down_turnover || 0.0001}"></i></div>
      <div class="blegend"><span><i class="up"></i>w rosnących <b>${fmtMoney(L.up_turnover)}</b> (${fmtNum(L.up_turnover / ut * 100, 0)}%)</span>
        <span><i class="down"></i>w spadających <b>${fmtMoney(L.down_turnover)}</b></span></div></div>
    <div class="kpi"><h3>Komunikaty od ${esc(d.since.slice(5).split(" ")[0].split("-").reverse().join("."))} ${esc(d.since.split(" ")[1] || "")}</h3>
      <div class="big">${d.espi.total}</div><p class="dim small">insiderzy i duzi akcjonariusze: <b>${ins}</b> · wezwania: <b>${c.wezwanie || 0}</b> · skup akcji: <b>${c.skup || 0}</b></p></div>
  </div>`;

  const w = d.watch;
  const watchHtml = !w
    ? `<p class="dim">Zaznacz swoje spółki w tabeli Spółki w kolumnie Tak/Nie (np. „Mam”, utwórz ją przyciskiem „Dodaj kolumnę”) albo w kolumnie listy, a potem wybierz ją wyżej w polu „Moje spółki z kolumny”.</p>`
    : !w.rows.length ? `<p class="dim">${w.key.startsWith("__portfolio") ? "Portfel jest pusty." : `W kolumnie „${esc(w.label)}” nie zaznaczono jeszcze żadnej spółki.`}</p>`
    : `<table class="stable"><thead><tr><th>Spółka</th><th class="n">Kurs</th><th class="n">Zmiana</th><th class="n">Obrót</th><th class="n">× śr.</th><th>Co się dzieje</th></tr></thead><tbody>
      ${w.rows.map((x) => `<tr><td><a class="tk" href="#" data-t="${esc(x.ticker)}">${esc(x.ticker)}</a> <span class="dim nm">${esc(x.name)}</span></td>
        <td class="n">${fmtNum(x.close, 2)}</td><td class="n">${chgCell(x)}</td><td class="n">${fmtMoney(x.turnover)}</td><td class="n">${ratioCell(x.ratio)}</td>
        <td>${sigList(x.signals)}</td></tr>`).join("")}</tbody></table>`;

  const winSeg = `<div class="seg sm" role="group" aria-label="Okno" id="sesWin">${[1, 5, 20].map((n) =>
      `<button data-ses="${n}" aria-pressed="${n === d.insider_sessions}">${n === 1 ? "od ostatniej sesji" : n + " sesji"}</button>`).join("")}</div>`;
  const series = d.series.length ? `<table class="stable"><thead><tr><th>Spółka</th><th class="n">Kupna</th><th class="n">Sprzedaże</th>
      <th class="n">Osób</th><th class="n">Saldo akcji</th><th class="n">Saldo wartości</th><th class="n">Kurs dziś</th><th>Ostatnie</th></tr></thead><tbody>
      ${d.series.map((g) => `<tr><td>${tk(g.ticker)} <span class="dim nm">${esc(g.name || "")}</span>${g.buys >= 3 && !g.sells ? ` <span class="sig up" title="Co najmniej 3 zakupy bez sprzedaży w oknie">seria zakupów</span>` : ""}${g.sells >= 3 && !g.buys ? ` <span class="sig down" title="Co najmniej 3 sprzedaże bez zakupów w oknie">seria sprzedaży</span>` : ""}</td>
        <td class="n up">${g.buys || ""}</td><td class="n down">${g.sells || ""}</td><td class="n">${g.people}</td>
        <td class="n ${g.net > 0 ? "up" : g.net < 0 ? "down" : ""}">${g.net > 0 ? "+" : ""}${fmtNum(g.net, 0)}</td>
        <td class="n">${signedMoney(g.value || null)}${g.unpriced ? ` <span class="dim" title="Część transakcji bez ceny">*</span>` : ""}</td>
        <td class="n">${g.chg == null ? "" : signed(g.chg)}</td><td class="dim">${esc(dd(g.last.slice(0, 10)))}</td></tr>`).join("")}</tbody></table>`
    : `<p class="dim">Brak zawiadomień w tym oknie.</p>`;
  const holders = d.holders.length ? `<details ${d.insider_sessions === 1 ? "open" : ""}><summary>Pojedyncze zawiadomienia (${d.holders.length})</summary><table class="stable"><thead><tr><th>Publikacja</th><th>Spółka</th><th>Kto</th><th>Rodzaj</th>
      <th class="n">Akcje</th><th class="n">Wartość</th><th class="n">Kurs dziś</th></tr></thead><tbody>
      ${d.holders.map((h) => `<tr class="${h.transfer ? "muted-row" : ""}"><td class="dim n">${esc(h.ts.slice(8, 10) + "." + h.ts.slice(5, 7) + " " + h.ts.slice(11, 16))}</td>
        <td><a class="tk" href="#" data-t="${esc(h.ticker)}">${esc(h.ticker)}</a></td>
        <td>${esc(h.investor)}${h.transfer ? ` <span class="sig info" title="Kupno i sprzedaż w tej spółce się znoszą – przesunięcie między powiązanymi podmiotami">przesunięcie</span>` : ""}</td>
        <td><span class="tag ${h.source}">${h.source === "mar" ? "insider (MAR)" : "art. 69"}</span></td>
        <td class="n ${h.delta > 0 ? "up" : "down"}">${h.delta > 0 ? "+" : ""}${fmtNum(h.delta, 0)}</td>
        <td class="n">${h.value == null ? `<span class="dim">–</span>` : fmtMoney(h.value)}</td>
        <td class="n">${h.chg == null ? "" : `<span class="${h.chg > 0 ? "up" : h.chg < 0 ? "down" : ""}">${h.chg > 0 ? "+" : ""}${fmtNum(h.chg, 2)}%</span>`}</td></tr>`).join("")}
      </tbody></table></details>` : "";

  const imp = d.espi.important.length ? `<ul class="esp">${d.espi.important.map((e) =>
      `<li><span class="tag ${e.category}">${{ wezwanie: "wezwanie", skup: "skup akcji", wz_lista: "akcjonariusze na WZ" }[e.category] || e.category}</span>
       ${e.ticker ? `<a class="tk" href="#" data-t="${esc(e.ticker)}">${esc(e.ticker)}</a>` : ""} ${esc(e.title)} <span class="dim">${esc(e.ts.slice(11, 16))}</span></li>`).join("")}</ul>`
    : `<p class="dim">Brak.</p>`;

  $("#sesBody").innerHTML = `${kpi}
    <div class="scard"><h2>Moje spółki${w ? ` <span class="dim">– ${w.key.startsWith("__portfolio") ? (w.key === "__portfolio" ? "wszystkie portfele" : `portfel „${esc(w.label)}”`) : `kolumna „${esc(w.label)}”`}</span>` : ""}</h2>${watchHtml}</div>
    ${marketCard(mktData)}
    <div class="scols">
      <div class="scard"><h2>Najmocniej rosną</h2>${moversTable(d.gainers, "Żadna płynna spółka nie rośnie.")}</div>
      <div class="scard"><h2>Najmocniej spadają</h2>${moversTable(d.losers, "Żadna płynna spółka nie spada.")}</div>
    </div>
    ${shortTermCard(d)}
    ${calendarCard(calData, 14)}
    <div class="scard"><h2>Nie dotykaj bez sprawdzenia <span class="dim">– ostrzeżenia wśród płynnych spółek</span></h2>
      ${d.warned.length ? moversTable(d.warned, "") : `<p class="dim">Brak płynnych spółek z ostrzeżeniami.</p>`}
      <p class="dim small">Emisja akcji, sprzedaż dużych akcjonariuszy lub insiderów po wzroście, brak lub opóźnienie raportu. Wszystkie spółki z ostrzeżeniami (także NewConnect ze skrajnymi wskaźnikami) – kolumna „Ostrzeżenia” w tabeli Spółki.</p></div>
    <div class="scard"><h2>Skoki obrotu <span class="dim">– co najmniej 2× średniej z 20 sesji</span></h2>${moversTable(d.spikes, "Brak spółek z wyraźnie wyższym obrotem.")}</div>
    <div class="scard"><div class="scard-head"><h2>Insiderzy i duzi akcjonariusze <span class="dim">– suma na spółkę w oknie</span></h2>${winSeg}</div>
      <p class="dim small">Zakupy zarządu działają z opóźnieniem i liczy się ich seria – w dłuższym oknie widać, kto kupuje regularnie.</p>${series}${holders}</div>
    ${d.exdiv.length ? `<div class="scard"><h2>Dzień odcięcia dywidendy</h2><p class="dim small">Kurs spada o wartość dywidendy, bo kupujący dziś już jej nie dostaną – w zestawieniach liczymy zmianę po jej doliczeniu.</p>${moversTable(d.exdiv, "")}</div>` : ""}
    <div class="scard"><h2>Wezwania, skup akcji, listy akcjonariuszy z walnych</h2>${imp}</div>`;
}

/* kalendarz */
let calData = null;
const CAL_KIND = { dywidenda: ["dywidenda", "up"], wyplata: ["wypłata", "up"], raport: ["raport", "info"], raport_termin: ["termin raportów", "info"],
  wz: ["walne", "info"], wezwanie: ["wezwanie", "warn"], rpp: ["RPP", "warn"], cpi: ["inflacja", "warn"] };
const DOW = ["nd", "pn", "wt", "śr", "cz", "pt", "sb"];
function calendarCard(c, days, opts = {}) {
  if (!c) return "";
  const ev = c.events.filter((e) => !opts.onlyHeld || e.held);
  const byDay = {};
  ev.forEach((e) => (byDay[e.date] ||= []).push(e));
  const body = Object.keys(byDay).length ? `<table class="stable cal"><tbody>${Object.entries(byDay).map(([d, es]) => `<tr>
      <td class="cal-d"><b>${d.slice(8, 10)}.${d.slice(5, 7)}</b> <span class="dim">${DOW[new Date(d + "T12:00").getDay()]}</span></td>
      <td>${es.map((e) => `<div class="cal-e ${e.held ? "held" : ""}" title="${esc([e.detail, e.source && "Źródło: " + e.source].filter(Boolean).join("\n"))}">
        <span class="sig ${CAL_KIND[e.kind]?.[1] || ""}">${CAL_KIND[e.kind]?.[0] || e.kind}</span>
        ${e.ticker ? tk(e.ticker) + ` <span class="dim nm">${esc(e.name || "")}</span>` : ""} ${esc(e.title)}${e.held ? ` <span class="pf-tag">w portfelu</span>` : ""}</div>`).join("")}</td></tr>`).join("")}</tbody></table>`
    : `<p class="dim">${opts.onlyHeld ? "Brak wydarzeń Twoich spółek w tym okresie." : "Brak wydarzeń."}</p>`;
  return `<div class="scard"><h2>${opts.title || `Kalendarz – ${days} dni`} <span class="dim">– ${dd(c.from)}–${dd(c.to)}</span></h2>${body}
    ${opts.onlyHeld ? "" : `<p class="dim small">Raporty okresowe z harmonogramów spółek (${c.schedules} spółek z harmonogramem) i ustawowe terminy; walne zgromadzenia i zapisy w wezwaniach z komunikatów; RPP z harmonogramu NBP${c.rpp_year_known ? "" : " (brak harmonogramu na ten rok – do uzupełnienia)"}; inflacja GUS orientacyjnie. Twoje spółki są wyróżnione.</p>`}</div>`;
}

/* sygnały krótkoterminowe (dni–tygodnie) */
const TAG_LABEL = { umowa: "umowa / kontrakt", wyniki: "wyniki szacunkowe", skup: "skup akcji", wezwanie: "wezwanie", emisja: "emisja akcji", dywidenda: "dywidenda", wz: "walne zgromadzenie" };
let sesTag = "";
function shortTermCard(d) {
  const gapCell = (x) => x.gap ? `<span class="${x.gap.dir === "up" ? "up" : "down"}">${x.gap.size > 0 ? "+" : ""}${fmtNum(x.gap.size, 1)}%</span> <span class="dim">${x.gap.filled ? "domknięta" : "niedomknięta"}</span>` : "";
  const gaps = d.gaps.length ? `<table class="stable"><thead><tr><th>Spółka</th><th class="n">Luka</th><th class="n">Zmiana</th><th class="n">× śr.</th></tr></thead><tbody>
      ${d.gaps.map((x) => `<tr><td>${tk(x.ticker)} <span class="dim nm">${esc(x.name)}</span></td><td class="n">${gapCell(x)}</td><td class="n">${chgCell(x)}</td><td class="n">${ratioCell(x.ratio)}</td></tr>`).join("")}</tbody></table>`
    : `<p class="dim">Brak luk co najmniej 1% wśród płynnych spółek.</p>`;
  const wig = d.wig_chg;
  const rsTitle = wig == null ? "Siła względna wobec WIG" : wig <= -0.5 ? `Rosną w spadkowy dzień (WIG ${fmtNum(wig, 2)}%)` : wig >= 0.5 ? `Najsłabsze w rosnący dzień (WIG +${fmtNum(wig, 2)}%)` : `Siła względna wobec WIG (WIG ${wig > 0 ? "+" : ""}${fmtNum(wig, 2)}%)`;
  const rsList = wig != null && wig >= 0.5 ? d.rs_bottom : d.rs_top;
  const rs = rsList.length ? `<table class="stable"><thead><tr><th>Spółka</th><th class="n">Zmiana</th><th class="n" title="Zmiana kursu minus zmiana WIG">vs WIG</th><th class="n">Obrót</th></tr></thead><tbody>
      ${rsList.map((x) => `<tr><td>${tk(x.ticker)} <span class="dim nm">${esc(x.name)}</span></td><td class="n">${chgCell(x)}</td><td class="n">${signed(x.rs_day, 1, " pp")}</td><td class="n">${fmtMoney(x.turnover)}</td></tr>`).join("")}</tbody></table>` : `<p class="dim">Brak danych WIG z dzisiejszej sesji.</p>`;
  const tags = d.espi.tagged.filter((e) => !sesTag || e.tags.includes(sesTag));
  const tagSeg = `<div class="seg sm" role="group" aria-label="Rodzaj komunikatu" id="sesTags"><button data-tag="" aria-pressed="${!sesTag}">wszystkie</button>${Object.entries(TAG_LABEL).filter(([k]) => d.espi.tagged.some((e) => e.tags.includes(k))).map(([k, l]) => `<button data-tag="${k}" aria-pressed="${sesTag === k}">${l}</button>`).join("")}</div>`;
  const espiList = tags.length ? `<ul class="esp">${tags.map((e) => `<li>${e.tags.map((t) => `<span class="tag kw-${t}">${TAG_LABEL[t]}</span>`).join(" ")}
      ${e.ticker ? tk(e.ticker) : ""} ${esc(e.title)} <span class="dim">${esc(e.ts.slice(11, 16))}</span>${e.chg == null ? "" : ` · ${signed(e.chg)}`}</li>`).join("")}</ul>` : `<p class="dim">Brak komunikatów z tymi słowami kluczowymi.</p>`;
  return `<div class="scard"><h2>Sygnały krótkoterminowe <span class="dim">– dni–tygodnie, wśród płynnych spółek</span></h2>
      <h3 class="sub" title="${esc(SIG_HELP.breakout)}">Wybicia do nowych maksimów przy obrocie ≥2×</h3>${moversTable(d.breakouts, "Dziś brak wybić przy wysokim obrocie.")}
      <div class="mcols"><div><h3 class="sub" title="${esc(SIG_HELP.gap_up)}">Luki cenowe</h3>${gaps}</div>
        <div><h3 class="sub" title="${esc(SIG_HELP.rs)}">${rsTitle}</h3>${rs}</div></div>
      <div class="scard-head"><h3 class="sub">Komunikaty ze słowami kluczowymi <span class="dim">– od ${esc(d.since.slice(11))} ${esc(dd(d.since.slice(0, 10)))}</span></h3>${tagSeg}</div>${espiList}</div>`;
}

/* ---------- trendy (średni termin) ---------- */
let trPref = { min: 100000, min_nc: 30000, trend: true, days: 365 };
try { trPref = { ...trPref, ...JSON.parse(localStorage.getItem("gpwt_trends") || "{}") }; } catch { /* brak pamięci */ }
async function loadTrends() {
  $("#trMin").value = String(trPref.min); $("#trMinNc").value = String(trPref.min_nc);
  $("#trTrend").checked = trPref.trend; $("#trDays").value = String(trPref.days);
  loadMarket().then((m) => renderMarketStrip($("#trMarket"), m)).catch(() => {});
  const d = await api(`/api/trends?${new URLSearchParams({ min: trPref.min, min_nc: trPref.min_nc, trend: trPref.trend ? 1 : 0, days: trPref.days })}`);
  $("#trAsOf").textContent = d.date ? `sesja ${dd(d.date)} · historia ${d.sessions} sesji` : "";
  const W = d.wig;
  const mom = d.momentum.length ? `<table class="stable"><thead><tr><th>#</th><th>Spółka</th><th>Sektor</th><th class="n">Momentum</th><th class="n">3 mies.</th><th class="n">6 mies.</th>
      <th class="n" title="3 miesiące minus WIG">vs WIG 3 mies.</th><th class="n">vs SMA200</th><th class="n">1 mies.</th><th></th></tr></thead><tbody>
      ${d.momentum.map((x, i) => `<tr><td class="dim">${i + 1}</td><td>${tk(x.ticker)} <span class="dim nm">${esc(x.name)}</span></td><td class="dim">${esc(x.sector || "")}</td>
        <td class="n"><b>${signed(x.mom, 1)}</b></td><td class="n">${signed(x.ret_3m, 1)}</td><td class="n">${signed(x.ret_6m, 1)}</td>
        <td class="n">${signed(x.rs_3m, 1, " pp")}</td><td class="n">${signed(x.vs200, 1)}</td><td class="n">${signed(x.ret_1m, 1)}</td>
        <td>${x.new_high52 ? `<span class="sig up">maks. 52 tyg.</span>` : ""}${x.ret_1m != null && x.ret_1m < -10 ? ` <span class="sig warn" title="Ostatni miesiąc słaby mimo dobrego 3–6 mies.">słabnie</span>` : ""}</td></tr>`).join("")}</tbody></table>
      <p class="dim small">${d.n_momentum} spółek spełnia warunki${d.trend_only ? " (SMA50 nad SMA200 i kurs nad SMA200)" : ""}. Momentum = średnia zmiana z 3 i 6 miesięcy. WIG w tym czasie: 3 mies. ${signed(W.ret_3m, 1)}, 6 mies. ${signed(W.ret_6m, 1)}. Badania pokazują, że momentum z 3–12 miesięcy ma tendencję do utrzymywania się, ale gwałtownie odwraca się w okresach paniki.</p>`
    : `<p class="dim">Za krótka historia notowań albo żadna spółka nie spełnia warunków.</p>`;
  const sec = d.sectors.length ? `<table class="stable"><thead><tr><th>Sektor</th><th class="n">Spółek</th><th class="n">1 mies.</th><th class="n">vs WIG 1 mies.</th>
      <th class="n">3 mies.</th><th class="n">vs WIG 3 mies.</th><th class="n" title="Odsetek spółek sektora nad średnią z 200 sesji">nad SMA200</th><th>Liderzy miesiąca</th></tr></thead><tbody>
      ${d.sectors.map((r) => `<tr><td>${esc(r.sector)}</td><td class="n">${r.n}</td><td class="n">${signed(r.ret_1m, 1)}</td><td class="n"><b>${signed(r.rs_1m, 1, " pp")}</b></td>
        <td class="n">${signed(r.ret_3m, 1)}</td><td class="n">${signed(r.rs_3m, 1, " pp")}</td><td class="n">${r.above200 == null ? "" : fmtNum(r.above200, 0) + "%"}</td>
        <td>${r.leaders.map(tk).join(" ")}</td></tr>`).join("")}</tbody></table>
      <p class="dim small">Zmiany ważone kapitalizacją spółek z obrotem od 20 tys. zł; sektory z co najmniej 3 spółkami. WIG: 1 mies. ${signed(W.ret_1m, 1)}, 3 mies. ${signed(W.ret_3m, 1)}.</p>` : "";
  const fundTable = (rows) => rows.length ? `<table class="stable"><thead><tr><th>Spółka</th><th class="n" title="Liczba funduszy, które zwiększyły udział">Zwiększyło</th><th class="n">Zmniejszyło</th>
      <th class="n">Saldo</th><th class="n" title="Saldo jako % kapitalizacji">% kap.</th><th class="n">3 mies.</th><th>Trend</th><th>Ostatnia zmiana</th></tr></thead><tbody>
      ${rows.map((r) => `<tr><td>${tk(r.ticker)} <span class="dim nm">${esc(r.name || "")}</span></td><td class="n up">${r.funds_up || ""}</td><td class="n down">${r.funds_down || ""}</td>
        <td class="n">${signedMoney(r.value || null)}${r.unpriced ? ` <span class="dim" title="Część zmian bez wyceny">*</span>` : ""}</td><td class="n">${r.value_pct_mcap == null ? "" : signed(r.value_pct_mcap, 2)}</td>
        <td class="n">${signed(r.ret_3m, 1)}</td><td>${r.trend == null ? "" : r.trend ? `<span class="up">▲</span>` : `<span class="down">▼</span>`}</td><td class="dim">${dd(r.last)}</td></tr>`).join("")}</tbody></table>` : `<p class="dim">Brak.</p>`;
  const qual = d.quality && d.quality.length ? `<table class="stable"><thead><tr><th>#</th><th>Spółka</th><th>Sektor</th><th class="n" title="${esc(QUAL_DESC)}">Jakość</th>
      <th class="n">F-Score</th><th class="n">ROE</th><th class="n" title="Najniższe ROE z ostatnich lat">ROE min.</th><th class="n">Dług/EBITDA</th>
      <th class="n">FCF+ lat</th><th class="n">Dywidenda lat</th><th class="n">C/Z vs 5 lat</th><th class="n">Zysk r/r</th><th>Trend</th></tr></thead><tbody>
      ${d.quality.map((r, i) => `<tr><td class="dim">${i + 1}</td><td>${tk(r.ticker)} <span class="dim nm">${esc(r.name || "")}</span></td><td class="dim">${esc(r.sector || "")}</td>
        <td class="n" title="${esc((r.quality_parts || []).map((p) => `${p.name}: ${fmtNum(p.points, 0)}/${p.of} (${p.text})`).join("\n"))}"><span class="qbadge ${r.quality >= 70 ? "good" : r.quality >= 45 ? "mid" : "bad"}">${r.quality}</span></td>
        <td class="n">${r.fscore == null ? "–" : r.fscore + "/9"}</td><td class="n">${r.roe == null ? "–" : fmtNum(r.roe, 1) + "%"}</td>
        <td class="n">${r.roe_min5 == null ? "–" : fmtNum(r.roe_min5, 1) + "%"}</td>
        <td class="n">${r.bank ? `<span class="dim">bank</span>` : r.net_cash ? `<span class="up">gotówka</span>` : r.nd_ebitda == null ? "–" : fmtNum(r.nd_ebitda, 1)}</td>
        <td class="n">${r.fcf_years ? `${r.fcf_pos_years}/${r.fcf_years}` : "–"}</td><td class="n">${r.div_streak || ""}</td>
        <td class="n">${r.cz_vs_med == null ? "–" : signed(r.cz_vs_med, 0)}</td><td class="n">${signed(r.np_ttm_yoy, 0)}</td>
        <td>${r.trend == null ? "" : r.trend ? `<span class="up">▲</span>` : `<span class="down">▼</span>`}</td></tr>`).join("")}</tbody></table>
      <p class="dim small">${d.n_quality} płynnych spółek ma ocenę. ${esc(QUAL_DESC)} Najedź na ocenę, żeby zobaczyć punkty.</p>`
    : `<p class="dim">Brak ocen jakości – sprawozdania finansowe pobierają się raz w tygodniu.</p>`;
  $("#trBody").innerHTML = `<div class="scard"><h2>Jakość biznesu <span class="dim">– długi termin (1–5 lat)</span></h2>${qual}</div>
    <div class="scard"><h2>Momentum 3–6 miesięcy ${d.trend_only ? `<span class="dim">– w trendzie wzrostowym</span>` : ""}</h2>${mom}</div>
    <div class="scard"><h2>Rotacja sektorowa <span class="dim">– kto od miesiąca wygrywa z WIG</span></h2>${sec}</div>
    <div class="mcols"><div class="scard"><h2>Fundusze zwiększają udziały</h2>${fundTable(d.funds_buy)}</div>
      <div class="scard"><h2>Fundusze zmniejszają udziały</h2>${fundTable(d.funds_sell)}</div></div>
    <p class="dim small">Fundusze: OFE (struktury portfeli co pół roku), TFI i inne fundusze z zawiadomień art. 69 i akcjonariatu, z wybranego okresu. Liczy się, ile różnych funduszy działa w tym samym kierunku.</p>`;
}
const saveTrPref = () => { try { localStorage.setItem("gpwt_trends", JSON.stringify(trPref)); } catch { /* brak pamięci */ } loadTrends(); };
$("#trMin").addEventListener("change", (e) => { trPref.min = +e.target.value; saveTrPref(); });
$("#trMinNc").addEventListener("change", (e) => { trPref.min_nc = +e.target.value; saveTrPref(); });
$("#trTrend").addEventListener("change", (e) => { trPref.trend = e.target.checked; saveTrPref(); });
$("#trDays").addEventListener("change", (e) => { trPref.days = +e.target.value; saveTrPref(); });

async function loadSession() {
  const p = await api("/api/settings/session");
  if (p) sesPref = { ...sesPref, ...p };
  $("#sesMin").value = String(sesPref.min);
  $("#sesMinNc").value = String(sesPref.min_nc);
  $$("#sesMkt button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.smkt === sesPref.market)));
  await refreshSession();
  clearInterval(sesTimer);
  sesTimer = setInterval(() => { if (current === "session" && !document.hidden) refreshSession(); }, 5 * 60 * 1000);
}
async function refreshSession() {
  const q = new URLSearchParams({ min: sesPref.min, min_nc: sesPref.min_nc, market: sesPref.market,
    watch: sesPref.watch || "", sessions: sesPref.sessions });
  const d = await api(`/api/session?${q}`);
  $("#sesWatch").innerHTML = `<option value="">${d.has_portfolio ? "Wszystkie portfele" : "– wybierz –"}</option>`
    + (d.portfolios.length > 1 ? d.portfolios.map((p) => `<option value="__portfolio:${p.id}">Portfel: ${esc(p.name)}</option>`).join("") : "")
    + d.watch_columns.map((c) =>
    `<option value="${esc(c.key)}">${esc(c.label)}</option>`).join("");
  $("#sesWatch").value = sesPref.watch || "";
  try { await loadMarket(); renderMarketStrip($("#sesMarket"), mktData); } catch { /* kontekst rynku niedostępny */ }
  try { calData = await api("/api/calendar?days=14"); } catch { calData = null; }
  renderSession(d);
}
const saveSesPref = () => { api("/api/settings/session", { method: "PUT", body: sesPref }).catch(() => {}); refreshSession(); };
$("#sesMin").addEventListener("change", (e) => { sesPref.min = +e.target.value; saveSesPref(); });
$("#sesMinNc").addEventListener("change", (e) => { sesPref.min_nc = +e.target.value; saveSesPref(); });
$("#sesBody").addEventListener("click", (e) => {
  const tg = e.target.closest("#sesTags button");
  if (tg) { sesTag = tg.dataset.tag; refreshSession(); return; }
  const b = e.target.closest("#sesWin button"); if (!b) return;
  sesPref.sessions = +b.dataset.ses; saveSesPref();
});
$("#sesWatch").addEventListener("change", (e) => { sesPref.watch = e.target.value; saveSesPref(); });
$$("#sesMkt button").forEach((b) => b.addEventListener("click", () => {
  sesPref.market = b.dataset.smkt;
  $$("#sesMkt button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  saveSesPref();
}));
$("#sesRefresh").addEventListener("click", async () => {
  const r = await api("/api/collect", { method: "POST", body: { quick: true } });
  toast(r.started ? "Pobieram notowania i nowe komunikaty – ok. minuty" : r.msg);
  pollStatus();
});

/* ---------- nawigacja ---------- */
const loaders = { portfolio: loadPortfolio, session: loadSession, trends: loadTrends, companies: loadCompanies, investors: loadInvestors, changes: loadChanges, espi: loadEspi, settings: loadSettings };
const loaded = {};
let current = "portfolio";
function showView(v) {
  current = v;
  $$(".rail [data-view]").forEach((b) => b.dataset.view === v ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current"));
  $$("main > section").forEach((s) => { s.hidden = s.id !== `view-${v}`; });
  if (!loaded[v]) { loaded[v] = true; loaders[v]().catch((e) => toast("Błąd: " + e.message)); }
  else if (v === "settings") loadSettings();
  else if (v === "session") refreshSession().catch(() => {});
  else if (v === "portfolio") loadPortfolio().catch(() => {});
  history.replaceState(null, "", `#${v}`);
}
function refreshCurrent() { Object.keys(loaded).forEach((k) => delete loaded[k]); showView(current); }
$$(".rail [data-view]").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));
const startView = location.hash.slice(1);
showView(startView in loaders ? startView : "portfolio");
api("/api/status").then((s) => { updateFoot(s); if (s.job_running) pollStatus(); }).catch(() => {});
