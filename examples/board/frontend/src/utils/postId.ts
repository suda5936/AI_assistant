const POST_ID_PATTERN = /^[1-9][0-9]{0,15}$/;

/** 라우트의 글 ID 원문을 검사한다. 안전한 양의 정수면 그 수, 아니면 null. */
export function parsePostId(raw: string | undefined): number | null {
  if (raw === undefined || !POST_ID_PATTERN.test(raw)) return null;
  const value = Number(raw);
  return Number.isSafeInteger(value) ? value : null;
}
