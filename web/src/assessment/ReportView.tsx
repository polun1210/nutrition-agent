import { Fragment, useEffect, type ReactNode } from "react";
import { useFootnoteState, type FootnoteState } from "./Explanations";
import { DrugCard, GroupCards, LegacyCard, Lines, SummaryCard, UlCards } from "./ReportParts";
import type { AssessmentCase, ReportSection } from "./types";

/**
 * 由上到下：摘要（#37）→ 重點（交互作用、上限、未評估成分）→ 展開才看的細節（#23）。
 * 舊報告的段落一樣照這個順序排；舊報告沒有摘要段落，就不顯示摘要卡。
 */
const ORDER = ["summary", "interaction", "ul_comparison", "not_evaluated", "profile", "scope"];
const COLLAPSED = new Set(["profile", "scope"]);

/** 各段落標題下的操作提示；純說明怎麼看，不改判定文字。 */
const HINTS: Record<string, string> = {
  interaction: "點開每一項，看原因、數字和資料出處。",
  ul_comparison: "深色直線是上限，只算你填的保健食品。",
};

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

function SectionBody({
  section,
  report,
  footnote,
}: {
  section: ReportSection;
  report: AssessmentCase;
  footnote: FootnoteState;
}) {
  const evidence = { explanations: report.report.explanations ?? [], footnotes: report.report.footnotes ?? [], footnote };
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
        <UlCards rows={section.table} photos={photos} />
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
  const footnote = useFootnoteState();
  // 列印時展開所有收合的區塊（含營養素手風琴）；出處原文在 Explanations 內處理
  useEffect(() => {
    const openAll = () => document.querySelectorAll("details").forEach((d) => (d.open = true));
    window.addEventListener("beforeprint", openAll);
    return () => window.removeEventListener("beforeprint", openAll);
  }, []);

  const sections = [...report.report.sections]
    .filter((s) => s.key !== "not_evaluated" || s.lines.length > 0)
    .sort((a, b) => rank(a) - rank(b));

  const firstCollapsed = sections.find((s) => COLLAPSED.has(s.key))?.key;
  const summary = sections.find((s) => s.key === "summary");
  const profileLines = report.report.sections.find((s) => s.key === "profile")?.lines ?? [];
  // 「你的資料」前三行固定是年齡、性別、慢性病；只在格式吻合時放進頁首
  const who = profileLines.slice(0, 3).filter((l) => /^(年齡|性別|你勾選|你未勾選)/.test(l));

  return (
    <main className="page">
      <header className="page-hero report-hero">
        {report.assessed_on && <p className="report-date">{report.assessed_on}</p>}
        <h1>這次的評估報告</h1>
        {who.length > 0 && <p className="report-who">{who.join("　")}</p>}
        {summary && <SummaryCard title={summary.title} groups={summary.groups ?? []} />}
      </header>
      {sections.map((s) =>
        s.key === "summary" ? null : COLLAPSED.has(s.key) ? (
          <Fragment key={s.key}>
            {s.key === firstCollapsed && <p className="hint more-hint">下面三項預設收合，點標題展開。</p>}
            <Collapsible id={s.key} title={s.title}>
              <SectionBody section={s} report={report} footnote={footnote} />
            </Collapsible>
          </Fragment>
        ) : (
          <section key={s.key} data-section={s.key}>
            <h2>{s.title}</h2>
            {HINTS[s.key] && <p className="hint">{HINTS[s.key]}</p>}
            <SectionBody section={s} report={report} footnote={footnote} />
          </section>
        ),
      )}
      <References report={report} />
      <div className="report-bar no-print">
        <div className="report-bar-inner">
          <button type="button" onClick={() => window.print()}>
            列印給醫師看
          </button>
          <button type="button" className="secondary" onClick={goHome}>
            {backLabel}
          </button>
        </div>
      </div>
    </main>
  );
}
