import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from './components/AppLayout';
import { RequireRole } from './components/RequireRole';
import { AnalystCardPage } from './pages/analyst/AnalystCardPage';
import { QueuePage } from './pages/analyst/QueuePage';
import { ApplyPage } from './pages/ApplyPage';
import { ApplicationPage } from './pages/application/ApplicationPage';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { RecommendPage } from './pages/RecommendPage';

export function App() {
  return (
    <Routes>
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
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
