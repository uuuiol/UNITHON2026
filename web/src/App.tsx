import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from './components/RequireAuth'
import { AbListPage } from './pages/AbListPage'
import { AbNewPage } from './pages/AbNewPage'
import { AbResultPage } from './pages/AbResultPage'
import { LoginPage } from './pages/LoginPage'
import { MissionPage } from './pages/MissionPage'
import { NewProjectPage } from './pages/NewProjectPage'
import { NewTestPage } from './pages/NewTestPage'
import { PersonaPage } from './pages/PersonaPage'
import { PlansPage } from './pages/PlansPage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { ReviewPage } from './pages/ReviewPage'
import { RunningPage } from './pages/RunningPage'
import { SettingsCreditPage } from './pages/SettingsCreditPage'
import { SettingsPlanPage } from './pages/SettingsPlanPage'
import { SettingsTeamPage } from './pages/SettingsTeamPage'
import { TestDetailPage } from './pages/TestDetailPage'
import { SidebarProvider } from './state/SidebarContext'
import { WizardProvider } from './state/WizardContext'

export default function App() {
  return (
    <SidebarProvider>
      <WizardProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/login" element={<LoginPage />} />

          <Route element={<RequireAuth />}>
            <Route path="/projects" element={<ProjectsPage />} />

            {/* A/B 테스트 — 'new' 가 :abId 보다 구체적이라 먼저 걸린다. */}
            <Route path="/ab" element={<AbListPage />} />
            <Route path="/ab/new" element={<AbNewPage />} />
            <Route path="/ab/:abId" element={<AbResultPage />} />

            {/* 크레딧·설정 */}
            <Route path="/credit" element={<PlansPage />} />
            <Route path="/settings" element={<SettingsTeamPage />} />
            <Route path="/settings/plan" element={<SettingsPlanPage />} />
            <Route path="/settings/credit" element={<SettingsCreditPage />} />
            <Route path="/projects/new" element={<NewProjectPage />} />
            <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
            <Route path="/projects/:projectId/tests/new" element={<NewTestPage />} />
            {/* 'new' 가 먼저 걸려야 마법사 첫 화면이 테스트 상세로 새지 않는다. */}
            <Route path="/projects/:projectId/tests/:testId" element={<TestDetailPage />} />
            <Route path="/projects/:projectId/tests/new/mission" element={<MissionPage />} />
            <Route path="/projects/:projectId/tests/new/persona" element={<PersonaPage />} />
            <Route path="/projects/:projectId/tests/new/review" element={<ReviewPage />} />
            <Route path="/projects/:projectId/tests/new/running" element={<RunningPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/projects" replace />} />
        </Routes>
      </WizardProvider>
    </SidebarProvider>
  )
}
