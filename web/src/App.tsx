import { useCallback, useEffect, useState } from "react";
import { fetchMe, request, type Me } from "./api";
import AssessmentFlow from "./assessment/AssessmentFlow";
import HistoryPage from "./assessment/HistoryPage";
import { HomePage, LoginPage, ProfilePage, RegisterPage } from "./pages";

type View = "home" | "profile" | "login" | "register" | "assess" | "history";

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("login");
  const [copyLatest, setCopyLatest] = useState(false);

  const refresh = useCallback(async (next?: View) => {
    try {
      const current = await fetchMe();
      setMe(current);
      setView(current ? (next ?? "home") : "login");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const logout = async () => {
    await request("POST", "/api/auth/logout");
    setMe(null);
    setView("login");
  };

  if (loading) return <main className="page">載入中…</main>;
  if (error) return <main className="page" role="alert">無法連線到後端：{error}</main>;

  if (!me) {
    return view === "register" ? (
      <RegisterPage onDone={() => void refresh()} goLogin={() => setView("login")} />
    ) : (
      <LoginPage onDone={() => void refresh()} goRegister={() => setView("register")} />
    );
  }
  if (view === "assess") {
    return (
      <AssessmentFlow copyFromLatest={copyLatest} me={me} onProfileSaved={() => void refresh("assess")} goHome={() => void refresh("home")} />
    );
  }
  if (view === "history") return <HistoryPage goHome={() => setView("home")} />;
  return view === "profile" ? (
    <ProfilePage me={me} onSaved={() => void refresh("profile")} goHome={() => setView("home")} />
  ) : (
    <HomePage me={me} startAssessment={(copy) => {
        setCopyLatest(copy);
        setView("assess");
      }}
      goHistory={() => setView("history")} goProfile={() => setView("profile")} onLogout={() => void logout()} />
  );
}
