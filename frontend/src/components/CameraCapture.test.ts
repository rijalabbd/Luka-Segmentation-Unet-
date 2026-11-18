import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { mount, type VueWrapper } from '@vue/test-utils';
import { nextTick } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CameraCapture from './CameraCapture.vue';
import GhostOverlay from './GhostOverlay.vue';
import PhotoDropzone from './PhotoDropzone.vue';

const activeWrappers: VueWrapper[] = [];

function trackMount<T>(wrapper: T & VueWrapper): T & VueWrapper {
  activeWrappers.push(wrapper);
  return wrapper;
}

function camQuery<T extends Element = HTMLElement>(selector: string): T | null {
  return document.body.querySelector<T>(selector);
}

function createMockStream(options?: { torch?: boolean }) {
  const stop = vi.fn();
  const applyConstraints = vi.fn().mockResolvedValue(undefined);
  const track = {
    stop,
    kind: 'video',
    getCapabilities: () => ({ torch: Boolean(options?.torch) }),
    applyConstraints,
  } as unknown as MediaStreamTrack;
  const stream = {
    getTracks: () => [track],
    getVideoTracks: () => [track],
  } as unknown as MediaStream;
  return { stream, stop, applyConstraints };
}

function mockMatchMedia(coarseMatches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('any-pointer: coarse') ? coarseMatches : false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

function mockMediaDevices(getUserMediaImpl: ReturnType<typeof vi.fn>, deviceCount = 2) {
  const devices = Array.from({ length: deviceCount }, (_, i) => ({
    kind: 'videoinput',
    deviceId: `cam-${i}`,
    label: `Camera ${i}`,
  }));
  Object.defineProperty(navigator, 'mediaDevices', {
    writable: true,
    configurable: true,
    value: {
      getUserMedia: getUserMediaImpl,
      enumerateDevices: vi.fn().mockResolvedValue(devices),
    },
  });
}

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
  await nextTick();
}

describe('CameraCapture, PhotoDropzone & GhostOverlay (Tahap 2 & 2b)', () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.style.overflow = '';
    document.body.style.overflow = '';
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn(() => 'blob:mock-preview');
    } else {
      vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-preview');
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn();
    } else {
      vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    }
  });

  afterEach(() => {
    while (activeWrappers.length > 0) {
      activeWrappers.pop()?.unmount();
    }
    vi.restoreAllMocks();
    document.documentElement.style.overflow = '';
    document.body.style.overflow = '';
  });

  it('1. Konteks aman dengan getUserMedia: CameraCapture terbuka dan dirender ke body', async () => {
    mockMatchMedia(true);
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true });
    const { stream } = createMockStream();
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    mockMediaDevices(getUserMedia);

    const wrapper = trackMount(
      mount(PhotoDropzone, {
        props: { isFollowUp: true, refImageUrl: '/ref.jpg', refLabel: 'awal' },
      }),
    );

    await wrapper.find('#take-photo').trigger('click');
    await flushPromises();

    expect(wrapper.findComponent(CameraCapture).exists()).toBe(true);
    const camRoot = camQuery('.cam-root');
    expect(camRoot).not.toBeNull();
    expect(camRoot?.parentElement).toBe(document.body);
    const videoEl = camQuery<HTMLVideoElement>('video.cam-video');
    expect(videoEl).not.toBeNull();
    expect(videoEl?.hasAttribute('playsinline')).toBe(true);
    expect(document.documentElement.style.overflow).toBe('hidden');
    expect(document.body.style.overflow).toBe('hidden');
    expect(getUserMedia).toHaveBeenCalledTimes(1);
  });

  it('2. Konteks tidak aman: memicu input tahap 1 dan baris keterangan hanya muncul pada kunjungan lanjutan', async () => {
    mockMatchMedia(true);
    Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true });
    mockMediaDevices(vi.fn());

    const followUp = trackMount(
      mount(PhotoDropzone, {
        props: { isFollowUp: true, refImageUrl: '/ref.jpg', refLabel: 'awal' },
      }),
    );
    const camInput1 = followUp.find('#file-camera').element as HTMLInputElement;
    const clickSpy1 = vi.spyOn(camInput1, 'click').mockImplementation(() => {});

    await followUp.find('#take-photo').trigger('click');
    expect(followUp.findComponent(CameraCapture).exists()).toBe(false);
    expect(clickSpy1).toHaveBeenCalledTimes(1);
    expect(followUp.find('#cam-fallback-note').text()).toBe(
      'Bayangan foto awal hanya tersedia lewat HTTPS. Memakai kamera bawaan ponsel.',
    );

    const baseline = trackMount(
      mount(PhotoDropzone, {
        props: { isFollowUp: false, refImageUrl: null },
      }),
    );
    const camInput2 = baseline.find('#file-camera').element as HTMLInputElement;
    const clickSpy2 = vi.spyOn(camInput2, 'click').mockImplementation(() => {});

    await baseline.find('#take-photo').trigger('click');
    expect(clickSpy2).toHaveBeenCalledTimes(1);
    expect(baseline.find('#cam-fallback-note').exists()).toBe(false);
  });

  it.each([
    [
      'NotAllowedError',
      'Izin kamera ditolak. Izinkan kamera di pengaturan browser, atau pakai kamera bawaan.',
    ],
    ['NotFoundError', 'Kamera tidak ditemukan.'],
    ['NotReadableError', 'Kamera sedang dipakai aplikasi lain.'],
  ])('3. %s menampilkan pesan tepat dan tombol cadangan memicu fallback', async (errName, expectedMsg) => {
    const err = new Error('mock error');
    err.name = errName;
    const getUserMedia = vi.fn().mockRejectedValue(err);
    mockMediaDevices(getUserMedia);

    const wrapper = trackMount(mount(CameraCapture));
    await flushPromises();

    expect(camQuery('.cam-error-msg')?.textContent).toBe(expectedMsg);
    camQuery<HTMLButtonElement>('#cam-fallback-btn')?.click();
    await nextTick();

    const emitted = wrapper.emitted('fallback');
    expect(emitted).toBeTruthy();
    expect(emitted?.[0]?.[0]).toBe(expectedMsg);
  });

  it('4. OverconstrainedError memanggil getUserMedia kedua kali tanpa resolusi ideal', async () => {
    const err = new Error('overconstrained');
    err.name = 'OverconstrainedError';
    const { stream } = createMockStream();
    const getUserMedia = vi
      .fn()
      .mockRejectedValueOnce(err)
      .mockResolvedValueOnce(stream);
    mockMediaDevices(getUserMedia);

    trackMount(mount(CameraCapture));
    await flushPromises();

    expect(getUserMedia).toHaveBeenCalledTimes(2);
    const firstCall = getUserMedia.mock.calls[0][0] as MediaStreamConstraints;
    const secondCall = getUserMedia.mock.calls[1][0] as MediaStreamConstraints;
    expect((firstCall.video as MediaTrackConstraints).width).toEqual({ ideal: 1920 });
    expect((secondCall.video as MediaTrackConstraints).width).toBeUndefined();
    expect((secondCall.video as MediaTrackConstraints).height).toBeUndefined();
  });

  it('5. refImageUrl kosong: tanpa bayangan, tombol Bayangan, maupun panel kontrol', async () => {
    const { stream } = createMockStream();
    mockMediaDevices(vi.fn().mockResolvedValue(stream));

    trackMount(
      mount(CameraCapture, {
        props: { refImageUrl: null, refLabel: 'awal' },
      }),
    );
    await flushPromises();

    expect(camQuery('.cam-shadow-img')).toBeNull();
    expect(camQuery('#cam-shadow-panel-btn')).toBeNull();
    expect(camQuery('#cam-opacity')).toBeNull();
    expect(camQuery('.cam-shadow-label')).toBeNull();
  });

  it('6. refImageUrl terisi: panel Bayangan tertutup secara bawaan, terbuka saat tombol Bayangan ditekan, dan label Garis bantu konsisten', async () => {
    const { stream } = createMockStream();
    mockMediaDevices(vi.fn().mockResolvedValue(stream));

    trackMount(
      mount(CameraCapture, {
        props: { refImageUrl: '/api/v1/storage/uploads/ref.jpg', refLabel: 'awal' },
      }),
    );
    await flushPromises();

    expect(camQuery('.cam-shadow-img')).not.toBeNull();
    expect(camQuery('.cam-shadow-label')).toBeNull();
    expect(camQuery('#cam-opacity')).toBeNull();

    const gridBtn = camQuery<HTMLButtonElement>('#cam-grid-toggle');
    expect(gridBtn?.textContent?.trim()).toBe('Garis bantu: mati');
    gridBtn?.click();
    await nextTick();
    expect(gridBtn?.textContent?.trim()).toBe('Garis bantu: nyala');

    const panelBtn = camQuery<HTMLButtonElement>('#cam-shadow-panel-btn');
    expect(panelBtn?.textContent?.trim()).toBe('Bayangan');
    panelBtn?.click();
    await nextTick();

    expect(camQuery('#cam-opacity')).not.toBeNull();
    expect(camQuery('#cam-scale')).not.toBeNull();
    expect(camQuery('#cam-toggle-shadow')).not.toBeNull();
    const resetBtn = camQuery<HTMLButtonElement>('#cam-reset-shadow');
    expect(resetBtn?.textContent?.trim()).toBe('Kembalikan');
  });

  it('7. Rana ditekan lalu Pakai foto ini: emit capture(File image/jpeg) dan semua track berhenti', async () => {
    const { stream, stop } = createMockStream();
    mockMediaDevices(vi.fn().mockResolvedValue(stream));

    const drawImage = vi.fn();
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      drawImage,
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((cb) => {
      cb(new Blob(['jpeg-bytes'], { type: 'image/jpeg' }));
    });

    const wrapper = trackMount(
      mount(CameraCapture, {
        props: { refImageUrl: '/ref.jpg', refLabel: 'awal' },
      }),
    );
    await flushPromises();

    const videoEl = camQuery<HTMLVideoElement>('video')!;
    Object.defineProperty(videoEl, 'videoWidth', { value: 1280, configurable: true });
    Object.defineProperty(videoEl, 'videoHeight', { value: 960, configurable: true });
    videoEl.dispatchEvent(new Event('loadedmetadata'));
    await nextTick();

    camQuery<HTMLButtonElement>('#cam-shutter')?.click();
    await flushPromises();

    // Selama pratinjau, stream tetap hidup
    expect(stop).not.toHaveBeenCalled();
    expect(camQuery('#cam-use-photo')).not.toBeNull();
    expect(camQuery('.cam-instruction')?.textContent?.trim()).toBe(
      'Periksa fokus dan cahaya. Luka harus terlihat jelas.',
    );

    camQuery<HTMLButtonElement>('#cam-use-photo')?.click();
    await nextTick();
    const captured = wrapper.emitted('capture');
    expect(captured).toBeTruthy();
    const file = captured?.[0]?.[0] as File;
    expect(file).toBeInstanceOf(File);
    expect(file.type).toBe('image/jpeg');
    expect(stop).toHaveBeenCalledTimes(1);
    expect(document.documentElement.style.overflow).toBe('');
    expect(document.body.style.overflow).toBe('');
  });

  it('8. Ulangi tidak memanggil getUserMedia lagi', async () => {
    const { stream, stop } = createMockStream();
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    mockMediaDevices(getUserMedia);

    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((cb) => {
      cb(new Blob(['jpeg-bytes'], { type: 'image/jpeg' }));
    });

    trackMount(mount(CameraCapture));
    await flushPromises();

    const videoEl = camQuery<HTMLVideoElement>('video')!;
    videoEl.dispatchEvent(new Event('loadedmetadata'));
    await nextTick();

    camQuery<HTMLButtonElement>('#cam-shutter')?.click();
    await flushPromises();

    camQuery<HTMLButtonElement>('#cam-retake')?.click();
    await flushPromises();

    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(stop).not.toHaveBeenCalled();
    expect(camQuery('#cam-shutter')).not.toBeNull();
  });

  it('9. Pembongkaran komponen menghentikan semua track dan melepas kunci scroll', async () => {
    const { stream, stop } = createMockStream();
    mockMediaDevices(vi.fn().mockResolvedValue(stream));

    const wrapper = trackMount(mount(CameraCapture));
    await flushPromises();

    expect(document.documentElement.style.overflow).toBe('hidden');
    expect(document.body.style.overflow).toBe('hidden');

    wrapper.unmount();
    expect(stop).toHaveBeenCalledTimes(1);
    expect(document.documentElement.style.overflow).toBe('');
    expect(document.body.style.overflow).toBe('');
  });

  it('10. GhostOverlay.vue tetap bekerja dengan benar setelah ekstraksi composable', () => {
    const wrapper = trackMount(
      mount(GhostOverlay, {
        props: {
          previewUrl: '/today.jpg',
          fileName: 'luka.jpg',
          fileSizeText: '120 KB',
          refImageUrl: '/ref.jpg',
          ghostActive: true,
          ghostOpacity: 60,
          ghostScale: 110,
          ghostX: 10,
          ghostY: -5,
        },
      }),
    );

    const ghostImg = wrapper.find('#ghost');
    expect(ghostImg.exists()).toBe(true);
    expect((ghostImg.element as HTMLImageElement).style.opacity).toBe('0.6');
    expect((ghostImg.element as HTMLImageElement).style.transform).toBe(
      'translate(10px, -5px) scale(1.1)',
    );
    expect(wrapper.find('#fname').text()).toBe('luka.jpg');
  });

  it('11. CSS h3_unggah.css memuat .cam-root dengan position: fixed tanpa blok scoped', () => {
    const cssPath = resolve(process.cwd(), 'src/assets/h3_unggah.css');
    const cssText = readFileSync(cssPath, 'utf-8');
    const camRootMatch = cssText.match(/\.cam-root\s*\{[^}]*\}/);
    expect(camRootMatch).not.toBeNull();
    expect(camRootMatch?.[0]).toContain('position: fixed');
    expect(camRootMatch?.[0]).not.toContain('width: 100vw');

    const camVueText = readFileSync(
      resolve(process.cwd(), 'src/components/CameraCapture.vue'),
      'utf-8',
    );
    const unggahVueText = readFileSync(
      resolve(process.cwd(), 'src/views/UnggahFotoView.vue'),
      'utf-8',
    );
    expect(camVueText).not.toMatch(/<style[^>]*\bscoped\b/);
    expect(unggahVueText).not.toMatch(/<style[^>]*\bscoped\b[^>]*h3_unggah\.css/);
  });

  it('12. Senter (torch) hanya muncul bila didukung dan memanggil applyConstraints saat ditekan', async () => {
    const noTorch = createMockStream({ torch: false });
    mockMediaDevices(vi.fn().mockResolvedValue(noTorch.stream));
    const w1 = trackMount(mount(CameraCapture));
    await flushPromises();
    expect(camQuery('#cam-torch')).toBeNull();
    w1.unmount();

    const withTorch = createMockStream({ torch: true });
    mockMediaDevices(vi.fn().mockResolvedValue(withTorch.stream));
    trackMount(mount(CameraCapture));
    await flushPromises();

    const torchBtn = camQuery<HTMLButtonElement>('#cam-torch');
    expect(torchBtn).not.toBeNull();
    expect(torchBtn?.textContent?.trim()).toBe('Senter');

    torchBtn?.click();
    await flushPromises();
    expect(withTorch.applyConstraints).toHaveBeenCalledWith({
      advanced: [{ torch: true }],
    });
    expect(torchBtn?.textContent?.trim()).toBe('Senter: Nyala');
  });

  it('13. Tangkapan kanvas memotong sesuai rasio layar stage (object-fit: cover)', async () => {
    const { stream } = createMockStream();
    mockMediaDevices(vi.fn().mockResolvedValue(stream));

    const drawImage = vi.fn();
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      drawImage,
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((cb) => {
      cb(new Blob(['jpeg-bytes'], { type: 'image/jpeg' }));
    });

    trackMount(mount(CameraCapture));
    await flushPromises();

    const videoEl = camQuery<HTMLVideoElement>('video')!;
    Object.defineProperty(videoEl, 'videoWidth', { value: 1600, configurable: true });
    Object.defineProperty(videoEl, 'videoHeight', { value: 1200, configurable: true });
    vi.spyOn(videoEl, 'getBoundingClientRect').mockReturnValue({
      width: 360,
      height: 540,
      top: 0,
      left: 0,
      right: 360,
      bottom: 540,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    } as DOMRect);

    videoEl.dispatchEvent(new Event('loadedmetadata'));
    await nextTick();

    camQuery<HTMLButtonElement>('#cam-shutter')?.click();
    await flushPromises();

    expect(drawImage).toHaveBeenCalledWith(videoEl, 400, 0, 800, 1200, 0, 0, 800, 1200);
  });

  it('14 (I.2). Panel Bayangan menutup otomatis 3 detik setelah interaksi terakhir dan dapat dibuka kembali', async () => {
    vi.useFakeTimers();
    try {
      const { stream } = createMockStream();
      mockMediaDevices(vi.fn().mockResolvedValue(stream));

      trackMount(
        mount(CameraCapture, {
          props: { refImageUrl: '/api/v1/storage/uploads/ref.jpg', refLabel: 'awal' },
        }),
      );
      await flushPromises();

      const panelBtn = camQuery<HTMLButtonElement>('#cam-shadow-panel-btn')!;
      panelBtn.click();
      await nextTick();
      expect(camQuery('.cam-shadow-ctl')).not.toBeNull();

      // Setelah 2 detik berinteraksi dengan tombol geser -> timer diperpanjang
      vi.advanceTimersByTime(2000);
      await nextTick();
      expect(camQuery('.cam-shadow-ctl')).not.toBeNull();

      camQuery<HTMLButtonElement>('#cam-nudge-right')?.click();
      await nextTick();

      // 2 detik lagi (total 4s dari buka, tapi baru 2s dari klik terakhir) -> panel masih terbuka
      vi.advanceTimersByTime(2000);
      await nextTick();
      expect(camQuery('.cam-shadow-ctl')).not.toBeNull();

      // 1,1 detik lagi (>= 3 detik sejak klik terakhir) -> panel menutup sendiri
      vi.advanceTimersByTime(1100);
      await nextTick();
      expect(camQuery('.cam-shadow-ctl')).toBeNull();

      // Tombol Bayangan membukanya kembali
      panelBtn.click();
      await nextTick();
      expect(camQuery('.cam-shadow-ctl')).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});
