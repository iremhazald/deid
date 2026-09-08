type Step = {
  key: string
  label: string
  status: 'done' | 'active' | 'pending'
}

type Props = {
  title: string
  steps: Step[]
}

export function ValidationProgress({ title, steps }: Props) {
  return (
    <section className="status-screen" aria-live="polite" aria-busy="true">
      <div className="status-card">
        <h1>{title}</h1>
        <ol className="status-list">
          {steps.map((step) => (
            <li key={step.key} className={step.status}>
              <span className="status-mark" aria-hidden="true">
                {step.status === 'done' ? '✓' : step.status === 'active' ? '●' : '○'}
              </span>
              <span>{step.label}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
