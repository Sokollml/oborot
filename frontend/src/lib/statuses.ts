import type { AppStatus, Purpose } from '../api/types';

// Цвета бейджей статусов: серый — ждём, синий — в работе, жёлтый — нужно действие,
// зелёный — хорошо, красный — отказ.
export const STATUS_COLOR: Record<AppStatus, string> = {
  DRAFT: 'gray',
  SUBMITTED: 'blue',
  CHECKING: 'blue',
  SCORING: 'blue',
  MANUAL_REVIEW: 'indigo',
  INFO_REQUESTED: 'yellow',
  OFFER: 'teal',
  SIGNING: 'yellow',
  ISSUED: 'green',
  REJECTED: 'red',
  CANCELLED: 'gray',
};

export const PURPOSES: { value: Purpose; title: string; hint: string }[] = [
  { value: 'stock_salary', title: 'Товар и зарплаты', hint: 'Закупка, зарплата, аренда — текущие расходы бизнеса' },
  { value: 'equipment', title: 'Оборудование и развитие', hint: 'Станки, транспорт, ремонт, новая точка' },
  { value: 'urgent', title: 'Срочно закрыть разрыв', hint: 'Деньги нужны сейчас, а оплата от клиентов придёт позже' },
];

export const PURPOSE_TITLE = Object.fromEntries(PURPOSES.map((p) => [p.value, p.title])) as Record<Purpose, string>;

// Документы, которые специалист может запросить (ключи — как на бэкенде, app/views.py DOC_TITLES).
export const DOC_TYPES = [
  { value: 'bank_statement', label: 'Выписка по счёту за 12 месяцев' },
  { value: 'financial_report', label: 'Бухгалтерская отчётность за год' },
  { value: 'collateral_docs', label: 'Документы на залог' },
  { value: 'other', label: 'Другой документ' },
];

export const RISK_COLOR: Record<string, string> = { A: 'green', B: 'teal', C: 'orange', D: 'red' };
