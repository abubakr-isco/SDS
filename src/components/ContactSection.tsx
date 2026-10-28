import { Clock, Mail, Phone, Route } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { contact, cta, type ContactItem } from '../config/site'
import { ButtonLink } from './ui/Button'
import { SectionHeading } from './ui/SectionHeading'

const rows: { item: ContactItem; icon: LucideIcon }[] = [
  { item: contact.phone, icon: Phone },
  { item: contact.email, icon: Mail },
  { item: contact.hours, icon: Clock },
  { item: contact.serviceArea, icon: Route },
]

export function ContactSection() {
  return (
    <section id="contact" aria-labelledby="contact-title" className="bg-white py-20 sm:py-28 lg:py-36">
      <div className="container-x grid gap-14 lg:grid-cols-12 lg:gap-12">
        <div className="lg:col-span-5">
          <SectionHeading
            id="contact-title"
            title="Ready to move forward?"
            intro="Call, email, or send a quote request. We will get back to you to talk through your freight."
          />
          <div className="mt-10 flex flex-col gap-3 sm:flex-row">
            <ButtonLink href={cta.quote.href} size="lg">
              {cta.quote.label}
            </ButtonLink>
            <ButtonLink href={contact.phone.href} size="lg" variant="outline-dark">
              <Phone size={16} aria-hidden="true" />
              Call us
            </ButtonLink>
          </div>
        </div>

        <div className="lg:col-span-6 lg:col-start-7">
          <dl className="border-t border-navy">
            {rows.map(({ item, icon: Icon }) => (
              <div key={item.label} className="grid grid-cols-[auto_1fr] items-start gap-x-5 border-b border-rule py-5 sm:grid-cols-[auto_9rem_1fr] sm:py-6">
                <Icon size={20} strokeWidth={1.75} aria-hidden="true" className="mt-0.5 text-orange-deep" />
                <dt className="label text-steel sm:pt-1">{item.label}</dt>
                <dd className="col-start-2 mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-lg text-navy sm:col-start-3 sm:mt-0">
                  {item.href ? (
                    <a href={item.href} className="font-semibold underline-offset-4 hover:text-orange-deep hover:underline">
                      {item.value}
                    </a>
                  ) : (
                    <span>{item.value}</span>
                  )}
                  {item.placeholder && <PlaceholderTag />}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  )
}

function PlaceholderTag() {
  return (
    <span
      title="Replace with real company information in src/config/site.ts"
      className="label border border-dashed border-steel/60 px-2 py-1 text-[0.625rem] text-steel"
    >
      Placeholder
    </span>
  )
}
