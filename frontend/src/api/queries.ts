// Запросы к API через TanStack Query: кэш, повторы, фоновое обновление.
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, api, newIdempotencyKey } from './client';
import type {
  AnalystCard,
  AnalystDecisionIn,
  Application,
  ApplicationListItem,
  ApplicationPatch,
  AppStatus,
  CompanyLookup,
  HistoryItem,
  Message,
  Meta,
  MyCompany,
  NotificationsResponse,
  Product,
  Purpose,
  QueueItem,
  RecommendResult,
  Stats,
  User,
} from './types';

// ---------- Авторизация ----------

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    // 401 — это не ошибка, а «пользователь не вошёл».
    queryFn: () =>
      api.get<User>('/auth/me').catch((e) => {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }),
    staleTime: Infinity,
    retry: false,
  });
}

export function useMeta() {
  return useQuery({ queryKey: ['meta'], queryFn: () => api.get<Meta>('/meta'), staleTime: Infinity });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) => api.post<User>('/auth/login', body),
    onSuccess: (user) => {
      qc.clear();
      qc.setQueryData(['me'], user);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>('/auth/logout'),
    onSuccess: () => {
      qc.clear();
      qc.setQueryData(['me'], null);
    },
  });
}

// ---------- Продукты ----------

export function useProducts() {
  return useQuery({ queryKey: ['products'], queryFn: () => api.get<Product[]>('/products'), staleTime: Infinity });
}

export function useRecommend() {
  return useMutation({
    mutationFn: (body: { purpose: Purpose; amount: number; term_months: number }) =>
      api.post<RecommendResult>('/products/recommend', body),
  });
}

export function useCompanyLookup() {
  return useMutation({
    mutationFn: (inn: string) => api.get<CompanyLookup>(`/companies/lookup?inn=${encodeURIComponent(inn)}`),
  });
}

// ---------- Заявки ----------

export function useMyApplications() {
  return useQuery({
    queryKey: ['applications'],
    queryFn: () => api.get<ApplicationListItem[]>('/applications'),
    refetchInterval: 5000, // статусы на главной обновляются сами
  });
}

// Статусы, в которых заявка «живёт» без участия клиента: её двигает воркер или специалист.
const LIVE_STATUSES: AppStatus[] = ['SUBMITTED', 'CHECKING', 'SCORING', 'MANUAL_REVIEW', 'INFO_REQUESTED', 'OFFER', 'REJECTED'];

/**
 * Заявка с автообновлением (polling).
 *
 * Пока заявка в работе, фронт раз в 3 секунды спрашивает у API её текущее состояние.
 * Почему так, а не WebSocket: проще, надёжнее за прокси, а задержка 3 с для кредитной заявки незаметна.
 * Когда заявка в конечном статусе (выдана, отменена) или это черновик — опрос останавливается.
 * Если вкладка свёрнута, TanStack Query сам ставит опрос на паузу.
 */
export function useApplication(id: number) {
  return useQuery({
    queryKey: ['application', id],
    queryFn: () => api.get<Application>(`/applications/${id}`),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && LIVE_STATUSES.includes(status) ? 3000 : false;
    },
    retry: (count, error) => !(error instanceof ApiError && [403, 404].includes(error.status)) && count < 3,
  });
}

// История перезапрашивается только когда сменился статус (он входит в ключ кэша).
export function useHistory(id: number, status: AppStatus | undefined) {
  return useQuery({
    queryKey: ['history', id, status],
    queryFn: () => api.get<HistoryItem[]>(`/applications/${id}/history`),
    enabled: status !== undefined,
    placeholderData: (prev) => prev,
  });
}

export function useCreateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { product_code: string; inn: string; purpose: Purpose; amount?: number; term_months?: number }) =>
      api.post<Application>('/applications', body),
    onSuccess: (app) => {
      qc.setQueryData(['application', app.id], app);
      qc.invalidateQueries({ queryKey: ['applications'] });
    },
  });
}

export function usePatchApplication(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ApplicationPatch) => api.patch<Application>(`/applications/${id}`, body),
    onSuccess: (app) => qc.setQueryData(['application', id], app),
  });
}

/** Действие с заявкой (принять, подписать…) — ответ сразу кладём в кэш, экран перестраивается. */
function useApplicationAction<TBody = void>(id: number, path: string, headers?: () => Record<string, string>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TBody) => api.post<Application>(`/applications/${id}/${path}`, body, headers?.()),
    onSuccess: (app) => {
      qc.setQueryData(['application', app.id], app);
      qc.invalidateQueries({ queryKey: ['applications'] });
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

export function useSubmitApplication(id: number) {
  // Один ключ на весь жизненный цикл экрана (useState запоминает его между перерисовками):
  // повторное нажатие «Отправить» или повтор запроса после обрыва сети не создаст вторую отправку.
  const [key] = useState(newIdempotencyKey);
  return useApplicationAction(id, 'submit', () => ({ 'Idempotency-Key': key }));
}

export const useAcceptOffer = (id: number) => useApplicationAction(id, 'offer/accept');
export const useDeclineOffer = (id: number) => useApplicationAction(id, 'offer/decline');
export const useCancelApplication = (id: number) => useApplicationAction(id, 'cancel');
export const useSign = (id: number) => useApplicationAction<{ code: string }>(id, 'sign');
export const useCloneApplication = (id: number) => useApplicationAction(id, 'clone');

// ---------- Уведомления ----------

export function useNotifications(enabled: boolean) {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.get<NotificationsResponse>('/notifications'),
    refetchInterval: 5000,
    enabled,
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.post<void>(`/notifications/${id}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>('/notifications/read-all'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  });
}

// ---------- Документы (клиент) ----------

export function useUploadDocument(applicationId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ documentRequestId, file }: { documentRequestId: number; file: File }) => {
      const form = new FormData();
      form.append('document_request_id', String(documentRequestId));
      form.append('file', file);
      return api.post<Application>(`/applications/${applicationId}/documents`, form);
    },
    onSuccess: (app) => {
      qc.setQueryData(['application', app.id], app);
      qc.invalidateQueries({ queryKey: ['applications'] });
    },
  });
}

// ---------- Кабинет специалиста ----------

export type QueueView = 'mine' | 'active' | 'all';

export function useAnalystQueue(view: QueueView, product: string | null) {
  const params = new URLSearchParams({ view, ...(product ? { product } : {}) });
  return useQuery({
    queryKey: ['analyst-queue', view, product],
    queryFn: () => api.get<QueueItem[]>(`/analyst/queue?${params}`),
    refetchInterval: 5000, // новые заявки появляются в очереди сами
    placeholderData: (prev) => prev,
  });
}

export function useAnalystCard(id: number) {
  return useQuery({
    queryKey: ['analyst-card', id],
    queryFn: () => api.get<AnalystCard>(`/analyst/applications/${id}`),
    refetchInterval: 3000, // клиент мог загрузить документы или принять предложение
  });
}

export function useAnalystDecision(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AnalystDecisionIn) => api.post<AnalystCard>(`/analyst/applications/${id}/decision`, body),
    onSuccess: (card) => {
      qc.setQueryData(['analyst-card', id], card);
      qc.invalidateQueries({ queryKey: ['analyst-queue'] });
    },
  });
}

// ---------- Мои компании и предодобренный лимит ----------

export function useMyCompanies() {
  return useQuery({ queryKey: ['companies'], queryFn: () => api.get<MyCompany[]>('/companies') });
}

export function useCalculatePotential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (companyId: number) => api.post<MyCompany>(`/companies/${companyId}/potential`, { consent: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['companies'] }),
  });
}

// ---------- Переписка по заявке ----------

/** role: 'client' — запросы клиента, 'analyst' — из кабинета специалиста. */
export function useMessages(applicationId: number, role: 'client' | 'analyst') {
  const base = role === 'analyst' ? `/analyst/applications/${applicationId}` : `/applications/${applicationId}`;
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ['messages', role, applicationId],
    queryFn: () => api.get<Message[]>(`${base}/messages`),
    refetchInterval: 5000, // ответ собеседника появляется сам
  });
  const send = useMutation({
    mutationFn: (text: string) => api.post<Message[]>(`${base}/messages`, { text }),
    onSuccess: (messages) => qc.setQueryData(['messages', role, applicationId], messages),
  });
  return { list, send };
}

// ---------- Аналитика и кредиты ----------

export function useStats() {
  return useQuery({ queryKey: ['stats'], queryFn: () => api.get<Stats>('/analyst/stats'), refetchInterval: 10000 });
}

export function useMyLoans() {
  return useQuery({ queryKey: ['loans'], queryFn: () => api.get<Application[]>('/loans') });
}
