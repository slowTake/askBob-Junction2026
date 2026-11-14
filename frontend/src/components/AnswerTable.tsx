import { useState } from "react";
import type { AnswerTable as Table, Citation } from "../api/types";

interface Props {
  table: Table;
  citations: Citation[];
  onCitation: (citation: Citation) => void;
}

const PREVIEW_ROWS = 5;

/** The whole cited row opens its source; its first cell is also a native keyboard button. */
export function AnswerTable({ table, citations, onCitation }: Props) {
  const [expanded, setExpanded] = useState(false);
  const rows = expanded ? table.rows : table.rows.slice(0, PREVIEW_ROWS);
  return (
    <div className="answer-inventory">
      <div className="answer-table-scroll" tabIndex={0} role="region" aria-label="Answer details">
        <table className="answer-table">
          <thead>
            <tr>
              {table.columns.map((column, i) => (
                <th key={i} scope="col">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const source = citations[row.citation - 1];
              return (
                <tr
                  key={i}
                  className={source ? "is-actionable" : undefined}
                  onClick={source ? () => onCitation(source) : undefined}
                  title={source ? "Show on the drawing" : undefined}
                >
                  {row.cells.map((cell, j) => (
                    <td key={j}>
                      {j === 0 && source ? (
                        <button
                          className="answer-item-link"
                          type="button"
                          aria-label={`${cell || "Source"}: show on the drawing`}
                        >
                          {cell || "Show source"}
                        </button>
                      ) : (
                        cell || "—"
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {table.rows.length > PREVIEW_ROWS && (
        <button
          className="answer-expand"
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "Show fewer" : `Show all ${table.rows.length}`}
        </button>
      )}
    </div>
  );
}
