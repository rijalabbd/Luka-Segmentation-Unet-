export interface WarningMeta {
  code: string
  title: string
  text: string
  strong: boolean
  role: 'alert' | 'status'
}

export const WARNING_DEFINITIONS: Record<string, Omit<WarningMeta, 'code'>> = {
  DISTANCE_SENSITIVE: {
    title: 'Perhatikan variasi jarak pemotretan',
    text: 'Perubahan sekecil ini dapat dipengaruhi variasi jarak pemotretan (±1 cm). Jika foto memuat penggaris, gunakan kalibrasi. Konfirmasi dengan pemeriksaan klinis langsung.',
    strong: false,
    role: 'status',
  },
  DISTANCE_LARGE: {
    title: 'Perubahan besar pada foto tanpa kalibrasi',
    text: 'Pada foto tanpa kalibrasi, selisih jarak pemotretan dapat menimbulkan perubahan luas semu yang besar (misalnya selisih 5 cm pada jarak 20 cm setara sekitar 36%). Periksa kembali jarak foto dengan overlay, atau gunakan kalibrasi jika ada penggaris.',
    strong: true,
    role: 'alert',
  },
  MIXED_BASIS: {
    title: 'PAC memakai luas relatif',
    text: 'PAC dihitung dengan luas relatif karena kunjungan awal tidak terkalibrasi. Kunjungan awal (baseline A₀) tidak memiliki data kalibrasi penggaris, sehingga perbandingan longitudinal tetap menggunakan basis persentase area citra (%).',
    strong: false,
    role: 'status',
  },
  LOW_BASELINE: {
    title: 'Luas awal sangat kecil',
    text: 'Luas awal kurang dari 1% dari citra, sehingga PAC sangat sensitif terhadap selisih kecil jumlah piksel.',
    strong: false,
    role: 'status',
  },
}

/**
 * Filter dan petakan kode peringatan sesuai basis PAC:
 * peringatan variasi jarak (DISTANCE_SENSITIVE / DISTANCE_LARGE) hanya berlaku pada pac_basis === 'relative'.
 */
export function buildActiveWarnings(
  warnings: string[] | null | undefined,
  pacBasis: 'relative' | 'calibrated' | null | undefined,
): WarningMeta[] {
  const list: WarningMeta[] = []
  for (const code of warnings ?? []) {
    if (
      (code === 'DISTANCE_SENSITIVE' || code === 'DISTANCE_LARGE') &&
      pacBasis !== 'relative'
    ) {
      continue
    }
    const def = WARNING_DEFINITIONS[code]
    if (def) {
      list.push({ code, ...def })
    }
  }
  return list
}

export type TrendClass = 'down' | 'up' | 'flat' | 'na'

export function getTrendCssClass(trendStatus: string | null | undefined): TrendClass {
  const txt = (trendStatus || '').toLowerCase()
  if (txt.includes('tidak dapat dihitung')) return 'na'
  if (txt.includes('menurun')) return 'down'
  if (txt.includes('meningkat')) return 'up'
  return 'flat'
}
