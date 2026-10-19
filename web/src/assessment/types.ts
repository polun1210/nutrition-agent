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

export type CompoundOption = { code: string; nutrient_code: string; name: string; element_ratio: number };

/** 只標化合物重量時可選「化合物」的礦物質；鋅不在比率表內，會被判定為無法判定。 */
export const MINERALS = ["calcium", "magnesium", "iron", "zinc"] as const;

export type IngredientLine = {
  ingredient_code: string;
  amount: number;
  unit: string;
  basis?: "labeled" | "compound";
  compound_code?: string | null;
};

export type Product = {
  name: string;
  dose_unit: (typeof DOSE_UNITS)[number];
  units_per_serving: number;
  ingredients: IngredientLine[];
  intake: Intake;
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

export const FREQUENCIES = [
  { value: "daily", label: "每天" },
  { value: "every_other_day", label: "每兩天" },
  { value: "weekly_days", label: "每週指定天數" },
  { value: "cycle", label: "週期性服用／停用" },
] as const;

export type Frequency = (typeof FREQUENCIES)[number]["value"];

export type Intake = {
  frequency: Frequency;
  times_per_day: number;
  units_per_time: number;
  days_per_week?: number | null;
  cycle_on_days?: number | null;
  cycle_off_days?: number | null;
};

export type MedicationInput = { name: string };

export type DrugIngredient = {
  code: string;
  name_en: string;
  name_zh: string;
  class_code: string;
  class_name_zh: string;
};

export type DrugCandidate = {
  name: string;
  scope_status: "in_scope" | "out_of_scope" | "unconfirmed";
  name_zh: string | null;
  ingredients: DrugIngredient[];
  out_of_scope_names: string[];
  brand_names: string[];
};

export type Draft = {
  id: number;
  products: Product[];
  medications: MedicationInput[];
  submitted_case_id: number | null;
};

export type ReportSection = { key: string; title: string; lines: string[] };

export type HistoryItem = {
  id: number;
  created_at: string;
  assessed_on: string;
  product_count: number;
  medication_count: number;
  reference_versions: Record<string, string>;
};

export type AssessmentCase = {
  id: number;
  age: number;
  products: Product[];
  reference_versions?: Record<string, string>;
  report: { sections: ReportSection[] };
};
