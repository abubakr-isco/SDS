import { useState } from 'react'
import { fleet, src, srcSet } from '../config/site'
import { useReveal } from '../hooks/useReveal'
import { SectionHeading } from './ui/SectionHeading'

export function FleetSection() {
  const [activeId, setActiveId] = useState(fleet[0]?.id)
  const frameRef = useReveal<HTMLDivElement>(0.15)

  if (!fleet.length) return null
  const active = fleet.find((f) => f.id === activeId) ?? fleet[0]

  return (
    <section id="fleet" aria-labelledby="fleet-title" className="overflow-hidden bg-navy py-20 text-white sm:py-28 lg:py-36">
      {/* Mobile order: heading, photo, list. Desktop: heading + list on the left, photo spanning the right. */}
      <div className="container-x grid gap-10 lg:grid-cols-12 lg:grid-rows-[auto_1fr] lg:gap-x-12 lg:gap-y-12">
        <div className="lg:col-span-5 lg:row-start-1">
          <SectionHeading
            id="fleet-title"
            tone="dark"
            title="Built for the road ahead."
            intro="Equipment matched to the freight. Select a category to see it."
          />
        </div>

        <div className="lg:col-span-5 lg:row-start-2">
          <ul className="border-b border-line" aria-label="Equipment categories">
            {fleet.map((item) => {
              const isActive = item.id === active.id
              return (
                <li key={item.id} className="border-t border-line">
                  <button
                    type="button"
                    aria-pressed={isActive}
                    onClick={() => setActiveId(item.id)}
                    onMouseEnter={() => setActiveId(item.id)}
                    onFocus={() => setActiveId(item.id)}
                    className="group relative block w-full py-5 pl-6 text-left sm:py-6"
                  >
                    <span
                      aria-hidden="true"
                      className={`absolute bottom-5 left-0 top-5 w-[3px] origin-top transition-transform duration-500 ease-[var(--ease-road)] sm:bottom-6 sm:top-6 ${
                        isActive ? 'lane scale-y-100' : 'scale-y-0 bg-white/30'
                      }`}
                    />
                    <span
                      className={`display block text-xl transition-colors duration-300 sm:text-2xl ${
                        isActive ? 'text-white' : 'text-white/45 group-hover:text-white/80'
                      }`}
                    >
                      {item.title}
                    </span>
                    <span
                      className={`mt-2 block text-[0.9375rem] leading-relaxed transition-colors duration-300 ${
                        isActive ? 'text-steel-light' : 'text-white/35'
                      }`}
                    >
                      {item.note}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>

        <div ref={frameRef} className="row-start-2 flex flex-col lg:col-span-7 lg:col-start-6 lg:row-span-2 lg:row-start-1">
          <div className="reveal-image relative aspect-[4/3] bg-charcoal lg:aspect-auto lg:min-h-[560px] lg:flex-1">
            {fleet.map((item) => (
              <img
                key={item.id}
                src={src(item.image)}
                srcSet={srcSet(item.image)}
                sizes="(min-width: 1024px) 55vw, 100vw"
                alt={item.image.alt}
                aria-hidden={item.id !== active.id}
                loading="lazy"
                decoding="async"
                style={{ objectPosition: item.image.position }}
                className={`absolute inset-0 h-full w-full object-cover transition-[opacity,transform] duration-700 ease-[var(--ease-road)] ${
                  item.id === active.id ? 'scale-100 opacity-100' : 'scale-[1.03] opacity-0'
                }`}
              />
            ))}
            <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-navy/80 to-transparent" />
            <p aria-hidden="true" className="display absolute bottom-5 left-5 right-5 text-lg text-white sm:bottom-7 sm:left-7 sm:text-2xl">
              {active.title}
            </p>
          </div>
          <p className="mt-4 text-sm text-steel-light">
            Representative equipment. Contact us to confirm availability for your shipment.
          </p>
        </div>
      </div>
    </section>
  )
}
