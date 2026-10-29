import { useEffect } from 'react'
import { AboutSection } from './components/AboutSection'
import { ContactSection } from './components/ContactSection'
import { FleetSection } from './components/FleetSection'
import { Footer } from './components/Footer'
import { HeroSection } from './components/HeroSection'
import { Navbar } from './components/Navbar'
import { QuoteSection } from './components/QuoteSection'
import { ServicesSection } from './components/ServicesSection'
import { TrustSection } from './components/TrustSection'

export default function App() {
  // Honour deep links like /#quote: the browser's own hash jump runs before React has rendered the sections.
  // Look the id up directly: a mangled hash (e.g. "#quote»" pasted from a message) is not a valid CSS
  // selector, and a querySelector exception here would unmount the whole page.
  useEffect(() => {
    let id = window.location.hash.slice(1)
    try {
      id = decodeURIComponent(id)
    } catch {
      // Malformed percent-encoding: try the raw value.
    }
    const target = id && document.getElementById(id)
    if (target) target.scrollIntoView({ behavior: 'instant' })
  }, [])

  return (
    <>
      <Navbar />
      <main id="main" tabIndex={-1} className="outline-none">
        <HeroSection />
        <TrustSection />
        <ServicesSection />
        <FleetSection />
        <AboutSection />
        <QuoteSection />
        <ContactSection />
      </main>
      <Footer />
    </>
  )
}
