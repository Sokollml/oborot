const money = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 });

export const rub = (value: number | null | undefined) => (value == null ? '—' : `${money.format(value)} ₽`);

/** Крупные суммы коротко: «22 млн ₽», «1,4 млн ₽», «850 тыс. ₽». */
export function rubShort(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value >= 1_000_000) return `${(value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} млн ₽`;
  if (value >= 1_000) return `${Math.round(value / 1_000)} тыс. ₽`;
  return rub(value);
}

export function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

export const months = (n: number | null | undefined) => (n == null ? '—' : `${n} ${plural(n, 'месяц', 'месяца', 'месяцев')}`);

export const rate = (value: number | null | undefined) =>
  value == null ? '—' : `${value.toLocaleString('ru-RU', { maximumFractionDigits: 1 })}% годовых`;

export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });

export const time = (iso: string) =>
  new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

export const date = (iso: string) => new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });

/** «3 мин назад», «вчера в 14:05» — для списков. */
export function ago(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'только что';
  if (diff < 3600) {
    const m = Math.floor(diff / 60);
    return `${m} ${plural(m, 'минуту', 'минуты', 'минут')} назад`;
  }
  if (diff < 86400) {
    const h = Math.floor(diff / 3600);
    return `${h} ${plural(h, 'час', 'часа', 'часов')} назад`;
  }
  return dateTime(iso);
}

/** Сколько длился этап: «12 с», «3 мин». */
export function duration(fromIso: string, toIso: string): string {
  const s = Math.max(0, Math.round((new Date(toIso).getTime() - new Date(fromIso).getTime()) / 1000));
  if (s < 60) return `${s} с`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} мин`;
  const h = Math.round(m / 60);
  return `${h} ч`;
}

/** Ежемесячный платёж равными частями: P = S·i / (1 − (1 + i)^−n), i — месячная ставка. */
export function annuity(amount: number, annualRatePct: number, termMonths: number): number {
  const i = annualRatePct / 100 / 12;
  if (i === 0) return Math.round(amount / termMonths);
  return Math.round((amount * i) / (1 - (1 + i) ** -termMonths));
}

/** Сколько ждёт: «5 мин», «2 ч», «3 дн». */
/**
 * Насколько срочно: клиенту обещано решение специалиста в течение рабочего дня (см. next_action на бэкенде).
 * После 4 часов — пора браться, после суток — обещание нарушено.
 */
export function waitingLevel(sinceIso: string): 'ok' | 'soon' | 'late' {
  const h = (Date.now() - new Date(sinceIso).getTime()) / 3_600_000;
  return h >= 24 ? 'late' : h >= 4 ? 'soon' : 'ok';
}

export function waiting(sinceIso: string): string {
  const s = Math.max(0, (Date.now() - new Date(sinceIso).getTime()) / 1000);
  if (s < 60) return 'меньше минуты';
  if (s < 3600) return `${Math.floor(s / 60)} мин`;
  if (s < 86400) return `${Math.floor(s / 3600)} ч ${Math.floor((s % 3600) / 60)} мин`;
  const d = Math.floor(s / 86400);
  return `${d} ${plural(d, 'день', 'дня', 'дней')}`;
}
