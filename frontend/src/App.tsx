import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from './components/AppLayout';
import { RequireRole } from './components/RequireRole';
import { AnalystCardPage } from './pages/analyst/AnalystCardPage';
import { QueuePage } from './pages/analyst/QueuePage';
import { StatsPage } from './pages/analyst/StatsPage';
import { LoansPage } from './pages/loans/LoansPage';
import { ApplyPage } from './pages/ApplyPage';
import { ApplicationPage } from './pages/application/ApplicationPage';
import { HomePage } from './pages/HomePage';
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { RecommendPage } from './pages/RecommendPage';

export function App() {
  return (
    <Routes>
      <Route path="/welcome" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />

      {/* Кабинет клиента */}
      <Route
        element={
          <RequireRole role="client">
            <AppLayout />
          </RequireRole>
        }
      >
        <Route path="/" element={<HomePage />} />
        <Route path="/new" element={<RecommendPage />} />
        <Route path="/apply" element={<ApplyPage />} />
        <Route path="/applications/:id/edit" element={<ApplyPage />} />
        <Route path="/applications/:id" element={<ApplicationPage />} />
        <Route path="/loans" element={<LoansPage />} />
      </Route>

      {/* Кабинет специалиста */}
      <Route
        element={
          <RequireRole role="analyst">
            <AppLayout />
          </RequireRole>
        }
      >
        <Route path="/analyst" element={<QueuePage />} />
        <Route path="/analyst/applications/:id" element={<AnalystCardPage />} />
        <Route path="/analyst/stats" element={<StatsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
