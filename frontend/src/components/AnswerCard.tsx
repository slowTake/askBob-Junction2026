import type { Citation } from "../api/types";
import type { Turn } from "../hooks/useAsk";
import { describeStep } from "../lib/steps";

interface Props {
  turn: Turn;
  latest: boolean;
  onCitation: (citation: Citation) => void;
}

/** The latest answer is the black, polarity-flipped card; older ones are white. */
export function AnswerCard({ turn, latest, onCitation }: Props) {
  const { answer, error, steps, pending } = turn;
  return (
    <article className={`answer-card${latest ? " is-latest" : ""}`}>
      <p className="question">{turn.question}</p>

      {pending && !answer && (
        <ul className="steps">
          {steps.length === 0 && <li>Thinking…</li>}
          {steps.map((s, i) => (
            <li key={i}>{describeStep(s.tool, s.input)}</li>
          ))}
        </ul>
      )}

      {error && <p className="error-text">{error.message}</p>}

      {answer && (
        <>
          <div className="chip-row">
            <span className={`badge ${answer.verified ? "badge-solid" : "badge-outline"}`}>
              {answer.verified ? "Verified sources" : "Not verified"}
            </span>
            <span className="badge badge-outline">{answer.confidence} confidence</span>
            {answer.cached && <span className="badge badge-outline">cached</span>}
          </div>
          <p className="answer-text">{answer.answer}</p>
          {answer.citations.length > 0 && (
            <div className="chip-row">
              {answer.citations.map((c, i) => (
                <button
                  key={i}
                  type="button"
                  className={`citation${c.verified ? "" : " is-unverified"}`}
                  onClick={() => onCitation(c)}
                  title={c.verified ? "Show on drawing" : "This citation could not be verified"}
                >
                  {i + 1}. {c.note || "source"}
                </button>
              ))}
            </div>
          )}
          {answer.caveats && <p className="caveats">{answer.caveats}</p>}
        </>
      )}
    </article>
  );
}
