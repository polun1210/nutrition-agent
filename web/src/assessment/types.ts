export const DOSE_UNITS = ["粒", "錠", "包", "匙", "毫升"] as const;
export const AMOUNT_UNITS = ["mg", "ug", "g", "IU"] as const;

/** 校對頁的成分單位：目錄單位代碼（顯示用名稱見 unitLabel）。 */
export const ROW_UNITS = ["mg", "ug", "g", "IU", "mg_alpha_te", "mg_ne", "ug_dfe", "kcal"] as const;
const UNIT_LABELS: Record<string, string> = {
  mg_alpha_te: "mg α-TE",
  mg_ne: "mg NE",
  ug_dfe: "µg DFE",
  ug: "µg",
};
export const unitLabel = (unit: string) => UNIT_LABELS[unit] ?? unit;

export type IngredientOption = { code: string; name: string; unit: string };

export type IngredientLine = { ingredient_code: string; amount: number; unit: string };

export type Product = {
  name: string;
  dose_unit: (typeof DOSE_UNITS)[number];
  units_per_serving: number;
  ingredients: IngredientLine[];
  intake: { frequency: "daily"; times_per_day: number; units_per_time: number };
  photo_ids?: number[];
};

export type ScopeStatus = "in_scope" | "out_of_scope" | "unconfirmed";

/** 後端照片辨識的預填結果（已做名稱標準化與多張合併）。 */
export type Extraction = {
  product_name: string | null;
  units_per_serving: number | null;
  dose_unit: string | null;
  rows: {
    raw_name: string;
    section: "nutrition_table" | "ingredient_list" | "per_unit_note";
    amount: number | null;
    unit: string | null;
    readable: boolean;
    ingredient_code: string | null;
    scope_status: ScopeStatus;
    photo_id: number;
  }[];
  photos: { photo_id: number; readable: boolean; hint: string | null }[];
};

export type Draft = { id: number; products: Product[]; submitted_case_id: number | null };

export type ReportSection = { key: string; title: string; lines: string[] };

export type AssessmentCase = {
  id: number;
  age: number;
  products: Product[];
  report: { sections: ReportSection[] };
};
