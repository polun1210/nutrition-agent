import { useEffect, useState } from "react";
import { request } from "../api";
import ReportView from "./ReportView";
import type { AssessmentCase, HistoryItem } from "./types";

/** 歷史報告：列出自己所有的評估個案，點進去看當時凍結的報告。 */
export default function HistoryPage({ goHome }: { goHome: () => void }) {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [selected, setSelected] = useState<AssessmentCase | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    request<HistoryItem[]>("GET", "/api/assessments")
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const open = async (id: number) => {
    setError(null);
    try {
      setSelected(await request<AssessmentCase>("GET", `/api/assessments/${id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  if (selected) return <ReportView report={selected} goHome={() => setSelected(null)} backLabel="回歷史列表" />;

  return (
    <main className="page">
      <h1>歷史報告</h1>
      {error && <p role="alert">{error}</p>}
      {items === null ? (
        <p>載入中…</p>
      ) : items.length === 0 ? (
        <p>還沒有評估紀錄。</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item.id}>
              <button type="button" className="secondary" onClick={() => void open(item.id)}>
                {item.assessed_on} 的評估（{item.product_count} 項保健食品、{item.medication_count} 項用藥）
              </button>
            </li>
          ))}
        </ul>
      )}
      <button type="button" className="secondary" onClick={goHome}>
        回首頁
      </button>
    </main>
  );
}
