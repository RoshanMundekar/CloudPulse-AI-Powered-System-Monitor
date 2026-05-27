import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { MetricsProvider }   from './context/MetricsContext'
import ToastContainer        from './components/ui/ToastContainer'
import Sidebar               from './components/Layout/Sidebar'
import Dashboard             from './pages/Dashboard'
import Analytics             from './pages/Analytics'
import Alerts                from './pages/Alerts'
import Processes             from './pages/Processes'

export default function App() {
  return (
    <BrowserRouter>
      <MetricsProvider>
        {/* Fixed toast layer — sits above everything */}
        <ToastContainer />

        <div className="flex min-h-screen bg-dark-400">
          <Sidebar />
          <div className="flex flex-col flex-1 min-w-0 max-h-screen overflow-hidden">
            <Routes>
              <Route path="/"          element={<Dashboard />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/alerts"    element={<Alerts />}    />
              <Route path="/processes" element={<Processes />} />
            </Routes>
          </div>
        </div>
      </MetricsProvider>
    </BrowserRouter>
  )
}
