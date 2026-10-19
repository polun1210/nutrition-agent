import { CONDITION_OPTIONS, NO_CONDITION, type Profile } from "./api";

type Props = {
  value: Profile;
  onChange: (next: Profile) => void;
};

const thisYear = new Date().getFullYear();

/** 出生年月、性別、已知疾病；「以上皆無」和慢性病互斥。 */
export default function ProfileFields({ value, onChange }: Props) {
  const toggleCondition = (condition: string, checked: boolean) => {
    if (condition === NO_CONDITION) {
      onChange({ ...value, conditions: checked ? [NO_CONDITION] : [] });
      return;
    }
    const others = value.conditions.filter((c) => c !== NO_CONDITION && c !== condition);
    onChange({ ...value, conditions: checked ? [...others, condition] : others });
  };

  return (
    <>
      <label>
        出生年
        <input
          type="number"
          required
          min={1900}
          max={thisYear}
          value={value.birth_year || ""}
          onChange={(e) => onChange({ ...value, birth_year: Number(e.target.value) })}
        />
      </label>
      <label>
        出生月
        <select
          required
          value={value.birth_month || ""}
          onChange={(e) => onChange({ ...value, birth_month: Number(e.target.value) })}
        >
          <option value="" disabled>
            請選擇
          </option>
          {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
            <option key={m} value={m}>
              {m} 月
            </option>
          ))}
        </select>
      </label>
      <fieldset>
        <legend>性別</legend>
        {(
          [
            ["female", "女"],
            ["male", "男"],
          ] as const
        ).map(([sex, label]) => (
          <label key={sex} className="choice">
            <input
              type="radio"
              name="sex"
              required
              checked={value.sex === sex}
              onChange={() => onChange({ ...value, sex })}
            />
            {label}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>已知疾病（必答，可複選）</legend>
        {CONDITION_OPTIONS.map((c) => (
          <label key={c.value} className="choice">
            <input
              type="checkbox"
              checked={value.conditions.includes(c.value)}
              onChange={(e) => toggleCondition(c.value, e.target.checked)}
            />
            {c.label}
          </label>
        ))}
        <label className="choice">
          <input
            type="checkbox"
            checked={value.conditions.includes(NO_CONDITION)}
            onChange={(e) => toggleCondition(NO_CONDITION, e.target.checked)}
          />
          以上皆無
        </label>
      </fieldset>
    </>
  );
}
