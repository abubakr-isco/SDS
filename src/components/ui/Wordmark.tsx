/**
 * SDS wordmark: two slanted lane stripes leading into expanded heavy
 * lettering. Pure type + geometry so it scales cleanly anywhere.
 */
export function Wordmark({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg viewBox="0 0 26 24" className="h-[0.9em] w-auto" aria-hidden="true">
        <path d="M8 0h7L7 24H0z" fill="#FF6A00" />
        <path d="M19 0h7l-8 24h-7z" fill="#FF6A00" opacity="0.55" />
      </svg>
      <span className="display leading-none tracking-[-0.02em]" style={{ fontWeight: 900 }}>
        SDS
      </span>
    </span>
  )
}
