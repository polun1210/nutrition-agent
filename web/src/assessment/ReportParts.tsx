import Explanations from "./Explanations";
import PhotoThumbs from "./PhotoThumbs";
import type { DrugGroup, FindingExplanation, Footnote, InteractionCard, ReportGroup, UlRow } from "./types";

type Evidence = { explanations: FindingExplanation[]; footnotes: Footnote[] };
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
function NutrientDetail({ card, explanations, footnotes }: { card: InteractionCard } & Evidence) {
  return (
    <section className="nutrient-detail">
      <h4>{card.ingredient}</h4>
      {card.reasons.map((r, i) => (
        <p key={i}>{r}</p>
      ))}
      {card.values.length > 0 && (
        <dl>
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
      />
    </section>
  );
}

const names = (cards: InteractionCard[]) => cards.map((c) => `「${c.ingredient}」`).join("、");

/** 以藥為主角的卡片：先講重點（跟哪些成分、怎麼做），後半段再放各成分的白話說明（#23）。 */
export function DrugCard({
  group,
  cards,
  photos,
  ...evidence
}: { group: DrugGroup; cards: InteractionCard[]; photos: PhotoMap } & Evidence) {
  const mine = group.ingredient_codes
    .map((code) => cards.find((c) => c.ingredient_code === code))
    .filter((c): c is InteractionCard => c !== undefined);
  const supplemented = mine.filter((c) => c.supplemented !== false);
  const affected = mine.filter((c) => c.supplemented === false);
  const english = group.drug_ingredients.filter((n) => n.toLowerCase() !== group.drug.toLowerCase());
  return (
    <article className="interaction-card" data-testid="interaction-card">
      <h3>
        你吃的：{group.drug}
        {english.length > 0 && `（${english.join("、")}）`}
      </h3>
      {supplemented.length > 0 && <p className="card-summary">與你補充的{names(supplemented)}有交互作用</p>}
      {affected.length > 0 && <p className="card-summary">可能影響你體內的{names(affected)}</p>}
      <ul className="card-points">
        {mine.map((c) => (
          <li key={c.ingredient_code}>
            <strong>{c.ingredient}</strong>
            {(c.products ?? []).length > 0 && (
              <>
                （來自 <ProductNames names={c.products!} photos={photos} />）
              </>
            )}
            ：{c.advice.join("；")}
          </li>
        ))}
      </ul>
      <div className="card-details">
        {mine.map((c) => (
          <NutrientDetail key={c.ingredient_code} card={c} {...evidence} />
        ))}
      </div>
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
      <NutrientDetail card={{ ...card, ingredient: "說明" }} {...evidence} />
    </article>
  );
}

/** 上限比對表格：範圍內、可以比對上限的營養素。 */
export function UlTable({ rows, photos }: { rows: UlRow[]; photos: PhotoMap }) {
  return (
    <table className="ul-table">
      <thead>
        <tr>
          <th scope="col">營養素</th>
          <th scope="col">來自補充劑</th>
          <th scope="col">上限</th>
          <th scope="col">佔上限</th>
        </tr>
      </thead>
      {rows.map((r) => (
        <tbody key={r.nutrient} data-exceeded={r.exceeded}>
          <tr>
            <th scope="row">
              {r.nutrient}
              {r.products.length > 0 && (
                <small>
                  <ProductNames names={r.products} photos={photos} />
                </small>
              )}
            </th>
            <td>{r.intake}</td>
            <td>{r.ul}</td>
            <td>
              {r.percent ?? "—"}
              {r.exceeded && <strong>已超過上限</strong>}
            </td>
          </tr>
          {r.note && (
            <tr className="ul-note">
              <td colSpan={4}>{r.note}</td>
            </tr>
          )}
        </tbody>
      ))}
    </table>
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
