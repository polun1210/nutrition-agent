import { useEffect, useState } from "react";
import { request, type Me, type Profile } from "../api";
import ProfileFields from "../ProfileFields";
import ProductForm from "./ProductForm";
import ReportView from "./ReportView";
import type { AssessmentCase, CompoundOption, Draft, IngredientOption, Product } from "./types";

/** 步驟條。之後的票（用藥等）在陣列中插入新步驟即可。 */
const STEPS = [
  { key: "profile", label: "個人資料" },
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

type Props = { me: Me; onProfileSaved: () => void; goHome: () => void };

export default function AssessmentFlow({ me, onProfileSaved, goHome }: Props) {
  const [step, setStep] = useState<StepKey>("profile");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [options, setOptions] = useState<IngredientOption[]>([]);
  const [compounds, setCompounds] = useState<CompoundOption[]>([]);
  const [report, setReport] = useState<AssessmentCase | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [profile, setProfile] = useState<Profile>(me.profile);

  useEffect(() => {
    void (async () => {
      try {
        setDraft(await request<Draft>("POST", "/api/assessments/drafts"));
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

  const saveProducts = (products: Product[]) =>
    guarded(async () => {
      if (!draft) return;
      setDraft(await request<Draft>("PUT", `/api/assessments/drafts/${draft.id}`, { products }));
    });

  const saveProfileAndNext = () =>
    guarded(async () => {
      if (profile.conditions.length === 0) throw new Error("請回答已知疾病，沒有請勾「以上皆無」");
      await request("PUT", "/api/me/profile", profile);
      onProfileSaved();
      setStep("supplements");
    });

  const submit = () =>
    guarded(async () => {
      if (!draft) return;
      const { id } = await request<{ id: number }>("POST", `/api/assessments/drafts/${draft.id}/submit`);
      setReport(await request<AssessmentCase>("GET", `/api/assessments/${id}`));
    });

  if (report) return <ReportView report={report} goHome={goHome} />;

  const products = draft?.products ?? [];
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
      {step === "supplements" && (
        <section>
          <h1>保健食品</h1>
          <ul>
            {products.map((p, i) => (
              <li key={i}>
                {p.name}
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
          </ul>
          <ProductForm options={options} compounds={compounds} onAdd={(p) => void saveProducts([...products, p])} />
          <button type="button" disabled={products.length === 0 || busy} onClick={() => setStep("submit")}>
            下一步
          </button>
        </section>
      )}
      {step === "submit" && (
        <section>
          <h1>送出評估</h1>
          <p>共 {products.length} 項保健食品。送出後會產生報告，且評估內容無法再修改。</p>
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
