/**
 * The CityCare mark: a plus whose centre is a node, for hospitals joined into one network. Drawn in the brand colour
 * (--sign, set from src/config/hospital.ts), so a hospital that changes its colour changes the logo too. Decorative:
 * the hospital's name is always next to it, so it is hidden from screen readers.
 */
export function Logo({ size = 36, className }: { size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 40 40"
      aria-hidden="true"
      focusable="false"
    >
      <rect width="40" height="40" rx="11" fill="var(--sign)" />
      <path d="M20 9.5v21M9.5 20h21" stroke="#fff" strokeWidth="6" strokeLinecap="round" />
      <circle cx="20" cy="20" r="3.6" fill="var(--sign)" />
      <circle cx="20" cy="20" r="1.7" fill="#8be3d6" />
    </svg>
  )
}
