import type { SVGProps } from 'react'

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  viewBox: '0 0 24 24',
  'aria-hidden': true,
} as const

type Props = SVGProps<SVGSVGElement>

export const LogoIcon = (p: Props) => (
  <svg {...base} {...p}>
    <path d="M6 3h8l4 4v8" />
    <path d="M6 3v18h7" />
    <circle cx="16.5" cy="16.5" r="3.5" />
    <path d="m19 19 2.5 2.5" />
  </svg>
)
export const UploadIcon = (p: Props) => (
  <svg {...base} {...p}>
    <path d="M12 16V4M7 9l5-5 5 5" />
    <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
  </svg>
)
export const CameraIcon = (p: Props) => (
  <svg {...base} {...p}>
    <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
    <circle cx="12" cy="13" r="3.5" />
  </svg>
)
export const DriveIcon = (p: Props) => (
  <svg {...base} {...p}>
    <path d="M8.5 4h7l6 10.5-3.5 6h-12L2.5 14.5z" />
    <path d="M8.5 4l6.5 10.5h6.5M2.5 14.5h12.5l-3.5 6" />
  </svg>
)
export const CheckIcon = (p: Props) => (
  <svg {...base} {...p}>
    <path d="m5 12.5 4.5 4.5L19 7.5" />
  </svg>
)
export const AlertIcon = (p: Props) => (
  <svg {...base} {...p}>
    <path d="M12 4 2.5 20h19z" />
    <path d="M12 10v4.5M12 17.5v.01" />
  </svg>
)
export const CloseIcon = (p: Props) => (
  <svg {...base} {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
)
export const TrashIcon = (p: Props) => (
  <svg {...base} {...p}>
    <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" />
  </svg>
)
export const LockIcon = (p: Props) => (
  <svg {...base} {...p}>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
)
export const Spinner = ({ className = '' }: { className?: string }) => (
  <span
    className={`inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-r-transparent ${className}`}
    aria-hidden="true"
  />
)
