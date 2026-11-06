import Explanations, { type FootnoteState } from "./Explanations";
import PhotoThumbs from "./PhotoThumbs";
import type { DrugGroup, FindingExplanation, Footnote, InteractionCard, ReportGroup, UlRow } from "./types";

type Evidence = {
  explanations: FindingExplanation[];
  footnotes: Footnote[];
  /** 同一時間只展開一則出處，狀態放在報告層。 */
  footnote: FootnoteState;
};
/** 產品名稱 → 照片編號，用來在名稱旁放縮圖。 */
export type PhotoMap = Record<string, number[] | undefined>;

function ProductNames({ names, photos }: { names: string[]; photos: PhotoMap }) {
  return (
    <>
      {names.map((n, i) => (
        <span key={n} className="product-name">
          {i > 0 && "、"}
          {n}
          <PhotoThumbs name={n} photoIds={photos[n]} />
        </span>
      ))}
    </>
  );
}

/** 一個成分的說明：審定說明、三個數值、白話解釋。 */
function NutrientDetail({ card, explanations, footnotes, footnote }: { card: InteractionCard } & Evidence) {
  return (
    <>
      {card.reasons.map((r, i) => (
        <p key={i}>{r}</p>
      ))}
      {card.values.length > 0 && (
        <dl className="vals">
          {card.values.map((v) => (
            <div key={v.label}>
              <dt>{v.label}</dt>
              <dd>{v.text}</dd>
            </div>
          ))}
        </dl>
      )}
      <Explanations
        explanations={explanations.filter((e) => e.ingredient_code === card.ingredient_code)}
        footnotes={footnotes}
        footnote={footnote}
      />
    </>
  );
}

const isConsult = (card: InteractionCard) => card.advice.some((a) => a.startsWith("合併使用前先諮詢"));

/** 手風琴卡片：收合時看得到營養素與建議行動，展開才看來源、原因、數值與白話解釋。顏色與圖示只代表建議行動（ADR-0001）。 */
function NutrientCard({ card, photos, ...evidence }: { card: InteractionCard; photos: PhotoMap } & Evidence) {
  const consult = isConsult(card);
  return (
    <details className="nutrient-card" data-testid="nutrient-card" data-action={consult ? "consult" : "inform"}>
      <summary>
        <span className="nutrient-head">
          <span className="nutrient-name">{card.ingredient}</span>
          <span className="nutrient-action">
            <span aria-hidden="true">{consult ? "⚑ " : "✎ "}</span>
            {card.advice.join("；")}
          </span>
        </span>
        <span className="chevron" aria-hidden="true">
          ›
        </span>
      </summary>
      <div className="nutrient-body" data-testid="nutrient-body">
        {card.supplemented === false ? (
          <p className="nutrient-from">你沒有補充，但這個藥可能影響體內的{card.ingredient}</p>
        ) : (
          (card.products ?? []).length > 0 && (
            <p className="nutrient-from">
              來自 <ProductNames names={card.products!} photos={photos} />
            </p>
          )
        )}
        <NutrientDetail card={card} {...evidence} />
      </div>
    </details>
  );
}

/** 以藥為主角的卡片：標題是你吃的藥，底下每個相關營養素一張手風琴卡片（#23、#54）。 */
export function DrugCard({
  group,
  cards,
  photos,
  ...evidence
}: { group: DrugGroup; cards: InteractionCard[]; photos: PhotoMap } & Evidence) {
  const mine = group.ingredient_codes
    .map((code) => cards.find((c) => c.ingredient_code === code))
    .filter((c): c is InteractionCard => c !== undefined);
  const english = group.drug_ingredients.filter((n) => n.toLowerCase() !== group.drug.toLowerCase());
  return (
    <article className="interaction-card" data-testid="interaction-card">
      <h3>
        你吃的：{group.drug}
        {english.length > 0 && `（${english.join("、")}）`}
      </h3>
      {mine.map((c) => (
        <NutrientCard key={c.ingredient_code} card={c} photos={photos} {...evidence} />
      ))}
    </article>
  );
}

/** 舊報告（沒有 drug_groups）的成分卡片。 */
export function LegacyCard({ card, ...evidence }: { card: InteractionCard } & Evidence) {
  return (
    <article className="interaction-card" data-testid="interaction-card">
      <h3>{card.ingredient}</h3>
      <p>因為你正在服用 {card.drugs.join(" 與 ")}</p>
      <p className="card-advice">建議行動：{card.advice.join("；")}</p>
      <NutrientDetail card={card} {...evidence} />
    </article>
  );
}

/** 軌道長度代表上限的 125%，上限線在 80% 的位置；填色 = 佔上限百分比 ÷ 125%，超過就畫滿。 */
const TRACK_RATIO = 1.25;
export const gaugeFill = (percent: string): number => {
  const value = parseFloat(percent);
  return Number.isFinite(value) ? Math.round(Math.min((value / 100 / TRACK_RATIO) * 100, 100) * 10) / 10 : 0;
};

/** 上限比對量表卡：每個營養素一張；沒有已知上限的不畫量表。 */
export function UlCards({ rows, photos }: { rows: UlRow[]; photos: PhotoMap }) {
  return (
    <div className="ul-cards">
      {rows.map((r) => (
        <article key={r.nutrient} className="ul-card" data-testid="ul-card" data-exceeded={r.exceeded}>
          <div className="ul-top">
            <h3>{r.nutrient}</h3>
            {r.exceeded && <span className="tag over-tag">已超過上限</span>}
          </div>
          {r.percent !== null ? (
            <div className="gauge-track" data-testid="ul-gauge" data-fill={gaugeFill(r.percent)}>
              <i style={{ width: `${gaugeFill(r.percent)}%` }} />
              <span className="gauge-limit" />
            </div>
          ) : null}
          <dl className="ul-figures">
            <div>
              <dt>來自補充劑</dt>
              <dd>{r.intake}</dd>
            </div>
            <div>
              <dt>上限</dt>
              <dd>{r.percent === null ? "無已知上限攝取量" : r.ul}</dd>
            </div>
            {r.percent !== null && (
              <div>
                <dt>佔上限</dt>
                <dd>{r.percent}</dd>
              </div>
            )}
          </dl>
          {r.products.length > 0 && (
            <p className="ul-products">
              來自 <ProductNames names={r.products} photos={photos} />
            </p>
          )}
          {r.note && <p className="ul-note">{r.note}</p>}
        </article>
      ))}
    </div>
  );
}

/** 摘要卡（#37、#53）：有 count 的項目畫大數字，沒有（舊報告、沒有判定的說明）畫文字。內容由後端模板從判定渲染。 */
export function SummaryCard({ title, groups }: { title: string; groups: ReportGroup[] }) {
  return (
    <section className="summary-card" data-section="summary" data-testid="report-summary">
      <h2>{title}</h2>
      <div className="summary-tiles">
        {groups.map((g) => (
          <SummaryTile key={g.title} group={g} />
        ))}
      </div>
    </section>
  );
}

function SummaryTile({ group }: { group: ReportGroup }) {
  const hasCount = typeof group.count === "number";
  // 顏色只代表需要注意與否（ADR-0001：沒有嚴重度）；0 項時不上警示色
  const tone = hasCount && group.count === 0 ? "neutral" : group.tone;
  return (
    <div className="summary-tile" data-tone={tone} data-kind={hasCount ? "count" : "text"}>
      <p className="summary-title">{group.title}</p>
      {hasCount && <p className="summary-count">{group.count}</p>}
      {group.lines.map((line, i) => (
        <p key={i} className="summary-line">
          {line}
        </p>
      ))}
      {group.note && <p className="summary-note">{group.note}</p>}
    </div>
  );
}

/** 字卡：同一類的揭露事項放在一起，警示類用不同底色。 */
export function GroupCards({ groups }: { groups: ReportGroup[] }) {
  return (
    <div className="group-cards">
      {groups.map((g) => (
        <article key={g.title} className="group-card" data-tone={g.tone}>
          <h3>{g.title}</h3>
          <ul>
            {g.lines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}

export function Lines({ lines }: { lines: string[] }) {
  return (
    <ul>
      {lines.map((line, i) => (
        <li key={i}>{line}</li>
      ))}
    </ul>
  );
}
