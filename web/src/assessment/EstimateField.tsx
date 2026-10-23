import { useEffect, useState } from "react";
import { request } from "../api";

/** 推估預覽需要的欄位；override 為使用者覆寫值（mg），null = 沿用系統推估。 */
export type EstimateInput = {
  code: string;
  compound: string;
  amount: string;
  unit: string;
  override: string | null;
};

/** 推估元素量：數值由後端計算（與送出時同一套），不同底色標示「推估」，可覆寫（覆寫後視為使用者提供的值）。 */
export function EstimateField({
  line,
  onOverride,
}: {
  line: EstimateInput;
  onOverride: (value: string | null) => void;
}) {
  const estimate = useEstimate(line);
  if (!line.compound) {
    return <p className="undetermined">此營養素的元素量無法判定，不會計入上限比對。</p>;
  }
  const overridden = line.override !== null;
  return (
    <label className={overridden ? "" : "estimated"}>
      元素量（mg）{overridden ? "：使用者提供" : "：推估"}
      <input
        type="number"
        min="0"
        step="any"
        aria-label="元素量"
        value={overridden ? line.override ?? "" : (estimate ?? "")}
        onChange={(e) => onOverride(e.target.value)}
      />
      {overridden && (
        <button type="button" className="secondary" onClick={() => onOverride(null)}>
          還原系統推估
        </button>
      )}
    </label>
  );
}

/** 向後端取推估預覽；輸入變動後稍等一下才送出請求，過期的回應丟掉。 */
function useEstimate(line: EstimateInput): number | null {
  const [estimate, setEstimate] = useState<number | null>(null);
  const { code, compound, amount, unit } = line;
  useEffect(() => {
    if (!compound || amount === "" || Number.isNaN(Number(amount))) {
      setEstimate(null);
      return;
    }
    let stale = false;
    const timer = setTimeout(() => {
      request<{ element_mg: number | null }>("POST", "/api/assessments/estimate", {
        ingredient_code: code,
        compound_code: compound,
        amount: Number(amount),
        unit,
      })
        .then((r) => !stale && setEstimate(r.element_mg))
        .catch(() => !stale && setEstimate(null));
    }, 200);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [code, compound, amount, unit]);
  return estimate;
}
