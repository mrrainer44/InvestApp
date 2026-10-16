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
  div: "Dywidendy", own: "Akcjonariat i przepływy", custom: "Moje kolumny",
};
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
  const latestDate = {};
  d.holders.filter((h) => h.source === "BR").forEach((h) => { if (!latestDate[h.holder_norm] || h.date_upd > latestDate[h.holder_norm]) latestDate[h.holder_norm] = h.date_upd; });
  const cur = d.holders.filter((h) => h.source === "BR" && latestDate[h.holder_norm] === h.date_upd).sort((a, b) => (b.pct || 0) - (a.pct || 0));
  $("#drawerBody").innerHTML = `
    <h2>${esc(c.ticker)} · ${esc(c.full_name || c.short_name)}</h2>
    <div class="dim">${esc(c.market === "NC" ? "NewConnect" : "GPW")}${c.sector ? " · " + esc(c.sector) : ""}${c.isin ? " · " + esc(c.isin) : ""}
      · <a href="https://www.biznesradar.pl/notowania/${encodeURIComponent(c.slug)}" target="_blank" rel="noopener">profil w Biznesradar</a></div>
    <div class="facts">
      <div><b>${fmtNum(row.price)}</b><span>Kurs</span></div>
      <div><b>${fmtMoney(row.mcap)}</b><span>Kapitalizacja</span></div>
      <div><b>${row.cz == null ? "–" : fmtNum(row.cz, 1)}</b><span>C/Z</span></div>
      <div><b>${row.cwk == null ? "–" : fmtNum(row.cwk, 1)}</b><span>C/WK</span></div>
      <div><b>${row.div_yield == null ? "–" : fmtNum(row.div_yield, 2) + "%"}</b><span>Stopa dywidendy</span></div>
      <div><b>${row.flow_30d == null ? "–" : fmtMoney(row.flow_30d)}</b><span>Przepływ 30 dni</span></div>
    </div>
    ${sparkline(d.prices)}
    <h3>Akcjonariat (ostatni odczyt)</h3>
    ${cur.length ? `<table><tr><th>Akcjonariusz</th><th class="n">Udział</th><th class="n">Akcje</th><th>Stan na</th></tr>
      ${cur.map((h) => `<tr><td>${esc(h.holder)}</td><td class="n">${fmtNum(h.pct, 2)}%</td><td class="n">${fmtNum(h.shares, 0)}</td><td>${esc(h.date_upd)}</td></tr>`).join("")}</table>`
      : `<p class="dim">Akcjonariat pobiera się raz w tygodniu.</p>`}
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
      <td><a href="https://www.biznesradar.pl${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a></td></tr>`).join("")}</table>` : `<p class="dim">Brak komunikatów w bazie.</p>`}`;
  $("#drawer").classList.add("open"); $("#drawer").setAttribute("aria-hidden", "false");
}

/* ---------- inwestorzy ---------- */
const SOURCES = { art69: "Zawiadomienia art. 69", mar: "Insiderzy (MAR)", fundusze: "Portfele OFE/TFI", akcjonariat: "Główni akcjonariusze", wz: "Walne zgromadzenia" };
const DEFAULT_SOURCES = ["art69", "mar", "fundusze", "akcjonariat"];
let period = "week", tblInv;
$("#srcChips").innerHTML = Object.entries(SOURCES).map(([k, v]) => `<label class="chip"><input type="checkbox" value="${k}" ${DEFAULT_SOURCES.includes(k) ? "checked" : ""}>${v}</label>`).join("");
const d90 = new Date(Date.now() - 90 * 864e5).toISOString().slice(0, 10);
$("#invFrom").value = d90;

async function loadInvestors() {
  const src = $$("#srcChips input:checked").map((i) => i.value).join(",");
  const qs = new URLSearchParams({ period, sources: src, from: $("#invFrom").value, to: $("#invTo").value });
  const data = await api(`/api/flows?${qs}`);
  const scale = data.map((d) => Math.abs(d.net)).sort((a, b) => b - a)[Math.min(3, data.length - 1)] || 1;
  const cols = [
    { field: "period", title: period === "week" ? "Tydzień" : "Miesiąc", width: 100, headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true } },
    { field: "investor", title: "Inwestor", width: 300, formatter: (c) => `<a href="#" class="inv">${esc(c.getValue())}</a>` },
    { field: "net", title: "Saldo (kupno − sprzedaż)", width: 240, formatter: (c) => flowBar(c.getValue(), scale), sorter: numSort },
    { field: "buy", title: "Kupno", hozAlign: "right", formatter: money, sorter: numSort },
    { field: "sell", title: "Sprzedaż", hozAlign: "right", formatter: money, sorter: numSort },
    { field: "n", title: "Zmian", hozAlign: "right" },
    { field: "tickers", title: "Spółki", width: 220, tooltip: true, formatter: (c) => esc(c.getValue()).split(", ").map((t) => `<a class="tk" href="#" data-t="${t}">${t}</a>`).join(" ") },
    { field: "sources", title: "Źródła" },
    { field: "unpriced", title: "Bez wyceny", hozAlign: "right", headerTooltip: "Zmiany, dla których nie znaleziono kursu – nie są wliczone do kwot" },
  ];
  if (tblInv) tblInv.destroy();
  tblInv = new Tabulator("#tblInvestors", { data, columns: cols, layout: "fitData", height: "calc(100vh - 190px)",
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
    placeholder: "Brak zmian. Pojawią się po pierwszym pobraniu komunikatów i akcjonariatu.",
    columns: [
      { field: "date", title: "Data", editor: "input", width: 100 },
      { field: "ticker", title: "Ticker", formatter: tickerFmt, width: 80 },
      { field: "investor", title: "Inwestor", editor: "input", width: 260, tooltip: true },
      { field: "shares_before", title: "Akcje przed", ...intEd },
      { field: "shares_after", title: "Akcje po", ...intEd },
      { field: "delta", title: "Zmiana", ...intEd, formatter: (c) => { const v = c.getValue(); return v == null ? "" : `<span class="${v > 0 ? "up" : "down"}">${v > 0 ? "+" : ""}${fmtNum(v, 0)}</span>`; } },
      { field: "price", title: "Cena", editor: "number", hozAlign: "right", formatter: num2, sorter: numSort },
      { field: "value", title: "Wartość", hozAlign: "right", formatter: money, sorter: numSort },
      { field: "source", title: "Źródło", formatter: (c) => `<span class="tag ${c.getValue()}">${esc(SOURCES[c.getValue()] || c.getValue())}</span>` },
      { field: "verified", title: "Sprawdzone", editor: "tickCross", formatter: "tickCross", hozAlign: "center", width: 100 },
      { field: "excluded", title: "Wyklucz z sum", editor: "tickCross", formatter: "tickCross", hozAlign: "center", width: 110 },
      { field: "note", title: "Uwagi", editor: "input", width: 240, tooltip: true },
      { field: "espi_id", title: "Raport", formatter: (c) => { const id = Math.floor((c.getValue() || 0) / 10);
        return id ? `<a href="https://www.biznesradar.pl/a/${id}" target="_blank" rel="noopener">otwórz</a>` : ""; } },
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
$("#chClear").addEventListener("click", () => { $("#chQ").value = ""; $("#chSrc").value = ""; $("#chUnverified").checked = false; filterChanges(); });

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
    placeholder: "Brak komunikatów w tym zakresie.",
    columns: [
      { field: "ts", title: "Czas", width: 140 },
      { field: "ticker", title: "Ticker", formatter: (c) => c.getValue() ? tickerFmt(c) : `<span class="dim" title="Kliknij, aby przypisać ticker">przypisz</span>`, editor: "input", width: 90 },
      { field: "category", title: "Rodzaj", formatter: (c) => `<span class="tag ${c.getValue()}">${esc(catLabel[c.getValue()] || c.getValue())}</span>`, width: 130 },
      { field: "title", title: "Tytuł", width: 520, formatter: (c) => `<a href="https://www.biznesradar.pl${esc(c.getRow().getData().url)}" target="_blank" rel="noopener">${esc(c.getValue())}</a>`, tooltip: true },
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
  $("#runState").textContent = s.job_running ? "Pobieranie trwa…" : "";
  const runs = s.runs.map((r) => ({ ...r, summaryText: summarize(r.summary) }));
  if (tblRuns) tblRuns.destroy();
  tblRuns = new Tabulator("#tblRuns", { data: runs, layout: "fitData", maxHeight: 300, placeholder: "Jeszcze nic nie pobrano.",
    columns: [{ field: "started", title: "Start" }, { field: "finished", title: "Koniec" }, { field: "kind", title: "Rodzaj", formatter: (c) => c.getValue() === "weekly" ? "pełne" : "dzienne" },
      { field: "status", title: "Wynik", formatter: (c) => c.getValue() === "ok" ? `<span class="up">udane</span>` : c.getValue() === "error" ? `<span class="down">błąd</span>` : "w toku" },
      { field: "summaryText", title: "Podsumowanie", width: 640, tooltip: true }] });
  const inv = await api("/api/investors");
  if (tblAl) tblAl.destroy();
  tblAl = new Tabulator("#tblAliases", { data: inv, index: "investor_norm", layout: "fitData", maxHeight: 420, placeholder: "Inwestorzy pojawią się po pierwszych zmianach.",
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
