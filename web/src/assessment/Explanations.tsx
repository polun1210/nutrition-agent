import { useState } from "react";
import type { FindingExplanation, Footnote } from "./types";

const TEMPLATE_NOTE = "AI 白話解釋暫時無法提供，上方為已審定的說明文字。";

/** 白話解釋：每句後面是腳註編號，點開看證據段落原文與來源。解釋在送出時就凍結，這裡只呈現。 */
export default function Explanations({
  explanations,
  footnotes,
}: {
  explanations: FindingExplanation[];
  footnotes: Footnote[];
}) {
  const [open, setOpen] = useState<number | null>(null);
  if (explanations.length === 0) return null;
  const opened = footnotes.find((f) => f.number === open);
  return (
    <div className="explanations" data-testid="explanations">
      <h3>白話解釋</h3>
      {explanations.map((e) =>
        e.source === "template" ? (
          <p key={e.ingredient_code}>{TEMPLATE_NOTE}</p>
        ) : (
          <p key={e.ingredient_code}>
            {e.sentences.map((s, i) => (
              <span key={i}>
                {s.text}
                {s.footnotes.map((n) => (
                  <button
                    key={n}
                    type="button"
                    className="footnote-ref"
                    aria-expanded={open === n}
                    aria-label={`腳註 ${n}`}
                    onClick={() => setOpen(open === n ? null : n)}
                  >
                    [{n}]
                  </button>
                ))}
              </span>
            ))}
          </p>
        ),
      )}
      {opened && (
        <aside className="footnote-detail" data-testid="footnote-detail">
          <strong>
            [{opened.number}] {opened.source_label}：{opened.document_name}（{opened.section}）
          </strong>
          <blockquote>{opened.text}</blockquote>
        </aside>
      )}
    </div>
  );
}
