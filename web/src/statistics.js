const headers = { "X-IDS-JMK-Client": "web" };
const number = (v) => new Intl.NumberFormat("cs-CZ").format(v || 0);
function bytes(v) {
  if (!v) return "0 B";
  const units = ["B", "kB", "MB", "GB", "TB"];
  const i = Math.min(4, Math.floor(Math.log(v) / Math.log(1000)));
  return `${new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 1 }).format(v / 1000 ** i)} ${units[i]}`;
}
const stamp = (v) =>
  v
    ? new Date(v).toLocaleString("cs-CZ", {
        timeZone: "Europe/Prague",
        hour12: false,
      })
    : "Zatím nestaženo";
const el = (tag, text, cls) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
};
const sourceNames = {
  gtfs: "Jízdní řády GTFS",
  realtime: "Realtime",
  api: "Externí požadavky API",
};
const pragueDay = () =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Prague" }).format(
    new Date(),
  );

export function setupStatistics() {
  const summary = document.getElementById("source-summary");
  const dialog = document.getElementById("statistics-dialog");
  const period = document.getElementById("stats-period");
  const date = document.getElementById("stats-date");
  const metric = document.getElementById("stats-metric");
  const content = document.getElementById("stats-content");
  const notice = document.getElementById("stats-notice");
  let data,
    sequence = 0,
    loading = false;
  date.value = pragueDay();

  function sourceSummary(sources) {
    summary.replaceChildren();
    for (const key of ["gtfs", "realtime"]) {
      const source = sources[key];
      const part = el("div");
      part.append(
        el("strong", sourceNames[key]),
        el("span", `Staženo: ${stamp(source.last_downloaded_at)}`),
      );
      part.append(
        el(
          "small",
          source.enabled
            ? source.last_error
              ? "Poslední kontrola selhala"
              : source.last_checked_at
                ? `Kontrola: ${stamp(source.last_checked_at)}`
                : "Čeká na první kontrolu"
            : "Stahování vypnuto",
        ),
      );
      summary.append(part);
    }
  }
  async function status() {
    if (document.hidden || dialog.open) return;
    try {
      const response = await fetch("/api/v1/status", {
        headers,
        cache: "no-store",
        signal: AbortSignal.timeout(15000),
      });
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (result.downloads) sourceSummary(result.downloads);
      else
        summary.textContent =
          "Pro přehled stahování aktualizujte server IDS JMK.";
    } catch {
      summary.textContent = "Přehled stahování nyní není dostupný.";
    }
  }
  function render() {
    if (!data) return;
    const expanded = new Set(
      [...content.querySelectorAll("details[open]")].map(
        (node) => node.dataset.section,
      ),
    );
    const scrollTop = dialog.scrollTop;
    content.replaceChildren();
    const start = new Date(data.start);
    const range = start.toLocaleDateString("cs-CZ", {
      timeZone: "Europe/Prague",
      year: "numeric",
      ...(data.period !== "year" ? { month: "long" } : {}),
      ...(data.period === "day" ? { day: "numeric" } : {}),
    });
    document.getElementById("stats-range").textContent = range;
    document.getElementById("stats-since").textContent =
      `Měření od ${stamp(data.tracking_since)} · Europe/Prague · obnoveno ${stamp(data.generated_at)}`;
    sourceSummary(data.sources);
    for (const source of ["gtfs", "realtime", "api"]) {
      const panel = el("section", undefined, "stats-panel");
      const head = el("div", undefined, "stats-panel-heading");
      head.append(el("h3", sourceNames[source]));
      if (source !== "api")
        head.append(
          el(
            "span",
            data.sources[source].enabled ? "Aktivní" : "Stahování vypnuto",
            "stats-state",
          ),
        );
      panel.append(head);
      const totals = data.totals[source];
      const cards = el("dl", undefined, "stats-totals");
      const fields =
        source === "api"
          ? [
              ["requests", "Dotazy"],
              ["errors", "Chyby (4xx / 5xx)"],
            ]
          : [
              ["requests", "Dotazy"],
              ["downloads", "Stažené soubory"],
              ["not_modified", "Beze změny (304)"],
              ["bytes", "Přeneseno"],
              ["errors", "Chyby"],
            ];
      for (const [key, label] of fields) {
        const pair = el("div");
        pair.append(
          el("dt", label),
          el("dd", key === "bytes" ? bytes(totals[key]) : number(totals[key])),
        );
        cards.append(pair);
      }
      panel.append(cards);
      if (source !== "api") {
        const info = data.sources[source];
        panel.append(
          el(
            "p",
            `Poslední stažení: ${stamp(info.last_downloaded_at)} · Poslední kontrola: ${info.last_checked_at ? stamp(info.last_checked_at) : "Zatím neproběhla"}`,
            "stats-caption",
          ),
        );
        if (info.last_error)
          panel.append(
            el(
              "p",
              `Poslední kontrola selhala (${info.last_error}).`,
              "stats-error",
            ),
          );
      }
      const transfer = metric.value === "bytes" && source !== "api";
      const chartFields =
        source === "api"
          ? [
              ["requests", "Dotazy"],
              ["errors", "Chyby"],
            ]
          : transfer
            ? [["bytes", "Přenos dat"]]
            : [
                ["requests", "Dotazy"],
                ["downloads", "Stažení"],
              ];
      const legend = el("div", undefined, "stats-legend");
      for (let i = 0; i < chartFields.length; i++)
        legend.append(el("span", chartFields[i][1], `series-${i}`));
      panel.append(legend);
      const max = Math.max(
        1,
        ...data.series.flatMap((row) =>
          chartFields.map(([key]) => row[source][key]),
        ),
      );
      panel.append(
        el(
          "p",
          `Maximum osy: ${transfer ? bytes(max) : number(max)}`,
          "stats-caption",
        ),
      );
      const scroll = el("div", undefined, "stats-chart-scroll");
      scroll.tabIndex = 0;
      scroll.setAttribute(
        "aria-label",
        `Graf ${sourceNames[source]} — lze posouvat vodorovně`,
      );
      const chart = el("div", undefined, "stats-chart");
      chart.style.setProperty("--bins", data.series.length);
      chart.setAttribute("role", "img");
      chart.setAttribute(
        "aria-label",
        `${sourceNames[source]}: sloupcový graf. Přesné hodnoty jsou v tabulce pod grafem.`,
      );
      for (const row of data.series) {
        const group = el("div", undefined, "stats-bin");
        const bars = el("div", undefined, "stats-bars");
        group.title = `${row.label}: ${chartFields.map(([key, label]) => `${label} ${transfer ? bytes(row[source][key]) : number(row[source][key])}`).join(", ")}`;
        for (let i = 0; i < chartFields.length; i++) {
          const bar = el("span", undefined, `stats-bar series-${i}`);
          bar.style.height = `${(row[source][chartFields[i][0]] / max) * 100}%`;
          bars.append(bar);
        }
        group.append(
          bars,
          el(
            "small",
            data.period === "day" ? row.label.slice(0, 2) : row.label,
          ),
        );
        chart.append(group);
      }
      scroll.append(chart);
      panel.append(scroll);
      if (!totals.requests)
        panel.append(
          el(
            "p",
            "V tomto období nejsou zaznamenané žádné dotazy.",
            "stats-caption",
          ),
        );
      const details = el("details");
      details.dataset.section = source;
      details.open = expanded.has(source);
      details.append(el("summary", "Přesné hodnoty po obdobích"));
      const wrap = el("div", undefined, "stats-table-wrap");
      const table = el("table");
      const thead = el("thead"),
        tr = el("tr");
      tr.append(
        el(
          "th",
          data.period === "day"
            ? "Hodina"
            : data.period === "month"
              ? "Den"
              : "Měsíc",
        ),
      );
      fields.forEach(([, label]) => tr.append(el("th", label)));
      thead.append(tr);
      table.append(thead);
      const tbody = el("tbody");
      for (const row of data.series) {
        const tr = el("tr");
        tr.append(el("td", row.label));
        fields.forEach(([key]) =>
          tr.append(
            el(
              "td",
              key === "bytes"
                ? bytes(row[source][key])
                : number(row[source][key]),
            ),
          ),
        );
        tbody.append(tr);
      }
      table.append(tbody);
      wrap.append(table);
      details.append(wrap);
      panel.append(details);
      content.append(panel);
    }
    if (data.api_endpoints.length) {
      const details = el("details", undefined, "stats-panel");
      details.dataset.section = "endpoints";
      details.open = expanded.has("endpoints");
      details.append(el("summary", "Externí dotazy podle API endpointu"));
      const list = el("ul", undefined, "stats-endpoints");
      for (const row of data.api_endpoints)
        list.append(
          el(
            "li",
            `${row.endpoint}: ${number(row.requests)} dotazů · ${number(row.errors)} chyb`,
          ),
        );
      details.append(list);
      content.append(details);
    }
    dialog.scrollTop = scrollTop;
  }
  async function load() {
    const current = ++sequence;
    loading = true;
    notice.textContent = "Načítání statistik…";
    content.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(
        `/api/v1/statistics?${new URLSearchParams({ period: period.value, date: date.value })}`,
        { headers, cache: "no-store", signal: AbortSignal.timeout(15000) },
      );
      if (!response.ok)
        throw new Error(
          response.status === 404
            ? "Pro statistiky aktualizujte server IDS JMK."
            : "Statistiky nelze načíst. Zkontrolujte datum a připojení.",
        );
      const result = await response.json();
      if (current !== sequence || !dialog.open) return;
      data = result;
      render();
      notice.textContent = "";
    } catch (error) {
      if (current === sequence) {
        data = null;
        notice.textContent = error.message;
        content.replaceChildren();
      }
    } finally {
      if (current === sequence) {
        loading = false;
        content.removeAttribute("aria-busy");
      }
    }
  }
  function move(delta) {
    const selected = new Date(`${date.value}T12:00:00Z`);
    if (!Number.isFinite(selected.getTime())) return;
    if (period.value === "day")
      selected.setUTCDate(selected.getUTCDate() + delta);
    else if (period.value === "month") {
      selected.setUTCDate(1);
      selected.setUTCMonth(selected.getUTCMonth() + delta);
    } else {
      selected.setUTCMonth(0, 1);
      selected.setUTCFullYear(selected.getUTCFullYear() + delta);
    }
    date.value = selected.toISOString().slice(0, 10);
    load();
  }
  document.getElementById("open-statistics").addEventListener("click", () => {
    dialog.showModal();
    load();
  });
  document
    .getElementById("close-statistics")
    .addEventListener("click", () => dialog.close());
  document.getElementById("stats-refresh").addEventListener("click", load);
  document
    .getElementById("stats-prev")
    .addEventListener("click", () => move(-1));
  document
    .getElementById("stats-next")
    .addEventListener("click", () => move(1));
  period.addEventListener("change", load);
  date.addEventListener("change", load);
  metric.addEventListener("change", render);
  dialog.addEventListener("close", () => {
    sequence++;
    loading = false;
  });
  setInterval(() => {
    if (!document.hidden) {
      if (dialog.open && !loading) load();
      else status();
    }
  }, 30000);
  status();
}
