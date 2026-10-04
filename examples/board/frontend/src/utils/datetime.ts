const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

// 날짜와 시각은 있지만 오프셋(Z, +09:00)이 없는 형태
const NO_OFFSET_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/;

/**
 * UTC ISO 8601 문자열을 KST "YYYY-MM-DD HH:mm"으로 바꾼다. 해석할 수 없으면 입력 그대로.
 * 오프셋이 없는 입력은 UTC로 해석한다(서버 시각은 UTC이고, 실행 환경 시간대에 의존하지 않기 위함).
 */
export function formatKst(iso: string): string {
  const time = new Date(NO_OFFSET_PATTERN.test(iso) ? `${iso}Z` : iso).getTime();
  if (Number.isNaN(time)) return iso;
  const kst = new Date(time + KST_OFFSET_MS);
  const date = `${kst.getUTCFullYear()}-${pad(kst.getUTCMonth() + 1)}-${pad(kst.getUTCDate())}`;
  return `${date} ${pad(kst.getUTCHours())}:${pad(kst.getUTCMinutes())}`;
}
