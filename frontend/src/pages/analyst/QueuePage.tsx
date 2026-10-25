// Кабинет специалиста, экран 1: очередь заявок. По умолчанию — «Ждут меня» (решение за специалистом).
import { Badge, Group, Paper, SegmentedControl, Select, Stack, Table, Text, Title, Tooltip } from '@mantine/core';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAnalystQueue, useProducts, type QueueView } from '../../api/queries';
import { EmptyState, ErrorState, Loading } from '../../components/StateViews';
import { StatusBadge } from '../../components/StatusBadge';
import { clickable } from '../../lib/a11y';
import { months, rub, waiting } from '../../lib/format';
import { Term } from '../../lib/glossary';
import { useIsMobile } from '../../lib/responsive';
import { RISK_COLOR } from '../../lib/statuses';

export function RiskBadge({ cls, score }: { cls: string | null | undefined; score?: number | null }) {
  if (!cls)
    return (
      <Tooltip label="Автоматическая оценка не проводилась (например, внешний сервис не ответил)">
        <Badge color="gray" variant="light">
          нет
        </Badge>
      </Tooltip>
    );
  return (
    <Badge color={RISK_COLOR[cls]} variant="filled" size="lg" radius="sm">
      {cls}
      {score != null ? ` · ${score}` : ''}
    </Badge>
  );
}

export function QueuePage() {
  const [view, setView] = useState<QueueView>('mine');
  const [product, setProduct] = useState<string | null>(null);
  const { data, isPending, error, refetch } = useAnalystQueue(view, product);
  const { data: products } = useProducts();
  const navigate = useNavigate();
  const mobile = useIsMobile();

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Очередь заявок</Title>
        <Text c="dimmed">Сверху — те, что ждут дольше всех. Список обновляется сам.</Text>
      </div>

      <Group justify="space-between" gap="sm">
        <SegmentedControl
          value={view}
          onChange={(v) => setView(v as QueueView)}
          radius="md"
          size={mobile ? 'sm' : 'md'}
          fullWidth={mobile}
          data={[
            { value: 'mine', label: 'Ждут меня' },
            { value: 'active', label: 'Все в работе' },
            { value: 'all', label: 'Все' },
          ]}
        />
        <Select
          placeholder="Все продукты"
          clearable
          value={product}
          onChange={setProduct}
          data={(products ?? []).map((p) => ({ value: p.code, label: p.name }))}
          w={{ base: '100%', sm: 260 }}
        />
      </Group>

      {isPending && <Loading text="Загружаем очередь…" />}
      {error && <ErrorState error={error} onRetry={refetch} />}
      {data && data.length === 0 && (
        <EmptyState
          title={view === 'mine' ? 'Все решения приняты' : 'Заявок нет'}
          text={view === 'mine' ? 'Сейчас нет заявок, которые ждут вашего решения. Новые появятся здесь сами.' : 'По выбранным фильтрам заявок нет.'}
        />
      )}
      {/* На телефоне — карточки вместо широкой таблицы */}
      {data && data.length > 0 && mobile && (
        <Stack gap="sm">
          {data.map((q) => (
            <Paper key={q.id} p="md" {...clickable(() => navigate(`/analyst/applications/${q.id}`), `Открыть заявку №${q.id}`)}>
              <Group justify="space-between" wrap="nowrap" mb={4}>
                <Text fw={700} truncate>
                  {q.company_name}
                </Text>
                <RiskBadge cls={q.risk_class} score={q.total_score} />
              </Group>
              <Text size="sm" c="dimmed">
                №{q.id} · {q.product_name}
              </Text>
              <Text fw={800} mt={4}>
                {rub(q.amount)}{' '}
                <Text span size="sm" c="dimmed" fw={400}>
                  на {months(q.term_months)}
                </Text>
              </Text>
              <Group justify="space-between" mt="xs">
                <StatusBadge status={q.status} label={q.status_label} />
                <Text size="xs" c="dimmed">
                  ждёт {waiting(q.waiting_since)}
                </Text>
              </Group>
            </Paper>
          ))}
        </Stack>
      )}
      {data && data.length > 0 && !mobile && (
        <Paper p={0} style={{ overflow: 'hidden' }}>
          <Table highlightOnHover verticalSpacing="md" horizontalSpacing="lg">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>№</Table.Th>
                <Table.Th>Компания</Table.Th>
                <Table.Th>Продукт</Table.Th>
                <Table.Th ta="right">Сумма и срок</Table.Th>
                <Table.Th>
                  <Term k="riskClass">Класс риска</Term>
                </Table.Th>
                <Table.Th>Статус</Table.Th>
                <Table.Th>Ждёт</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.map((q) => (
                <Table.Tr key={q.id} {...clickable(() => navigate(`/analyst/applications/${q.id}`), `Открыть заявку №${q.id}`)}>
                  <Table.Td c="dimmed">{q.id}</Table.Td>
                  <Table.Td>
                    <Text fw={600}>{q.company_name}</Text>
                    <Text size="xs" c="dimmed">
                      ИНН {q.company_inn}
                    </Text>
                  </Table.Td>
                  <Table.Td>{q.product_name}</Table.Td>
                  <Table.Td ta="right">
                    <Text fw={600}>{rub(q.amount)}</Text>
                    <Text size="xs" c="dimmed">
                      {months(q.term_months)}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <RiskBadge cls={q.risk_class} score={q.total_score} />
                  </Table.Td>
                  <Table.Td>
                    <StatusBadge status={q.status} label={q.status_label} />
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{waiting(q.waiting_since)}</Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}
    </Stack>
  );
}
