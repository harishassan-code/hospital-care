/** Save a file the user asked for: a temporary link to the blob is clicked, then both are dropped. */
export function saveFile(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  // Revoke after the browser has started the download, not before.
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}
