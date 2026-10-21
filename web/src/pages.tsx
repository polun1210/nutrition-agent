import { useEffect, useState, type FormEvent } from "react";
import { request, type Me, type Profile } from "./api";
import ProfileFields from "./ProfileFields";

const EMPTY_PROFILE: Profile = { birth_year: 0, birth_month: 0, sex: "" as never, conditions: [] };

function useSubmit(action: () => Promise<void>) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };
  return { error, busy, submit };
}

export function LoginPage({ onDone, goRegister }: { onDone: () => void; goRegister: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { error, busy, submit } = useSubmit(async () => {
    await request("POST", "/api/auth/login", { email, password });
    onDone();
  });
  return (
    <main className="page">
      <h1>登入</h1>
      <form onSubmit={submit}>
        <label>
          Email
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          密碼
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={busy}>
          登入
        </button>
      </form>
      <button type="button" className="link" onClick={goRegister}>
        還沒有帳號？註冊
      </button>
    </main>
  );
}

export function RegisterPage({ onDone, goLogin }: { onDone: () => void; goLogin: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [profile, setProfile] = useState<Profile>(EMPTY_PROFILE);
  const { error, busy, submit } = useSubmit(async () => {
    if (profile.conditions.length === 0) throw new Error("請回答已知疾病，沒有請勾「以上皆無」");
    await request("POST", "/api/auth/register", { email, password, ...profile });
    onDone();
  });
  return (
    <main className="page">
      <h1>註冊</h1>
      <form onSubmit={submit}>
        <label>
          Email
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          密碼（至少 8 個字元）
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <ProfileFields value={profile} onChange={setProfile} />
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={busy}>
          註冊
        </button>
      </form>
      <button type="button" className="link" onClick={goLogin}>
        已有帳號？登入
      </button>
    </main>
  );
}

export function HomePage({
  me,
  startAssessment,
  goHistory,
  goProfile,
  onLogout,
}: {
  me: Me;
  startAssessment: (copyFromLatest: boolean) => void;
  goHistory: () => void;
  goProfile: () => void;
  onLogout: () => void;
})  {
  const [hasHistory, setHasHistory] = useState(false);
  useEffect(() => {
    request<unknown[]>("GET", "/api/assessments")
      .then((items) => setHasHistory(items.length > 0))
      .catch(() => setHasHistory(false));
  }, []);
  return (
    <main className="page">
      <h1>補對了嗎？</h1>
      <p>你好，{me.email}（{me.age} 歲）</p>
      {!me.is_adult && <p role="alert">{me.underage_message}</p>}
      <button type="button" onClick={() => startAssessment(false)} disabled={!me.is_adult} title={me.is_adult ? undefined : "未滿 19 歲無法使用"}>
        開始評估
      </button>
      {hasHistory && (
        <>
          <button type="button" className="secondary" onClick={() => startAssessment(true)} disabled={!me.is_adult}>
            沿用上次的藥和保健食品
          </button>
          <p className="hint">帶入上次的內容，可以再新增或刪除</p>
          <button type="button" className="secondary" onClick={goHistory}>
            歷史報告
          </button>
        </>
      )}
      <button type="button" className="secondary" onClick={goProfile}>
        個人資料
      </button>
      <button type="button" className="secondary" onClick={onLogout}>
        登出
      </button>
    </main>
  );
}

export function ProfilePage({ me, onSaved, goHome }: { me: Me; onSaved: () => void; goHome: () => void }) {
  const [profile, setProfile] = useState<Profile>(me.profile);
  const [saved, setSaved] = useState(false);
  const { error, busy, submit } = useSubmit(async () => {
    setSaved(false);
    if (profile.conditions.length === 0) throw new Error("請回答已知疾病，沒有請勾「以上皆無」");
    await request("PUT", "/api/me/profile", profile);
    setSaved(true);
    onSaved();
  });
  return (
    <main className="page">
      <h1>個人資料</h1>
      <form onSubmit={submit}>
        <ProfileFields value={profile} onChange={setProfile} />
        {error && <p role="alert">{error}</p>}
        {saved && <p role="status">已儲存</p>}
        <button type="submit" disabled={busy}>
          儲存
        </button>
      </form>
      <button type="button" className="secondary" onClick={goHome}>
        回首頁
      </button>
    </main>
  );
}
