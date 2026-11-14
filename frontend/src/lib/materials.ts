/** How each IFC class looks in the 3D viewer. Monochrome, per DESIGN.md. */

export type MaterialRole = "space" | "glass" | "marker" | "fixture" | "solid";

const ROLES: Record<string, MaterialRole> = {
  IfcSpace: "space",
  IfcWindow: "glass",
  IfcDoor: "marker", // drawings place doors as a floor marker; IFC uploads have real doors
  IfcSanitaryTerminal: "fixture",
  IfcFlowTerminal: "fixture",
  IfcFurniture: "fixture",
  IfcFurnishingElement: "fixture",
  IfcBuildingElementProxy: "fixture",
};

export function materialRole(ifcClass: string): MaterialRole {
  return ROLES[ifcClass] ?? "solid";
}

/** Translucent roles are drawn without edges and without writing depth. */
export function isTranslucent(role: MaterialRole): boolean {
  return role === "space" || role === "glass";
}
