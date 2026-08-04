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

/** Modules the user actually collects, in display order. */
export function useEnabledModules() {
  const { settings } = useSettings();
  const on = settings?.enabled_modules || MODULES.map((m) => m.key);
  return MODULES.filter((m) => on.includes(m.key));
}
