import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';


import { AppLayout } from './components/AppLayout';
import { RequireRole } from './components/RequireRole';
import { Loading } from './components/StateViews';
import { ApplyPage } from './pages/ApplyPage';
import { ApplicationPage } from './pages/application/ApplicationPage';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { RecommendPage } from './pages/RecommendPage';

// Редкие экраны грузятся отдельно, только когда на них переходят: клиенту не нужен код кабинета
// специалиста, а гостю на витрине — код кабинета.
const LandingPage = lazy(() => import('./pages/LandingPage').then((m) => ({ default: m.LandingPage })));
const LoansPage = lazy(() => import('./pages/loans/LoansPage').then((m) => ({ default: m.LoansPage })));
const QueuePage = lazy(() => import('./pages/analyst/QueuePage').then((m) => ({ default: m.QueuePage })));
const AnalystCardPage = lazy(() => import('./pages/analyst/AnalystCardPage').then((m) => ({ default: m.AnalystCardPage })));
const StatsPage = lazy(() => import('./pages/analyst/StatsPage').then((m) => ({ default: m.StatsPage })));

export function App() {
  return (
    <Suspense fallback={<Loading />}>
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
    </Suspense>
  );
}
