import { useEffect, useState } from "react";
import { request, type Me, type Profile } from "../api";
import ProfileFields from "../ProfileFields";
import PhotoProductForm from "./PhotoProductForm";
import PhotoThumbs from "./PhotoThumbs";
import MedicationStep from "./MedicationStep";
import ProductForm from "./ProductForm";
import ReportView from "./ReportView";
import type {
  AssessmentCase,
  CompoundOption,
  Draft,
  IngredientOption,
  MedicationInput,
  Product,
} from "./types";

/** 步驟條。順序依 spec：個人資料 → 用藥 → 保健食品 → 送出。 */
const STEPS = [
  { key: "profile", label: "個人資料" },
  { key: "medications", label: "用藥" },
  { key: "supplements", label: "保健食品" },
  { key: "submit", label: "送出" },
] as const;
type StepKey = (typeof STEPS)[number]["key"];

function StepBar({ current }: { current: StepKey }) {
  const index = STEPS.findIndex((s) => s.key === current);
  return (
    <ol className="stepper" aria-label="評估步驟">
      {STEPS.map((s, i) => (
        <li key={s.key} aria-current={s.key === current ? "step" : undefined} className={i < index ? "done" : ""}>
          {i + 1}. {s.label}
        </li>
      ))}
    </ol>
  );
}

/** 保健食品步驟的子頁：清單 → 新增（選方式）／修改（單獨一頁）。 */
type SupplementView =
  | { kind: "list" }
  | { kind: "add"; method: "photo" | "manual" | null }
  | { kind: "edit"; index: number };

type Props = { copyFromLatest?: boolean; me: Me; onProfileSaved: () => void; goHome: () => void };

export default function AssessmentFlow({ copyFromLatest = false, me, onProfileSaved, goHome }: Props) {
  const [step, setStep] = useState<StepKey>("profile");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [supplementView, setSupplementView] = useState<SupplementView>({ kind: "list" });
  const [options, setOptions] = useState<IngredientOption[]>([]);
  const [compounds, setCompounds] = useState<CompoundOption[]>([]);
  const [report, setReport] = useState<AssessmentCase | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [profile, setProfile] = useState<Profile>(me.profile);

  useEffect(() => {
    void (async () => {
      try {
        setDraft(await request<Draft>(
            "POST",
            copyFromLatest ? "/api/assessments/drafts?copy_from=latest" : "/api/assessments/drafts",
          ));
        setOptions(await request<IngredientOption[]>("GET", "/api/assessments/ingredient-options"));
        setCompounds(await request<CompoundOption[]>("GET", "/api/assessments/compound-options"));
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, []);

  const guarded = async (action: () => Promise<void>) => {
    setError(null);
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const saveDraft = (products: Product[], medications: MedicationInput[]) =>
    guarded(async () => {
      if (!draft) return;
      setDraft(
        await request<Draft>("PUT", `/api/assessments/drafts/${draft.id}`, { products, medications }),
      );
    });

  const saveProducts = (products: Product[]) => saveDraft(products, draft?.medications ?? []);
  const addProduct = (product: Product) => {
    void saveProducts([...(draft?.products ?? []), product]);
    setSupplementView({ kind: "list" });
  };
  const saveMedications = (medications: MedicationInput[]) => saveDraft(draft?.products ?? [], medications);

  const saveProfileAndNext = () =>
    guarded(async () => {
      if (profile.conditions.length === 0) throw new Error("請回答已知疾病，沒有請勾「以上皆無」");
      await request("PUT", "/api/me/profile", profile);
      onProfileSaved();
      setStep("medications");
    });

  const submit = () =>
    guarded(async () => {
      if (!draft) return;
      const { id } = await request<{ id: number }>("POST", `/api/assessments/drafts/${draft.id}/submit`);
      setReport(await request<AssessmentCase>("GET", `/api/assessments/${id}`));
    });

  if (report) return <ReportView report={report} goHome={goHome} />;

  const products = draft?.products ?? [];
  const medications = draft?.medications ?? [];
  return (
    <main className="page">
      <StepBar current={step} />
      {error && <p role="alert">{error}</p>}
      {step === "profile" && (
        <section>
          <h1>確認個人資料</h1>
          <p>本次評估使用以下資料，需要的話可以直接修改。</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void saveProfileAndNext();
            }}
          >
            <ProfileFields value={profile} onChange={setProfile} />
            <button type="submit" disabled={busy || !draft}>
              資料正確，下一步
            </button>
          </form>
        </section>
      )}
      {step === "supplements" && supplementView.kind === "list" && (
        <section>
          <h1>保健食品</h1>
          <ul>
            {products.map((p, i) => (
              <li key={i}>
                {p.name}
                <PhotoThumbs name={p.name} photoIds={p.photo_ids} />
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => setSupplementView({ kind: "edit", index: i })}
                >
                  修改 {p.name}
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => void saveProducts(products.filter((_, j) => j !== i))}
                >
                  刪除 {p.name}
                </button>
              </li>
            ))}
            {products.length === 0 && <li>尚未加入任何保健食品</li>}
          </ul>
          <button type="button" disabled={busy || !draft} onClick={() => setSupplementView({ kind: "add", method: null })}>
            新增一項
          </button>
          <button type="button" disabled={products.length === 0 || busy} onClick={() => setStep("submit")}>
            下一步
          </button>
          <button type="button" className="secondary" onClick={() => setStep("medications")}>
            上一步
          </button>
        </section>
      )}
      {step === "supplements" && supplementView.kind === "add" && draft && (
        <section>
          <h1>新增一項保健食品</h1>
          {supplementView.method === null && (
            <div role="group" aria-label="新增方式">
              <button type="button" onClick={() => setSupplementView({ kind: "add", method: "photo" })}>
                用照片新增
              </button>
              <button type="button" onClick={() => setSupplementView({ kind: "add", method: "manual" })}>
                手動輸入
              </button>
            </div>
          )}
          {supplementView.method === "photo" && (
            <PhotoProductForm draftId={draft.id} options={options} onAdd={(p) => addProduct(p)} />
          )}
          {supplementView.method === "manual" && (
            <ProductForm options={options} compounds={compounds} onAdd={(p) => addProduct(p)} />
          )}
          <button type="button" className="secondary" onClick={() => setSupplementView({ kind: "list" })}>
            返回清單
          </button>
        </section>
      )}
      {step === "supplements" && supplementView.kind === "edit" && products[supplementView.index] && (
        <section>
          <h1>修改保健食品</h1>
          <ProductForm
            key={supplementView.index}
            options={options}
            compounds={compounds}
            initial={products[supplementView.index]}
            onAdd={(p) => {
              const index = supplementView.index;
              void saveProducts(products.map((old, j) => (j === index ? p : old)));
              setSupplementView({ kind: "list" });
            }}
            onCancel={() => setSupplementView({ kind: "list" })}
          />
        </section>
      )}
      {step === "medications" && draft && (
        <MedicationStep
          draftId={draft.id}
          medications={medications}
          busy={busy}
          onChange={(next) => void saveMedications(next)}
          onNext={() => setStep("supplements")}
        />
      )}
      {step === "submit" && (
        <section>
          <h1>送出評估</h1>
          <p>共 {products.length} 項保健食品、{medications.length} 項用藥。送出後會產生報告，且評估內容無法再修改。</p>
          <button type="button" disabled={busy} onClick={() => void submit()}>
            {busy ? "計算中…" : "送出評估"}
          </button>
          <button type="button" className="secondary" onClick={() => setStep("supplements")}>
            上一步
          </button>
        </section>
      )}
    </main>
  );
}
