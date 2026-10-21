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
