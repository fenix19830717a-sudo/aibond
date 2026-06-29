import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme, Spin } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import MainLayout from './components/MainLayout';
import Login from './pages/Login';
import Landing from './pages/Landing';
import { useAuthStore } from './store/authStore';

// Lazy load pages for code splitting
const Chat = lazy(() => import('./pages/Chat'));
const Groups = lazy(() => import('./pages/Groups'));
const GroupDetail = lazy(() => import('./pages/GroupDetail'));
const Agents = lazy(() => import('./pages/Agents'));
const Workflow = lazy(() => import('./pages/Workflow'));
const WorkflowEditor = lazy(() => import('./pages/WorkflowEditor'));
const Social = lazy(() => import('./pages/Social'));
const ScheduledTasks = lazy(() => import('./pages/ScheduledTasks'));
const Parliament = lazy(() => import('./pages/Parliament'));
const ParliamentDetail = lazy(() => import('./pages/ParliamentDetail'));
const Tasks = lazy(() => import('./pages/Tasks'));
const AuditLog = lazy(() => import('./pages/AuditLog'));
const SkillsMarket = lazy(() => import('./pages/SkillsMarket'));
const TeamTemplates = lazy(() => import('./pages/TeamTemplates'));
const CliAgents = lazy(() => import('./pages/CliAgents'));

const PageLoader = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
    <Spin size="large" />
  </div>
);

const App: React.FC = () => {
  const { token } = useAuthStore();

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 8,
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={token ? <Navigate to="/app" /> : <Login />} />
          <Route path="/app" element={token ? <MainLayout /> : <Navigate to="/login" />}>
            <Route index element={<Suspense fallback={<PageLoader />}><Chat /></Suspense>} />
            <Route path="groups" element={<Suspense fallback={<PageLoader />}><Groups /></Suspense>} />
            <Route path="groups/:groupId" element={<Suspense fallback={<PageLoader />}><GroupDetail /></Suspense>} />
            <Route path="agents" element={<Suspense fallback={<PageLoader />}><Agents /></Suspense>} />
            <Route path="social" element={<Suspense fallback={<PageLoader />}><Social /></Suspense>} />
            <Route path="workflows" element={<Suspense fallback={<PageLoader />}><Workflow /></Suspense>} />
            <Route path="workflows/:id" element={<Suspense fallback={<PageLoader />}><WorkflowEditor /></Suspense>} />
            <Route path="scheduled" element={<Suspense fallback={<PageLoader />}><ScheduledTasks /></Suspense>} />
            <Route path="tasks" element={<Suspense fallback={<PageLoader />}><Tasks /></Suspense>} />
            <Route path="parliament" element={<Suspense fallback={<PageLoader />}><Parliament /></Suspense>} />
            <Route path="parliament/:id" element={<Suspense fallback={<PageLoader />}><ParliamentDetail /></Suspense>} />
            <Route path="audit" element={<Suspense fallback={<PageLoader />}><AuditLog /></Suspense>} />
            <Route path="skills" element={<Suspense fallback={<PageLoader />}><SkillsMarket /></Suspense>} />
            <Route path="templates" element={<Suspense fallback={<PageLoader />}><TeamTemplates /></Suspense>} />
            <Route path="cli-agents" element={<Suspense fallback={<PageLoader />}><CliAgents /></Suspense>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
