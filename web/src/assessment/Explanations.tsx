import { useEffect, useState } from "react";
import { flushSync } from "react-dom";
import type { FindingExplanation, Footnote } from "./types";

const TEMPLATE_NOTE = "AI 白話解釋暫時無法提供，上方為已審定的說明文字。";

/** 報告層的出處展開狀態：同一時間只展開一則，key 是「成分:句子:編號」。 */
export type FootnoteState = { open: string | null; toggle: (key: string) => void };

export function useFootnoteState(): FootnoteState {
  const [open, setOpen] = useState<string | null>(null);
  return { open, toggle: (key) => setOpen((cur) => (cur === key ? null : key)) };
}

/** 列印期間為 true：此時所有出處都展開。 */
function usePrinting(): boolean {
  const [printing, setPrinting] = useState(false);
  useEffect(() => {
    // beforeprint 要同步更新畫面，瀏覽器才會印到展開後的內容
    const on = () => flushSync(() => setPrinting(true));
    const off = () => setPrinting(false);
    window.addEventListener("beforeprint", on);
    window.addEventListener("afterprint", off);
    return () => {
      window.removeEventListener("beforeprint", on);
      window.removeEventListener("afterprint", off);
    };
  }, []);
  return printing;
}

function Quote({ footnote }: { footnote: Footnote }) {
  return (
    <span className="quote" data-testid="footnote-detail">
      <strong>
        出處 {footnote.number}・{footnote.source_label}：{footnote.document_name}（{footnote.section}）
      </strong>
      <span className="quote-text">{footnote.text}</span>
    </span>
  );
}

/** 白話解釋：每句後面是出處編號，點開在該句下方就地展開證據段落原文。解釋在送出時就凍結，這裡只呈現。 */
export default function Explanations({
  explanations,
  footnotes,
  footnote,
}: {
  explanations: FindingExplanation[];
  footnotes: Footnote[];
  footnote: FootnoteState;
}) {
  const printing = usePrinting();
  if (explanations.length === 0) return null;
  return (
    <div className="talk" data-testid="explanations">
      <b>白話解釋</b>
      {explanations.map((e) =>
        e.source === "template" ? (
          <p key={e.ingredient_code}>{TEMPLATE_NOTE}</p>
        ) : (
          <p key={e.ingredient_code}>
            {e.sentences.map((s, i) => {
              const shown = s.footnotes
                .map((n) => ({ n, key: `${e.ingredient_code}:${i}:${n}` }))
                .filter(({ key }) => printing || footnote.open === key);
              return (
                <span key={i}>
                  {s.text}
                  {s.footnotes.map((n) => {
                    const key = `${e.ingredient_code}:${i}:${n}`;
                    return (
                      <button
                        key={n}
                        type="button"
                        className="footnote-ref"
                        aria-expanded={footnote.open === key}
                        aria-label={`腳註 ${n}`}
                        onClick={() => footnote.toggle(key)}
                      >
                        {n}
                      </button>
                    );
                  })}
                  {shown.map(({ n, key }) => {
                    const f = footnotes.find((x) => x.number === n);
                    return f ? <Quote key={key} footnote={f} /> : null;
                  })}
                </span>
              );
            })}
          </p>
        ),
      )}
    </div>
  );
}
