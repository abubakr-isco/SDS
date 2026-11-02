import { freightTypes, smsConsentText, smsConsentVersion } from '../config/site'

export type FreightType = (typeof freightTypes)[number]

export type QuoteRequest = {
  fullName: string
  companyName: string
  email: string
  phone: string
  pickupLocation: string
  deliveryLocation: string
  pickupDate: string
  freightType: FreightType | ''
  estimatedWeight: string
  details: string
}

export type QuoteField = keyof QuoteRequest
export type QuoteErrors = Partial<Record<QuoteField, string>>

export const emptyQuote: QuoteRequest = {
  fullName: '',
  companyName: '',
  email: '',
  phone: '',
  pickupLocation: '',
  deliveryLocation: '',
  pickupDate: '',
  freightType: '',
  estimatedWeight: '',
  details: '',
}

export const requiredFields: QuoteField[] = [
  'fullName',
  'companyName',
  'email',
  'phone',
  'pickupLocation',
  'deliveryLocation',
  'pickupDate',
  'freightType',
]

// City, then a comma, then a state (ZIP optional) — matches the server's rules.
const LOCATION = /^[^,]{2,80},\s*[A-Za-z][A-Za-z .]{1,24}\.?(?:\s*,?\s*\d{5}(?:-\d{4})?)?$/

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

// Digits plus the usual separators; anything else (letters, "ext") is rejected.
const PHONE_CHARS = /^\+?[\d\s().-]+$/
// North American number: area code and exchange can't start with 0 or 1.
const NANP = /^[2-9]\d{2}[2-9]\d{6}$/

/**
 * Normalizes a phone number to E.164 (+12155550123), or returns undefined if it isn't valid.
 * Numbers without "+" are read as US/Canada numbers; others need "+" and the country code.
 */
export function toE164(input: string): string | undefined {
  const value = input.trim()
  if (!PHONE_CHARS.test(value)) return undefined
  const digits = value.replace(/\D/g, '')

  if (value.startsWith('+')) {
    if (digits.startsWith('1')) return NANP.test(digits.slice(1)) ? `+${digits}` : undefined
    return /^[2-9]\d{7,14}$/.test(digits) ? `+${digits}` : undefined
  }
  if (NANP.test(digits)) return `+1${digits}`
  if (digits.length === 11 && digits.startsWith('1') && NANP.test(digits.slice(1))) return `+${digits}`
  return undefined
}

/** What the visitor agreed to (or didn't) about text messages, recorded with every request. */
export type SmsConsentRecord = {
  /** true only if the visitor checked the box themselves; never defaulted to true. */
  smsConsent: boolean
  phone: string
  /** When the box was checked and the form submitted (UTC, ISO 8601); null without consent. */
  consentedAt: string | null
  source: string
  /** Wording shown next to the checkbox, whether or not it was checked. */
  consentText: string
  consentVersion: string
  submissionId: string
  submittedAt: string
}

export function buildConsentRecord(
  smsConsent: boolean,
  phone: string,
  submissionId: string,
  submittedAt: string,
  pageUrl: string,
): SmsConsentRecord {
  const consented = smsConsent === true
  return {
    smsConsent: consented,
    phone: toE164(phone) ?? phone.trim(),
    consentedAt: consented ? submittedAt : null,
    source: `Website quote form (${pageUrl})`,
    consentText: smsConsentText,
    consentVersion: smsConsentVersion,
    submissionId,
    submittedAt,
  }
}

/** Reference shown to the visitor and used as the form submission ID, e.g. SDS-W-3F9A2C1B. */
export function requestIdFor(submissionKey: string) {
  return `SDS-W-${submissionKey.replace(/-/g, '').slice(0, 8).toUpperCase()}`
}

/** Page the form was sent from, without the query string (which could carry tracking data). */
function pageUrl() {
  return typeof window === 'undefined' ? '' : `${window.location.origin}${window.location.pathname}#quote`
}

export function todayISO() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 10)
}

export function validateField(field: QuoteField, data: QuoteRequest): string | undefined {
  const value = data[field].trim()

  if (requiredFields.includes(field) && !value) {
    const messages: Partial<Record<QuoteField, string>> = {
      fullName: 'Enter your full name.',
      companyName: 'Enter your company name.',
      email: 'Enter your business email.',
      phone: 'Enter a phone number we can reach you on.',
      pickupLocation: 'Enter the pickup city and state.',
      deliveryLocation: 'Enter the delivery city and state.',
      pickupDate: 'Choose a pickup date.',
      freightType: 'Choose a freight type.',
    }
    return messages[field]
  }

  switch (field) {
    case 'email':
      return EMAIL.test(value) ? undefined : 'Enter an email address like name@company.com.'
    case 'phone':
      return toE164(value)
        ? undefined
        : 'Enter a valid phone number with area code, e.g. (215) 555-0123. For numbers outside the US, start with + and the country code.'
    case 'pickupLocation':
    case 'deliveryLocation':
      return LOCATION.test(value) ? undefined : 'Enter a city and state, e.g. Dallas, TX.'
    case 'pickupDate':
      return value >= todayISO() ? undefined : 'Choose today or a later date.'
    case 'estimatedWeight': {
      if (!value) return undefined
      const pounds = Number(value.replace(/,/g, '').replace(/\s*(lbs?|pounds?)\.?$/i, ''))
      return Number.isFinite(pounds) && pounds > 0 ? undefined : 'Enter the weight in pounds, e.g. 42000.'
    }
    case 'details':
      return value.length <= 1000 ? undefined : 'Keep shipment details under 1,000 characters.'
    default:
      return undefined
  }
}

export function validateQuote(data: QuoteRequest): QuoteErrors {
  const errors: QuoteErrors = {}
  for (const field of Object.keys(data) as QuoteField[]) {
    const error = validateField(field, data)
    if (error) errors[field] = error
  }
  return errors
}

export class QuoteNotConfiguredError extends Error {}

export class QuoteRateLimitedError extends Error {}

/** The server rejected some fields; `errors` uses the same field names as the form. */
export class QuoteFieldErrors extends Error {
  errors: QuoteErrors

  constructor(errors: QuoteErrors) {
    super('Quote request has invalid fields')
    this.errors = errors
  }
}

/** Idempotency key for one filled-in form: resubmitting it never creates a second request. */
export function newSubmissionKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  // Fallback for non-secure contexts (plain-http previews).
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

/**
 * Sends the quote request as JSON to the SDS bot server (POST /api/quote), which saves it and
 * notifies the team in Telegram; `smsConsent` is stored as proof of the opt-in. Resolves with the request ID (e.g. SDS-Q-2026-0001).
 * Throws QuoteNotConfiguredError when no endpoint is configured, so the UI can say plainly that
 * nothing was sent.
 */
export async function submitQuote(
  data: QuoteRequest,
  endpoint: string,
  submissionKey: string,
  smsConsent: boolean,
  signal?: AbortSignal,
): Promise<string> {
  if (!endpoint) throw new QuoteNotConfiguredError('No quote endpoint configured')

  const consent = buildConsentRecord(smsConsent, data.phone, requestIdFor(submissionKey), new Date().toISOString(), pageUrl())
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      ...data,
      smsConsent: consent.smsConsent,
      smsConsentAt: consent.consentedAt,
      smsConsentSource: consent.source,
      smsConsentText: consent.consentText,
      smsConsentVersion: consent.consentVersion,
      submissionKey,
      website: '',
    }),
    signal,
  })
  const body = (await response.json().catch(() => null)) as
    | { ok?: boolean; requestId?: string; errors?: Record<string, string> }
    | null

  if (response.status === 422 && body?.errors) {
    const known = Object.keys(emptyQuote)
    const errors = Object.fromEntries(Object.entries(body.errors).filter(([k]) => known.includes(k))) as QuoteErrors
    throw new QuoteFieldErrors(errors)
  }
  if (response.status === 429) throw new QuoteRateLimitedError('Too many requests')
  if (!response.ok || !body?.ok || !body.requestId) throw new Error(`Quote request failed with status ${response.status}`)
  return body.requestId
}

const WEB3FORMS_URL = 'https://api.web3forms.com/submit'

/**
 * Emails the quote request to SDS through Web3Forms and resolves with a reference ID
 * (e.g. SDS-W-3F9A2C1B) that appears both on the confirmation screen and in the email.
 * Every email carries the full SMS consent record (yes or no, number, UTC time, source,
 * wording and its version, submission ID), so the inbox doubles as the opt-in log.
 */
export async function submitQuoteByEmail(
  data: QuoteRequest,
  accessKey: string,
  submissionKey: string,
  smsConsent: boolean,
  signal?: AbortSignal,
): Promise<string> {
  const requestId = requestIdFor(submissionKey)
  const submittedAt = new Date().toISOString()
  const consent = buildConsentRecord(smsConsent, data.phone, requestId, submittedAt, pageUrl())

  const response = await fetch(WEB3FORMS_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      access_key: accessKey,
      subject: `Quote request ${requestId}: ${data.pickupLocation} → ${data.deliveryLocation}`,
      from_name: 'SDS UZ INC website quote form',
      email: data.email, // Web3Forms uses it as the reply-to address
      'Request ID': requestId,
      'Full name': data.fullName,
      Company: data.companyName,
      Phone: data.phone,
      Pickup: data.pickupLocation,
      Delivery: data.deliveryLocation,
      'Pickup date': data.pickupDate,
      'Freight type': data.freightType,
      'Estimated weight (lbs)': data.estimatedWeight || 'Not provided',
      'Shipment details': data.details || 'None provided',
      'SMS consent': consent.smsConsent
        ? 'TRUE: the customer checked the SMS consent box'
        : 'FALSE: the box was left unchecked. Do not text this customer.',
      'SMS consent phone': consent.phone,
      'SMS consent timestamp (UTC)': consent.consentedAt ?? 'None (no consent given)',
      'SMS consent source': consent.source,
      'SMS consent version': consent.consentVersion,
      'SMS consent text shown': consent.consentText,
      'Form submission ID': consent.submissionId,
      'Submitted at (UTC)': submittedAt,
    }),
    signal,
  })
  const body = (await response.json().catch(() => null)) as { success?: boolean } | null

  if (response.status === 429) throw new QuoteRateLimitedError('Too many requests')
  if (!response.ok || !body?.success) throw new Error(`Web3Forms request failed with status ${response.status}`)
  return requestId
}
