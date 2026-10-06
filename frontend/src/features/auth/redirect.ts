/**
 * The `next` page to return to after signing in, only if it's a path on this site.
 * "//evil.example", "/\evil.example" and "https://evil.example" are refused, so a crafted login link
 * can't send someone to another website (an open redirect).
 */
export function safeNext(next: string | null): string | null {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return null
  return next
}
