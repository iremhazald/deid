type Step = {
  key: string
  label: string
  status: 'done' | 'active' | 'pending'
}

type Props = {
  title: string
  steps: Step[]
}

function StatusMark({ status }: { status: Step['status'] }) {
  return (
    <span className="status-mark" aria-hidden="true">
      {status === 'done' ? (
        <svg viewBox="0 0 16 16" width="12" height="12">
          <path
            d="M3.2 8.2 6.5 11.4 12.8 4.8"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.85"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : status === 'active' ? (
        <span className="status-spinner" />
      ) : null}
    </span>
  )
}

export function ProcessingStatus({ title, steps }: Props) {
  const heading = title.replace(/[.…]+$/u, '').trimEnd()
  const total = steps.length
  const activeIndex = steps.findIndex((step) => step.status === 'active')
  const doneCount = steps.filter((step) => step.status === 'done').length
  const progress =
    total === 0
      ? 0
      : activeIndex >= 0
        ? ((activeIndex + 0.55) / total) * 100
        : (doneCount / total) * 100

  return (
    <section className="status-screen" aria-live="polite" aria-busy="true">
      <div className="status-card status-card--process">
        <div
          className="status-progress"
          role="progressbar"
          aria-label={title}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress)}
        >
          <span className="status-progress-bar" style={{ width: `${progress}%` }} />
        </div>

        <div className="status-card-body">
          <h1 aria-label={title}>
            {heading}
            <span className="status-ellipsis" aria-hidden="true" />
          </h1>

          <ol className="status-list">
            {steps.map((step) => (
              <li
                key={step.key}
                className={step.status}
                aria-current={step.status === 'active' ? 'step' : undefined}
              >
                <StatusMark status={step.status} />
                <span className="status-label">{step.label}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  )
}
