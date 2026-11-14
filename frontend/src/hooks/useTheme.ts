import { useEffect, useState } from "react";
import {
  parseChoice,
  resolveTheme,
  THEME_STORAGE_KEY,
  toggleChoice,
  type Theme,
  type ThemeChoice,
} from "../lib/theme";

const DARK_QUERY = "(prefers-color-scheme: dark)";

function readStored(): ThemeChoice {
  try {
    return parseChoice(localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return "system"; // storage blocked (private window, policy)
  }
}

/** Follows the OS until the user toggles; the choice is remembered in localStorage. */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [choice, setChoice] = useState<ThemeChoice>(readStored);
  const [systemDark, setSystemDark] = useState(() => window.matchMedia(DARK_QUERY).matches);

  useEffect(() => {
    const mq = window.matchMedia(DARK_QUERY);
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const theme = resolveTheme(choice, systemDark);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const toggle = () => {
    const next = toggleChoice(choice, systemDark);
    setChoice(next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // not remembered; the toggle still works for this visit
    }
  };

  return { theme, toggle };
}
