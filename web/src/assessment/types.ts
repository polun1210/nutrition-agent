export const DOSE_UNITS = ["粒", "錠", "包", "匙", "毫升"] as const;
export const AMOUNT_UNITS = ["mg", "ug", "g", "IU"] as const;

export type IngredientOption = { code: string; name: string; unit: string };

export type IngredientLine = { ingredient_code: string; amount: number; unit: string };

export type Product = {
  name: string;
  dose_unit: (typeof DOSE_UNITS)[number];
  units_per_serving: number;
  ingredients: IngredientLine[];
  intake: Intake;
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
  reference_versions?: Record<string, string>;
  report: { sections: ReportSection[] };
};
