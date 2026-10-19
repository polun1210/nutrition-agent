import { useState, type FormEvent } from "react";
import {
  AMOUNT_UNITS,
  DOSE_UNITS,
  type IngredientLine,
  type IngredientOption,
  type Product,
} from "./types";

type Props = { options: IngredientOption[]; onAdd: (product: Product) => void };

type LineDraft = { code: string; amount: string; unit: string };

const emptyLine = (options: IngredientOption[]): LineDraft => ({
  code: options[0]?.code ?? "",
  amount: "",
  unit: options[0]?.unit ?? "mg",
});

/** 手動新增一項保健食品：成分只能從選單挑選。 */
export default function ProductForm({ options, onAdd }: Props) {
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
