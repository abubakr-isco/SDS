import { Mail, Phone } from 'lucide-react'
import { contact } from '../config/site'
import { useReveal } from '../hooks/useReveal'
import { QuoteForm } from './QuoteForm'
import { SectionHeading } from './ui/SectionHeading'

const steps = [
  { title: 'Share your shipment', text: 'Lanes, dates, freight type and anything we should know.' },
  { title: 'We review the details', text: 'Our team looks at equipment, timing and route requirements.' },
  { title: 'We follow up', text: 'We contact you to discuss options and next steps.' },
]

export function QuoteSection() {
  const stepsRef = useReveal<HTMLOListElement>(0.2)

  return (
    <section id="quote" aria-labelledby="quote-heading" className="relative bg-charcoal py-20 text-white sm:py-28 lg:py-36">
      <span aria-hidden="true" className="lane-h absolute inset-x-0 top-0 h-1 opacity-90" />
      <div className="container-x grid gap-14 lg:grid-cols-12 lg:gap-12">
        <div className="lg:col-span-5">
          <SectionHeading
            id="quote-heading"
            tone="dark"
            title="Let’s get your freight moving."
            intro="Tell us about your shipment, and our team can follow up to discuss your transportation needs."
          />

          <h3 className="label mt-14 text-white/60">What happens next</h3>
          <ol ref={stepsRef} className="mt-6 space-y-6">
            {steps.map((step, i) => (
              <li key={step.title} className="reveal flex gap-5" style={{ transitionDelay: `${i * 100}ms` }}>
                <span className="display flex h-10 w-10 shrink-0 items-center justify-center border-2 border-orange text-base text-orange">
                  {i + 1}
                </span>
                <div>
                  <p className="font-semibold text-white">{step.title}</p>
                  <p className="mt-1 text-[0.9375rem] leading-relaxed text-steel-light">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>

          <div className="mt-14 border-t border-line pt-8">
            <p className="text-[0.9375rem] text-steel-light">Prefer to talk it through?</p>
            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:gap-8">
              <a href={contact.phone.href} className="inline-flex items-center gap-2.5 font-semibold text-white hover:text-orange">
                <Phone size={18} aria-hidden="true" className="text-orange" />
                {contact.phone.value}
              </a>
              <a href={contact.email.href} className="inline-flex items-center gap-2.5 font-semibold text-white hover:text-orange">
                <Mail size={18} aria-hidden="true" className="text-orange" />
                {contact.email.value}
              </a>
            </div>
          </div>
        </div>

        <div className="lg:col-span-7">
          <div className="bg-white p-6 text-charcoal sm:p-10 lg:p-12">
            <h3 id="quote-title" className="display text-2xl text-navy sm:text-[1.75rem]">
              Request a freight quote
            </h3>
            <div className="mt-6">
              <QuoteForm />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
