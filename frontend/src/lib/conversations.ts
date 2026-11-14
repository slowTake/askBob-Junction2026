/** One conversation per document: picking a document in the list shows its own chat, a
 * new upload starts an empty one, and nothing is lost by switching. Pure and immutable:
 * every change returns a new record and keeps untouched conversations as they are. */

export type Conversations<T> = Readonly<Record<string, readonly T[]>>;

const NONE: readonly never[] = [];

export function turnsOf<T>(all: Conversations<T>, key: string | null): readonly T[] {
  return (key !== null && all[key]) || NONE;
}

export function addTurn<T>(all: Conversations<T>, key: string, turn: T): Conversations<T> {
  return { ...all, [key]: [...turnsOf(all, key), turn] };
}

/** Change one turn, wherever it is: an answer may finish after the user opened another
 * document. A turn whose conversation was dropped is ignored. */
export function updateTurn<T extends { id: string }>(
  all: Conversations<T>,
  id: string,
  change: (turn: T) => T,
): Conversations<T> {
  for (const [key, turns] of Object.entries(all)) {
    const i = turns.findIndex((t) => t.id === id);
    if (i >= 0) return { ...all, [key]: turns.map((t, j) => (j === i ? change(t) : t)) };
  }
  return all;
}

export function dropConversation<T>(all: Conversations<T>, key: string): Conversations<T> {
  if (!(key in all)) return all;
  const rest = { ...all };
  delete rest[key];
  return rest;
}

/** A question in this conversation is still being answered. */
export function isBusy<T extends { pending: boolean }>(
  all: Conversations<T>,
  key: string | null,
): boolean {
  return turnsOf(all, key).some((t) => t.pending);
}

/** Changes when a question is asked, when it is answered, and when another conversation
 * is shown, but not while steps stream in. The chat scrolls to the end on each change. */
export function chatMilestone<T extends { id: string; pending: boolean }>(
  turns: readonly T[],
): string {
  const last = turns.at(-1);
  return last ? `${last.id}:${last.pending ? "asking" : "done"}` : "";
}

/** The conversation on screen: the `pinned` one (picked in the list, or asked in) while its
 * document exists, else the open document's. Pinning when asking keeps the answer in view
 * when the agent's views or a clicked source open another document. */
export function conversationShown(
  pinned: string | null,
  openId: string | null,
  documentIds: readonly string[],
): string | null {
  return pinned !== null && documentIds.includes(pinned) ? pinned : openId;
}
