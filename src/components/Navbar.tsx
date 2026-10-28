import { Menu, Phone, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { contact, cta, navigation } from '../config/site'
import { useActiveSection, useScrolled } from '../hooks/useScrollState'
import { ButtonLink } from './ui/Button'
import { Wordmark } from './ui/Wordmark'

// Observe every section (not just nav targets) so nothing stays highlighted in sections without a nav item.
const sectionIds = ['top', 'approach', 'services', 'fleet', 'about', 'quote', 'contact']

export function Navbar() {
  const scrolled = useScrolled(24)
  const active = useActiveSection(sectionIds)
  const [open, setOpen] = useState(false)
  const toggleRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  const close = useCallback((returnFocus = false) => {
    setOpen(false)
    if (returnFocus) toggleRef.current?.focus()
  }, [])

  // Mobile menu: scroll lock, Escape to close, focus trap, close on desktop resize.
  useEffect(() => {
    if (!open) return
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'
    panelRef.current?.querySelector<HTMLElement>('a')?.focus()

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close(true)
      if (e.key !== 'Tab' || !panelRef.current || !toggleRef.current) return
      const focusables = [toggleRef.current, ...panelRef.current.querySelectorAll<HTMLElement>('a, button')]
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    const mq = window.matchMedia('(min-width: 1024px)')
    const onMq = () => mq.matches && close()

    document.addEventListener('keydown', onKey)
    mq.addEventListener('change', onMq)
    return () => {
      document.body.style.overflow = overflow
      document.removeEventListener('keydown', onKey)
      mq.removeEventListener('change', onMq)
    }
  }, [open, close])

  const solid = scrolled || open

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-[background-color,border-color,backdrop-filter] duration-300 ${
        // No backdrop-filter while the menu is open: it would become the containing block for the fixed panel.
        open
          ? 'border-b border-white/10 bg-navy'
          : solid
            ? 'border-b border-white/10 bg-navy/95 backdrop-blur-md'
            : 'border-b border-transparent bg-transparent'
      }`}
    >
      <a
        href="#main"
        className="label sr-only z-[60] bg-orange px-4 py-3 text-navy focus:not-sr-only focus:absolute focus:left-4 focus:top-3"
      >
        Skip to content
      </a>

      <div className="container-x flex h-16 items-center justify-between gap-6 lg:h-20">
        <a href="#top" className="text-2xl text-white lg:text-[1.75rem]" aria-label="SDS — back to top" onClick={() => close()}>
          <Wordmark />
        </a>

        <nav aria-label="Primary" className="hidden lg:block">
          <ul className="flex items-center gap-1">
            {navigation.map((item) => {
              const isActive = active === item.href.slice(1)
              return (
                <li key={item.href}>
                  <a
                    href={item.href}
                    aria-current={isActive ? 'location' : undefined}
                    className={`relative block px-4 py-2 text-[0.9375rem] font-medium transition-colors duration-200 hover:text-white ${
                      isActive ? 'text-white' : 'text-white/70'
                    }`}
                  >
                    {item.label}
                    <span
                      aria-hidden="true"
                      className={`absolute inset-x-4 -bottom-0.5 h-[2px] origin-left bg-orange transition-transform duration-300 ease-out ${
                        isActive ? 'scale-x-100' : 'scale-x-0'
                      }`}
                    />
                  </a>
                </li>
              )
            })}
          </ul>
        </nav>

        <div className="flex items-center gap-2">
          <div className="hidden sm:block">
            <ButtonLink href={cta.quote.href} size="sm" className="lg:h-11 lg:px-5">
              {cta.quote.label}
            </ButtonLink>
          </div>
          <button
            ref={toggleRef}
            type="button"
            className="-mr-2 inline-flex h-11 w-11 items-center justify-center text-white lg:hidden"
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? 'Close menu' : 'Open menu'}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X size={26} strokeWidth={1.75} /> : <Menu size={26} strokeWidth={1.75} />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      <div
        id="mobile-menu"
        ref={panelRef}
        hidden={!open}
        className="fixed inset-x-0 bottom-0 top-16 overflow-y-auto bg-navy lg:hidden"
      >
        <div className="container-x flex min-h-full flex-col py-8">
          <nav aria-label="Mobile">
            <ul>
              {navigation.map((item, i) => (
                <li
                  key={item.href}
                  className="hero-fade border-b border-white/10"
                  style={{ '--d': `${60 + i * 50}ms` } as CSSProperties}
                >
                  <a
                    href={item.href}
                    onClick={() => close()}
                    aria-current={active === item.href.slice(1) ? 'location' : undefined}
                    className="display flex items-center justify-between py-5 text-[1.75rem] text-white aria-[current]:text-orange"
                  >
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <div className="mt-auto space-y-4 pt-10">
            <ButtonLink href={cta.quote.href} size="lg" className="w-full" onClick={() => close()}>
              {cta.quote.label}
            </ButtonLink>
            <a
              href={contact.phone.href}
              className="flex items-center justify-center gap-2 py-2 text-white/80 hover:text-white"
            >
              <Phone size={16} aria-hidden="true" />
              {contact.phone.value}
            </a>
          </div>
        </div>
      </div>
    </header>
  )
}
