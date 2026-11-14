import { createRouter, createWebHistory } from 'vue-router'
import BerandaView from '@/views/BerandaView.vue'
import PilihPasienView from '@/views/PilihPasienView.vue'
import UnggahFotoView from '@/views/UnggahFotoView.vue'
import HasilKunjunganView from '@/views/HasilKunjunganView.vue'
import RiwayatPasienView from '@/views/RiwayatPasienView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'beranda',
      component: BerandaView,
    },
    {
      path: '/pemeriksaan',
      name: 'pilih-pasien',
      component: PilihPasienView,
    },
    {
      path: '/pemeriksaan/:patientId/unggah',
      name: 'unggah-foto',
      component: UnggahFotoView,
    },
    {
      path: '/kunjungan/:visitId',
      name: 'hasil-kunjungan',
      component: HasilKunjunganView,
    },
    {
      path: '/pasien/:patientId',
      name: 'riwayat-pasien',
      component: RiwayatPasienView,
    },
  ],
  scrollBehavior(to, _from, savedPosition) {
    if (to.hash) {
      return { el: to.hash, behavior: 'smooth' }
    }
    if (savedPosition) {
      return savedPosition
    }
    return { top: 0 }
  },
})

export default router
