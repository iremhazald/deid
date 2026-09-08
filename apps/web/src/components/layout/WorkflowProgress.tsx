type Step = {
  key: string
  label: string
}

type Props = {
  steps: Step[]
  currentIndex: number
  label: string
}

export function WorkflowProgress({ steps, currentIndex, label }: Props) {
  return (
    <nav className="workflow" aria-label={label}>
      <ol>
        {steps.map((step, index) => {
          const state = index < currentIndex ? 'done' : index === currentIndex ? 'current' : ''
          return (
            <li key={step.key} className={state} aria-current={index === currentIndex ? 'step' : undefined}>
              {index > 0 && <span className="workflow-sep" aria-hidden="true">→</span>}
              <span>{step.label}</span>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
