import { useState, type ChangeEvent } from "react";
import { upload } from "../api";
import PhotoThumbs from "./PhotoThumbs";
import {
  DOSE_UNITS,
  ROW_UNITS,
  unitLabel,
  type Extraction,
  type IngredientOption,
  type Product,
} from "./types";

type Props = { draftId: number; options: IngredientOption[]; onAdd: (product: Product) => void };

type Row = {
  key: number;
  rawName: string;
  code: string;
  amount: string;
  unit: string;
};

type Review = {
  name: string;
  perServing: string;
  doseUnit: string;
  rows: Row[];
  /** 範圍外成分：校對頁不顯示，照樣加入產品，報告列為「本系統未評估」。 */
  outOfScope: Product["ingredients"];
  otherIngredients: string[];
  photos: Extraction["photos"];
};

type ExtractedRow = Extraction["rows"][number];

const UNKNOWN = "unknown";

/** 成分欄上沒有含量的列只是列出配料，不進入評估。 */
const isListedOnly = (r: ExtractedRow) => r.section === "ingredient_list" && r.amount === null;

function toReview(result: Extraction): Review {
  // 熱量、蛋白質這類營養標示欄位不是成分，直接不顯示（#22）
  const rows = result.rows.filter((r) => !r.nutrition_fact && !isListedOnly(r));
  const outOfScope = rows.filter((r) => r.scope_status === "out_of_scope");
  return {
    name: result.product_name ?? "",
    perServing: result.units_per_serving?.toString() ?? "",
    doseUnit: result.dose_unit ?? "",
    rows: rows
      .filter((r) => r.scope_status !== "out_of_scope")
      .map((r, key) => ({
        key,
        rawName: r.raw_name,
        code: r.ingredient_code ?? UNKNOWN,
        amount: r.amount?.toString() ?? "",
        unit: r.unit ?? "mg",
      })),
    outOfScope: outOfScope.map((r) => ({ ingredient_code: r.ingredient_code ?? UNKNOWN, amount: r.amount ?? 0, unit: r.unit ?? "mg" })),
    otherIngredients: result.rows.filter((r) => !r.nutrition_fact && isListedOnly(r)).map((r) => r.raw_name),
    photos: result.photos,
  };
}

/** 用照片新增一項保健食品：上傳 → 辨識中 → 校對（整瓶看過確認一次）→ 加入。 */
export default function PhotoProductForm({ draftId, options, onAdd }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [keptIds, setKeptIds] = useState<number[]>([]); // 已辨識且讀得到、重傳時沿用的照片
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [timesPerDay, setTimesPerDay] = useState("1");
  const [perTime, setPerTime] = useState("1");

  const recognize = async () => {
    setError(null);
    setBusy(true);
    try {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      keptIds.forEach((id) => form.append("photo_ids", String(id)));
      const result = await upload<Extraction>(`/api/assessments/drafts/${draftId}/photos`, form);
      setKeptIds(result.photos.filter((p) => p.readable).map((p) => p.photo_id));
      setFiles([]);
      setReview(toReview(result));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onPick = (e: ChangeEvent<HTMLInputElement>) => setFiles(Array.from(e.target.files ?? []));

  const patchRow = (key: number, patch: Partial<Row>) =>
    review && setReview({ ...review, rows: review.rows.map((r) => (r.key === key ? { ...r, ...patch } : r)) });

  const addRow = () =>
    review &&
    setReview({
      ...review,
      rows: [
        ...review.rows,
        {
          key: Math.max(-1, ...review.rows.map((r) => r.key)) + 1,
          rawName: "",
          code: options[0]?.code ?? UNKNOWN,
          amount: "",
          unit: options[0]?.unit ?? "mg",
        },
      ],
    });

  const reset = () => {
    setReview(null);
    setFiles([]);
    setKeptIds([]);
    setError(null);
  };

  const add = () => {
    if (!review) return;
    if (!review.name.trim()) return setError("請填寫產品名稱（只用來顯示）");
    if (!review.perServing || !review.doseUnit) return setError("請填寫每份量與劑型單位");
    const missing = review.rows.find((r) => r.amount === "" || Number(r.amount) < 0);
    if (missing) return setError(`「${missing.rawName || "新增的列"}」還沒有含量，請填寫，或刪除這一列`);
    onAdd({
      name: review.name.trim(),
      dose_unit: review.doseUnit as Product["dose_unit"],
      units_per_serving: Number(review.perServing),
      ingredients: [
        ...review.rows.map((r) => ({ ingredient_code: r.code, amount: Number(r.amount), unit: r.unit })),
        ...review.outOfScope,
      ],
      intake: { frequency: "daily", times_per_day: Number(timesPerDay), units_per_time: Number(perTime) },
      photo_ids: review.photos.map((p) => p.photo_id),
    });
    reset();
  };

  const unreadable = review?.photos.map((p, i) => ({ ...p, index: i + 1 })).filter((p) => !p.readable) ?? [];

  return (
    <section aria-label="用照片新增">
      <h2>用照片新增</h2>
      <p>請拍成分欄與營養標示，同一項產品可以選多張。</p>
      <label>
        標示照片
        <input type="file" accept="image/*" multiple onChange={onPick} />
      </label>
      <button type="button" disabled={busy || (files.length === 0 && keptIds.length === 0)} onClick={() => void recognize()}>
        {busy ? "辨識中…" : "開始辨識"}
      </button>
      {error && <p role="alert">{error}</p>}
      {unreadable.map((p) => (
        <p key={p.photo_id} role="alert">
          第 {p.index} 張照片：{p.hint} 請重新選擇照片後再按「開始辨識」。
        </p>
      ))}
      {review && (
        <form
          aria-label="校對辨識結果"
          onSubmit={(e) => {
            e.preventDefault();
            add();
          }}
        >
          <p>以下是照片上讀到的營養素，請對照包裝看過一遍，有錯就直接修改，最後按下方按鈕確認。</p>
          <PhotoThumbs name={review.name || "這項產品"} photoIds={review.photos.map((p) => p.photo_id)} />
          <label>
            產品名稱
            <input
              required
              value={review.name}
              placeholder={review.name ? undefined : "包裝上讀不到品名，請自己取一個名字"}
              onChange={(e) => setReview({ ...review, name: e.target.value })}
            />
          </label>
          <label>
            每份量
            <input
              type="number"
              required
              min="0.01"
              step="any"
              value={review.perServing}
              onChange={(e) => setReview({ ...review, perServing: e.target.value })}
            />
          </label>
          <label>
            劑型單位
            <select required value={review.doseUnit} onChange={(e) => setReview({ ...review, doseUnit: e.target.value })}>
              <option value="">請選擇</option>
              {DOSE_UNITS.map((u) => (
                <option key={u}>{u}</option>
              ))}
            </select>
          </label>
          <fieldset>
            <legend>辨識到的成分</legend>
            {review.rows.map((r) => (
              <div key={r.key} className="ingredient-row" data-unknown={r.code === UNKNOWN}>
                {r.rawName && <p>包裝上寫：{r.rawName}</p>}
                {r.code === UNKNOWN && <p className="undetermined">系統認不出這個名稱。如果它是營養素，請從選單改選；不是的話可以刪除。</p>}
                <label>
                  成分
                  <select
                    aria-label="成分"
                    value={r.code}
                    onChange={(e) => patchRow(r.key, { code: e.target.value })}
                  >
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
                    aria-label="含量"
                    type="number"
                    min="0"
                    step="any"
                    value={r.amount}
                    onChange={(e) => patchRow(r.key, { amount: e.target.value })}
                  />
                </label>
                <label>
                  單位
                  <select aria-label="單位" value={r.unit} onChange={(e) => patchRow(r.key, { unit: e.target.value })}>
                    {(ROW_UNITS as readonly string[]).includes(r.unit) ? null : <option value={r.unit}>{r.unit}</option>}
                    {ROW_UNITS.map((u) => (
                      <option key={u} value={u}>
                        {unitLabel(u)}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setReview({ ...review, rows: review.rows.filter((x) => x.key !== r.key) })}
                >
                  刪除這一列
                </button>
              </div>
            ))}
            <button type="button" className="secondary" onClick={addRow}>
              新增漏掉的成分列
            </button>
          </fieldset>
          {review.otherIngredients.length > 0 && (
            <details>
              <summary>成分欄的其他配料（{review.otherIngredients.length} 項，不進入評估）</summary>
              <p>{review.otherIngredients.join("、")}</p>
            </details>
          )}
          <p>服用方式：每天服用</p>
          <label>
            每日次數
            <input type="number" required min="1" max="24" step="1" value={timesPerDay} onChange={(e) => setTimesPerDay(e.target.value)} />
          </label>
          <label>
            每次幾{review.doseUnit || "個"}
            <input type="number" required min="0.01" step="any" value={perTime} onChange={(e) => setPerTime(e.target.value)} />
          </label>
          <button type="submit">內容都核對過了，加入這項保健食品</button>
          <button type="button" className="secondary" onClick={reset}>
            放棄這次辨識
          </button>
        </form>
      )}
    </section>
  );
}
