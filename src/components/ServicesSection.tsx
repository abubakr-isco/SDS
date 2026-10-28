import { Plus } from 'lucide-react'
import { useState } from 'react'
import { cta, services, src, srcSet, type Service } from '../config/site'
import { useReveal } from '../hooks/useReveal'
import { SectionHeading } from './ui/SectionHeading'

// Alternating 7/5 and 5/7 column spans give the grid an editorial rhythm.
const spans = ['lg:col-span-7', 'lg:col-span-5', 'lg:col-span-5', 'lg:col-span-7', 'lg:col-span-7', 'lg:col-span-5']

export function ServicesSection() {
  return (
    <section id="services" aria-labelledby="services-title" className="bg-mist py-20 sm:py-28 lg:py-36">
      <div className="container-x">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <SectionHeading
            id="services-title"
            title={
              <>
                Services built
                <br className="hidden sm:block" /> around your freight.
              </>
            }
            intro="Tell us what you are shipping, where it needs to go, and when. We will talk through the option that fits."
          />
          <a
            href={cta.quote.href}
            className="label shrink-0 self-start border-b-2 border-orange pb-1 text-navy transition-colors hover:text-orange-deep lg:self-end"
          >
            Not sure which fits? Ask us
          </a>
        </div>

        <ul className="mt-14 grid gap-x-6 gap-y-12 sm:grid-cols-2 lg:mt-20 lg:grid-cols-12 lg:gap-y-16">
          {services.map((service, i) => (
            <ServiceCard key={service.id} service={service} className={spans[i % spans.length]} />
          ))}
        </ul>
      </div>
    </section>
  )
}

function ServiceCard({ service, className }: { service: Service; className: string }) {
  const [open, setOpen] = useState(false)
  const ref = useReveal<HTMLLIElement>(0.2)
  const panelId = `service-${service.id}-detail`

  return (
    <li ref={ref} className={`group ${className}`}>
      <div className="reveal-image relative h-64 overflow-hidden bg-navy sm:h-72 lg:h-[400px]">
        <img
          src={src(service.image)}
          srcSet={srcSet(service.image)}
          sizes="(min-width: 1024px) 58vw, (min-width: 640px) 50vw, 100vw"
          alt={service.image.alt}
          loading="lazy"
          decoding="async"
          style={{ objectPosition: service.image.position }}
          className="h-full w-full object-cover transition-transform duration-[900ms] ease-[var(--ease-road)] group-hover:scale-[1.04]"
        />
        <span
          aria-hidden="true"
          className="absolute bottom-0 left-0 h-1 w-16 bg-orange transition-[width] duration-500 ease-[var(--ease-road)] group-hover:w-full"
        />
      </div>

      <div className="reveal pt-7">
        <h3 className="display text-2xl text-navy sm:text-[1.75rem]">{service.title}</h3>
        <p className="mt-3 max-w-lg text-base leading-relaxed text-steel">{service.summary}</p>

        <div
          id={panelId}
          className={`grid transition-[grid-template-rows] duration-500 ease-[var(--ease-road)] ${
            open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
          }`}
        >
          <div className="overflow-hidden" inert={!open}>
            <div className="mt-5 max-w-lg border-l-2 border-orange pl-5">
              <p className="leading-relaxed text-charcoal">{service.detail}</p>
              <a
                href={cta.quote.href}
                className="label mt-4 inline-block text-orange-deep underline decoration-2 underline-offset-4 hover:text-navy"
              >
                Request a quote
              </a>
            </div>
          </div>
        </div>

        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((v) => !v)}
          className="label mt-6 inline-flex items-center gap-2 text-navy transition-colors hover:text-orange-deep"
        >
          <span className="flex h-7 w-7 items-center justify-center border-2 border-current">
            <Plus
              size={14}
              strokeWidth={2.5}
              aria-hidden="true"
              className={`transition-transform duration-300 ${open ? 'rotate-45' : ''}`}
            />
          </span>
          {open ? 'Show less' : 'Learn more'}
          <span className="sr-only"> about {service.title}</span>
        </button>
      </div>
    </li>
  )
}
