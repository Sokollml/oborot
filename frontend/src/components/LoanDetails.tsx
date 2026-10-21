// Прозрачные условия до подписания: график платежей, ПСК и основные условия кредита.
import { Anchor, Button, Checkbox, Group, Modal, Paper, ScrollArea, SimpleGrid, Stack, Table, Text, ThemeIcon } from '@mantine/core';
import { IconCalendarStats, IconFileDescription, IconFileText } from '@tabler/icons-react';
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

export function Conditions({ app }: { app: Application }) {
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

// ---------- Пакет документов на подпись ----------

function Guarantee({ app }: { app: Application }) {
  const d = app.decision!;
  return (
    <Stack gap="sm">
      <Text size="sm">
        <b>Поручитель:</b> {app.company.director} — руководитель {app.company.name}.
      </Text>
      <Text size="sm">
        Поручитель обязуется отвечать перед банком за исполнение заёмщиком обязательств по кредиту на сумму {rub(d.amount)} сроком{' '}
        {months(d.term)} в том же объёме, что и заёмщик: основной долг, проценты и возможные неустойки.
      </Text>
      <Text size="sm">Поручительство действует до полного погашения кредита. Подписывается тем же кодом, что и кредитный договор.</Text>
      <Text size="xs" c="dimmed">
        Демо: для беззалоговых кредитов банк обычно просит поручительство собственника бизнеса. Мы условно считаем им руководителя из реестра.
      </Text>
    </Stack>
  );
}

function Pledge({ app }: { app: Application }) {
  return (
    <Stack gap="sm">
      <Text size="sm">
        <b>Предмет залога:</b> {app.collateral_description ?? 'по описанию в заявке'}.
      </Text>
      <Text size="sm">
        Имущество остаётся у {app.company.name} и используется в работе. Банк вправе обратить на него взыскание, только если кредит не будет
        возвращён. Залог прекращается после полного погашения.
      </Text>
      <Text size="xs" c="dimmed">
        Демо: оценка и регистрация залога в реальном процессе проходят до выдачи.
      </Text>
    </Stack>
  );
}

/**
 * Документы, которые клиент подписывает одним кодом. Пока он не отметил, что ознакомился, код ввести нельзя.
 * onReadChange — сообщает блоку подписи, можно ли разблокировать ввод кода.
 */
export function SigningDocuments({ app, onReadChange }: { app: Application; onReadChange: (read: boolean) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [read, setRead] = useState(false);
  const start = useMemo(() => new Date(), []);
  const docs: { key: string; title: string; body: ReactNode }[] = [
    { key: 'contract', title: 'Кредитный договор — индивидуальные условия', body: <Conditions app={app} /> },
    { key: 'schedule', title: 'График платежей', body: <ScheduleTable app={app} start={start} /> },
    app.product.needs_collateral
      ? { key: 'pledge', title: 'Договор залога', body: <Pledge app={app} /> }
      : { key: 'guarantee', title: `Договор поручительства — ${app.company.director}`, body: <Guarantee app={app} /> },
  ];
  const current = docs.find((d) => d.key === open);
  return (
    <Stack gap="xs">
      <Text size="sm" fw={600}>
        Документы на подпись
      </Text>
      {docs.map((d) => (
        <Paper key={d.key} p="sm" radius="lg" bg="gray.0">
          <Group justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap">
              <ThemeIcon size={30} radius="md" variant="light" color="gray">
                <IconFileText size={18} />
              </ThemeIcon>
              <Text size="sm" fw={500}>
                {d.title}
              </Text>
            </Group>
            <Anchor component="button" type="button" size="sm" fw={600} onClick={() => setOpen(d.key)}>
              Открыть
            </Anchor>
          </Group>
        </Paper>
      ))}
      <Checkbox
        mt="xs"
        checked={read}
        onChange={(e) => {
          setRead(e.currentTarget.checked);
          onReadChange(e.currentTarget.checked);
        }}
        label="Я ознакомился с документами и согласен с условиями"
      />
      <Modal opened={current !== undefined} onClose={() => setOpen(null)} title={<b>{current?.title}</b>} size="xl" centered>
        {current?.body}
      </Modal>
    </Stack>
  );
}
