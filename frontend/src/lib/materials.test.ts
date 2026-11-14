import { describe, expect, it } from "vitest";
import { isTranslucent, materialRole } from "./materials";

describe("materialRole", () => {
  it("maps rooms, windows, doors and fixtures", () => {
    expect(materialRole("IfcSpace")).toBe("space");
    expect(materialRole("IfcWindow")).toBe("glass");
    expect(materialRole("IfcDoor")).toBe("marker");
    expect(materialRole("IfcSanitaryTerminal")).toBe("fixture");
  });

  it("treats anything else as solid building fabric", () => {
    expect(materialRole("IfcWall")).toBe("solid");
    expect(materialRole("IfcSomethingNew")).toBe("solid");
  });

  it("only rooms and glass are see-through", () => {
    expect(isTranslucent("space")).toBe(true);
    expect(isTranslucent("glass")).toBe(true);
    expect(isTranslucent("solid")).toBe(false);
  });
});
