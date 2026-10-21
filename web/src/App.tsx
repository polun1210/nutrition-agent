import { useCallback, useEffect, useState } from "react";
import { fetchMe, request, type Me } from "./api";
import AssessmentFlow from "./assessment/AssessmentFlow";
import HistoryPage from "./assessment/HistoryPage";
import { useHistoryState } from "./history";
import { HomePage, LoginPage, ProfilePage, RegisterPage } from "./pages";

type View = "home" | "profile" | "login" | "register" | "assess" | "history";

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, navigate, replaceView] = useHistoryState<View>("view", "login");
  const [copyLatest, setCopyLatest] = useState(false);

  const refresh = useCallback(async (next?: View) => {
    try {
      const current = await fetchMe();
      setMe(current);
      replaceView(current ? (next ?? "home") : "login");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [replaceView]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const logout = async () => {
    await request("POST", "/api/auth/logout");
    setMe(null);
    replaceView("login");
  };

  if (loading) return <main className="page">載入中…</main>;
  if (error) return <main className="page" role="alert">無法連線到後端：{error}</main>;

  if (!me) {
    return view === "register" ? (
      <RegisterPage onDone={() => void refresh()} goLogin={() => replaceView("login")} />
    ) : (
      <LoginPage onDone={() => void refresh()} goRegister={() => replaceView("register")} />
    );
  }
  if (view === "assess") {
    return (
      <AssessmentFlow copyFromLatest={copyLatest} me={me} onProfileSaved={() => void refresh("assess")} goHome={() => navigate("home")} />
    );
  }
  if (view === "history") return <HistoryPage goHome={() => navigate("home")} />;
  return view === "profile" ? (
    <ProfilePage me={me} onSaved={() => void refresh("profile")} goHome={() => navigate("home")} />
  ) : (
    <HomePage me={me} startAssessment={(copy) => {
        setCopyLatest(copy);
        navigate("assess");
      }}
      goHistory={() => navigate("history")} goProfile={() => navigate("profile")} onLogout={() => void logout()} />
  );
}
