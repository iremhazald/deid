type Props = {
  title: string
  steps: string[]
}

export function MethodsRail({ title, steps }: Props) {
  return (
    <aside className="methods-rail">
      <h2>{title}</h2>
      <ol className="review-next-steps">
        {steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </aside>
  )
}
