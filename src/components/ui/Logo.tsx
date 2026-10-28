/** SDS UZ Inc. logo. `onDark` uses the white-lettered version for navy backgrounds. */
export function Logo({ onDark = true, className = '' }: { onDark?: boolean; className?: string }) {
  return (
    <img
      src={onDark ? '/images/logo-sds-white.webp' : '/images/logo-sds.webp'}
      alt="SDS UZ Inc."
      width={211}
      height={160}
      decoding="async"
      className={`w-auto ${className}`}
    />
  )
}
