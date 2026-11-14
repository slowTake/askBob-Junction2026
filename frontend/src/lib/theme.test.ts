import { describe, expect, it } from "vitest";
import { parseChoice, resolveTheme, toggleChoice } from "./theme";

describe("parseChoice", () => {
  it("keeps a valid stored choice", () => {
    expect(parseChoice("light")).toBe("light");
    expect(parseChoice("dark")).toBe("dark");
    expect(parseChoice("system")).toBe("system");
  });

  it("falls back to system for missing or unknown values", () => {
    // Nothing stored (first visit) or a value from an older build: follow the OS.
    expect(parseChoice(null)).toBe("system");
    expect(parseChoice("")).toBe("system");
    expect(parseChoice("blue")).toBe("system");
  });
});

describe("resolveTheme", () => {
  it("uses the OS setting only when the choice is system", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });

  it("an explicit choice wins over the OS setting", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
});

describe("toggleChoice", () => {
  it("flips whatever is on screen to the explicit opposite", () => {
    // OS is dark and nothing chosen: screen is dark, so the toggle picks light.
    expect(toggleChoice("system", true)).toBe("light");
    expect(toggleChoice("system", false)).toBe("dark");
    expect(toggleChoice("dark", false)).toBe("light");
    expect(toggleChoice("light", false)).toBe("dark");
  });
});
