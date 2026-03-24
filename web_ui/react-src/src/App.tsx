import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

const Index = React.lazy(() => import('./pages/index/Index'))
const Subjects = React.lazy(() => import('./pages/subjects/Subjects'))
const Protocols = React.lazy(() => import('./pages/protocols/Protocols'))
const ProtocolsCreate = React.lazy(() => import('./pages/protocols-create/ProtocolsCreate'))
const SubjectSessions = React.lazy(() => import('./pages/subject-sessions/SubjectSessions'))
const PilotSessions = React.lazy(() => import('./pages/pilot-sessions/PilotSessions'))
const Projects = React.lazy(() => import('./pages/projects/Projects'))
const ProjectDetail = React.lazy(() => import('./pages/projects/ProjectDetail'))
const ExperimentDetail = React.lazy(() => import('./pages/experiments/ExperimentDetail'))
const Researchers = React.lazy(() => import('./pages/researchers/Researchers'))
const IACUC = React.lazy(() => import('./pages/researchers/IACUC'))
const TaskDefinitions = React.lazy(() => import('./pages/task-definitions/TaskDefinitions'))
const TaskEditor = React.lazy(() => import('./pages/task-editor/TaskEditor'))
const Toolkits = React.lazy(() => import('./pages/toolkits/Toolkits'))

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
          <Route path="projects-ui" element={<Projects />} />
          <Route path="projects/:projectId" element={<ProjectDetail />} />
          <Route path="experiments/:experimentId" element={<ExperimentDetail />} />
          <Route path="researchers-ui" element={<Researchers />} />
          <Route path="iacuc-ui" element={<IACUC />} />
          <Route path="task-definitions-ui" element={<TaskDefinitions />} />
          <Route path="task-editor/:id" element={<TaskEditor />} />
          <Route path="toolkits-ui" element={<Toolkits />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
