// Экран 2. Главная клиента: мои заявки, плашка «нужно ваше действие», кнопка «Получить финансирование».
import { Badge, Button, Card, Group, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { IconArrowRight, IconPlus } from '@tabler/icons-react';
import { Link } from 'react-router-dom';

import { useMyApplications } from '../api/queries';
import type { ApplicationListItem } from '../api/types';
import { EmptyState, ErrorState, Loading } from '../components/StateViews';
import { StatusBadge } from '../components/StatusBadge';
import { ago, months, rub } from '../lib/format';

export function HomePage() {
  const { data, isPending, error, refetch } = useMyApplications();

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <div>
          <Title order={2}>Мои заявки</Title>
          <Text c="dimmed">Статусы обновляются сами — страницу перезагружать не нужно</Text>
        </div>
        <Button component={Link} to="/new" size="md" leftSection={<IconPlus size={18} />}>
          Получить финансирование
        </Button>
      </Group>

      {isPending && <Loading text="Загружаем заявки…" />}
      {error && <ErrorState error={error} onRetry={refetch} />}
      {data && data.length === 0 && (
        <EmptyState
          title="Заявок пока нет"
          text="Ответьте на три вопроса — подберём подходящий кредит и посчитаем примерный платёж. Это займёт пару минут."
          action={
            <Button component={Link} to="/new" mt="sm">
              Подобрать кредит
            </Button>
          }
        />
      )}
      {data && data.length > 0 && (
        <SimpleGrid cols={{ base: 1, md: 2 }}>
          {data.map((a) => (
            <ApplicationCard key={a.id} app={a} />
          ))}
        </SimpleGrid>
      )}
    </Stack>
  );
}

function ApplicationCard({ app }: { app: ApplicationListItem }) {
  const target = app.status === 'DRAFT' ? `/applications/${app.id}/edit` : `/applications/${app.id}`;
  return (
    <Card withBorder radius="md" padding="lg" component={Link} to={target} style={{ borderColor: app.action_required ? 'var(--mantine-color-yellow-5)' : undefined }}>
      <Stack gap="xs">
        <Group justify="space-between" wrap="nowrap">
          <Text fw={600} truncate>
            {app.company_name}
          </Text>
          <StatusBadge status={app.status} label={app.status_label} />
        </Group>
        <Text size="sm" c="dimmed">
          Заявка №{app.id} · {app.product_name}
        </Text>
        <Text size="lg" fw={600}>
          {rub(app.amount)} <Text span c="dimmed" size="sm" fw={400}>на {months(app.term_months)}</Text>
        </Text>
        <Group justify="space-between">
          {app.action_required ? (
            <Badge color="yellow" variant="filled" tt="none">
              Нужно ваше действие
            </Badge>
          ) : (
            <Text size="xs" c="dimmed">
              Обновлено {ago(app.updated_at)}
            </Text>
          )}
          <IconArrowRight size={18} color="var(--mantine-color-gray-5)" />
        </Group>
      </Stack>
    </Card>
  );
}
