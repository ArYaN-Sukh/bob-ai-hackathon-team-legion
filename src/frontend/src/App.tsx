import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import SiteDetail from './pages/SiteDetail'
import Patients from './pages/Patients'
import PatientTimeline from './pages/PatientTimeline'
import DeviationLog from './pages/DeviationLog'
import Capa from './pages/Capa'
import CapaReport from './pages/CapaReport'
import BobChat from './pages/BobChat'

export default function App() {
  return (
    <div className="min-h-screen bg-surface-alt">
      <Navbar />
      <main className="max-w-[1440px] mx-auto px-6 py-page">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/sites/:siteId" element={<SiteDetail />} />
          <Route path="/patients" element={<Patients />} />
          <Route path="/patients/:patientId" element={<PatientTimeline />} />
          <Route path="/deviations" element={<DeviationLog />} />
          <Route path="/capa" element={<Capa />} />
          <Route path="/capa/:capaId" element={<CapaReport />} />
          <Route path="/bob" element={<BobChat />} />
        </Routes>
      </main>
    </div>
  )
}
