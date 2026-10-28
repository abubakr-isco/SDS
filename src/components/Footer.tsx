import type { ReactNode } from 'react'
import { company, contact, cta, legalLinks, navigation, services, socialLinks } from '../config/site'
import { ButtonLink } from './ui/Button'
import { Wordmark } from './ui/Wordmark'

const year = new Date().getFullYear()

export function Footer() {
  const social = socialLinks.filter((s) => s.href)

  return (
    <footer className="bg-navy text-white">
      <div className="container-x py-16 lg:py-24">
        <div className="grid gap-12 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <a href="#top" className="text-3xl" aria-label="SDS — back to top">
              <Wordmark />
            </a>
            <p className="mt-6 max-w-sm leading-relaxed text-steel-light">{company.description}</p>
            <ButtonLink href={cta.quote.href} className="mt-8">
              {cta.quote.label}
            </ButtonLink>
          </div>

          <FooterColumn title="Company" className="lg:col-span-2 lg:col-start-6">
            {navigation.map((n) => (
              <li key={n.href}>
                <a href={n.href} className="text-steel-light transition-colors hover:text-white">
                  {n.label}
                </a>
              </li>
            ))}
          </FooterColumn>

          <FooterColumn title="Services" className="lg:col-span-3">
            {services.map((s) => (
              <li key={s.id}>
                <a href="#services" className="text-steel-light transition-colors hover:text-white">
                  {s.title}
                </a>
              </li>
            ))}
          </FooterColumn>

          <FooterColumn title="Contact" className="lg:col-span-2">
            <li>
              <a href={contact.phone.href} className="text-steel-light transition-colors hover:text-white">
                {contact.phone.value}
              </a>
            </li>
            <li>
              <a href={contact.email.href} className="break-all text-steel-light transition-colors hover:text-white">
                {contact.email.value}
              </a>
            </li>
            {social.map((s) => (
              <li key={s.href}>
                <a href={s.href} target="_blank" rel="noopener noreferrer" className="text-steel-light hover:text-white">
                  {s.label}
                </a>
              </li>
            ))}
          </FooterColumn>
        </div>
      </div>

      <div className="border-t border-line">
        <div className="container-x flex flex-col gap-4 py-6 text-sm text-steel-light sm:flex-row sm:items-center sm:justify-between">
          <p>
            © {year} {company.name}. All rights reserved.
            {company.registration && <span className="ml-3">{company.registration}</span>}
          </p>
          <ul className="flex gap-6">
            {legalLinks.map((l) => (
              <li key={l.href}>
                <a href={l.href} className="hover:text-white">
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </footer>
  )
}

function FooterColumn({ title, className = '', children }: { title: string; className?: string; children: ReactNode }) {
  return (
    <div className={className}>
      <h2 className="label text-white">{title}</h2>
      <ul className="mt-6 space-y-3 text-[0.9375rem]">{children}</ul>
    </div>
  )
}
