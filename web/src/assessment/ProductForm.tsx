import { useState, type FormEvent } from "react";
import {
  AMOUNT_UNITS,
  DOSE_UNITS,
  FREQUENCIES,
  type Frequency,
  type IngredientLine,
  type IngredientOption,
  type Product,
} from "./types";

type Props = {
  options: IngredientOption[];
  onAdd: (product: Product) => void;
  /** 有值 = 修改既有產品；沒有 = 新增。 */
  initial?: Product;
  onCancel?: () => void;
};

type LineDraft = { code: string; amount: string; unit: string };

const emptyLine = (options: IngredientOption[]): LineDraft => ({
  code: options[0]?.code ?? "",
  amount: "",
  unit: options[0]?.unit ?? "mg",
});

/** 手動新增一項保健食品：成分只能從選單挑選。 */
export default function ProductForm({ options, onAdd, initial, onCancel }: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [perServing, setPerServing] = useState(String(initial?.units_per_serving ?? 1));
  const [doseUnit, setDoseUnit] = useState<Product["dose_unit"]>(initial?.dose_unit ?? "粒");
  const [lines, setLines] = useState<LineDraft[]>(
    initial
      ? initial.ingredients.map((i) => ({ code: i.ingredient_code, amount: String(i.amount), unit: i.unit }))
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
    updateLine(index, { code, unit: option?.unit ?? "mg" });
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const ingredients: IngredientLine[] = lines.map((l) => ({
      ingredient_code: l.code,
      amount: Number(l.amount),
      unit: l.unit,
    }));
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
            <label>
              含量
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
      <button type="submit">{initial ? "儲存修改" : "加入這項保健食品"}</button>
      {onCancel && (
        <button type="button" className="secondary" onClick={onCancel}>
          取消修改
        </button>
      )}
    </form>
  );
}
