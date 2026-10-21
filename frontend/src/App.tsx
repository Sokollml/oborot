import { Text, Title } from '@mantine/core';
import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from './components/AppLayout';
import { RequireRole } from './components/RequireRole';
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

      {/* Кабинет специалиста — фаза 4 */}
      <Route
        element={
          <RequireRole role="analyst">
            <AppLayout />
          </RequireRole>
        }
      >
        <Route
          path="/analyst/*"
          element={
            <>
              <Title order={2}>Кабинет специалиста</Title>
              <Text c="dimmed">Скоро здесь появится очередь заявок.</Text>
            </>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
