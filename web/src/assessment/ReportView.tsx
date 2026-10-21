import { useEffect, type ReactNode } from "react";
import { DrugCard, GroupCards, LegacyCard, Lines, UlTable } from "./ReportParts";
import type { AssessmentCase, ReportSection } from "./types";

/** 由上到下：重點（交互作用、上限、未評估成分）→ 展開才看的細節（#23）。舊報告的段落一樣照這個順序排。 */
const ORDER = ["interaction", "ul_comparison", "not_evaluated", "profile", "scope"];
const COLLAPSED = new Set(["profile", "scope"]);

const rank = (s: ReportSection) => (ORDER.includes(s.key) ? ORDER.indexOf(s.key) : ORDER.length);

function Collapsible({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section data-section={id}>
      <details className="collapsible">
        <summary>
          <h2>{title}</h2>
        </summary>
        {children}
      </details>
    </section>
  );
}

function SectionBody({ section, report }: { section: ReportSection; report: AssessmentCase }) {
  const evidence = { explanations: report.report.explanations ?? [], footnotes: report.report.footnotes ?? [] };
  const photos = Object.fromEntries(report.products.map((p) => [p.name, p.photo_ids]));
  const cards = section.cards ?? [];
  if (section.drug_groups && section.drug_groups.length > 0) {
    return (
      <>
        {section.drug_groups.map((g) => (
          <DrugCard key={g.drug} group={g} cards={cards} photos={photos} {...evidence} />
        ))}
      </>
    );
  }
  if (cards.length > 0) {
    return (
      <>
        {cards.map((c, i) => (
          <LegacyCard key={i} card={c} {...evidence} />
        ))}
      </>
    );
  }
  if (section.table && section.table.length > 0) {
    return (
      <>
        <UlTable rows={section.table} photos={photos} />
        {section.notes && section.notes.length > 0 && <Lines lines={section.notes} />}
      </>
    );
  }
  if (section.groups && section.groups.length > 0) return <GroupCards groups={section.groups} />;
  return <Lines lines={section.lines} />;
}

/** 參考資料來源：白話解釋引用的原文出處與參考資料版本。 */
function References({ report }: { report: AssessmentCase }) {
  const footnotes = report.report.footnotes ?? [];
  return (
    <Collapsible id="references" title="參考資料來源">
      {footnotes.length > 0 ? (
        <ol className="references">
          {footnotes.map((f) => (
            <li key={f.number} value={f.number}>
              {f.source_label}：{f.document_name}（{f.section}）
            </li>
          ))}
        </ol>
      ) : (
        <p>這份報告的白話解釋沒有引用外部資料。</p>
      )}
      {report.reference_versions && (
        <p data-testid="reference-versions">
          參考資料版本：
          {Object.entries(report.reference_versions)
            .map(([name, version]) => `${name} ${version}`)
            .join("、")}
        </p>
      )}
    </Collapsible>
  );
}

/** 報告：後端模板已把判定渲染成文字與表格欄位，前端只負責排版。 */
export default function ReportView({
  report,
  goHome,
  backLabel = "回首頁",
}: {
  report: AssessmentCase;
  goHome: () => void;
  backLabel?: string;
}) {
  // 列印時展開所有收合的區塊
  useEffect(() => {
    const openAll = () => document.querySelectorAll("details").forEach((d) => (d.open = true));
    window.addEventListener("beforeprint", openAll);
    return () => window.removeEventListener("beforeprint", openAll);
  }, []);

  const sections = [...report.report.sections]
    .filter((s) => s.key !== "not_evaluated" || s.lines.length > 0)
    .sort((a, b) => rank(a) - rank(b));

  return (
    <main className="page">
      <h1>評估報告</h1>
      {sections.map((s) =>
        COLLAPSED.has(s.key) ? (
          <Collapsible key={s.key} id={s.key} title={s.title}>
            <SectionBody section={s} report={report} />
          </Collapsible>
        ) : (
          <section key={s.key} data-section={s.key}>
            <h2>{s.title}</h2>
            <SectionBody section={s} report={report} />
          </section>
        ),
      )}
      <References report={report} />
      <button type="button" className="no-print" onClick={() => window.print()}>
        列印報告
      </button>
      <button type="button" className="secondary no-print" onClick={goHome}>
        {backLabel}
      </button>
    </main>
  );
}
