import { describe, expect, it, vi } from 'vitest'
import { writeClipboardText } from './copyText'

describe('writeClipboardText', () => {
  it('writes the transformed text and nothing else', async () => {
    const writeText = vi.fn(async () => undefined)
    const text = 'Ada [GİZLENDİ]\nBob [REDACTED]'
    await writeClipboardText(text, writeText)
    expect(writeText).toHaveBeenCalledOnce()
    expect(writeText).toHaveBeenCalledWith(text)
  })
})
