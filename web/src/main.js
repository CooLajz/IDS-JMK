import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { renderAlerts } from "./alerts.js";
import { vehicleIcon, mdiIcon, mdiBicycle, mdiWheelchairAccessibility } from "./transport-icons.js";

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
  stopLayer = null,
  followedStopKey = null,
  followedVehiclePosition = null,
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
function vehicleFeatures(d, includeTransport = false) {
  const features = document.createElement("span");
  features.className = "trip-features";
  if (includeTransport) {
    const transport = vehicleIcon(d.transport_mode);
    if (transport) features.append(transport);
  }
  const icons = [
    [
      d.wheelchair_accessible,
      "Vozidlo přístupné vozíčkářům podle jízdního řádu",
      mdiWheelchairAccessibility,
    ],
    [
      d.bikes_allowed,
      "Přeprava kol podle jízdního řádu",
      mdiBicycle,
    ],
  ];
  for (const [available, label, drawing] of icons) {
    if (available !== true) continue;
    features.append(mdiIcon(drawing, label));
  }
  return features;
}
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
function filterLink(container, name, value, label, key) {
  if (!value || ![...$(name).options].some((o) => o.value === value)) {
    container.textContent = label;
    return;
  }
  const button = document.createElement("button");
  button.type = "button";
  button.className = "filter-link";
  button.dataset.key = `${key}/${name}`;
  button.textContent = label;
  const filterName = { line: "linku", direction: "směr", platform: "stanoviště" }[name];
  button.title = `Filtrovat ${filterName}: ${label}`;
  button.setAttribute("aria-label", button.title);
  button.addEventListener("click", () => {
    $(name).value = value;
    refresh();
  });
  container.append(button);
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
      data.realtime_enabled === false
        ? "Jízdní řád · realtime je na serveru vypnutý. U spoje můžete zobrazit trasu zastávek."
        : data.realtime_stale
        ? "Realtime údaje nejsou čerstvé. Odjezdy jsou podle jízdního řádu."
        : "Živá tabule · obnova každých 30 sekund. Kliknutím na linku, směr nebo stanoviště nastavíte filtr, tlačítkem „Poloha“ otevřete mapu.",
    );
  } catch (e) {
    if (seq === boardSequence) {
      board = null;
      renderAlerts($("alerts"), null);
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
  renderAlerts($("alerts"), board);
  const focused = document.activeElement.closest?.("#departures button");
  const focusKey = focused?.dataset.key;
  $("departures").replaceChildren();
  $("empty").hidden = board.departures.length > 0;
  $("empty").textContent =
    "Pro tento výběr nejsou v příštích 24 hodinách žádné odjezdy.";
  $("subtitle").textContent = "Nejbližší odjezdy";
  $("updated").textContent = `Aktualizováno ${timeText(board.generated_at)}`;
  const rows = [...(board.previous_departures || []), ...board.departures];
  $("estimate-note").hidden = !rows.length || board.realtime_enabled === false;
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
    const key = `${d.trip_id}/${d.service_date}/${d.stop_sequence}`;
    const route = cell("", "route");
    filterLink(route, "line", d.line, d.line, key);
    const transport = vehicleIcon(d.transport_mode);
    if (transport) route.querySelector("button")?.prepend(transport);
    const dest = cell("");
    filterLink(dest, "direction", d.destination, d.destination || "—", key);
    if (d.has_vehicle_position || board.realtime_enabled === false) {
      const position = document.createElement("button");
      position.className = "position-link";
      position.dataset.key = `${key}/map`;
      const staticRoute = board.realtime_enabled === false;
      position.title = staticRoute ? "Zobrazit trasu zastávek na mapě" : "Zobrazit aktuální polohu vozidla na mapě";
      position.setAttribute(
        "aria-label",
        `${staticRoute ? "Trasa" : "Poloha vozidla"} linky ${d.line}, ${d.destination}`,
      );
      position.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s7-7 7-12a7 7 0 0 0-14 0c0 5 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5"/></svg> Poloha';
      if (staticRoute) position.lastChild.textContent = " Trasa";
      position.addEventListener("click", () => showTrip(d));
      dest.append(position);
    }
    const pastLabel = document.createElement("small");
    pastLabel.className = "past-label";
    dest.append(pastLabel);
    dest.append(vehicleFeatures(d));
    const platform = cell("", "platform-col");
    filterLink(platform, "platform", d.platform ? d.stop_id : null, d.platform || "—", key);
    const time = cell("");
    const strong = document.createElement("span");
    strong.className = "time";
    strong.textContent = timeText(d.scheduled_departure);
    strong.title = "Odjezd podle jízdního řádu";
    time.append(strong);
    const sub = document.createElement("small");
    const date = new Date(d.scheduled_departure).toLocaleDateString("cs-CZ", {
      timeZone: "Europe/Prague",
    });
    const today = new Date(board.generated_at).toLocaleDateString("cs-CZ", {
      timeZone: "Europe/Prague",
    });
    const delayMinutes = Number.isFinite(d.delay_seconds)
      ? Math.round(d.delay_seconds / 60)
      : 0;
    const label = d.cancelled
      ? "Zrušeno"
      : d.source === "schedule"
        ? "Jízdní řád"
        : delayMinutes !== 0
          ? `${d.source === "vehicle_estimate" ? "Odhadované zpoždění" : "Zpoždění"} ${delayMinutes > 0 ? "+" : ""}${delayMinutes} min`
          : "";
    sub.textContent = [date !== today ? date : "", label].filter(Boolean).join(" · ");
    if (d.source !== "schedule") sub.className = "estimated";
    if (sub.textContent) time.append(sub);
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
function centerOnVehicle() {
  if (map && followedVehiclePosition && $("follow-vehicle").checked) {
    map.panTo([followedVehiclePosition.lat, followedVehiclePosition.lon], { animate: false });
  }
}
$("follow-vehicle").addEventListener("change", centerOnVehicle);
async function showTrip(d) {
  selectedTrip = d;
  if (map) {
    map.remove();
    map = null;
  }
  vehicleLayer = null;
  stopLayer = null;
  followedStopKey = null;
  followedVehiclePosition = null;
  $("follow-vehicle").checked = false;
  $("map-controls").hidden = true;
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
    $("detail-features").replaceChildren(vehicleFeatures(trip, true));
    const vehicles = (trip.vehicles || []).filter((v) => !v.stale && v.position);
    const stopProgress = (s) => vehicles.find((v) =>
      v.current_stop?.stop_sequence === s.seq && v.current_stop.stop_id === s.stop_id,
    )?.current_stop;
    const stopStatus = (s) => stopProgress(s)?.status;
    const stopLabel = (status) => ({
      in_transit_to: "Následující zastávka",
      incoming_at: "Přijíždí do zastávky",
      stopped_at: "Právě v zastávce",
      before_departure: "Před plánovaným odjezdem",
    })[status];
    const stopList = $("trip-stops");
    const previousScroll = stopList.scrollTop;
    stopList.replaceChildren();
    for (const s of trip.stops) {
      const li = document.createElement("li"),
        t = document.createElement("strong");
      t.textContent = timeText(s.scheduled_departure);
      const name = document.createElement("span");
      name.textContent = s.name;
      li.append(t, name);
      const label = stopLabel(stopStatus(s));
      if (label) {
        li.dataset.stopKey = `${s.stop_id}/${s.seq}`;
        li.classList.add("vehicle-stop");
        const badge = document.createElement("small");
        const progress = stopProgress(s);
        const delay = Number.isFinite(progress.delay_seconds)
          ? Math.round(progress.delay_seconds / 60)
          : 0;
        const delayLabel = delay !== 0
          ? `${progress.delay_source === "vehicle_estimate" ? "odhad" : "zpoždění"} ${delay > 0 ? "+" : ""}${delay} min`
          : "";
        badge.textContent = [label, delayLabel].filter(Boolean).join(" · ");
        li.append(badge);
      }
      $("trip-stops").append(li);
    }
    $("detail-status").replaceChildren();
    if (vehicles.length) {
      const caption = document.createElement("span");
      caption.textContent = "Aktualizace polohy";
      const updated = document.createElement("time");
      updated.dateTime = vehicles[0].updated_at;
      updated.textContent = timeText(vehicles[0].updated_at);
      updated.title = new Date(vehicles[0].updated_at).toLocaleString("cs-CZ", { timeZone: "Europe/Prague" });
      $("detail-status").append(caption, updated);
    } else {
      $("detail-status").textContent = trip.realtime_enabled === false
        ? "Trasa podle pořadí zastávek · realtime vypnutý" : "Poloha není dostupná";
    }
    followedVehiclePosition = vehicles[0]?.position ?? null;
    $("map-controls").hidden = !vehicles.length;
    const showRoute = trip.realtime_enabled === false && trip.stops.length > 0;
    $("map").hidden = !vehicles.length && !showRoute;
    if (vehicles.length || showRoute) {
      const firstMap = !map;
      if (firstMap) {
        map = L.map("map");
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution:
            '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(map);
        stopLayer = L.layerGroup().addTo(map);
        vehicleLayer = L.layerGroup().addTo(map);
      }
      stopLayer.clearLayers();
      for (const s of trip.stops) {
        const label = stopLabel(stopStatus(s));
        const tooltip = document.createElement(label ? "strong" : "span");
        tooltip.textContent = s.name;
        L.circleMarker([s.lat, s.lon], {
          radius: label ? 7 : 4,
          color: label ? "#1e40af" : "#647762",
          fillColor: label ? "#60a5fa" : "#647762",
          weight: label ? 3 : 2,
          fillOpacity: 1,
        }).addTo(stopLayer).bindTooltip(tooltip, { direction: "top" });
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
      centerOnVehicle();
      setTimeout(() => {
        map?.invalidateSize();
        centerOnVehicle();
      }, 50);
    }
    stopList.scrollTop = previousScroll;
    const followedStop = stopList.querySelector(".vehicle-stop");
    const nextStopKey = followedStop?.dataset.stopKey ?? null;
    if (followedStop && nextStopKey !== followedStopKey) {
      const top = followedStop.getBoundingClientRect().top - stopList.getBoundingClientRect().top
        + stopList.scrollTop - (stopList.clientHeight - followedStop.offsetHeight) / 2;
      stopList.scrollTo({ top: Math.max(0, top), behavior: "instant" });
    }
    followedStopKey = nextStopKey;
  } catch (e) {
    if (seq === tripSequence) {
      $("detail-status").textContent = e.message;
      followedVehiclePosition = null;
      $("map-controls").hidden = true;
      $("map").hidden = true;
    }
  }
}
$("close-detail").addEventListener("click", () => $("detail").close());
$("detail").addEventListener("close", () => {
  ++tripSequence;
  selectedTrip = null;
  followedVehiclePosition = null;
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
