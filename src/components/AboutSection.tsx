import { useReveal } from '../hooks/useReveal'
import { ButtonLink } from './ui/Button'
import { SectionHeading } from './ui/SectionHeading'

export function AboutSection() {
  const imageRef = useReveal<HTMLDivElement>(0.2)
  const textRef = useReveal<HTMLDivElement>(0.2)

  return (
    <section id="about" aria-labelledby="about-title" className="relative bg-white lg:min-h-[760px]">
      <div ref={imageRef} className="relative h-[60vw] max-h-[520px] min-h-[280px] lg:absolute lg:inset-y-0 lg:left-0 lg:h-auto lg:max-h-none lg:w-1/2">
        <div className="reveal-image absolute inset-0 bg-charcoal">
          <img
            src="/images/about-highway-bw-800.webp"
            srcSet="/images/about-highway-bw-800.webp 800w, /images/about-highway-bw-1400.webp 1400w"
            sizes="(min-width: 1024px) 50vw, 100vw"
            alt="A semi-truck on an open highway beneath storm clouds and mountains, in black and white"
            loading="lazy"
            decoding="async"
            className="h-full w-full object-cover object-[30%_60%]"
          />
        </div>
        <span aria-hidden="true" className="lane absolute bottom-0 right-0 top-0 hidden w-[4px] lg:block" />
      </div>

      <div className="container-x lg:grid lg:min-h-[760px] lg:grid-cols-2">
        <div ref={textRef} className="py-16 sm:py-24 lg:col-start-2 lg:flex lg:flex-col lg:justify-center lg:py-32 lg:pl-20">
          <SectionHeading id="about-title" title="Driven by purpose. Built on trust." />
          <div className="reveal mt-8 max-w-xl space-y-5 text-lg leading-relaxed text-steel">
            <p>
              At SDS, we believe transportation is about more than moving freight. It’s about helping businesses stay
              connected, meet their commitments, and keep moving forward.
            </p>
            <p>
              Our goal is to build dependable relationships through professional service, clear communication, and a
              practical approach to transportation.
            </p>
          </div>
          <div className="reveal mt-10">
            <ButtonLink href="#approach" variant="dark" size="lg">
              Our approach
            </ButtonLink>
          </div>
        </div>
      </div>
    </section>
  )
}
