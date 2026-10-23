import { useState, type FormEvent } from "react";
import { EstimateField } from "./EstimateField";
import IntakeFields, { intakeDraftFrom, toIntake, type IntakeDraft } from "./IntakeFields";
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
  const [intake, setIntake] = useState<IntakeDraft>(intakeDraftFrom(initial?.intake));

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
      intake: toIntake(intake),
    });
    if (initial) return;
    setName("");
    setPerServing("1");
    setLines([emptyLine(options)]);
    setIntake(intakeDraftFrom());
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
      <IntakeFields value={intake} onChange={setIntake} doseUnit={doseUnit} />
      <button type="submit">{initial ? "儲存修改" : "加入這項保健食品"}</button>
      {onCancel && (
        <button type="button" className="secondary" onClick={onCancel}>
          取消修改
        </button>
      )}
    </form>
  );
}
