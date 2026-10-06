import styles from './FilterBar.module.css'

export type FilterOption<T extends string> = { value: T; label: string; count?: number }

type FilterBarProps<T extends string> = {
  /** Names the group for screen readers, e.g. "Show doctors from". */
  label: string
  options: readonly FilterOption<T>[]
  value: T
  onChange: (value: T) => void
}

/** A row of mutually exclusive toggle buttons. */
export function FilterBar<T extends string>({ label, options, value, onChange }: FilterBarProps<T>) {
  return (
    <div className={styles.bar} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={styles.option}
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
          {option.count !== undefined && <span className={styles.count}>{option.count}</span>}
        </button>
      ))}
    </div>
  )
}
