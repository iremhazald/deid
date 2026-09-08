type Props = {
  size?: number
  className?: string
}

/**
 * DeID product mark.
 *
 * A geometric "D" whose counter holds three record lines. The middle line
 * stops short and the bowl is cut open at exactly that height, so the removal
 * passes through both the content and the outline of the identity itself:
 * the record remains, part of it was deliberately taken out.
 *
 * Reads as a single silhouette at favicon sizes and carries no page, shield
 * or lock imagery.
 */
export function DeIDMark({ size = 22, className }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      role="presentation"
      aria-hidden="true"
    >
      <path
        d="M5.5 20V4h5a8 8 0 0 1 7.84 6.4M18.34 13.6A8 8 0 0 1 10.5 20H5.5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="8.5" y="7.8" width="6.2" height="1.6" rx="0.8" fill="currentColor" />
      <rect x="8.5" y="11.2" width="3" height="1.6" rx="0.8" fill="currentColor" />
      <rect x="8.5" y="14.6" width="6.2" height="1.6" rx="0.8" fill="currentColor" />
    </svg>
  )
}
