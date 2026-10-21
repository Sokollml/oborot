// Прозрачные условия до подписания: график платежей, ПСК и основные условия кредита.
import { Button, Group, Modal, ScrollArea, SimpleGrid, Stack, Table, Text } from '@mantine/core';
import { IconCalendarStats, IconFileDescription } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';

import type { Application } from '../api/types';
import { date, months, rate, rub } from '../lib/format';
import { Term } from '../lib/glossary';
import { buildSchedule, totalInterest } from '../lib/schedule';
import { PURPOSE_TITLE } from '../lib/statuses';

function useSchedule(app: Application, start: Date) {
  const d = app.decision!;
  return useMemo(() => buildSchedule(d.amount ?? 0, d.rate ?? 0, d.term ?? 1, start), [d.amount, d.rate, d.term, start]);
}

export function ScheduleTable({ app, start }: { app: Application; start: Date }) {
  const rows = useSchedule(app, start);
  return (
    <Stack>
      <SimpleGrid cols={3}>
        <Fact label="Платёж в месяц" value={rub(rows[0]?.payment)} />
        <Fact label="Переплата за весь срок" value={rub(totalInterest(rows))} />
        <Fact label="Всего к возврату" value={rub((app.decision?.amount ?? 0) + totalInterest(rows))} />
      </SimpleGrid>
      <ScrollArea.Autosize mah={420}>
        <Table striped verticalSpacing={6} fz="sm" stickyHeader>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>№</Table.Th>
              <Table.Th>Дата</Table.Th>
              <Table.Th ta="right">Платёж</Table.Th>
              <Table.Th ta="right">Основной долг</Table.Th>
              <Table.Th ta="right">Проценты</Table.Th>
              <Table.Th ta="right">Остаток</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((r) => (
              <Table.Tr key={r.n}>
                <Table.Td c="dimmed">{r.n}</Table.Td>
                <Table.Td>{r.date.toLocaleDateString('ru-RU')}</Table.Td>
                <Table.Td ta="right" fw={600}>
                  {rub(r.payment)}
                </Table.Td>
                <Table.Td ta="right">{rub(r.principal)}</Table.Td>
                <Table.Td ta="right">{rub(r.interest)}</Table.Td>
                <Table.Td ta="right" c="dimmed">
                  {rub(r.balance)}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea.Autosize>
      <Text size="xs" c="dimmed">
        Платёж <Term k="annuity">равными частями</Term>: сумма одинаковая, а доля процентов в ней со временем уменьшается.
        Даты — ориентировочные, от даты выдачи.
      </Text>
    </Stack>
  );
}

function Fact({ label, value }: { label: ReactNode; value: ReactNode }) {
  return (
    <div>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700}>{value}</Text>
    </div>
  );
}

function Conditions({ app }: { app: Application }) {
  const d = app.decision!;
  const rows: [ReactNode, ReactNode][] = [
    ['Заёмщик', `${app.company.name}, ИНН ${app.company.inn}`],
    ['Кредит', app.product.name],
    ['Сумма', rub(d.amount)],
    ['Срок', months(d.term)],
    [<Term k="rate">Процентная ставка</Term>, rate(d.rate)],
    [<Term k="psk">Полная стоимость кредита (ПСК)</Term>, rate(d.rate)],
    ['Платёж', `${rub(d.monthly_payment)} в месяц, равными частями`],
    ['Цель', PURPOSE_TITLE[app.purpose]],
    ['Залог', app.product.needs_collateral ? app.collateral_description ?? 'по договору' : 'не нужен'],
    ['Комиссии', 'нет: за выдачу, обслуживание и досрочное погашение'],
    ['Досрочное погашение', 'в любой день, полностью или частично, без комиссии'],
  ];
  return (
    <Stack gap={0}>
      <Table verticalSpacing={8} fz="sm">
        <Table.Tbody>
          {rows.map(([k, v], i) => (
            <Table.Tr key={i}>
              <Table.Td c="dimmed" w="45%">
                {k}
              </Table.Td>
              <Table.Td fw={500}>{v}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Text size="xs" c="dimmed" mt="sm">
        Демо: основные условия условные и сформированы по решению по заявке. В реальном договоре — полный текст индивидуальных условий.
      </Text>
    </Stack>
  );
}

/** Кнопки «График платежей» и «Условия кредита» с модальными окнами. */
export function LoanDetailsButtons({ app, start }: { app: Application; start?: Date }) {
  const [open, setOpen] = useState<'schedule' | 'conditions' | null>(null);
  const startDate = useMemo(() => start ?? new Date(), [start]);
  if (!app.decision?.amount) return null;
  return (
    <>
      <Group gap="xs">
        <Button variant="default" size="sm" leftSection={<IconCalendarStats size={16} />} onClick={() => setOpen('schedule')}>
          График платежей
        </Button>
        <Button variant="default" size="sm" leftSection={<IconFileDescription size={16} />} onClick={() => setOpen('conditions')}>
          Условия кредита
        </Button>
      </Group>
      <Modal opened={open === 'schedule'} onClose={() => setOpen(null)} title={<b>График платежей</b>} size="xl" centered>
        <ScheduleTable app={app} start={startDate} />
      </Modal>
      <Modal opened={open === 'conditions'} onClose={() => setOpen(null)} title={<b>Основные условия кредита</b>} size="lg" centered>
        <Conditions app={app} />
      </Modal>
    </>
  );
}

/** Ближайший платёж после выдачи (через месяц от даты выдачи). */
export function nextPaymentDate(issuedAt: string): string {
  const d = new Date(issuedAt);
  const now = new Date();
  const next = new Date(d);
  do next.setMonth(next.getMonth() + 1);
  while (next < now);
  return date(next.toISOString());
}
