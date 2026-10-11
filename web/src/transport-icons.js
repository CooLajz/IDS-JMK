// Unmodified paths from Material Design Icons 7.4.47 by Pictogrammers.
import {
  mdiTram, mdiBus, mdiTrain, mdiBusElectric, mdiSubwayVariant, mdiFerry,
  mdiGondola, mdiBicycle, mdiWheelchairAccessibility,
} from "@mdi/js";
export { mdiBicycle, mdiWheelchairAccessibility };
const modes = {
  tram: [mdiTram, "Šalina"], bus: [mdiBus, "Autobus"], rail: [mdiTrain, "Vlak"],
  trolleybus: [mdiBusElectric, "Trolejbus"], subway: [mdiSubwayVariant, "Metro"],
  ferry: [mdiFerry, "Lodní doprava"], aerial_lift: [mdiGondola, "Visutá lanovka"],
  cable_tram: [mdiTram, "Dráha tažená lanem"], funicular: [mdiTrain, "Pozemní lanovka"],
  monorail: [mdiTrain, "Jednokolejnicová dráha"],
};
export function mdiIcon(path, label) {
  const icon = document.createElement("span");
  icon.className = "amenity-icon";
  icon.title = label;
  icon.setAttribute("role", "img");
  icon.setAttribute("aria-label", label);
  // Paths come exclusively from the pinned icon package, never from API data.
  icon.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"/></svg>`;
  return icon;
}
export function vehicleIcon(mode) {
  return Object.hasOwn(modes, mode) ? mdiIcon(...modes[mode]) : null;
}
