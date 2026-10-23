import { FREQUENCIES, type Frequency, type Intake } from "./types";

/** 服用方式表單草稿：數值欄位用字串，送出前才轉成 Intake。 */
export type IntakeDraft = {
  frequency: Frequency;
  timesPerDay: string;
  perTime: string;
  daysPerWeek: string;
  onDays: string;
  offDays: string;
};

export const intakeDraftFrom = (intake?: Intake): IntakeDraft => ({
  frequency: intake?.frequency ?? "daily",
  timesPerDay: String(intake?.times_per_day ?? 1),
  perTime: String(intake?.units_per_time ?? 1),
  daysPerWeek: String(intake?.days_per_week ?? 3),
  onDays: String(intake?.cycle_on_days ?? 21),
  offDays: String(intake?.cycle_off_days ?? 7),
});

export const toIntake = (d: IntakeDraft): Intake => ({
  frequency: d.frequency,
  times_per_day: Number(d.timesPerDay),
  units_per_time: Number(d.perTime),
  days_per_week: d.frequency === "weekly_days" ? Number(d.daysPerWeek) : null,
  cycle_on_days: d.frequency === "cycle" ? Number(d.onDays) : null,
  cycle_off_days: d.frequency === "cycle" ? Number(d.offDays) : null,
});

type Props = { value: IntakeDraft; onChange: (value: IntakeDraft) => void; doseUnit: string };

/** 服用頻率與劑量欄位：手動表單與照片校對頁共用。 */
export default function IntakeFields({ value, onChange, doseUnit }: Props) {
  const set = (patch: Partial<IntakeDraft>) => onChange({ ...value, ...patch });
  return (
    <>
      <label>
        服用頻率
        <select value={value.frequency} onChange={(e) => set({ frequency: e.target.value as Frequency })}>
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
      {value.frequency === "weekly_days" && (
        <label>
          每週服用幾天
          <input
            type="number"
            required
            min="1"
            max="6"
            step="1"
            value={value.daysPerWeek}
            onChange={(e) => set({ daysPerWeek: e.target.value })}
          />
        </label>
      )}
      {value.frequency === "cycle" && (
        <>
          <label>
            連續服用幾天
            <input type="number" required min="1" step="1" value={value.onDays} onChange={(e) => set({ onDays: e.target.value })} />
          </label>
          <label>
            停用幾天
            <input type="number" required min="1" step="1" value={value.offDays} onChange={(e) => set({ offDays: e.target.value })} />
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
          value={value.timesPerDay}
          onChange={(e) => set({ timesPerDay: e.target.value })}
        />
      </label>
      <label>
        每次幾{doseUnit || "個"}
        <input
          type="number"
          required
          min="0.01"
          step="any"
          value={value.perTime}
          onChange={(e) => set({ perTime: e.target.value })}
        />
      </label>
    </>
  );
}
