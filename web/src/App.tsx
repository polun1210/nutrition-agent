import { useCallback, useEffect, useState } from "react";
import { fetchMe, request, type Me } from "./api";
import { HomePage, LoginPage, ProfilePage, RegisterPage } from "./pages";

type View = "home" | "profile" | "login" | "register";

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("login");

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
  return view === "profile" ? (
    <ProfilePage me={me} onSaved={() => void refresh("profile")} goHome={() => setView("home")} />
  ) : (
    <HomePage me={me} goProfile={() => setView("profile")} onLogout={() => void logout()} />
  );
}
