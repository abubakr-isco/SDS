import type { CSSProperties } from 'react'
import { cta } from '../config/site'
import { ButtonLink } from './ui/Button'

const delay = (ms: number) => ({ '--d': `${ms}ms` }) as CSSProperties

const headline = ['Freight', 'moves.', 'Business', 'grows.']

export function HeroSection() {
  return (
    <section
      id="top"
      aria-labelledby="hero-title"
      className="relative isolate flex min-h-[100svh] flex-col overflow-hidden bg-navy text-white"
    >
      {/* SDS's own truck. Phones: photo across the top, copy below. Desktop: photo panel on the right. */}
      <div className="absolute inset-x-0 top-0 -z-10 h-[56svh] overflow-hidden lg:inset-y-0 lg:left-auto lg:right-0 lg:h-full lg:w-[58%]">
        <img
          src="/images/hero-sds-960.webp"
          srcSet="/images/hero-sds-640.webp 640w, /images/hero-sds-960.webp 960w, /images/hero-sds-1440.webp 1440w"
          sizes="(min-width: 1024px) 58vw, 100vw"
          alt="A white SDS UZ semi-truck and trailer at a truck stop at night"
          fetchPriority="high"
          decoding="async"
          className="hero-photo h-full w-full object-cover object-[64%_62%] lg:object-[55%_72%]"
        />
        {/* Readability overlays: blend the photo into the navy background */}
        <div className="absolute inset-x-0 bottom-0 h-3/4 bg-gradient-to-t from-navy via-navy/60 to-transparent lg:h-1/3" />
        <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-navy/80 to-transparent" />
        <div className="absolute inset-y-0 left-0 hidden w-2/3 bg-gradient-to-r from-navy via-navy/70 to-transparent lg:block" />
      </div>

      <div className="container-x flex flex-1 flex-col justify-end pb-10 pt-28 lg:justify-center lg:pb-12 lg:pt-28">
        <div className="max-w-3xl">
          <p className="label hero-fade flex items-center gap-3 text-white/85" style={delay(100)}>
            <span aria-hidden="true" className="lane-h block h-[3px] w-10" />
            American trucking &amp; logistics
          </p>

          <h1
            id="hero-title"
            className="display mt-6 text-[clamp(2.75rem,12.5vw,4.25rem)] leading-[0.9] sm:text-[clamp(4.25rem,9vw,6.5rem)] lg:mt-7 lg:text-[min(6.4vw,11.5vh,7.5rem)]"
          >
            <span className="sr-only">Freight moves. Business grows.</span>
            <span aria-hidden="true">
              {headline.map((word, i) => (
                <span key={word} className="hero-line">
                  <span style={delay(200 + i * 110)}>{word}</span>
                </span>
              ))}
            </span>
          </h1>

          <p
            className="hero-fade mt-7 max-w-[34rem] text-[1.0625rem] leading-relaxed text-white/85 sm:text-lg lg:mt-8"
            style={delay(750)}
          >
            Reliable trucking solutions built around your business. We help keep your freight moving with a
            commitment to safety, communication, and dependable service.
          </p>

          <div className="hero-fade mt-8 flex flex-col gap-3 sm:flex-row sm:gap-4 lg:mt-9" style={delay(900)}>
            <ButtonLink href={cta.quote.href} size="lg">
              {cta.quote.label}
            </ButtonLink>
            <ButtonLink href={cta.services.href} size="lg" variant="outline-light">
              {cta.services.label}
            </ButtonLink>
          </div>
        </div>
      </div>

      <div className="hero-fade border-t border-white/15" style={delay(1150)}>
        <div className="container-x flex h-16 items-center justify-between gap-6 lg:h-20">
          <p className="label text-[0.6875rem] text-white/70">Reliable transportation. Real-world solutions.</p>
          <a
            href="#approach"
            className="group hidden items-center gap-4 text-white/70 transition-colors hover:text-white sm:flex"
          >
            <span className="label text-[0.6875rem]">Scroll</span>
            <span aria-hidden="true" className="relative h-10 w-[3px] overflow-hidden bg-white/10">
              <span className="lane animate-lane absolute inset-0" />
            </span>
          </a>
        </div>
      </div>
    </section>
  )
}
