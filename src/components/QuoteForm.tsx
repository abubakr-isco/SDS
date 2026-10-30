import { AlertTriangle, CheckCircle2, Info, Loader2 } from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react'
import { contact, freightTypes, quoteForm, smsConsentText } from '../config/site'
import {
  QuoteFieldErrors,
  QuoteNotConfiguredError,
  QuoteRateLimitedError,
  emptyQuote,
  newSubmissionKey,
  requiredFields,
  submitQuote,
  submitQuoteByEmail,
  todayISO,
  validateField,
  validateQuote,
  type QuoteErrors,
  type QuoteField,
  type QuoteRequest,
} from '../lib/quote'
import { Button } from './ui/Button'

type Status = 'idle' | 'submitting' | 'sent' | 'failed' | 'demo'

// Submissions faster than this are almost certainly automated.
const MIN_FILL_MS = 3000

export function QuoteForm() {
  // Form data lives in memory only — never written to localStorage.
  const [data, setData] = useState<QuoteRequest>(emptyQuote)
  const [errors, setErrors] = useState<QuoteErrors>({})
  const [touched, setTouched] = useState<Partial<Record<QuoteField, boolean>>>({})
  const [status, setStatus] = useState<Status>('idle')
  const [failMessage, setFailMessage] = useState('')
  const [honeypot, setHoneypot] = useState('')
  // Optional and unchecked by default: SMS consent is never a condition of a quote.
  const [smsConsent, setSmsConsent] = useState(false)
  const [requestId, setRequestId] = useState('')
  // Set after mount: the page is prerendered at build time, when "today" was a different day.
  const [minPickupDate, setMinPickupDate] = useState<string>()
  const startedAt = useRef(0)
  const submissionKey = useRef('')
  const formRef = useRef<HTMLFormElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    startedAt.current = Date.now()
    submissionKey.current = newSubmissionKey()
    // oxlint-disable-next-line react/set-state-in-effect -- must differ from the prerendered HTML only after hydration
    setMinPickupDate(todayISO())
  }, [])

  useEffect(() => {
    if (status === 'sent' || status === 'demo' || status === 'failed') resultRef.current?.focus()
  }, [status])

  const update = (field: QuoteField) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const next = { ...data, [field]: e.target.value }
    setData(next)
    if (touched[field]) setErrors((prev) => ({ ...prev, [field]: validateField(field, next) }))
  }

  const blur = (field: QuoteField) => () => {
    setTouched((prev) => ({ ...prev, [field]: true }))
    setErrors((prev) => ({ ...prev, [field]: validateField(field, data) }))
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (status === 'submitting') return

    const found = validateQuote(data)
    setErrors(found)
    setTouched(Object.fromEntries(Object.keys(data).map((k) => [k, true])))
    const firstInvalid = (Object.keys(data) as QuoteField[]).find((f) => found[f])
    if (firstInvalid) {
      formRef.current?.querySelector<HTMLElement>(`[name="${firstInvalid}"]`)?.focus()
      return
    }

    // Spam checks: hidden honeypot field and a minimum time on the form.
    if (honeypot) return
    if (Date.now() - startedAt.current < MIN_FILL_MS) {
      setFailMessage('That was quick. Review your details, then select Request a quote again.')
      setStatus('failed')
      return
    }

    setStatus('submitting')
    try {
      if (!quoteForm.web3formsKey && !quoteForm.endpoint) {
        // Demo mode: show the loading state briefly, then say clearly that nothing was sent.
        await new Promise((r) => setTimeout(r, 700))
      }
      const id = quoteForm.web3formsKey
        ? await submitQuoteByEmail(data, quoteForm.web3formsKey, submissionKey.current, smsConsent)
        : await submitQuote(data, quoteForm.endpoint, submissionKey.current, smsConsent)
      setRequestId(id)
      setStatus('sent')
      setData(emptyQuote)
      setSmsConsent(false)
      setTouched({})
      submissionKey.current = newSubmissionKey()
    } catch (err) {
      if (err instanceof QuoteNotConfiguredError) {
        setStatus('demo')
      } else if (err instanceof QuoteFieldErrors) {
        // The server found problems the browser didn't: show them next to the fields.
        setErrors(err.errors)
        setStatus('idle')
        const first = (Object.keys(data) as QuoteField[]).find((f) => err.errors[f])
        if (first) formRef.current?.querySelector<HTMLElement>(`[name="${first}"]`)?.focus()
      } else if (err instanceof QuoteRateLimitedError) {
        setFailMessage(
          'You have sent several requests recently. Please wait a while before sending another, or contact us directly by phone or email.',
        )
        setStatus('failed')
      } else {
        setFailMessage(
          'Your request could not be sent. Check your connection and try again, or contact us directly by phone or email.',
        )
        setStatus('failed')
      }
    }
  }

  const reset = () => {
    setStatus('idle')
    startedAt.current = Date.now()
  }

  if (status === 'sent' || status === 'demo') {
    const sent = status === 'sent'
    return (
      <div ref={resultRef} tabIndex={-1} role="status" className="flex min-h-[520px] flex-col justify-center outline-none">
        <span
          className={`flex h-14 w-14 items-center justify-center ${sent ? 'bg-orange text-navy' : 'bg-mist text-orange-deep'}`}
        >
          {sent ? <CheckCircle2 size={28} aria-hidden="true" /> : <Info size={28} aria-hidden="true" />}
        </span>
        <h3 className="display mt-8 text-3xl text-navy">{sent ? 'Quote request sent' : 'Your request was not sent'}</h3>
        {sent ? (
          <div className="mt-4 max-w-md space-y-4 text-lg leading-relaxed text-steel">
            <p>
              Request ID: <strong className="font-semibold text-navy">{requestId}</strong>
            </p>
            <p>
              Thanks. Our team will review your shipment details and follow up using the contact information you
              provided.
            </p>
          </div>
        ) : (
          <div className="mt-4 max-w-md space-y-4 text-lg leading-relaxed text-steel">
            <p>
              This form is in demo mode: your details passed validation, but no email service or API is connected
              yet, so nothing was delivered to SDS UZ INC.
            </p>
            <p>
              To request a quote now, call{' '}
              <a className="font-semibold text-navy underline underline-offset-4" href={contact.phone.href}>
                {contact.phone.value}
              </a>{' '}
              or email{' '}
              <a className="font-semibold text-navy underline underline-offset-4" href={contact.email.href}>
                {contact.email.value}
              </a>
              .
            </p>
          </div>
        )}
        <div className="mt-10">
          <Button variant="outline-dark" onClick={reset}>
            {sent ? 'Request another quote' : 'Back to the form'}
          </Button>
        </div>
      </div>
    )
  }

  const fieldProps = (field: QuoteField) => ({
    id: `quote-${field}`,
    name: field,
    value: data[field],
    onChange: update(field),
    onBlur: blur(field),
    required: requiredFields.includes(field),
    'aria-invalid': errors[field] ? true : undefined,
    'aria-describedby': errors[field] ? `quote-${field}-error` : undefined,
    className: inputClass(Boolean(errors[field])),
  })

  const errorCount = Object.values(errors).filter(Boolean).length

  return (
    <form ref={formRef} noValidate onSubmit={onSubmit} aria-labelledby="quote-title" className="relative">
      {status === 'failed' && (
        <div
          ref={resultRef}
          tabIndex={-1}
          role="alert"
          className="mb-8 flex gap-3 border-l-4 border-red-700 bg-red-50 p-4 text-[0.9375rem] leading-relaxed text-red-900 outline-none"
        >
          <AlertTriangle size={20} className="mt-0.5 shrink-0" aria-hidden="true" />
          <p>{failMessage}</p>
        </div>
      )}

      <p className="mb-8 text-sm text-steel">
        Fields marked <span aria-hidden="true" className="text-orange-deep">*</span>
        <span className="sr-only">with an asterisk</span> are required.
      </p>

      <div className="grid gap-x-5 gap-y-6 sm:grid-cols-2">
        <Field field="fullName" label="Full name" error={errors.fullName} required>
          <input type="text" autoComplete="name" {...fieldProps('fullName')} />
        </Field>
        <Field field="companyName" label="Company name" error={errors.companyName} required>
          <input type="text" autoComplete="organization" {...fieldProps('companyName')} />
        </Field>
        <Field field="email" label="Business email" error={errors.email} required>
          <input type="email" autoComplete="email" inputMode="email" {...fieldProps('email')} />
        </Field>
        <Field field="phone" label="Phone number" error={errors.phone} required>
          <input type="tel" autoComplete="tel" inputMode="tel" {...fieldProps('phone')} />
        </Field>
        <div className="sm:col-span-2">
          <label htmlFor="quote-smsConsent" className="flex items-start gap-3 text-sm leading-relaxed text-steel">
            <input
              id="quote-smsConsent"
              type="checkbox"
              name="smsConsent"
              checked={smsConsent}
              onChange={(e) => setSmsConsent(e.target.checked)}
              className="mt-1 h-4 w-4 shrink-0 accent-navy"
            />
            <span>
              {smsConsentText} See our{' '}
              <a href="/privacy" className="font-semibold text-navy underline underline-offset-4">
                Privacy Policy
              </a>{' '}
              and{' '}
              <a href="/sms-terms" className="font-semibold text-navy underline underline-offset-4">
                SMS Terms
              </a>
              .
            </span>
          </label>
        </div>
        <Field field="pickupLocation" label="Pickup city and state" error={errors.pickupLocation} required>
          <input type="text" placeholder="e.g. Dallas, TX" {...fieldProps('pickupLocation')} />
        </Field>
        <Field field="deliveryLocation" label="Delivery city and state" error={errors.deliveryLocation} required>
          <input type="text" placeholder="e.g. Atlanta, GA" {...fieldProps('deliveryLocation')} />
        </Field>
        <Field field="pickupDate" label="Pickup date" error={errors.pickupDate} required>
          <input type="date" min={minPickupDate} {...fieldProps('pickupDate')} />
        </Field>
        <Field field="freightType" label="Freight type" error={errors.freightType} required>
          <select {...fieldProps('freightType')}>
            <option value="" disabled>
              Select freight type
            </option>
            {freightTypes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </Field>
        <Field field="estimatedWeight" label="Estimated weight" hint="Optional" error={errors.estimatedWeight}>
          <div className="relative">
            <input type="text" inputMode="numeric" placeholder="e.g. 42,000" {...fieldProps('estimatedWeight')} />
            <span className="pointer-events-none absolute inset-y-0 right-4 flex items-center text-sm text-steel">lbs</span>
          </div>
        </Field>
        <div className="sm:col-span-2">
          <Field field="details" label="Shipment details" hint="Optional" error={errors.details}>
            <textarea
              rows={4}
              placeholder="Commodity, pallet count, dimensions, special handling, delivery windows…"
              {...fieldProps('details')}
              className={`${inputClass(Boolean(errors.details))} h-auto resize-y py-3`}
            />
          </Field>
        </div>
      </div>

      {/* Honeypot — hidden from people and assistive tech, often filled by bots */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
        <label htmlFor="quote-website">Website</label>
        <input
          id="quote-website"
          type="text"
          name="website"
          tabIndex={-1}
          autoComplete="off"
          value={honeypot}
          onChange={(e) => setHoneypot(e.target.value)}
        />
      </div>

      <div className="mt-10 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-xs text-sm leading-relaxed text-steel">
          We use these details only to respond to your quote request. We text you only if you check the box above.
        </p>
        <Button type="submit" variant="dark" size="lg" disabled={status === 'submitting'} aria-disabled={status === 'submitting'}>
          {status === 'submitting' ? (
            <>
              <Loader2 size={18} className="animate-spin" aria-hidden="true" />
              Sending request…
            </>
          ) : (
            'Request a quote'
          )}
        </Button>
      </div>

      <p className="sr-only" aria-live="polite">
        {status === 'submitting'
          ? 'Sending your quote request.'
          : errorCount > 0
            ? `${errorCount} ${errorCount === 1 ? 'field needs' : 'fields need'} attention.`
            : ''}
      </p>
    </form>
  )
}

function inputClass(invalid: boolean) {
  return `block h-12 w-full rounded-[2px] border bg-white px-4 text-base text-navy placeholder:text-steel/60 transition-colors duration-150 focus:outline-none focus:ring-0 focus-visible:outline-none ${
    invalid ? 'border-red-700 focus:border-red-700 focus:shadow-[0_0_0_1px_#b91c1c]' : 'border-[#c9d0d9] hover:border-steel focus:border-navy focus:shadow-[0_0_0_1px_#0b1220]'
  }`
}

function Field({
  field,
  label,
  hint,
  error,
  required,
  children,
}: {
  field: QuoteField
  label: string
  hint?: string
  error?: string
  required?: boolean
  children: ReactNode
}) {
  return (
    <div>
      <label htmlFor={`quote-${field}`} className="mb-2 flex items-baseline justify-between gap-2 text-sm font-semibold text-navy">
        <span>
          {label}
          {required && (
            <span aria-hidden="true" className="ml-0.5 text-orange-deep">
              *
            </span>
          )}
        </span>
        {hint && <span className="text-xs font-normal text-steel">{hint}</span>}
      </label>
      {children}
      {error && (
        <p id={`quote-${field}-error`} className="mt-2 flex items-start gap-1.5 text-sm text-red-700">
          <AlertTriangle size={14} className="mt-[3px] shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  )
}
