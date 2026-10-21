// Защита маршрутов: не вошёл — на экран входа; зашёл не в свой кабинет — в свой.
// Настоящая проверка доступа — на сервере; здесь только удобная навигация.
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useMe } from '../api/queries';
import type { User } from '../api/types';
import { ErrorState, Loading } from './StateViews';

export function RequireRole({ role, children }: { role: User['role']; children: ReactNode }) {
  const { data: user, isPending, error, refetch } = useMe();
  const location = useLocation();

  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.role !== role) return <Navigate to={user.role === 'analyst' ? '/analyst' : '/'} replace />;
  return <>{children}</>;
}
