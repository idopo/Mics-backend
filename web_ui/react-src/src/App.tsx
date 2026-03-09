import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

const Index = React.lazy(() => import('./pages/index/Index'))
const Subjects = React.lazy(() => import('./pages/subjects/Subjects'))
const Protocols = React.lazy(() => import('./pages/protocols/Protocols'))
const ProtocolsCreate = React.lazy(() => import('./pages/protocols-create/ProtocolsCreate'))
const SubjectSessions = React.lazy(() => import('./pages/subject-sessions/SubjectSessions'))
const PilotSessions = React.lazy(() => import('./pages/pilot-sessions/PilotSessions'))

export default function App() {
  return (
    <BrowserRouter basename="/react">
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Index />} />
          <Route path="subjects-ui" element={<Subjects />} />
          <Route path="protocols-ui" element={<Protocols />} />
          <Route path="protocols-create" element={<ProtocolsCreate />} />
          <Route path="subjects/:subject/sessions-ui" element={<SubjectSessions />} />
          <Route path="pilots/:pilot/sessions-ui" element={<PilotSessions />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
