import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  const html = renderToStaticMarkup(<LoginPage onLogin={() => {}} />);

  it("shows the app name, a labelled password field and a Log in button", () => {
    expect(html).toContain("askBob");
    expect(html).toContain('for="login-password"');
    expect(html).toContain('type="password"');
    expect(html).toContain(">Log in</button>");
  });

  it("names all four team members", () => {
    for (const name of ["Peter Nurmi", "Cristian Dohanici", "Niklas Raatikainen", "Lucio Surco"])
      expect(html).toContain(name);
  });

  it("disables Log in until something is typed and shows no error yet", () => {
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Log in/);
    expect(html).not.toContain('role="alert"');
  });
});
