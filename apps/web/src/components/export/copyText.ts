export async function writeClipboardText(
  text: string,
  writeText: (value: string) => Promise<void>,
): Promise<void> {
  await writeText(text)
}
