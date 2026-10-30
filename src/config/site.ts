/**
 * ---------------------------------------------------------------
 *  SDS UZ INC — central site configuration
 * ---------------------------------------------------------------
 *  Every piece of company-specific content lives here so it can be
 *  edited without touching components.
 *
 *  Anything marked `placeholder: true` (or wrapped in [brackets])
 *  is NOT real company information yet. Replace it with verified
 *  details before launch. Do not publish invented phone numbers,
 *  addresses, fleet counts, certifications or statistics.
 * ---------------------------------------------------------------
 */
import type { LucideIcon } from 'lucide-react'
import { Handshake, MessageSquareText, ShieldCheck, Waypoints } from 'lucide-react'

export type ContactItem = {
  label: string
  value: string
  /** tel:, mailto: or https: link. Omit for plain text. */
  href?: string
  /** true until the real value has been supplied */
  placeholder: boolean
}

export type Service = {
  id: string
  title: string
  summary: string
  /** Shown when a visitor expands the card. */
  detail: string
  image: ResponsiveImage
  /**
   * Services are PROPOSED offerings. Set to true once the company
   * confirms it actually provides the service; remove the entry if not.
   */
  confirmed: boolean
}

export type FleetCategory = {
  id: string
  title: string
  note: string
  image: ResponsiveImage
  /** Only list categories the company actually operates. */
  confirmed: boolean
}

export type ResponsiveImage = {
  /** Base name in /public/images, without the "-<width>.webp" suffix */
  name: string
  widths: number[]
  alt: string
  /** CSS object-position, e.g. "50% 40%" */
  position?: string
}

export const company = {
  legalName: 'SDS UZ INC',
  tagline: 'Moving America Forward.',
  description:
    'SDS UZ INC provides trucking and freight transportation for businesses that need freight moved safely, efficiently and on time.',
  /** Production URL — also update index.html, public/robots.txt, public/sitemap.xml and the public/*.html pages */
  siteUrl: 'https://sdsuz-inc.com',
  /** e.g. 'USDOT 0000000 · MC 000000' — leave empty until verified */
  registration: '',
}

export const contact: Record<'company' | 'phone' | 'email' | 'address' | 'hours' | 'serviceArea', ContactItem> = {
  company: {
    label: 'Company',
    value: 'SDS UZ INC',
    placeholder: false,
  },
  phone: {
    label: 'Phone',
    value: '(215) 268-3886',
    href: 'tel:+12152683886',
    placeholder: false,
  },
  email: {
    label: 'Email',
    value: 'dispatch@sdsuzinc.com',
    href: 'mailto:dispatch@sdsuzinc.com',
    placeholder: false,
  },
  address: {
    label: 'Address',
    value: '133 Carters Mill RD, Feasterville Trevose, PA 19053',
    placeholder: false,
  },
  // Placeholder items are not shown on the site until real values are supplied.
  hours: {
    label: 'Hours',
    value: '[Operating hours, e.g. Mon–Fri, 7:00 AM – 6:00 PM CT]',
    placeholder: true,
  },
  serviceArea: {
    label: 'Service area',
    value: '[States or regions served]',
    placeholder: true,
  },
}

/**
 * Social profiles. Only add real, active profiles — entries with an
 * empty href are not rendered.
 */
export const socialLinks: { label: string; href: string }[] = [
  // { label: 'LinkedIn', href: 'https://www.linkedin.com/company/...' },
]

/** Dropping the first character of an href gives the homepage section that highlights the item. */
export const navigation = [
  { label: 'Home', href: '#top' },
  { label: 'About Us', href: '/about' },
  { label: 'Services', href: '#services' },
  { label: 'Our Fleet', href: '#fleet' },
  { label: 'Contact', href: '/contact' },
] as const

export const cta = {
  quote: { label: 'Get a freight quote', href: '#quote' },
  services: { label: 'Explore our services', href: '#services' },
}

export const values: { title: string; text: string; icon: LucideIcon }[] = [
  {
    title: 'Dependable service',
    text: 'A professional approach to freight transportation and clear communication from pickup to delivery.',
    icon: Handshake,
  },
  {
    title: 'Safety first',
    text: 'A commitment to responsible transportation practices on every load and every mile.',
    icon: ShieldCheck,
  },
  {
    title: 'Business-focused solutions',
    text: 'Transportation services designed around the requirements of each individual shipment.',
    icon: Waypoints,
  },
  {
    title: 'Communication that matters',
    text: 'Clear updates and responsive support throughout the process, so you are never left guessing.',
    icon: MessageSquareText,
  },
]

const W = [800, 1400]

export const services: Service[] = [
  {
    id: 'ftl',
    title: 'Full Truckload (FTL)',
    summary: 'Dedicated truck capacity for larger shipments and business-critical freight.',
    detail:
      'Your freight travels on its own trailer from pickup to delivery, with no stops to load or unload other customers’ shipments.',
    image: {
      name: 'svc-sds-ftl',
      widths: [640, 960],
      alt: 'A white SDS UZ semi-truck with its trailer at a warehouse loading dock at dusk',
      position: '50% 55%',
    },
    confirmed: true,
  },
  {
    id: 'ltl',
    title: 'Less Than Truckload (LTL)',
    summary: 'Flexible shipping options for freight that does not require a full trailer.',
    detail:
      'Ship palletized freight without paying for an entire trailer. Tell us the dimensions, weight and handling needs and we will discuss options.',
    image: { name: 'svc-ltl', widths: W, alt: 'Palletized freight staged inside a large distribution warehouse', position: '50% 50%' },
    confirmed: true,
  },
  {
    id: 'long-haul',
    title: 'Long-Haul Transportation',
    summary: 'Transportation solutions for shipments moving across longer distances.',
    detail:
      'Planning for multi-day, multi-state moves, with pickup and delivery windows agreed before the truck rolls.',
    image: { name: 'svc-sds-longhaul', widths: W, alt: 'A white SDS UZ semi-truck and branded trailer moving at speed on a highway', position: '30% 55%' },
    confirmed: true,
  },
  {
    id: 'regional',
    title: 'Regional Freight',
    summary: 'Transportation support for regional routes and recurring shipping needs.',
    detail:
      'Shorter routes and repeat lanes within a region, suited to shippers who move freight on a regular schedule.',
    image: { name: 'svc-sds-regional', widths: W, alt: 'A white SDS UZ semi-truck and branded trailer on a highway under a blue sky', position: '45% 60%' },
    confirmed: true,
  },
  {
    id: 'dedicated',
    title: 'Dedicated Transportation',
    summary: 'Consistent transportation capacity for businesses with ongoing requirements.',
    detail:
      'Capacity set aside for your business on an agreed schedule, for shippers who need the same reliable service week after week.',
    image: { name: 'svc-sds-dedicated', widths: W, alt: 'A white SDS UZ semi-truck and branded trailer parked at a warehouse loading dock', position: '45% 60%' },
    confirmed: true,
  },
  {
    id: 'logistics',
    title: 'Logistics Coordination',
    summary: 'Practical coordination to help manage freight movements and delivery expectations.',
    detail:
      'Help scheduling pickups, coordinating with docks and receivers, and keeping delivery expectations clear on every side.',
    image: { name: 'svc-logistics', widths: W, alt: 'Aerial view of trailers backed into the loading docks of a distribution center', position: '50% 50%' },
    confirmed: true,
  },
]

/**
 * Equipment categories confirmed by SDS (Oct 2026). Photos are stock images
 * that represent each category — replace them with SDS's own fleet photos
 * when available. Add other categories (e.g. day cabs) the same way.
 */
export const fleet: FleetCategory[] = [
  {
    id: 'sleeper',
    title: 'Sleeper cab tractors',
    note: 'Built for long distances and multi-day routes.',
    image: {
      name: 'fleet-sds-sleeper',
      widths: [640, 960],
      alt: 'A white SDS UZ Freightliner sleeper cab with its trailer at a loading facility at dusk',
      position: '50% 68%',
    },
    confirmed: true,
  },
  {
    id: 'dry-van',
    title: 'Dry van trailers',
    note: 'Enclosed trailers for general, palletized freight.',
    image: { name: 'fleet-dryvan', widths: W, alt: 'White dry van trailers backed into loading dock doors', position: '50% 50%' },
    confirmed: true,
  },
  {
    id: 'reefer',
    title: 'Refrigerated trailers',
    note: 'Temperature-controlled trailers for freight that has to stay cold.',
    image: { name: 'fleet-reefer', widths: W, alt: 'A long row of refrigerated trailers parked in a yard', position: '50% 55%' },
    confirmed: true,
  },
  {
    id: 'flatbed',
    title: 'Flatbed trailers',
    note: 'Open-deck trailers for freight loaded from the side or top.',
    image: { name: 'fleet-cascadia', widths: W, alt: 'A white semi-truck hauling a covered flatbed load on a two-lane highway under a stormy sky', position: '50% 62%' },
    confirmed: true,
  },
]

/** Must match the freight types in sds-telegram-bot/config/company.toml (the server validates them). */
export const freightTypes = [
  'General Freight',
  'Palletized Goods',
  'Machinery / Equipment',
  'Temperature-Controlled Freight',
  'Other',
] as const

/**
 * Quote form delivery. The first one configured wins:
 *
 * 1. VITE_WEB3FORMS_ACCESS_KEY — the request is emailed to SDS through
 *    Web3Forms (https://web3forms.com). The key is public by design; it only
 *    lets a form send email to the address it was created for.
 * 2. VITE_QUOTE_ENDPOINT — the SDS bot server's /api/quote URL
 *    (e.g. https://bot.example.com/api/quote). The bot saves the request and
 *    sends it to the SDS team in Telegram.
 *
 * With neither set, the form runs in demo mode: it validates the request but
 * clearly tells the visitor nothing was sent.
 */
export const quoteForm = {
  web3formsKey: (import.meta.env.VITE_WEB3FORMS_ACCESS_KEY as string | undefined) ?? '',
  endpoint: (import.meta.env.VITE_QUOTE_ENDPOINT as string | undefined) ?? '',
}

/**
 * SMS opt-in wording shown next to the checkbox. The exact text is also emailed with
 * each request as proof of what the customer agreed to — keep it in sync with
 * public/sms-terms.html and the RingCentral campaign.
 */
export const smsConsentText =
  'I agree to receive text messages from SDS UZ INC about quote follow-ups, shipment and delivery updates, and customer support replies at the mobile number provided. Consent is not a condition of purchase. Message frequency may vary. Message and data rates may apply. Reply STOP to opt out, HELP for help.'

export const legalLinks = [
  { label: 'Privacy Policy', href: '/privacy' },
  { label: 'SMS Terms & Conditions', href: '/sms-terms' },
  { label: 'Terms & Conditions', href: '/terms' },
]

export function srcSet(img: ResponsiveImage) {
  return img.widths.map((w) => `/images/${img.name}-${w}.webp ${w}w`).join(', ')
}

export function src(img: ResponsiveImage) {
  return `/images/${img.name}-${img.widths[0]}.webp`
}
