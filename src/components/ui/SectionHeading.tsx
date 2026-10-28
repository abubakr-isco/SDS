import type { ReactNode } from 'react'
import { useReveal } from '../../hooks/useReveal'

type Props = {
  id?: string
  title: ReactNode
  intro?: ReactNode
  tone?: 'light' | 'dark'
  className?: string
}

/** Section headline: expanded caps with a short lane stripe above it. */
export function SectionHeading({ id, title, intro, tone = 'light', className = '' }: Props) {
  const ref = useReveal<HTMLDivElement>()
  const dark = tone === 'dark'

  return (
    <div ref={ref} className={`reveal ${className}`}>
      <span aria-hidden="true" className="lane-h mb-6 block h-[3px] w-16" />
      <h2
        id={id}
        className={`display text-[clamp(1.5rem,8vw,2.5rem)] sm:text-5xl lg:text-[3.5rem] ${dark ? 'text-white' : 'text-navy'}`}
      >
        {title}
      </h2>
      {intro && (
        <p className={`mt-6 max-w-xl text-lg leading-relaxed ${dark ? 'text-steel-light' : 'text-steel'}`}>{intro}</p>
      )}
    </div>
  )
}
