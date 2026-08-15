import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api.js";

// One place the whole app reads preferences from, so a change in Settings
// takes effect everywhere without a reload.
const Ctx = createContext(null);

export const MODULES = [
  { key: "cards", label: "Cards", icon: "card", blurb: "Pokémon TCG" },
  { key: "games", label: "Games", icon: "pad", blurb: "Cartridges & discs" },
  { key: "hardware", label: "Hardware", icon: "console", blurb: "Consoles & gear" },
  { key: "movies", label: "Movies", icon: "disc", blurb: "Physical media" },
  { key: "books", label: "Books", icon: "book", blurb: "Shelves & spines" },
  { key: "records", label: "Records", icon: "vinyl", blurb: "Vinyl & crates" },
  { key: "lego", label: "LEGO", icon: "brick", blurb: "Sets & minifigs" },
  { key: "comics", label: "Comics", icon: "comic", blurb: "Issues & runs" },
];

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(null); // null while loading

  useEffect(() => {
    api
      .settings()
      .then(setSettings)
      .catch(() => setSettings({ enabled_modules: MODULES.map((m) => m.key) }));
  }, []);

  const save = async (patch) => {
    const next = await api.saveSettings(patch);
    setSettings(next);
    return next;
  };

  return <Ctx.Provider value={{ settings, save }}>{children}</Ctx.Provider>;
}

export function useSettings() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSettings outside SettingsProvider");
  return v;
}

/** A collection's sort or filter, remembered between visits.
 *
 *  Drop-in for useState: same shape, same call site. A sort you chose is a
 *  decision about how you like to look at your shelf, not a per-visit whim,
 *  and re-picking "last added" every time you open the app is exactly the
 *  kind of small tax that makes software feel like it isn't listening.
 *
 *  Server-side rather than localStorage on purpose — this app is used from a
 *  phone and a desk, and the preference should be the same in both.
 */
export function useListPref(module, key, fallback) {
  const { settings, save } = useSettings();
  const prefs = settings?.list_prefs || {};
  // settings load after the first render, so until they arrive the fallback
  // stands in; ?? not || so that a deliberately empty filter survives
  const value = prefs[module]?.[key] ?? fallback;
  const set = (next) =>
    save({
      list_prefs: {
        ...prefs,
        [module]: { ...(prefs[module] || {}), [key]: next },
      },
    });
  return [value, set];
}

/** Modules the user actually collects, in display order. */
export function useEnabledModules() {
  const { settings } = useSettings();
  const on = settings?.enabled_modules || MODULES.map((m) => m.key);
  return MODULES.filter((m) => on.includes(m.key));
}

/** Modules this server carries at all, in display order.
 *
 *  Different from the above and not a preference: the hosted service cannot
 *  legally offer some of these, so they are absent rather than switched off.
 *  Offering a toggle for one would be offering a switch wired to nothing.
 *
 *  Falls back to all of them, which is what a self-hosted install has and
 *  what every version before this one reported.
 */
/** Whether a collection is behind the paywall for this person.
 *
 *  False for everything on a self-hosted install, where nothing is paid, and
 *  false for everything once somebody has subscribed. Locked is not the same
 *  as absent: their records are still there, still theirs, and still in the
 *  backup — the door is shut, the room is not empty.
 */
export function useLocked() {
  const { settings } = useSettings();
  const paid = settings?.paid_modules || [];
  const paying = settings?.subscribed;
  return (key) => paid.includes(key) && !paying;
}

export function useAvailableModules() {
  const { settings } = useSettings();
  const here = settings?.available_modules;
  if (!here || !here.length) return MODULES;
  return MODULES.filter((m) => here.includes(m.key));
}
