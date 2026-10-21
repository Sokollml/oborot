// Разделы карточки заявки для специалиста: данные клиента, проверки, скоринг, документы, история.
import { Alert, Anchor, Badge, Box, Group, Paper, SimpleGrid, Stack, Text, ThemeIcon, Timeline, Title } from '@mantine/core';
import { IconAlertTriangle, IconCheck, IconFileText, IconX } from '@tabler/icons-react';
import type { ReactNode } from 'react';

import type { AnalystCard, CheckOut, FactorOut, ScoringOut } from '../../api/types';
import { date, dateTime, months, rub } from '../../lib/format';
import { Term } from '../../lib/glossary';
import { PURPOSE_TITLE } from '../../lib/statuses';
import { RiskBadge } from './QueuePage';

export function Section({ title, children, extra }: { title: ReactNode; children: ReactNode; extra?: ReactNode }) {
  return (
    <Paper p="xl">
      <Group justify="space-between" mb="md">
        <Title order={4}>{title}</Title>
        {extra}
      </Group>
      {children}
    </Paper>
  );
}

function Row({ label, value }: { label: ReactNode; value: ReactNode }) {
  return (
    <Group justify="space-between" gap="xs" wrap="nowrap" align="flex-start">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text size="sm" ta="right" fw={500}>
        {value}
      </Text>
    </Group>
  );
}

export function ClientSection({ card }: { card: AnalystCard }) {
  const a = card.application;
  return (
    <Section title="Клиент и заявка">
      <SimpleGrid cols={2} spacing="xl">
        <Stack gap={6}>
          <Text fw={700}>{a.company.name}</Text>
          <Row label={<Term k="inn">ИНН</Term>} value={a.company.inn} />
          <Row label="Руководитель" value={a.company.director} />
          <Row label="Зарегистрирована" value={date(a.company.registered_at)} />
          <Row label={<Term k="okved">ОКВЭД</Term>} value={a.company.okved.split(' — ')[0]} />
          <Row label="Сотрудников" value={a.employees ?? '—'} />
        </Stack>
        <Stack gap={6}>
          <Text fw={700}>
            {a.product.name}: {rub(a.amount)}
          </Text>
          <Row label="Срок" value={months(a.term_months)} />
          <Row label="Цель" value={PURPOSE_TITLE[a.purpose]} />
          <Row label="Выручка за 12 мес." value={rub(a.revenue_12m)} />
          <Row label="Выручка годом ранее" value={rub(a.revenue_prev_year)} />
          <Row label="Платежи по кредитам" value={`${rub(a.monthly_debt_payments)} / мес.`} />
        </Stack>
      </SimpleGrid>
      {a.collateral_description && (
        <Paper bg="gray.0" p="sm" radius="lg" mt="md">
          <Text size="sm">
            <b>
              <Term k="collateral">Залог</Term>:
            </b>{' '}
            {a.collateral_description}
          </Text>
        </Paper>
      )}
    </Section>
  );
}

const LEVEL = {
  ok: { color: 'green', bg: '#ebf8ef', icon: <IconCheck size={16} /> },
  warn: { color: 'orange', bg: '#fff4e5', icon: <IconAlertTriangle size={16} /> },
  bad: { color: 'red', bg: '#ffeceb', icon: <IconX size={16} /> },
} as const;

function CheckCard({ check }: { check: CheckOut }) {
  const l = LEVEL[check.level as keyof typeof LEVEL] ?? LEVEL.warn;
  return (
    <Paper p="md" radius="lg" style={{ background: l.bg }}>
      <Group gap={8} mb={8} wrap="nowrap">
        <ThemeIcon color={l.color} size={24} radius="xl">
          {l.icon}
        </ThemeIcon>
        <Text fw={700} size="sm">
          {check.title}
        </Text>
      </Group>
      <Stack gap={2}>
        {check.lines.map((line) => (
          <Group key={line.label} justify="space-between" wrap="nowrap" gap={6}>
            <Text size="xs" c="dimmed">
              {line.label}
            </Text>
            <Text size="xs" fw={600} c={line.level === 'bad' ? 'red.8' : line.level === 'warn' ? 'orange.8' : undefined} ta="right">
              {line.value}
            </Text>
          </Group>
        ))}
      </Stack>
    </Paper>
  );
}

export function ChecksSection({ checks }: { checks: CheckOut[] }) {
  return (
    <Section title="Проверки во внешних источниках">
      {checks.length === 0 ? (
        <Text c="dimmed" size="sm">
          Проверки ещё не проводились.
        </Text>
      ) : (
        <SimpleGrid cols={3} spacing="sm">
          {checks.map((c) => (
            <CheckCard key={c.source} check={c} />
          ))}
        </SimpleGrid>
      )}
    </Section>
  );
}

/** Полоска «плюс/минус»: от центральной линии вправо зелёная (баллы в плюс), влево красная (в минус). */
function FactorBar({ factor, max }: { factor: FactorOut; max: number }) {
  const width = `${(Math.abs(factor.points) / max) * 50}%`;
  const positive = factor.points > 0;
  return (
    <Box>
      <Group justify="space-between" wrap="nowrap" gap="xs" mb={4}>
        <div>
          <Text size="sm" fw={600}>
            {factor.title}: <Text span fw={400}>{factor.value}</Text>
          </Text>
          <Text size="xs" c="dimmed">
            {factor.comment}
          </Text>
        </div>
        <Text fw={800} c={factor.points > 0 ? 'green.7' : factor.points < 0 ? 'red.7' : 'dimmed'} style={{ minWidth: 36 }} ta="right">
          {factor.points > 0 ? `+${factor.points}` : factor.points < 0 ? `−${Math.abs(factor.points)}` : '0'}
        </Text>
      </Group>
      <Box pos="relative" h={8} bg="gray.0" style={{ borderRadius: 4 }}>
        <Box pos="absolute" left="50%" top={-2} h={12} w={2} bg="gray.4" />
        {factor.points !== 0 && (
          <Box
            pos="absolute"
            top={0}
            h={8}
            w={width}
            left={positive ? '50%' : undefined}
            right={positive ? undefined : '50%'}
            bg={positive ? 'green.6' : 'red.6'}
            style={{ borderRadius: 4 }}
          />
        )}
      </Box>
    </Box>
  );
}

export function ScoringSection({ scoring }: { scoring: ScoringOut | null | undefined }) {
  if (!scoring)
    return (
      <Section title={<Term k="scoring">Скоринг</Term>}>
        <Alert color="orange" icon={<IconAlertTriangle size={18} />}>
          Автоматическая оценка не проводилась: не удалось получить данные из внешних сервисов. Решение — по данным анкеты и документам.
        </Alert>
      </Section>
    );
  const max = Math.max(20, ...scoring.factors.map((f) => Math.abs(f.points)));
  return (
    <Section
      title={<Term k="scoring">Скоринг</Term>}
      extra={
        <Group gap="xs">
          <Text fw={800} size="xl">
            {scoring.total_score} баллов
          </Text>
          <RiskBadge cls={scoring.risk_class} />
        </Group>
      }
    >
      {scoring.stop_factors.length > 0 && (
        <Alert color="red" icon={<IconX size={18} />} title="Стоп-фактор — кредит выдать нельзя" mb="md">
          {scoring.stop_factors.map((f) => `${f.title}: ${f.value}`).join('; ')}
        </Alert>
      )}
      <Text size="xs" c="dimmed" mb="md">
        Старт — {scoring.base_score} баллов, каждый фактор добавляет или отнимает. Итог 0–100: A ≥ 70, B 55–69, C 40–54, D &lt; 40. Модель {scoring.model_version}.
      </Text>
      <Stack gap="md">
        {scoring.factors.map((f) => (
          <FactorBar key={f.code} factor={f} max={max} />
        ))}
      </Stack>
    </Section>
  );
}

export function DocumentsSection({ card }: { card: AnalystCard }) {
  const docs = card.application.documents;
  if (docs.length === 0) return null;
  return (
    <Section title="Документы">
      <Stack gap="xs">
        {docs.map((d) => (
          <Group key={d.id} justify="space-between">
            <Group gap="xs">
              <IconFileText size={18} />
              <Text size="sm">{d.title}</Text>
            </Group>
            {d.status === 'uploaded' ? (
              <Anchor href={`/api/analyst/documents/${d.id}`} target="_blank" size="sm" fw={600}>
                {d.file_name} — открыть
              </Anchor>
            ) : (
              <Badge color="gray" variant="light" tt="none">
                Ждём от клиента
              </Badge>
            )}
          </Group>
        ))}
      </Stack>
    </Section>
  );
}

const ACTOR = { client: 'клиент', analyst: 'специалист', system: 'система' } as const;

export function HistorySection({ card }: { card: AnalystCard }) {
  const items = [...card.history].reverse();
  return (
    <Section title="История">
      <Timeline bulletSize={14} lineWidth={2} active={items.length}>
        {items.map((h, i) => (
          <Timeline.Item key={i} title={<Text size="sm" fw={600}>{h.to_label}</Text>}>
            {h.comment && <Text size="sm">{h.comment}</Text>}
            <Text size="xs" c="dimmed">
              {dateTime(h.created_at)} · {ACTOR[h.actor_type]}
            </Text>
          </Timeline.Item>
        ))}
      </Timeline>
    </Section>
  );
}
