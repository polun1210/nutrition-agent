import { useCallback, useEffect, useMemo, useState } from "react";

type Setter<T> = (next: T) => void;

/**
 * 把畫面狀態寫進瀏覽紀錄，讓瀏覽器的上一頁回到 app 內的前一個畫面（#21）。
 * 元件掛載時從 initial 開始並記進目前這筆紀錄；navigate 新增一筆紀錄，replace 改寫目前這筆。
 */
export function useHistoryState<T>(key: string, initial: T): [T, Setter<T>, Setter<T>] {
  const [value, setValue] = useState<T>(initial);

  useEffect(() => {
    window.history.replaceState({ ...window.history.state, [key]: initial }, "");
    const onPop = (e: PopStateEvent) => setValue((e.state?.[key] as T | undefined) ?? initial);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [key]); // initial 只在掛載時使用

  const write = useCallback(
    (method: "pushState" | "replaceState") => (next: T) => {
      window.history[method]({ ...window.history.state, [key]: next }, "");
      setValue(next);
    },
    [key],
  );
  const navigate = useMemo(() => write("pushState"), [write]);
  const replace = useMemo(() => write("replaceState"), [write]);
  return [value, navigate, replace];
}
