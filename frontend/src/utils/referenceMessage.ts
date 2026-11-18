import type { VisitRecord } from '../types/patient';

export interface ReferenceComparisonInfo {
  effectiveRefVisit: VisitRecord | null;
  hasDistinctLatestWithPhoto: boolean;
  latestWithPhotoVisit: VisitRecord | null;
  comparisonSentence: string;
  missingPhotoSentence: string;
}

function joinIndonesianList(items: string[]): string {
  if (items.length === 0) return '';
  if (items.length === 1) return items[0];
  if (items.length === 2) return `${items[0]} dan ${items[1]}`;
  return `${items.slice(0, -1).join(', ')}, dan ${items[items.length - 1]}`;
}

export function buildReferenceComparisonInfo(
  finalVisits: VisitRecord[],
  activeTab: 'baseline' | 'latest',
  formatDateFn: (dateStr: string | null | undefined) => string,
): ReferenceComparisonInfo {
  const visitsWithPhoto = finalVisits.filter((v) => Boolean(v.image_path && v.image_path.trim()));
  const visitsWithoutPhoto = finalVisits.filter((v) => !v.image_path || !v.image_path.trim());

  const firstWithPhoto = visitsWithPhoto[0] ?? null;
  const lastWithPhoto = visitsWithPhoto[visitsWithPhoto.length - 1] ?? null;
  const firstDate = firstWithPhoto?.visit_date?.slice(0, 10) ?? '';
  const lastDate = lastWithPhoto?.visit_date?.slice(0, 10) ?? '';
  const hasDistinctLatestWithPhoto = Boolean(
    firstWithPhoto &&
      lastWithPhoto &&
      firstWithPhoto.id !== lastWithPhoto.id &&
      firstWithPhoto.image_path !== lastWithPhoto.image_path &&
      firstDate !== lastDate,
  );

  const isUsingLatest = activeTab === 'latest' && hasDistinctLatestWithPhoto;
  const effectiveRefVisit = isUsingLatest ? lastWithPhoto : firstWithPhoto;

  const comparisonSentence = effectiveRefVisit
    ? `${isUsingLatest ? 'Foto terakhir' : 'Foto awal'} dari ${formatDateFn(effectiveRefVisit.visit_date)} dipakai sebagai pembanding.`
    : 'Belum ada foto pembanding dari kunjungan sebelumnya. Ikuti panduan foto di bawah.';

  const missingDates = visitsWithoutPhoto.map((v) => formatDateFn(v.visit_date));
  const missingPhotoSentence =
    missingDates.length > 0 ? `Kunjungan ${joinIndonesianList(missingDates)} tidak punya foto.` : '';

  return {
    effectiveRefVisit,
    hasDistinctLatestWithPhoto,
    latestWithPhotoVisit: hasDistinctLatestWithPhoto ? lastWithPhoto : null,
    comparisonSentence,
    missingPhotoSentence,
  };
}
