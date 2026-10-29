import { freightTypes } from '../config/site'

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
    case 'phone': {
      const digits = value.replace(/\D/g, '')
      return digits.length >= 10 && digits.length <= 15 ? undefined : 'Enter a 10-digit phone number, including area code.'
    }
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

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ ...data, smsConsent, submissionKey, website: '' }),
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
