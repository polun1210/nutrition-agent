export const CONDITION_OPTIONS = [
  { value: "hypertension", label: "高血壓" },
  { value: "type2_diabetes", label: "第二型糖尿病" },
  { value: "hyperlipidemia", label: "高血脂" },
  { value: "chronic_arthritis", label: "慢性關節炎" },
  { value: "chronic_insomnia", label: "慢性失眠症" },
] as const;
export const NO_CONDITION = "none";

export type Profile = {
  birth_year: number;
  birth_month: number;
  sex: "male" | "female";
  conditions: string[];
};

export type Me = {
  id: number;
  email: string;
  profile: Profile;
  age: number;
  is_adult: boolean;
  underage_message: string | null;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "資料格式不正確，請檢查每個欄位";
  return "發生未知錯誤";
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  return send<T>(method, path, body === undefined ? undefined : JSON.stringify(body), body !== undefined);
}

/** 上傳檔案（multipart）；瀏覽器自己帶 boundary，不能手動設 Content-Type。 */
export async function upload<T>(path: string, form: FormData): Promise<T> {
  return send<T>("POST", path, form, false);
}

async function send<T>(method: string, path: string, body: BodyInit | undefined, json: boolean): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: json ? { "Content-Type": "application/json" } : undefined,
    body,
  });
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new ApiError(res.status, describe(data.detail));
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export async function fetchMe(): Promise<Me | null> {
  try {
    return await request<Me>("GET", "/api/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}
