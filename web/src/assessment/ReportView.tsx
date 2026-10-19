import type { AssessmentCase } from "./types";

/** 報告：後端模板已把每段渲染成文字行，前端只負責呈現。 */
export default function ReportView({ report, goHome }: { report: AssessmentCase; goHome: () => void }) {
  return (
    <main className="page">
      <h1>評估報告</h1>
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
      <button type="button" className="secondary" onClick={goHome}>
        回首頁
      </button>
    </main>
  );
}
