import { useEffect, useState } from "react";

type Ping = { message: string; count: number };

export default function App() {
  const [ping, setPing] = useState<Ping | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/ping", { method: "POST", signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<Ping>;
      })
      .then(setPing)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(String(err));
      });
    return () => controller.abort();
  }, []);

  return (
    <main className="page">
      <h1>補對了嗎？</h1>
      {error && <p role="alert">無法連線到後端：{error}</p>}
      {!error && !ping && <p>連線中…</p>}
      {ping && (
        <p>
          後端回應：{ping.message}（資料庫累計 {ping.count} 次）
        </p>
      )}
    </main>
  );
}
