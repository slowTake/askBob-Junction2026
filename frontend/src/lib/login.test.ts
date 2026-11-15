import { describe, expect, it } from "vitest";
import { gateFor, LOGGED_OUT_EVENT, loginErrorMessage, signalLoggedOut, TEAM } from "./login";

describe("gateFor", () => {
  it("asks for a login when the server requires one and the browser has none", () => {
    expect(gateFor({ required: true, authenticated: false })).toBe("login");
  });

  it("opens the app when logged in or when no login is required", () => {
    expect(gateFor({ required: true, authenticated: true })).toBe("open");
    expect(gateFor({ required: false, authenticated: true })).toBe("open");
    expect(gateFor({ required: false, authenticated: false })).toBe("open");
  });

  it("opens the app when the server cannot be asked, so its own errors show", () => {
    expect(gateFor(null)).toBe("open");
  });
});

describe("loginErrorMessage", () => {
  it("says the password is wrong only for wrong_password", () => {
    expect(loginErrorMessage("wrong_password")).toBe("That password is not right.");
  });

  it("separates an unreachable server from other failures", () => {
    expect(loginErrorMessage("network")).toBe("Cannot reach the server. Try again.");
    expect(loginErrorMessage("timeout")).toBe("Cannot reach the server. Try again.");
    expect(loginErrorMessage("internal_error")).toBe("Logging in failed. Try again.");
  });
});

describe("TEAM", () => {
  it("lists the four team members in the order the team gave", () => {
    expect(TEAM).toEqual(["Peter Nurmi", "Cristian Dohanici", "Niklas Raatikainen", "Lucio Surco"]);
  });
});

describe("signalLoggedOut", () => {
  it("fires the logged-out event on the target once", () => {
    const target = new EventTarget();
    let fired = 0;
    target.addEventListener(LOGGED_OUT_EVENT, () => fired++);
    signalLoggedOut(target);
    expect(fired).toBe(1);
  });

  it("does nothing without a window (server render, tests)", () => {
    expect(() => signalLoggedOut(undefined)).not.toThrow();
  });
});
