import { mount, type VueWrapper } from '@vue/test-utils';
import { nextTick } from 'vue';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { VisitRecord } from '@/types/patient';
import RulerCalibration from './RulerCalibration.vue';

const activeWrappers: VueWrapper[] = [];

function trackMount<T>(wrapper: T & VueWrapper): T & VueWrapper {
  activeWrappers.push(wrapper);
  return wrapper;
}

function makeDraftVisit(overrides: Partial<VisitRecord> = {}): VisitRecord {
  return {
    id: 60,
    patient_id: 'RM-0017',
    visit_date: '2026-11-18',
    status: 'draft',
    visit_index: 2,
    image_path: 'uploads/P17T_2.jpg',
    mask_path: 'masks/P17T_2.png',
    overlay_path: 'overlays/P17T_2.png',
    distance_confirmed: true,
    confirm_zero_area: false,
    n_wound_px: 3168,
    area_pct: 4.83,
    delta_area: null,
    pac: null,
    trend_status: null,
    measure_mode: 'relative',
    img_width_px: 640,
    img_height_px: 480,
    calib_x1: null,
    calib_y1: null,
    calib_x2: null,
    calib_y2: null,
    calib_length_cm: null,
    scale_cm_per_px: null,
    area_cm2: null,
    pac_rel: null,
    pac_cm2: null,
    pac_basis: null,
    preview: null,
    clinician_notes: null,
    patient_narrative: null,
    narrative_source: null,
    warnings: [],
    created_at: '2026-11-18T00:00:00Z',
    confirmed_at: null,
    ...overrides,
  };
}

function mockImageRect(imgEl: HTMLImageElement, width = 320, height = 240) {
  vi.spyOn(imgEl, 'getBoundingClientRect').mockReturnValue({
    left: 0,
    top: 0,
    right: width,
    bottom: height,
    width,
    height,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  } as DOMRect);
}

describe('RulerCalibration', () => {
  afterEach(() => {
    while (activeWrappers.length > 0) {
      activeWrappers.pop()?.unmount();
    }
    vi.restoreAllMocks();
  });

  it('C.3: loupe memiliki latar gambar tidak kosong dan posisi latarnya mengikuti titik', async () => {
    const visit = makeDraftVisit();
    const imageUrl = 'http://localhost:8000/api/v1/storage/uploads/P17T_2.jpg';
    const wrapper = trackMount(
      mount(RulerCalibration, {
        props: { visit, imageUrl },
      }),
    );

    await wrapper.find('#calbox > summary').trigger('click');
    await nextTick();

    const imgEl = wrapper.find('#calImg').element as HTMLImageElement;
    mockImageRect(imgEl, 320, 240);
    await wrapper.find('#calImg').trigger('load');
    await nextTick();

    await wrapper.find('#calImg').trigger('pointerdown', {
      clientX: 100,
      clientY: 80,
      pointerId: 1,
      pointerType: 'touch',
      button: 0,
    });
    await nextTick();

    const loupe1 = wrapper.find('.cal-loupe');
    expect(loupe1.exists()).toBe(true);
    const style1 = (loupe1.element as HTMLElement).style;
    expect(style1.backgroundImage).toContain(imageUrl);
    expect(style1.backgroundSize).toBe('800px 600px');
    // half (56) - 100 * 2.5 = -194px; half (56) - 80 * 2.5 = -144px
    expect(style1.backgroundPosition).toBe('-194px -144px');

    await wrapper.find('#calImg').trigger('pointermove', {
      clientX: 160,
      clientY: 120,
      pointerId: 1,
      pointerType: 'touch',
    });
    await nextTick();

    const style2 = (wrapper.find('.cal-loupe').element as HTMLElement).style;
    expect(style2.backgroundPosition).toBe('-344px -244px');
  });

  it('D.1 & D.2: kartu luas tampil "–" sebelum Terapkan, berubah jadi "Sudah diterapkan", dan kembali "–" saat diubah; preset 1/2/5/10 cm', async () => {
    const visit = makeDraftVisit();
    const wrapper = trackMount(
      mount(RulerCalibration, {
        props: { visit, imageUrl: 'http://localhost:8000/api/v1/storage/uploads/P17T_2.jpg' },
      }),
    );

    await wrapper.find('#calbox > summary').trigger('click');
    await nextTick();

    const presetTexts = wrapper.findAll('.cal-preset-btn').map((b) => b.text());
    expect(presetTexts).toEqual(['1 cm', '2 cm', '5 cm', '10 cm']);

    // Sebelum diterapkan: isi koordinat tidak langsung mengisi kartu luas
    await wrapper.find('#calX1').setValue('100');
    await wrapper.find('#calY1').setValue('100');
    await wrapper.find('#calX2').setValue('200');
    await wrapper.find('#calY2').setValue('100');
    await nextTick();

    expect(wrapper.find('#calChip').text()).toBe('Belum diterapkan');
    expect(wrapper.find('#oArea').text()).toBe('–');

    // Setelah diterapkan dari server: lencana "Sudah diterapkan" dan angka muncul
    const appliedVisit = makeDraftVisit({
      measure_mode: 'calibrated',
      calib_x1: 100,
      calib_y1: 100,
      calib_x2: 200,
      calib_y2: 100,
      calib_length_cm: 2,
      scale_cm_per_px: 0.02,
      area_cm2: 5.3,
    });
    await wrapper.setProps({ visit: appliedVisit });
    await nextTick();

    expect(wrapper.find('#calChip').text()).toBe('Sudah diterapkan');
    expect(wrapper.find('#oArea').text()).toBe('5,3 cm²');

    // Saat preset jarak diubah ke 10 cm, lencana kembali Belum diterapkan dan kartu kembali "–"
    await wrapper.findAll('.cal-preset-btn')[3].trigger('click');
    await nextTick();

    expect(wrapper.find('#calChip').text()).toBe('Belum diterapkan');
    expect(wrapper.find('#oArea').text()).toBe('–');
  });

  it('D.3: kontrol zoom memperbesar foto antara 1× hingga 4×', async () => {
    const wrapper = trackMount(
      mount(RulerCalibration, {
        props: { visit: makeDraftVisit(), imageUrl: 'http://localhost:8000/api/v1/storage/uploads/P17T_2.jpg' },
      }),
    );

    await wrapper.find('#calbox > summary').trigger('click');
    await nextTick();

    expect(wrapper.find('#calZoomVal').text()).toBe('1×');
    expect((wrapper.find('#calZoomOut').element as HTMLButtonElement).disabled).toBe(true);

    await wrapper.find('#calZoomIn').trigger('click');
    expect(wrapper.find('#calZoomVal').text()).toBe('1,5×');

    for (let i = 0; i < 6; i++) {
      await wrapper.find('#calZoomIn').trigger('click');
    }
    expect(wrapper.find('#calZoomVal').text()).toBe('4×');
    expect((wrapper.find('#calZoomIn').element as HTMLButtonElement).disabled).toBe(true);

    await wrapper.find('#calZoomReset').trigger('click');
    expect(wrapper.find('#calZoomVal').text()).toBe('1×');
  });
});
