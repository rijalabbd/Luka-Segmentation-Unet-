import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CameraCapture from './CameraCapture.vue';
import GhostOverlay from './GhostOverlay.vue';
import PhotoDropzone from './PhotoDropzone.vue';

function createMockStream() {
  const stop = vi.fn();
  const track = { stop, kind: 'video' } as unknown as MediaStreamTrack;
  const stream = {
    getTracks: () => [track],
  } as unknown as MediaStream;
  return { stream, stop };
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
}

describe('CameraCapture, PhotoDropzone & GhostOverlay (Tahap 2)', () => {
  beforeEach(() => {
    window.localStorage.clear();
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
    vi.restoreAllMocks();
    document.body.style.overflow = '';
  });

  it('1. Konteks aman dengan getUserMedia: CameraCapture terbuka saat tombol Ambil Foto ditekan', async () => {
    mockMatchMedia(true);
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true });
    const { stream } = createMockStream();
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    mockMediaDevices(getUserMedia);

    const wrapper = mount(PhotoDropzone, {
      props: { isFollowUp: true, refImageUrl: '/ref.jpg', refLabel: 'awal' },
    });

    await wrapper.find('#take-photo').trigger('click');
    await flushPromises();

    expect(wrapper.findComponent(CameraCapture).exists()).toBe(true);
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it('2. Konteks tidak aman: memicu input tahap 1 dan baris keterangan hanya muncul pada kunjungan lanjutan', async () => {
    mockMatchMedia(true);
    Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true });
    mockMediaDevices(vi.fn());

    // Kunjungan lanjutan -> baris keterangan muncul
    const followUp = mount(PhotoDropzone, {
      props: { isFollowUp: true, refImageUrl: '/ref.jpg', refLabel: 'awal' },
    });
    const camInput1 = followUp.find('#file-camera').element as HTMLInputElement;
    const clickSpy1 = vi.spyOn(camInput1, 'click').mockImplementation(() => {});

    await followUp.find('#take-photo').trigger('click');
    expect(followUp.findComponent(CameraCapture).exists()).toBe(false);
    expect(clickSpy1).toHaveBeenCalledTimes(1);
    expect(followUp.find('#cam-fallback-note').text()).toBe(
      'Bayangan foto awal hanya tersedia lewat HTTPS. Memakai kamera bawaan ponsel.',
    );
    followUp.unmount();

    // Kunjungan pertama -> input terpicu tanpa baris keterangan
    const baseline = mount(PhotoDropzone, {
      props: { isFollowUp: false, refImageUrl: null },
    });
    const camInput2 = baseline.find('#file-camera').element as HTMLInputElement;
    const clickSpy2 = vi.spyOn(camInput2, 'click').mockImplementation(() => {});

    await baseline.find('#take-photo').trigger('click');
    expect(clickSpy2).toHaveBeenCalledTimes(1);
    expect(baseline.find('#cam-fallback-note').exists()).toBe(false);
    baseline.unmount();
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

    const wrapper = mount(CameraCapture);
    await flushPromises();

    expect(wrapper.find('.cam-error-msg').text()).toBe(expectedMsg);
    await wrapper.find('#cam-fallback-btn').trigger('click');

    const emitted = wrapper.emitted('fallback');
    expect(emitted).toBeTruthy();
    expect(emitted?.[0]?.[0]).toBe(expectedMsg);
    wrapper.unmount();
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

    const wrapper = mount(CameraCapture);
    await flushPromises();

    expect(getUserMedia).toHaveBeenCalledTimes(2);
    const firstCall = getUserMedia.mock.calls[0][0] as MediaStreamConstraints;
    const secondCall = getUserMedia.mock.calls[1][0] as MediaStreamConstraints;
    expect((firstCall.video as MediaTrackConstraints).width).toEqual({ ideal: 1920 });
    expect((secondCall.video as MediaTrackConstraints).width).toBeUndefined();
    expect((secondCall.video as MediaTrackConstraints).height).toBeUndefined();
    wrapper.unmount();
  });

  it('5. refImageUrl kosong: tanpa bayangan, slider, maupun label', async () => {
    const { stream } = createMockStream();
    mockMediaDevices(vi.fn().mockResolvedValue(stream));

    const wrapper = mount(CameraCapture, {
      props: { refImageUrl: null, refLabel: 'awal' },
    });
    await flushPromises();

    expect(wrapper.find('.cam-shadow-img').exists()).toBe(false);
    expect(wrapper.find('#cam-opacity').exists()).toBe(false);
    expect(wrapper.find('.cam-shadow-label').exists()).toBe(false);
    wrapper.unmount();
  });

  it('6. refImageUrl terisi: bayangan, slider, dan label "Bayangan: foto awal" muncul', async () => {
    const { stream } = createMockStream();
    mockMediaDevices(vi.fn().mockResolvedValue(stream));

    const wrapper = mount(CameraCapture, {
      props: { refImageUrl: '/api/v1/storage/uploads/ref.jpg', refLabel: 'awal' },
    });
    await flushPromises();

    expect(wrapper.find('.cam-shadow-img').exists()).toBe(true);
    expect(wrapper.find('#cam-opacity').exists()).toBe(true);
    expect(wrapper.find('.cam-shadow-label').text()).toBe('Bayangan: foto awal');
    wrapper.unmount();
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

    const wrapper = mount(CameraCapture, {
      props: { refImageUrl: '/ref.jpg', refLabel: 'awal' },
    });
    await flushPromises();

    const videoEl = wrapper.find('video').element as HTMLVideoElement;
    Object.defineProperty(videoEl, 'videoWidth', { value: 1280, configurable: true });
    Object.defineProperty(videoEl, 'videoHeight', { value: 960, configurable: true });
    await wrapper.find('video').trigger('loadedmetadata');

    await wrapper.find('#cam-shutter').trigger('click');
    await flushPromises();

    // Selama pratinjau, stream tetap hidup
    expect(stop).not.toHaveBeenCalled();
    expect(wrapper.find('#cam-use-photo').exists()).toBe(true);

    await wrapper.find('#cam-use-photo').trigger('click');
    const captured = wrapper.emitted('capture');
    expect(captured).toBeTruthy();
    const file = captured?.[0]?.[0] as File;
    expect(file).toBeInstanceOf(File);
    expect(file.type).toBe('image/jpeg');
    expect(stop).toHaveBeenCalledTimes(1);
    wrapper.unmount();
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

    const wrapper = mount(CameraCapture);
    await flushPromises();
    await wrapper.find('video').trigger('loadedmetadata');
    await wrapper.find('#cam-shutter').trigger('click');
    await flushPromises();

    await wrapper.find('#cam-retake').trigger('click');
    await flushPromises();

    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(stop).not.toHaveBeenCalled();
    expect(wrapper.find('#cam-shutter').exists()).toBe(true);
    wrapper.unmount();
  });

  it('9. Pembongkaran komponen menghentikan semua track', async () => {
    const { stream, stop } = createMockStream();
    mockMediaDevices(vi.fn().mockResolvedValue(stream));

    const wrapper = mount(CameraCapture);
    await flushPromises();

    wrapper.unmount();
    expect(stop).toHaveBeenCalledTimes(1);
  });

  it('10. GhostOverlay.vue tetap bekerja dengan benar setelah ekstraksi composable', () => {
    const wrapper = mount(GhostOverlay, {
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
    });

    const ghostImg = wrapper.find('#ghost');
    expect(ghostImg.exists()).toBe(true);
    expect((ghostImg.element as HTMLImageElement).style.opacity).toBe('0.6');
    expect((ghostImg.element as HTMLImageElement).style.transform).toBe(
      'translate(10px, -5px) scale(1.1)',
    );
    expect(wrapper.find('#fname').text()).toBe('luka.jpg');
    wrapper.unmount();
  });
});
