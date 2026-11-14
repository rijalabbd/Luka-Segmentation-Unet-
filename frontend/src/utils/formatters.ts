const MONTHS_SHORT = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'Mei',
  'Jun',
  'Jul',
  'Agu',
  'Sep',
  'Okt',
  'Nov',
  'Des',
]

export function getTodayISO(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function formatDateID(isoDate: string | null | undefined): string {
  if (!isoDate) return '-'
  const parts = isoDate.split('-').map(Number)
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return isoDate
  const [y, m, d] = parts
  const monthName = MONTHS_SHORT[(m ?? 1) - 1] ?? ''
  return `${String(d).padStart(2, '0')} ${monthName} ${y}`
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`
  }
  return `${(bytes / (1048576)).toFixed(1)} MB`
}

export function formatDecimalID(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '–'
  return value.toFixed(digits).replace('.', ',')
}

export function formatSignedDecimalID(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '–'
  const roundedZero = Math.abs(value) < 0.5 * Math.pow(10, -digits)
  const sign = roundedZero ? '' : value > 0 ? '+' : '−'
  return `${sign}${Math.abs(value).toFixed(digits).replace('.', ',')}`
}
