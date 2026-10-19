import { useState } from "react";
import { request } from "../api";
import type { DrugCandidate, MedicationInput } from "./types";

const SCOPE_TEXT = {
  in_scope: "在評估範圍內",
  out_of_scope: "不在本系統評估範圍",
  unconfirmed: "無法確認",
} as const;

type Props = {
  medications: MedicationInput[];
  busy: boolean;
  onChange: (medications: MedicationInput[]) => void;
  onNext: () => void;
};

/** 用藥步驟：搜尋藥名 → 從候選加入，或自由輸入；也可以直接按「我沒有用藥」略過。 */
export default function MedicationStep({ medications, busy, onChange, onNext }: Props) {
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState<DrugCandidate[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async () => {
    setError(null);
    try {
      const found = await request<DrugCandidate[]>(
        "GET",
        `/api/assessments/drug-search?q=${encodeURIComponent(query)}`,
      );
      setCandidates(found);
      setSearched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const add = (name: string) => {
    const trimmed = name.trim();
    if (!trimmed || medications.some((m) => m.name === trimmed)) return;
    onChange([...medications, { name: trimmed }]);
    setQuery("");
    setCandidates([]);
    setSearched(false);
  };

  return (
    <section>
      <h1>用藥</h1>
      <p>搜尋你正在吃的藥（中文名、商品名或學名皆可），從候選中加入。</p>
      {error && <p role="alert">{error}</p>}
      <form
        aria-label="搜尋藥名"
        onSubmit={(e) => {
          e.preventDefault();
          void search();
        }}
      >
        <label>
          藥名
          <input value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <button type="submit" disabled={!query.trim()}>
          搜尋
        </button>
      </form>
      {searched && (
        <div aria-label="搜尋結果">
          {candidates.length === 0 && <p>找不到符合的藥名。</p>}
          <ul>
            {candidates.map((c) => (
              <li key={c.name}>
                <strong>{c.name}</strong>（{SCOPE_TEXT[c.scope_status]}）
                {c.ingredients.length > 0 && (
                  <div>
                    有效成分：{c.ingredients.map((i) => `${i.name_zh} ${i.name_en}`).join("、")}
                  </div>
                )}
                {c.brand_names.length > 0 && <div>常見商品名：{c.brand_names.join("、")}</div>}
                <button type="button" onClick={() => add(c.name)}>
                  加入 {c.name}
                </button>
              </li>
            ))}
          </ul>
          <p>
            都不是？
            <button type="button" className="secondary" onClick={() => add(query)}>
              以「{query.trim()}」自行輸入加入
            </button>
            （系統會標示為無法確認）
          </p>
        </div>
      )}
      <h2>已加入的用藥</h2>
      <ul>
        {medications.map((m) => (
          <li key={m.name}>
            {m.name}
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => onChange(medications.filter((x) => x.name !== m.name))}
            >
              刪除 {m.name}
            </button>
          </li>
        ))}
        {medications.length === 0 && <li>尚未加入任何藥</li>}
      </ul>
      <button type="button" disabled={busy} onClick={onNext}>
        {medications.length === 0 ? "我沒有用藥" : "下一步"}
      </button>
    </section>
  );
}
