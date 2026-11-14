/** The agent's answer text as blocks the chat can lay out: a summary, group headings and
 * bullet lists. Pure; the answer is rendered as elements, never as HTML. Plain answers
 * from older answers stay one paragraph. */

export type AnswerBlock =
  | { type: "p"; text: string }
  | { type: "heading"; text: string }
  | { type: "list"; items: string[] };

const BULLET = /^[-•*]\s+/;
const MAX_HEADING = 48; // "Lower floor:" is a heading; a sentence ending in ":" is not

export function answerBlocks(text: string): AnswerBlock[] {
  const blocks: AnswerBlock[] = [];
  let paragraph: string[] = [];
  let list: string[] | null = null;

  const endParagraph = () => {
    if (paragraph.length) blocks.push({ type: "p", text: paragraph.join(" ") });
    paragraph = [];
  };
  const endList = () => {
    if (list?.length) blocks.push({ type: "list", items: list });
    list = null;
  };

  for (const raw of text.split("\n")) {
    const line = raw.trim().replace(/\*\*(.+?)\*\*/g, "$1");
    if (line === "") {
      endParagraph();
      endList();
    } else if (BULLET.test(line)) {
      endParagraph();
      (list ??= []).push(line.replace(BULLET, ""));
    } else if (line.endsWith(":") && line.length <= MAX_HEADING) {
      endParagraph();
      endList();
      blocks.push({ type: "heading", text: line.slice(0, -1) });
    } else {
      endList();
      paragraph.push(line);
    }
  }
  endParagraph();
  endList();
  return blocks;
}
