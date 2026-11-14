import { describe, expect, it } from "vitest";
import { addTurn, dropConversation, isBusy, turnsOf, updateTurn } from "./conversations";

interface T {
  id: string;
  pending: boolean;
  text?: string;
}

const t = (id: string, pending = false): T => ({ id, pending });

describe("addTurn", () => {
  it("starts a document's conversation and appends to it, without changing the input", () => {
    const empty = {};
    const one = addTurn(empty, "docA", t("1"));
    const two = addTurn(one, "docA", t("2"));
    expect(empty).toEqual({});
    expect(one).toEqual({ docA: [t("1")] });
    expect(two).toEqual({ docA: [t("1"), t("2")] });
  });

  it("keeps each document's conversation separate", () => {
    const both = addTurn(addTurn({}, "docA", t("1")), "docB", t("2"));
    expect(both).toEqual({ docA: [t("1")], docB: [t("2")] });
  });
});

describe("updateTurn", () => {
  it("updates a turn in whichever conversation holds it", () => {
    // The answer for docA's question streams in while docB is open.
    const all = { docA: [t("1", true)], docB: [t("2")] };
    const done = updateTurn(all, "1", (turn) => ({ ...turn, pending: false, text: "4 rooms" }));
    expect(done).toEqual({ docA: [{ id: "1", pending: false, text: "4 rooms" }], docB: [t("2")] });
    expect(done.docB).toBe(all.docB); // untouched conversations keep their identity
  });

  it("changes nothing for a turn that is gone (its conversation was dropped)", () => {
    const all = { docA: [t("1")] };
    expect(updateTurn(all, "missing", (turn) => ({ ...turn, pending: true }))).toBe(all);
  });
});

describe("dropConversation", () => {
  it("forgets one document's conversation and keeps the others", () => {
    const all = { docA: [t("1")], docB: [t("2")] };
    expect(dropConversation(all, "docA")).toEqual({ docB: [t("2")] });
    expect(dropConversation(all, "nope")).toBe(all);
  });
});

describe("turnsOf and isBusy", () => {
  it("reads a document's conversation; a new document has none", () => {
    const all = { docA: [t("1"), t("2", true)] };
    expect(turnsOf(all, "docA")).toEqual([t("1"), t("2", true)]);
    expect(turnsOf(all, "docB")).toEqual([]);
    expect(turnsOf(all, null)).toEqual([]);
    expect(turnsOf(all, "docB")).toBe(turnsOf(all, null)); // one shared empty list
  });

  it("is busy while a question in that conversation is still being answered", () => {
    const all = { docA: [t("1"), t("2", true)], docB: [t("3")] };
    expect(isBusy(all, "docA")).toBe(true);
    expect(isBusy(all, "docB")).toBe(false);
    expect(isBusy(all, "docC")).toBe(false);
  });
});
