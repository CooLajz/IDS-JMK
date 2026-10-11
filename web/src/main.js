import "leaflet/dist/leaflet.css";
import L from "leaflet";

const $ = (id) => document.getElementById(id);
let selected = null,
  board = null,
  map = null,
  searchTimer,
  searchSequence = 0,
  boardSequence = 0,
  selectionSequence = 0,
  tripSequence = 0;
let selectedTrip = null,
  vehicleLayer = null,
  boardReceivedAt = 0,
  refreshTimer,
  nextRefreshAt = 0;
const boardNow = () =>
  new Date(board.generated_at).getTime() + performance.now() - boardReceivedAt;
const timeText = (v) =>
  new Date(v).toLocaleTimeString("cs-CZ", {
    timeZone: "Europe/Prague",
    hour: "2-digit",
    minute: "2-digit",
  });
function notice(text, error = false) {
  $("notice").textContent = text;
  $("notice").classList.toggle("error", error);
}
async function api(path) {
  const res = await fetch(`/api/v1/${path}`, {
    signal: AbortSignal.timeout(15000),
  });
  const data = await res.json();
  if (!res.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Požadavek se nepodařilo zpracovat.",
    );
  return data;
}
function option(value, label) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = label;
  return o;
}
function filterOptions(id, values, label) {
  $(id).replaceChildren(
    option("", label),
    ...values.map((v) => option(v.value ?? v, v.label ?? v)),
  );
  $(id).disabled = false;
}
function closeResults() {
  $("results").hidden = true;
  $("search").setAttribute("aria-expanded", "false");
}
async function search() {
  const seq = ++searchSequence,
    query = $("search").value.trim();
  if (query.length < 2) {
    closeResults();
    return;
  }
  try {
    const data = await api(`stops?query=${encodeURIComponent(query)}`);
    if (seq !== searchSequence) return;
    $("results").replaceChildren();
    for (const stop of data.stops) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = stop.name;
      const sub = document.createElement("small");
      sub.textContent = stop.platforms
        ? `${stop.platforms} stanovišť · všechny odjezdy`
        : `Zastávka ${stop.id}`;
      b.append(sub);
      b.addEventListener("click", () => selectStop(stop.id));
      $("results").append(b);
    }
    if (!data.stops.length) {
      const p = document.createElement("p");
      p.textContent = "Žádná zastávka. Zkuste kratší název.";
      $("results").append(p);
    }
    $("results").hidden = false;
    $("search").setAttribute("aria-expanded", "true");
  } catch (e) {
    if (seq === searchSequence) notice(e.message, true);
  }
}
$("search").addEventListener("input", () => {
  ++searchSequence;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(search, 220);
});
$("search").addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeResults();
  if (e.key === "ArrowDown") {
    e.preventDefault();
    $("results").querySelector("button")?.focus();
  }
  if (e.key === "Enter") {
    e.preventDefault();
    $("results").querySelector("button")?.click();
  }
});
$("results").addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") {
    e.preventDefault();
    document.activeElement.nextElementSibling?.focus();
  }
  if (e.key === "ArrowUp") {
    e.preventDefault();
    (document.activeElement.previousElementSibling || $("search")).focus();
  }
  if (e.key === "Escape") {
    closeResults();
    $("search").focus();
  }
});
document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-wrap")) closeResults();
});
async function selectStop(id, params = new URLSearchParams()) {
  const seq = ++selectionSequence;
  ++searchSequence;
  ++boardSequence;
  closeResults();
  notice("Načítám zastávku…");
  try {
    const stop = await api(`stops/${encodeURIComponent(id)}`);
    if (seq !== selectionSequence) return;
    selected = stop;
    $("search").value = stop.name;
    $("stop-title").textContent = stop.name;
    filterOptions("direction", stop.directions, "Všechny směry");
    filterOptions("line", stop.lines, "Všechny linky");
    filterOptions(
      "platform",
      stop.platforms.map((p) => ({ value: p.id, label: p.platform || p.id })),
      "Všechna stanoviště",
    );
    for (const name of ["direction", "line", "platform"])
      if (params.get(name)) $(name).value = params.get(name);
    $("refresh").disabled = false;
    $("ha").disabled = false;
    $("api-link").disabled = false;
    await refresh();
  } catch (e) {
    if (seq === selectionSequence) notice(e.message, true);
  }
}
function boardPath(includePrevious = false) {
  const p = new URLSearchParams({ limit: "12", horizon: "1440" });
  if (includePrevious) p.set("previous_limit", "1");
  for (const name of ["line", "direction"])
    if ($(name).value) p.set(name, $(name).value);
  return `stops/${encodeURIComponent($("platform").value || selected.id)}/departures?${p}`;
}
async function refresh() {
  if (!selected) return;
  const seq = ++boardSequence;
  clearTimeout(refreshTimer);
  $("refresh").disabled = true;
  const params = new URLSearchParams({ stop: selected.id });
  for (const name of ["line", "direction", "platform"])
    if ($(name).value) params.set(name, $(name).value);
  if ($("show-previous").checked) params.set("previous", "1");
  history.replaceState(null, "", `?${params}`);
  try {
    const data = await api(boardPath($("show-previous").checked));
    if (seq !== boardSequence) return;
    board = data;
    boardReceivedAt = performance.now();
    renderBoard();
    notice(
      data.realtime_stale
        ? "Realtime údaje nejsou čerstvé. Odjezdy jsou podle jízdního řádu."
        : "Živá tabule · obnova každých 30 sekund. Značka „Poloha“ otevře mapu vozidla.",
    );
  } catch (e) {
    if (seq === boardSequence) {
      board = null;
      $("departures").replaceChildren();
      $("empty").hidden = false;
      $("empty").textContent = "Odjezdy nejsou dostupné. Zkuste je obnovit.";
      $("updated").textContent = "";
      notice(e.message, true);
    }
  } finally {
    if (seq === boardSequence) {
      $("refresh").disabled = false;
      nextRefreshAt = performance.now() + 30000;
      refreshTimer = setTimeout(refreshVisible, 30000);
      updateCountdowns();
    }
  }
}
function renderBoard() {
  const focused = document.activeElement.closest?.("#departures button");
  const focusKey = focused?.dataset.key;
  $("departures").replaceChildren();
  $("empty").hidden = board.departures.length > 0;
  $("empty").textContent =
    "Pro tento výběr nejsou v příštích 24 hodinách žádné odjezdy.";
  $("subtitle").textContent = "Nejbližší odjezdy";
  $("updated").textContent = `Aktualizováno ${timeText(board.generated_at)}`;
  const rows = [...(board.previous_departures || []), ...board.departures];
  $("estimate-note").hidden = !rows.length;
  for (const d of rows) {
    const tr = document.createElement("tr");
    if (d.cancelled) tr.classList.add("cancelled");
    tr.dataset.departure = d.departure_time;
    tr.dataset.cancelled = String(!!d.cancelled);
    tr.dataset.source = d.source;
    const cell = (text, cls = "") => {
      const td = document.createElement("td");
      td.textContent = text;
      td.className = cls;
      tr.append(td);
      return td;
    };
    cell(d.line, "route");
    const dest = cell("");
    const button = document.createElement("button");
    button.className = "trip-link";
    button.dataset.key = `${d.trip_id}/${d.service_date}/${d.stop_sequence}`;
    button.textContent = d.destination || "Detail spoje";
    button.addEventListener("click", () => showTrip(d));
    dest.append(button);
    if (d.has_vehicle_position) {
      const position = document.createElement("button");
      position.className = "position-link";
      position.dataset.key = `${button.dataset.key}/map`;
      position.title = "Zobrazit aktuální polohu vozidla na mapě";
      position.setAttribute(
        "aria-label",
        `Poloha vozidla linky ${d.line}, ${d.destination}`,
      );
      position.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s7-7 7-12a7 7 0 0 0-14 0c0 5 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5"/></svg> Poloha';
      position.addEventListener("click", () => showTrip(d));
      dest.append(position);
    }
    const pastLabel = document.createElement("small");
    pastLabel.className = "past-label";
    dest.append(pastLabel);
    const features = document.createElement("span");
    features.className = "trip-features";
    const icons = [
      [
        d.wheelchair_accessible,
        "Vozidlo přístupné vozíčkářům podle jízdního řádu",
        '<circle cx="13" cy="4" r="2"/><path d="m12 7-1 7h6l3 6 2-1M12 10h6M8 10a6 6 0 1 0 6 9"/>',
      ],
      [
        d.bikes_allowed,
        "Přeprava kol podle jízdního řádu",
        '<circle cx="5" cy="17" r="4"/><circle cx="19" cy="17" r="4"/><path d="m5 17 5-9 5 9H5m5-9h7l2 9M8 5h4m3-1h3l2 4"/>',
      ],
    ];
    for (const [available, label, drawing] of icons) {
      if (available !== true) continue;
      const icon = document.createElement("span");
      icon.className = "amenity-icon";
      icon.title = label;
      icon.setAttribute("role", "img");
      icon.setAttribute("aria-label", label);
      icon.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${drawing}</svg>`;
      features.append(icon);
    }
    dest.append(features);
    cell(d.platform || "—", "platform-col");
    const time = cell("");
    const strong = document.createElement("span");
    strong.className = "time";
    strong.textContent = timeText(d.departure_time);
    time.append(strong);
    const sub = document.createElement("small");
    const date = new Date(d.departure_time).toLocaleDateString("cs-CZ", {
      timeZone: "Europe/Prague",
    });
    const today = new Date(board.generated_at).toLocaleDateString("cs-CZ", {
      timeZone: "Europe/Prague",
    });
    const prefix = date !== today ? `${date} · ` : "";
    sub.textContent =
      prefix +
      (d.cancelled
        ? "Zrušeno"
        : d.source === "schedule"
          ? "Jízdní řád"
          : `${d.source === "vehicle_estimate" ? "Odhad" : "Realtime"} ${d.delay_seconds >= 0 ? "+" : ""}${Math.round(d.delay_seconds / 60)} min`);
    if (d.source !== "schedule") sub.className = "estimated";
    time.append(sub);
    cell(d.cancelled ? "—" : `${d.minutes_until} min`, "minutes");
    $("departures").append(tr);
  }
  updateCountdowns();
  if (focusKey) {
    [...$("departures").querySelectorAll("button")]
      .find((b) => b.dataset.key === focusKey)
      ?.focus({ preventScroll: true });
  }
}
function updateCountdowns() {
  if (!board) return;
  const now = boardNow();
  for (const row of $("departures").rows) {
    const difference = new Date(row.dataset.departure).getTime() - now;
    const past = difference < 0;
    row.hidden = past && !$("show-previous").checked;
    const cancelled = row.dataset.cancelled === "true";
    row.classList.toggle("past-departure", past);
    row.querySelector(".past-label").textContent = !past
      ? ""
      : cancelled
        ? "Minulý zrušený spoj"
        : row.dataset.source === "schedule"
          ? "Podle JŘ již odjel"
          : "Podle odhadu již odjel";
    row.querySelector(".minutes").textContent = cancelled
      ? "—"
      : past
        ? `před ${Math.floor(-difference / 60000)} min`
        : `${Math.ceil(difference / 60000)} min`;
  }
  const seconds = Math.max(
    0,
    Math.ceil((nextRefreshAt - performance.now()) / 1000),
  );
  $("updated").textContent =
    `Obnoveno ${timeText(board.generated_at)} · další za ${seconds} s`;
}
for (const name of ["direction", "line", "platform"])
  $(name).addEventListener("change", refresh);
$("refresh").addEventListener("click", refresh);
$("show-previous").addEventListener("change", refresh);
$("fullscreen").addEventListener("click", async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch {
    notice("Prohlížeč režim celé obrazovky nepodporuje.");
  }
});
document.addEventListener("fullscreenchange", () => {
  $("fullscreen").textContent = document.fullscreenElement
    ? "Ukončit celou obrazovku"
    : "Celá obrazovka";
});
async function showTrip(d) {
  selectedTrip = d;
  if (map) {
    map.remove();
    map = null;
  }
  vehicleLayer = null;
  $("detail-title").textContent = `${d.line} · ${d.destination}`;
  $("detail-status").textContent = "Načítám spoj…";
  $("detail-features").textContent = "";
  $("trip-stops").replaceChildren();
  $("map").hidden = true;
  if (!$("detail").open) $("detail").showModal();
  await updateTrip();
}
async function updateTrip() {
  if (!selectedTrip || !$("detail").open) return;
  const d = selectedTrip,
    seq = ++tripSequence;
  try {
    const trip = await api(
      `trips/${encodeURIComponent(d.trip_id)}?service_date=${d.service_date}`,
    );
    if (seq !== tripSequence || !$("detail").open) return;
    const featureText = (value) =>
      value === true ? "ano" : value === false ? "ne" : "neuvedeno";
    $("detail-features").textContent =
      `Podle jízdního řádu: vozidlo přístupné vozíčkářům — ${featureText(trip.wheelchair_accessible)}; přeprava kol — ${featureText(trip.bikes_allowed)}. Údaje nepotvrzují aktuálně nasazený vůz, přístupnost nástupiště ani volnou kapacitu.`;
    $("trip-stops").replaceChildren();
    for (const s of trip.stops) {
      const li = document.createElement("li"),
        t = document.createElement("strong");
      t.textContent = timeText(s.scheduled_departure);
      li.append(t, document.createTextNode(s.name));
      $("trip-stops").append(li);
    }
    const vehicles = trip.vehicles.filter((v) => !v.stale && v.position);
    $("detail-status").textContent = vehicles.length
      ? `Poloha aktualizována ${timeText(vehicles[0].updated_at)}. Časy zastávek jsou podle jízdního řádu.`
      : "Čerstvá poloha vozidla není dostupná. Zobrazené časy jsou podle jízdního řádu.";
    $("map").hidden = !vehicles.length;
    if (vehicles.length) {
      const firstMap = !map;
      if (firstMap) {
        map = L.map("map");
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution:
            '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(map);
        for (const s of trip.stops) {
          const p = [s.lat, s.lon];
          L.circleMarker(p, { radius: 4, color: "#647762", fillOpacity: 1 })
            .addTo(map)
            .bindTooltip(document.createTextNode(s.name));
        }
        vehicleLayer = L.layerGroup().addTo(map);
      }
      vehicleLayer.clearLayers();
      for (const v of vehicles) {
        const p = [v.position.lat, v.position.lon];
        L.circleMarker(p, {
          radius: 10,
          color: "#172910",
          fillColor: "#b8ed60",
          fillOpacity: 1,
          weight: 3,
        })
          .addTo(vehicleLayer)
          .bindTooltip(document.createTextNode(`Vozidlo ${v.label || v.id}`));
      }
      if (firstMap) {
        const points = [
          ...trip.stops.map((s) => [s.lat, s.lon]),
          ...vehicles.map((v) => [v.position.lat, v.position.lon]),
        ];
        map.fitBounds(points, { padding: [25, 25], maxZoom: 15 });
      }
      setTimeout(() => map?.invalidateSize(), 50);
    }
  } catch (e) {
    if (seq === tripSequence) {
      $("detail-status").textContent = e.message;
      $("map").hidden = true;
    }
  }
}
$("close-detail").addEventListener("click", () => $("detail").close());
$("detail").addEventListener("close", () => {
  ++tripSequence;
  selectedTrip = null;
  if (map) {
    map.remove();
    map = null;
  }
});
$("api-link").addEventListener("click", () => {
  const url = new URL(
    `/api/v1/${boardPath($("show-previous").checked)}`,
    location.origin,
  ).href;
  $("api-url").value = url;
  $("open-api").href = url;
  $("api-copy-status").textContent = "";
  $("api-dialog").showModal();
});
$("close-api").addEventListener("click", () => $("api-dialog").close());
$("copy-api").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("api-url").value);
    $("api-copy-status").textContent = "URL zkopírována.";
  } catch {
    $("api-url").focus();
    $("api-url").select();
    $("api-copy-status").textContent =
      "Odkaz je označený. Zkopírujte ho klávesovou zkratkou nebo nabídkou prohlížeče.";
  }
});
$("close-ha").addEventListener("click", () => $("ha-dialog").close());
function haConfig() {
  let base;
  try {
    base = new URL($("ha-url").value);
    if (
      !["http:", "https:"].includes(base.protocol) ||
      base.username ||
      base.password
    )
      throw Error();
  } catch {
    $("ha-code").value =
      "Zadejte platnou HTTP(S) adresu serveru bez přihlašovacích údajů.";
    return;
  }
  const resource = `${base.href.replace(/\/$/, "")}/api/v1/${boardPath()}`;
  const lines = [
    "rest:",
    `  - resource: ${JSON.stringify(resource)}`,
    "    scan_interval: 30",
    "    sensor:",
    '      - name: "IDS JMK odjezdy"',
    '        unique_id: "ids_jmk_rest_board"',
    '        value_template: "{{ value_json.departures | count }}"',
    "        json_attributes:",
    "          - departures",
    "          - generated_at",
    "",
    "# Následující část vložte jako ruční kartu na dashboard:",
    "type: custom:flex-table-card",
    "title: " + JSON.stringify(selected.name),
    "entities:",
    "  include: sensor.ids_jmk_odjezdy",
    "columns:",
    ...[
      "Linka|line",
      "Směr|destination",
      "Čas|departure_time_display",
      "Za (min)|minutes_until",
    ].flatMap((v) => {
      const [name, field] = v.split("|");
      return [
        `  - name: ${JSON.stringify(name)}`,
        "    data: departures",
        `    modify: ${JSON.stringify(field === "minutes_until" ? "x.cancelled ? 'Zrušeno' : x.minutes_until" : `String(x.${field}).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')`)}`,
      ];
    }),
  ];
  $("ha-code").value = lines.join("\n");
}
$("ha").addEventListener("click", () => {
  $("ha-url").value = location.origin;
  $("copy-status").textContent = "";
  haConfig();
  $("ha-dialog").showModal();
});
$("ha-url").addEventListener("input", haConfig);
$("copy-ha").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("ha-code").value);
    $("copy-status").textContent =
      "Zkopírováno. Senzor a kartu vložte do příslušných částí konfigurace.";
  } catch {
    $("ha-code").select();
    $("copy-status").textContent = "Označeno — zkopírujte klávesovou zkratkou.";
  }
});
async function init() {
  try {
    const status = await api("status");
    if (!status.ready) {
      notice(
        "Probíhá první import jízdních řádů. Stránka se připojí automaticky.",
      );
      setTimeout(init, 5000);
      return;
    }
    notice(
      status.schedule_expired
        ? "Platnost jízdních řádů skončila. Server čeká na nová data."
        : "Jízdní řády jsou připravené. Vyhledejte zastávku.",
    );
    const params = new URLSearchParams(location.search);
    $("show-previous").checked = params.get("previous") === "1";
    if (params.get("stop")) await selectStop(params.get("stop"), params);
  } catch (e) {
    notice(`Server není dostupný: ${e.message}`, true);
    setTimeout(init, 10000);
  }
}
function refreshVisible() {
  if (!document.hidden) {
    refresh();
    updateTrip();
  }
}

setInterval(() => {
  if (!document.hidden) updateCountdowns();
}, 1000);
document.addEventListener("visibilitychange", refreshVisible);
window.addEventListener("online", refreshVisible);
init();
