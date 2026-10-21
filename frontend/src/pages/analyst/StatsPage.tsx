// Аналитика конвейера: те метрики, по которым мы предлагаем судить о продукте (docs/product.md).
// Главные числа — крупными плитками, распределения — горизонтальными столбиками одного цвета с подписями.
import { Box, Group, Paper, SimpleGrid, Stack, Text, Title, Tooltip } from '@mantine/core';
import type { ReactNode } from 'react';

import { useStats } from '../../api/queries';
import type { StatItem } from '../../api/types';
import { ErrorState, Loading } from '../../components/StateViews';
import { plural, rubShort } from '../../lib/format';
import { Term } from '../../lib/glossary';

const BAR = '#0b1f35'; // одна нейтральная графитовая заливка для величин
const RISK_FILL: Record<string, string> = { A: '#2f9e44', B: '#0ca678', C: '#f08c00', D: '#e03131' };

function duration(sec: number | null | undefined): string {
  if (sec == null) return '—';
  if (sec < 60) return `${sec} с`;
  if (sec < 3600) return `${Math.round(sec / 60)} мин`;
  if (sec < 86400) return `${Math.round(sec / 3600)} ч`;
  return `${Math.round(sec / 86400)} дн`;
}

function Tile({ label, value, hint }: { label: ReactNode; value: string; hint?: string }) {
  return (
    <Paper p="lg">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text fz={30} fw={800} lh={1.2} mt={4} style={{ whiteSpace: 'nowrap' }}>
        {value}
      </Text>
      {hint && (
        <Text size="xs" c="dimmed" mt={4}>
          {hint}
        </Text>
      )}
    </Paper>
  );
}

/** Горизонтальные столбики: подпись слева, значение справа, тонкая полоса со скруглённым концом. */
function Bars({ items, colorOf, total }: { items: StatItem[]; colorOf?: (key: string) => string; total?: number }) {
  const max = Math.max(1, ...items.map((i) => i.count));
  const sum = total ?? items.reduce((s, i) => s + i.count, 0);
  return (
    <Stack gap={10}>
      {items.map((i) => (
        <Tooltip key={i.key} label={`${i.label}: ${i.count}${sum ? ` (${Math.round((i.count / sum) * 100)}%)` : ''}`} position="top-start" withArrow>
          <Box style={{ cursor: 'default' }} py={2}>
            <Group justify="space-between" mb={4} wrap="nowrap">
              <Text size="sm">{i.label}</Text>
              <Text size="sm" fw={700}>
                {i.count}
              </Text>
            </Group>
            <Box h={10} bg="gray.0" style={{ borderRadius: 4 }}>
              <Box
                h={10}
                w={`${(i.count / max) * 100}%`}
                style={{ background: colorOf ? colorOf(i.key) : BAR, borderRadius: 4, minWidth: i.count ? 4 : 0 }}
              />
            </Box>
          </Box>
        </Tooltip>
      ))}
    </Stack>
  );
}

export function StatsPage() {
  const { data: s, isPending, error, refetch } = useStats();
  if (isPending) return <Loading text="Считаем показатели…" />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Аналитика конвейера</Title>
        <Text c="dimmed">Насколько быстро клиент получает ответ и сколько решений система принимает сама. Обновляется каждые 10 секунд.</Text>
      </div>

      <SimpleGrid cols={4}>
        <Tile
          label="Решено без специалиста"
          value={s.auto_share == null ? '—' : `${s.auto_share}%`}
          hint={`${s.auto_count} авто · ${s.manual_count} специалистом`}
        />
        <Tile label="Первый ответ клиенту" value={duration(s.median_first_response_sec)} hint="медиана: от отправки до решения или запроса" />
        <Tile
          label="Решение специалиста"
          value={duration(s.median_manual_decision_sec)}
          hint={`автоматическое — ${duration(s.median_auto_decision_sec)} (медианы)`}
        />
        <Tile
          label="Выдано"
          value={rubShort(s.issued_volume)}
          hint={`${s.issued_count} ${plural(s.issued_count, 'кредит', 'кредита', 'кредитов')}, средний — ${rubShort(s.average_issued)}`}
        />
      </SimpleGrid>

      <SimpleGrid cols={2} spacing="lg">
        <Paper p="xl">
          <Title order={4} mb="md">
            Воронка: от заявки до денег
          </Title>
          <Bars items={s.funnel} total={s.funnel[0]?.count} />
        </Paper>
        <Paper p="xl">
          <Title order={4} mb="md">
            Где сейчас заявки
          </Title>
          <Bars items={s.status_groups} />
        </Paper>
        <Paper p="xl">
          <Title order={4} mb="md">
            <Term k="riskClass">Классы риска</Term>
          </Title>
          <Bars items={s.risk_classes} colorOf={(k) => RISK_FILL[k] ?? BAR} />
          <Text size="xs" c="dimmed" mt="sm">
            A — низкий риск, D — высокий. Заявки без оценки (внешний сервис не ответил) не учитываются.
          </Text>
        </Paper>
        <Paper p="xl">
          <Title order={4} mb="md">
            Продукты
          </Title>
          <Bars items={s.products} />
        </Paper>
      </SimpleGrid>
    </Stack>
  );
}
