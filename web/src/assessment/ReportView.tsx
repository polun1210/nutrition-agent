import PhotoThumbs from "./PhotoThumbs";
import type { AssessmentCase } from "./types";

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
          <ul>
            {s.lines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
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
      <button type="button" className="secondary" onClick={goHome}>
        {backLabel}
      </button>
    </main>
  );
}
