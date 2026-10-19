import { useState, type FormEvent } from "react";
import {
  AMOUNT_UNITS,
  DOSE_UNITS,
  MINERALS,
  type CompoundOption,
  type IngredientLine,
  type IngredientOption,
  type Product,
} from "./types";

type Props = {
  options: IngredientOption[];
  compounds: CompoundOption[];
  onAdd: (product: Product) => void;
};

type LineDraft = {
  code: string;
  amount: string;
  unit: string;
  basis: "labeled" | "compound"; // 標示元素量／只標化合物重量
  compound: string; // 化合物代碼；"" = 不在清單內（無法判定）
  override: string | null; // 使用者覆寫推估值（mg）；null = 沿用系統推估
};

const TO_MG: Record<string, number> = { mg: 1, g: 1000, ug: 0.001 };

/** 校對頁即時預覽；最終推估值仍由後端判定引擎計算。 */
export function estimateMg(line: LineDraft, compounds: CompoundOption[]): number | null {
  const ratio = compounds.find((c) => c.code === line.compound)?.element_ratio;
  const factor = TO_MG[line.unit];
  const amount = Number(line.amount);
  if (ratio === undefined || factor === undefined || line.amount === "" || Number.isNaN(amount)) return null;
  return Math.round(amount * factor * ratio * 100) / 100;
}

const emptyLine = (options: IngredientOption[]): LineDraft => ({
  code: options[0]?.code ?? "",
  amount: "",
  unit: options[0]?.unit ?? "mg",
  basis: "labeled",
  compound: "",
  override: null,
});

/** 手動新增一項保健食品：成分只能從選單挑選。 */
export default function ProductForm({ options, compounds, onAdd }: Props) {
  const [name, setName] = useState("");
  const [perServing, setPerServing] = useState("1");
  const [doseUnit, setDoseUnit] = useState<Product["dose_unit"]>("粒");
  const [lines, setLines] = useState<LineDraft[]>([emptyLine(options)]);
  const [timesPerDay, setTimesPerDay] = useState("1");
  const [perTime, setPerTime] = useState("1");

  const updateLine = (index: number, patch: Partial<LineDraft>) =>
    setLines(lines.map((l, i) => (i === index ? { ...l, ...patch } : l)));

  const pickIngredient = (index: number, code: string) => {
    const option = options.find((o) => o.code === code);
    updateLine(index, { code, unit: option?.unit ?? "mg", basis: "labeled", compound: "", override: null });
  };

  // 覆寫推估值後，這一行視為使用者提供的標示值。
  const toIngredientLine = (l: LineDraft): IngredientLine => {
    if (l.basis === "compound" && l.override !== null && l.override !== "") {
      return { ingredient_code: l.code, amount: Number(l.override), unit: "mg" };
    }
    if (l.basis === "compound") {
      return {
        ingredient_code: l.code,
        amount: Number(l.amount),
        unit: l.unit,
        basis: "compound",
        compound_code: l.compound || null,
      };
    }
    return { ingredient_code: l.code, amount: Number(l.amount), unit: l.unit };
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const ingredients: IngredientLine[] = lines.map(toIngredientLine);
    onAdd({
      name: name.trim(),
      dose_unit: doseUnit,
      units_per_serving: Number(perServing),
      ingredients,
      intake: { frequency: "daily", times_per_day: Number(timesPerDay), units_per_time: Number(perTime) },
    });
    setName("");
    setPerServing("1");
    setLines([emptyLine(options)]);
    setTimesPerDay("1");
    setPerTime("1");
  };

  return (
    <form onSubmit={submit} aria-label="新增保健食品">
      <label>
        產品名稱
        <input required value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        每份量
        <input
          type="number"
          required
          min="0.01"
          step="any"
          value={perServing}
          onChange={(e) => setPerServing(e.target.value)}
        />
      </label>
      <label>
        劑型單位
        <select value={doseUnit} onChange={(e) => setDoseUnit(e.target.value as Product["dose_unit"])}>
          {DOSE_UNITS.map((u) => (
            <option key={u}>{u}</option>
          ))}
        </select>
      </label>
      <fieldset>
        <legend>每份含的成分</legend>
        {lines.map((l, i) => (
          <div key={i} className="ingredient-row">
            <label>
              成分
              <select aria-label="成分" value={l.code} onChange={(e) => pickIngredient(i, e.target.value)}>
                {options.map((o) => (
                  <option key={o.code} value={o.code}>
                    {o.name}
                  </option>
                ))}
              </select>
            </label>
            {(MINERALS as readonly string[]).includes(l.code) && (
              <label>
                標示方式
                <select
                  aria-label="標示方式"
                  value={l.basis}
                  onChange={(e) =>
                    updateLine(i, { basis: e.target.value as LineDraft["basis"], compound: "", override: null })
                  }
                >
                  <option value="labeled">標示元素量</option>
                  <option value="compound">只標化合物重量</option>
                </select>
              </label>
            )}
            {l.basis === "compound" && (
              <label>
                化合物
                <select
                  aria-label="化合物"
                  value={l.compound}
                  onChange={(e) => updateLine(i, { compound: e.target.value, override: null })}
                >
                  <option value="">其他／不在清單內（無法判定）</option>
                  {compounds
                    .filter((c) => c.nutrient_code === l.code)
                    .map((c) => (
                      <option key={c.code} value={c.code}>
                        {c.name}
                      </option>
                    ))}
                </select>
              </label>
            )}
            <label>
              {l.basis === "compound" ? "化合物重量" : "含量"}
              <input
                type="number"
                required
                min="0"
                step="any"
                value={l.amount}
                onChange={(e) => updateLine(i, { amount: e.target.value })}
              />
            </label>
            <label>
              單位
              <select value={l.unit} onChange={(e) => updateLine(i, { unit: e.target.value })}>
                {AMOUNT_UNITS.map((u) => (
                  <option key={u}>{u}</option>
                ))}
              </select>
            </label>
            {l.basis === "compound" && <EstimateField line={l} compounds={compounds} onOverride={(v) => updateLine(i, { override: v })} />}
            {lines.length > 1 && (
              <button type="button" className="secondary" onClick={() => setLines(lines.filter((_, j) => j !== i))}>
                刪除這個成分
              </button>
            )}
          </div>
        ))}
        <button type="button" className="secondary" onClick={() => setLines([...lines, emptyLine(options)])}>
          再加一個成分
        </button>
      </fieldset>
      <p>服用方式：每天服用</p>
      <label>
        每日次數
        <input
          type="number"
          required
          min="1"
          max="24"
          step="1"
          value={timesPerDay}
          onChange={(e) => setTimesPerDay(e.target.value)}
        />
      </label>
      <label>
        每次幾個劑型單位
        <input
          type="number"
          required
          min="0.01"
          step="any"
          value={perTime}
          onChange={(e) => setPerTime(e.target.value)}
        />
      </label>
      <button type="submit">加入這項保健食品</button>
    </form>
  );
}

/** 推估元素量：不同底色標示「推估」，可直接覆寫（覆寫後視為使用者提供的值）。 */
function EstimateField({
  line,
  compounds,
  onOverride,
}: {
  line: LineDraft;
  compounds: CompoundOption[];
  onOverride: (value: string | null) => void;
}) {
  const estimate = estimateMg(line, compounds);
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
