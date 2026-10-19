import { useEffect } from 'react'
import { Route, Routes } from 'react-router-dom'
import { useStore } from './store/useStore'
import { startBackendMirror } from './services/api'
import { Layout } from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Fleet from './pages/Fleet'
import Monitoring from './pages/Monitoring'
import Agents from './pages/Agents'
import Comms from './pages/Comms'
import Policies from './pages/Policies'
import Approvals from './pages/Approvals'
import Maintenance from './pages/Maintenance'
import Missions from './pages/Missions'
import Audit from './pages/Audit'

export default function App() {
  // Autonomous agent runtime: runs for the life of the app, regardless of which page is open.
  useEffect(() => {
    const id = setInterval(() => useStore.getState().tick(), 2500)
    return () => clearInterval(id)
  }, [])
  useEffect(() => startBackendMirror(), [])
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="fleet" element={<Fleet />} />
        <Route path="monitoring" element={<Monitoring />} />
        <Route path="agents" element={<Agents />} />
        <Route path="comms" element={<Comms />} />
        <Route path="policies" element={<Policies />} />
        <Route path="approvals" element={<Approvals />} />
        <Route path="maintenance" element={<Maintenance />} />
        <Route path="missions" element={<Missions />} />
        <Route path="audit" element={<Audit />} />
        <Route path="*" element={<div className="text-mute">Page not found.</div>} />
      </Route>
    </Routes>
  )
}
