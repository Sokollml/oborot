// Тонкая обёртка над fetch: все запросы идут на /api (nginx проксирует их на бэкенд),
// cookie со входом браузер отправляет сам. Ошибки превращаются в ApiError с текстом для человека.

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const FALLBACK: Record<number, string> = {
  401: 'Войдите в кабинет, чтобы продолжить',
  403: 'У вас нет доступа к этой странице',
  404: 'Не нашли такую страницу или заявку',
  409: 'Сейчас это действие недоступно — обновите страницу',
  413: 'Файл слишком большой — до 10 МБ',
  422: 'Проверьте введённые данные',
};

async function request<T>(method: string, path: string, body?: unknown, headers?: Record<string, string>): Promise<T> {
  const isForm = body instanceof FormData;
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      headers: { ...(body && !isForm ? { 'Content-Type': 'application/json' } : {}), ...headers },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз');
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : undefined;
    throw new ApiError(res.status, detail ?? FALLBACK[res.status] ?? 'Что-то пошло не так. Попробуйте ещё раз через минуту');
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown, headers?: Record<string, string>) => request<T>('POST', path, body, headers),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
};

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : 'Что-то пошло не так';
}

// Ключ идемпотентности для отправки заявки. crypto.randomUUID есть не везде (только https/localhost).
export function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
