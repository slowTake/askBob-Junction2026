/** Light/dark theme choice. Pure: storage and the OS setting are passed in. */

export type Theme = "light" | "dark";
export type ThemeChoice = Theme | "system";

export const THEME_STORAGE_KEY = "bob.theme";

export function parseChoice(stored: string | null): ThemeChoice {
  return stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
}

export function resolveTheme(choice: ThemeChoice, systemDark: boolean): Theme {
  if (choice === "system") return systemDark ? "dark" : "light";
  return choice;
}

/** The toggle always flips what is on screen, and the result is an explicit choice. */
export function toggleChoice(choice: ThemeChoice, systemDark: boolean): Theme {
  return resolveTheme(choice, systemDark) === "dark" ? "light" : "dark";
}
