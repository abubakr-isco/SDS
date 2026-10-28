import { values } from '../config/site'
import { useReveal } from '../hooks/useReveal'
import { SectionHeading } from './ui/SectionHeading'

export function TrustSection() {
  const listRef = useReveal<HTMLUListElement>(0.1)

  return (
    <section id="approach" aria-labelledby="approach-title" className="bg-white py-20 sm:py-28 lg:py-36">
      <div className="container-x grid gap-12 lg:grid-cols-12 lg:gap-10">
        <div className="lg:col-span-5">
          <div className="lg:sticky lg:top-32">
            <SectionHeading
              id="approach-title"
              title="More than transportation. A partner you can count on."
              intro="Shipping freight is a commitment to your own customers. We treat every load with that in mind."
            />
          </div>
        </div>

        <ul ref={listRef} className="lg:col-span-6 lg:col-start-7">
          {values.map(({ title, text, icon: Icon }, i) => (
            <li
              key={title}
              className="reveal grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 border-t border-rule py-8 first:border-t-0 first:pt-0 sm:gap-x-8 sm:py-10 lg:first:pt-2"
              style={{ transitionDelay: `${i * 90}ms` }}
            >
              <span className="row-span-2 flex h-14 w-14 items-center justify-center bg-mist text-orange-deep">
                <Icon size={26} strokeWidth={1.6} aria-hidden="true" />
              </span>
              <h3 className="display self-end text-xl text-navy sm:text-2xl">{title}</h3>
              <p className="max-w-md text-base leading-relaxed text-steel">{text}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
