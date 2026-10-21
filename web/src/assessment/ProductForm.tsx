import { useEffect, useState, type FormEvent } from "react";
import { request } from "../api";
import {
  AMOUNT_UNITS,
  DOSE_UNITS,
  FREQUENCIES,
  MINERALS,
  type CompoundOption,
  type Frequency,
  type IngredientLine,
  type IngredientOption,
  type Product,
} from "./types";

type Props = {
  options: IngredientOption[];
  compounds: CompoundOption[];
  onAdd: (product: Product) => void;
  /** 有值 = 修改既有產品；沒有 = 新增。 */
  initial?: Product;
  onCancel?: () => void;
};

type LineDraft = {
  code: string;
  amount: string;
  unit: string;
  basis: "labeled" | "compound"; // 標示元素量／只標化合物重量
  compound: string; // 化合物代碼；"" = 不在清單內（無法判定）
  override: string | null; // 使用者覆寫推估值（mg）；null = 沿用系統推估
};

const emptyLine = (options: IngredientOption[]): LineDraft => ({
  code: options[0]?.code ?? "",
  amount: "",
  unit: options[0]?.unit ?? "mg",
  basis: "labeled",
  compound: "",
  override: null,
});

const draftFromLine = (i: IngredientLine): LineDraft => ({
  code: i.ingredient_code,
  amount: String(i.amount),
  unit: i.unit,
  basis: i.basis ?? "labeled",
  compound: i.compound_code ?? "",
  override: i.element_override_mg == null ? null : String(i.element_override_mg),
});

/** 手動新增一項保健食品：成分只能從選單挑選。 */
export default function ProductForm({ options, compounds, onAdd, initial, onCancel }: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [perServing, setPerServing] = useState(String(initial?.units_per_serving ?? 1));
  const [doseUnit, setDoseUnit] = useState<Product["dose_unit"]>(initial?.dose_unit ?? "粒");
  const [lines, setLines] = useState<LineDraft[]>(
    initial
      ? initial.ingredients.map(draftFromLine)
      : [emptyLine(options)],
  );
  const [timesPerDay, setTimesPerDay] = useState(String(initial?.intake.times_per_day ?? 1));
  const [perTime, setPerTime] = useState(String(initial?.intake.units_per_time ?? 1));
  const [frequency, setFrequency] = useState<Frequency>(initial?.intake.frequency ?? "daily");
  const [daysPerWeek, setDaysPerWeek] = useState(String(initial?.intake.days_per_week ?? 3));
  const [onDays, setOnDays] = useState(String(initial?.intake.cycle_on_days ?? 21));
  const [offDays, setOffDays] = useState(String(initial?.intake.cycle_off_days ?? 7));

  const updateLine = (index: number, patch: Partial<LineDraft>) =>
    setLines(lines.map((l, i) => (i === index ? { ...l, ...patch } : l)));

  const pickIngredient = (index: number, code: string) => {
    const option = options.find((o) => o.code === code);
    updateLine(index, { code, unit: option?.unit ?? "mg", basis: "labeled", compound: "", override: null });
  };

  // 覆寫推估值時，化合物與化合物重量照舊保留，另存覆寫的元素量，使用者之後可以還原系統推估。
  const toIngredientLine = (l: LineDraft): IngredientLine => {
    if (l.basis === "compound") {
      return {
        ingredient_code: l.code,
        amount: Number(l.amount),
        unit: l.unit,
        basis: "compound",
        compound_code: l.compound || null,
        element_override_mg: l.override !== null && l.override !== "" ? Number(l.override) : null,
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
      intake: {
        frequency,
        times_per_day: Number(timesPerDay),
        units_per_time: Number(perTime),
        days_per_week: frequency === "weekly_days" ? Number(daysPerWeek) : null,
        cycle_on_days: frequency === "cycle" ? Number(onDays) : null,
        cycle_off_days: frequency === "cycle" ? Number(offDays) : null,
      },
    });
    if (initial) return;
    setName("");
    setPerServing("1");
    setLines([emptyLine(options)]);
    setTimesPerDay("1");
    setPerTime("1");
    setFrequency("daily");
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
            {l.basis === "compound" && <EstimateField line={l} onOverride={(v) => updateLine(i, { override: v })} />}
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
      <label>
        服用頻率
        <select value={frequency} onChange={(e) => setFrequency(e.target.value as Frequency)}>
          {FREQUENCIES.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
      </label>
      <p className="hint">
        「需要時才吃」無法量化每日攝取量，所以不提供這個選項；請依你實際的規律選最接近的頻率。
      </p>
      {frequency === "weekly_days" && (
        <label>
          每週服用幾天
          <input
            type="number"
            required
            min="1"
            max="6"
            step="1"
            value={daysPerWeek}
            onChange={(e) => setDaysPerWeek(e.target.value)}
          />
        </label>
      )}
      {frequency === "cycle" && (
        <>
          <label>
            連續服用幾天
            <input type="number" required min="1" step="1" value={onDays} onChange={(e) => setOnDays(e.target.value)} />
          </label>
          <label>
            停用幾天
            <input type="number" required min="1" step="1" value={offDays} onChange={(e) => setOffDays(e.target.value)} />
          </label>
        </>
      )}
      <label>
        服用當日的次數
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
        每次幾{doseUnit}
        <input
          type="number"
          required
          min="0.01"
          step="any"
          value={perTime}
          onChange={(e) => setPerTime(e.target.value)}
        />
      </label>
      <button type="submit">{initial ? "儲存修改" : "加入這項保健食品"}</button>
      {onCancel && (
        <button type="button" className="secondary" onClick={onCancel}>
          取消修改
        </button>
      )}
    </form>
  );
}

/** 推估元素量：數值由後端計算（與送出時同一套），不同底色標示「推估」，可覆寫（覆寫後視為使用者提供的值）。 */
function EstimateField({
  line,
  onOverride,
}: {
  line: LineDraft;
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
function useEstimate(line: LineDraft): number | null {
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
