import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'outline-light' | 'outline-dark' | 'dark'
type Size = 'md' | 'lg' | 'sm'

const base =
  'label inline-flex items-center justify-center gap-2.5 rounded-[2px] border-2 transition-[background-color,border-color,color,transform] duration-200 ease-out active:translate-y-px disabled:pointer-events-none disabled:opacity-60 whitespace-nowrap'

const variants: Record<Variant, string> = {
  // Navy on orange keeps the label at ~6.7:1 contrast.
  primary: 'border-orange bg-orange text-navy hover:bg-white hover:border-white',
  'outline-light': 'border-white/40 text-white hover:border-white hover:bg-white hover:text-navy',
  'outline-dark': 'border-navy/25 text-navy hover:border-navy hover:bg-navy hover:text-white',
  dark: 'border-navy bg-navy text-white hover:bg-orange hover:border-orange hover:text-navy',
}

const sizes: Record<Size, string> = {
  sm: 'h-10 px-4 text-[0.6875rem]',
  md: 'h-12 px-6',
  lg: 'h-14 px-7 sm:px-8 text-[0.8125rem]',
}

type Common = { variant?: Variant; size?: Size; className?: string; children: ReactNode }

export function ButtonLink({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...rest
}: Common & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...rest}>
      {children}
    </a>
  )
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  type = 'button',
  ...rest
}: Common & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type={type} className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...rest}>
      {children}
    </button>
  )
}
