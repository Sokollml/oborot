// Лента этапов: пройдено (галочка, время, сколько длилось) / сейчас / впереди.
// Строится из истории статусов, которую пишет state machine на бэкенде.
import { Loader, Paper, Text, ThemeIcon, Timeline, Title } from '@mantine/core';
import { IconCheck, IconPointFilled, IconX } from '@tabler/icons-react';

import type { AppStatus, Application, HistoryItem } from '../../api/types';
import { duration, time } from '../../lib/format';

type Stage = { title: string; hint: string; statuses: AppStatus[] };

const STAGES: Stage[] = [
  { title: 'Заявка отправлена', hint: 'Встала в очередь на проверку', statuses: ['SUBMITTED'] },
  { title: 'Проверка данных компании', hint: 'Реестр компаний, налоговая, кредитная история', statuses: ['CHECKING'] },
  { title: 'Оценка заявки', hint: 'Считаем, какую сумму и на каких условиях можем предложить', statuses: ['SCORING'] },
  { title: 'Решение', hint: 'Предложение, запрос документов или решение специалиста', statuses: ['MANUAL_REVIEW', 'INFO_REQUESTED', 'OFFER', 'REJECTED'] },
  { title: 'Подписание договора', hint: 'Подпись кодом прямо в кабинете', statuses: ['SIGNING'] },
  { title: 'Деньги зачислены', hint: 'На расчётный счёт компании', statuses: ['ISSUED'] },
];

const DECISION_LABEL: Partial<Record<AppStatus, string>> = {
  MANUAL_REVIEW: 'Смотрит специалист',
  INFO_REQUESTED: 'Нужны документы',
  OFFER: 'Есть предложение',
  REJECTED: 'Отказ',
};

const stageOf = (status: AppStatus) => STAGES.findIndex((s) => s.statuses.includes(status));

export function StageTimeline({ app, history }: { app: Application; history: HistoryItem[] }) {
  // Для отменённой заявки показываем этап, на котором её отменили.
  const lastLive = [...history].reverse().find((h) => stageOf(h.to_status) >= 0)?.to_status;
  const effective: AppStatus = app.status === 'CANCELLED' ? (lastLive ?? 'SUBMITTED') : app.status;
  const current = stageOf(effective);
  const finished = app.status === 'ISSUED';
  const stopped = app.status === 'REJECTED' || app.status === 'CANCELLED';

  // Когда заявка попала в каждый этап. Берём последний вход: после загрузки документов
  // проверка и оценка проходят ещё раз, и показывать нужно свежее время.
  const enteredAt = STAGES.map((stage) => history.filter((h) => stage.statuses.includes(h.to_status)).at(-1)?.created_at);

  return (
    <Paper p="xl">
      <Title order={4} mb="md">
        Ход рассмотрения
      </Title>
      <Timeline active={finished ? STAGES.length - 1 : current} bulletSize={26} lineWidth={2}>
        {STAGES.map((stage, i) => {
          const done = i < current || finished;
          const isCurrent = i === current && !finished;
          const skipped = stopped && i > current;
          const at = enteredAt[i];
          const nextAt = enteredAt.slice(i + 1).find(Boolean);

          let bullet = <IconPointFilled size={12} />;
          if (done) bullet = <IconCheck size={14} />;
          else if (isCurrent && app.status === 'REJECTED') bullet = <IconX size={14} />;
          else if (isCurrent && !app.next_action.action_required && !stopped) bullet = <Loader size={14} color="white" />;

          const title = i === 3 && isCurrent && DECISION_LABEL[effective] ? `Решение: ${DECISION_LABEL[effective]}` : stage.title;

          return (
            <Timeline.Item
              key={stage.title}
              bullet={
                <ThemeIcon size={26} radius="xl" color={app.status === 'REJECTED' && isCurrent ? 'red' : done || isCurrent ? 'accent' : 'gray.4'}>
                  {bullet}
                </ThemeIcon>
              }
              title={
                <Text fw={isCurrent ? 700 : 500} c={skipped ? 'dimmed' : undefined}>
                  {title}
                </Text>
              }
            >
              <Text size="sm" c="dimmed">
                {skipped ? '—' : stage.hint}
              </Text>
              {at && (done || isCurrent) && (
                <Text size="xs" c="dimmed" mt={2}>
                  {time(at)}
                  {done && nextAt ? ` · заняло ${duration(at, nextAt)}` : ''}
                  {isCurrent && !finished && app.status === 'CANCELLED' ? ' · заявка отменена' : ''}
                </Text>
              )}
            </Timeline.Item>
          );
        })}
      </Timeline>
    </Paper>
  );
}
