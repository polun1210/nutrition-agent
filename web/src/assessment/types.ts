export const DOSE_UNITS = ["粒", "錠", "包", "匙", "毫升"] as const;
export const AMOUNT_UNITS = ["mg", "ug", "g", "IU"] as const;

export type IngredientOption = { code: string; name: string; unit: string };

export type IngredientLine = { ingredient_code: string; amount: number; unit: string };

export type Product = {
  name: string;
  dose_unit: (typeof DOSE_UNITS)[number];
  units_per_serving: number;
  ingredients: IngredientLine[];
  intake: { frequency: "daily"; times_per_day: number; units_per_time: number };
};

export type Draft = { id: number; products: Product[]; submitted_case_id: number | null };

export type ReportSection = { key: string; title: string; lines: string[] };

export type AssessmentCase = {
  id: number;
  age: number;
  report: { sections: ReportSection[] };
};
