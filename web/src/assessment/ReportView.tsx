import Explanations from "./Explanations";
import PhotoThumbs from "./PhotoThumbs";
import type { AssessmentCase, FindingExplanation, Footnote, InteractionCard } from "./types";

function Card({
  card,
  explanations,
  footnotes,
}: {
  card: InteractionCard;
  explanations: FindingExplanation[];
  footnotes: Footnote[];
}) {
  return (
    <article className="interaction-card" data-testid="interaction-card">
      <h3>{card.ingredient}</h3>
      <p>因為你正在服用 {card.drugs.join(" 與 ")}</p>
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
      <p className="card-advice">建議行動：{card.advice.join("；")}</p>
      <Explanations
        explanations={explanations.filter((e) => e.ingredient_code === card.ingredient_code)}
        footnotes={footnotes}
      />
    </article>
  );
}

/** 報告：後端模板已把每段渲染成文字行，前端只負責呈現。 */
export default function ReportView({
  report,
  goHome,
  backLabel = "回首頁",
}: {
  report: AssessmentCase;
  goHome: () => void;
  backLabel?: string;
}) {
  return (
    <main className="page">
      <h1>評估報告</h1>
      {report.products.some((p) => (p.photo_ids ?? []).length > 0) && (
        <section data-section="photos">
          <h2>評估的保健食品</h2>
          <ul>
            {report.products.map((p, i) => (
              <li key={i}>
                {p.name}
                <PhotoThumbs name={p.name} photoIds={p.photo_ids} />
              </li>
            ))}
          </ul>
        </section>
      )}
      {report.report.sections.map((s) => (
        <section key={s.key} data-section={s.key}>
          <h2>{s.title}</h2>
          {s.cards && s.cards.length > 0 ? (
            s.cards.map((c, i) => (
              <Card
                key={i}
                card={c}
                explanations={report.report.explanations ?? []}
                footnotes={report.report.footnotes ?? []}
              />
            ))
          ) : (
            <ul>
              {s.lines.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          )}
        </section>
      ))}
      {report.reference_versions && (
        <p data-testid="reference-versions">
          參考資料版本：
          {Object.entries(report.reference_versions)
            .map(([name, version]) => `${name} ${version}`)
            .join("、")}
        </p>
      )}
      <button type="button" className="no-print" onClick={() => window.print()}>
        列印報告
      </button>
      <button type="button" className="secondary no-print" onClick={goHome}>
        {backLabel}
      </button>
    </main>
  );
}
