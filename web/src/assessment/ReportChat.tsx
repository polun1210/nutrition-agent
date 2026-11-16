import { useEffect, useRef, useState, type FormEvent } from "react";
import { request } from "../api";

type Source = { source_label: string; document_name: string; section: string; text: string };
type Message = { role: "user" | "assistant"; content: string; sources?: Source[] };

const MAX_QUESTION_CHARS = 500;
const COUNTER_WARN_AT = 450;
const FALLBACK_ERROR = "問答暫時無法使用，請稍後再試。";

function SourceList({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;
  return (
    <details className="chat-sources">
      <summary>來源（{sources.length}）</summary>
      <ol>
        {sources.map((s, i) => (
          <li key={i}>
            <strong>
              {s.source_label}：{s.document_name}（{s.section}）
            </strong>
            <p>{s.text}</p>
          </li>
        ))}
      </ol>
    </details>
  );
}

/**
 * 報告問答：右下角浮動按鈕＋底部半屏面板。
 * 對話只放在這個元件的 state：收起面板時保留，離開報告頁（元件卸載）就清掉，不存瀏覽器儲存空間。
 */
export default function ReportChat({ caseId }: { caseId: number }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [open, messages, pending, error]);

  const question = draft.trim();
  const canSend = question.length > 0 && !pending;

  async function send(e: FormEvent) {
    e.preventDefault();
    if (!canSend) return;
    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages([...messages, { role: "user", content: question }]);
    setDraft("");
    setPending(true);
    setError(null);
    try {
      const res = await request<{ answer: string; sources: Source[] }>("POST", `/api/assessments/${caseId}/chat`, {
        question,
        history,
      });
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer, sources: res.sources }]);
    } catch (err) {
      setMessages((prev) => prev.slice(0, -1)); // 失敗：移除這則提問，輸入內容還給使用者
      setDraft(question);
      setError(err instanceof Error && err.message ? err.message : FALLBACK_ERROR);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="no-print">
      {!open && (
        <button type="button" className="chat-fab" onClick={() => setOpen(true)} aria-label="開啟報告問答">
          問答
        </button>
      )}
      {open && (
        <section className="chat-panel" role="dialog" aria-label="報告問答">
          <header className="chat-head">
            <h2>問這份報告</h2>
            <button type="button" className="secondary chat-close" onClick={() => setOpen(false)} aria-label="關閉問答">
              關閉
            </button>
          </header>
          <div className="chat-log" ref={logRef} aria-live="polite">
            {messages.length === 0 && <p className="hint">可以問報告裡的任何內容，例如「為什麼這個藥跟這個成分有關？」</p>}
            {messages.map((m, i) => (
              <div key={i} className={`chat-bubble ${m.role}`}>
                <p>{m.content}</p>
                {m.sources && <SourceList sources={m.sources} />}
              </div>
            ))}
            {pending && <div className="chat-bubble assistant pending">思考中…</div>}
          </div>
          {error && (
            <p className="chat-error" role="alert">
              {error}
            </p>
          )}
          <form className="chat-form" onSubmit={send}>
            <input
              type="text"
              value={draft}
              maxLength={MAX_QUESTION_CHARS}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="輸入你的問題"
              aria-label="問題"
            />
            <span
              className={`chat-counter${draft.length >= COUNTER_WARN_AT ? " near-limit" : ""}`}
              role={draft.length >= MAX_QUESTION_CHARS ? "status" : undefined}
            >
              {draft.length}/{MAX_QUESTION_CHARS}
              {draft.length >= MAX_QUESTION_CHARS && "（已達上限）"}
            </span>
            <button type="submit" disabled={!canSend}>
              {pending ? "思考中…" : "送出"}
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
