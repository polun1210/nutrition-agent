/** 各等待情境的預期時間（秒）。先用估計值，之後依實測調整。 */
export interface ExpectedSeconds {
  min: number;
  max: number;
}

export const SUPPLEMENT_PHOTO_SECONDS: ExpectedSeconds = { min: 10, max: 30 };
export const MEDICATION_PHOTO_SECONDS: ExpectedSeconds = { min: 5, max: 20 };
export const SUBMIT_SECONDS: ExpectedSeconds = { min: 3, max: 10 };
