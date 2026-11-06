import type { ExpectedSeconds } from "./waitingTimes";

interface Props {
  active: boolean;
  title: string;
  detail?: string;
  expected: ExpectedSeconds;
  error?: string | null;
  onRetry?: () => void;
}

/** 等待區塊：不確定進度的動畫＋預期時間；失敗時改顯示錯誤與重試。不顯示假的進度百分比。 */
export default function Waiting({ active, title, detail, expected, error, onRetry }: Props) {
  return (
    <>
      <div role="status" aria-live="polite">
        {active && (
          <div className="card waiting-card" data-testid="waiting">
            <span className="waiting-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <div>
              <p className="waiting-title">{title}</p>
              {detail && <p>{detail}</p>}
              <p className="waiting-expected">
                通常需要 {expected.min}–{expected.max} 秒，請不要關閉或離開此頁。
              </p>
            </div>
          </div>
        )}
      </div>
      {!active && error && (
        <div className="card waiting-error" role="alert" data-testid="waiting-error">
          <p>{error}</p>
          {onRetry && (
            <button type="button" onClick={onRetry}>
              重試
            </button>
          )}
        </div>
      )}
    </>
  );
}
