import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import FarmerChat from './pages/FarmerChat'
import AdminDashboard from './pages/AdminDashboard'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<FarmerChat />} />
        <Route path="/admin" element={<AdminDashboard />} />
      </Routes>
    </BrowserRouter>
  )
}
