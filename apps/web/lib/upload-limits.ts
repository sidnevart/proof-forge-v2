// Single source of truth for client-side upload limits, shared by every surface
// that accepts files (topic materials, chat attachments, practice answers).
// Validate here BEFORE the request so the user gets an instant, clear message
// instead of a 413 (which nginx returns without CORS headers, surfacing as a
// confusing CORS error) or a generic backend rejection.

export type UploadLimit = { maxBytes: number; maxFiles: number; maxMB: number }

const mb = (n: number) => ({ maxBytes: n * 1024 * 1024, maxMB: n })

export const LIMITS = {
  // Topic materials upload as one request per file; the cap sits below nginx's
  // client_max_body_size (30m) so multipart overhead never trips a 413.
  material: { ...mb(25), maxFiles: 5 },
  // Chat attachments are base64-inflated (~33%) before going to the LLM; backend
  // enforces the same 8 MB / 5 in app/routers/chat.py.
  chatAttachment: { ...mb(8), maxFiles: 5 },
  // Practice answer attachments mirror chat limits.
  practiceAttachment: { ...mb(8), maxFiles: 5 },
} satisfies Record<string, UploadLimit>

export type ValidationResult =
  | { ok: true; accepted: File[] }
  | { ok: false; code: 'tooBig'; fileName: string }
  | { ok: false; code: 'tooMany' }

// Reject the whole batch if any file is oversized or the batch would exceed the
// count cap — partial acceptance is more confusing than a single clear refusal.
export function validateFiles(
  incoming: File[],
  existingCount: number,
  limit: UploadLimit,
): ValidationResult {
  const oversized = incoming.find((f) => f.size > limit.maxBytes)
  if (oversized) return { ok: false, code: 'tooBig', fileName: oversized.name }
  if (existingCount + incoming.length > limit.maxFiles) return { ok: false, code: 'tooMany' }
  return { ok: true, accepted: incoming }
}

// Format a failed ValidationResult into a localized message using the shared
// limit.* i18n keys, interpolating the file name and the relevant cap.
export function limitErrorMessage(
  t: (key: string) => string,
  res: Extract<ValidationResult, { ok: false }>,
  limit: UploadLimit,
): string {
  if (res.code === 'tooBig') {
    return t('limit.fileTooBig')
      .replace('{name}', res.fileName)
      .replace('{max}', String(limit.maxMB))
  }
  return t('limit.tooManyFiles').replace('{max}', String(limit.maxFiles))
}
