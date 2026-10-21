// Экран 5 — главный экран демо. Слева лента этапов, справа «Что дальше».
// Данные обновляются сами раз в 3 секунды (см. useApplication), поэтому статус «движется» на глазах.
import { Anchor, Badge, Button, Grid, Group, Loader, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { IconArrowLeft, IconClockHour4, IconHandClick, IconInfoCircle } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { useApplication, useHistory } from '../../api/queries';
import type { Application } from '../../api/types';
import { Chat } from '../../components/Chat';
import { ErrorState, Loading } from '../../components/StateViews';
import { StatusBadge } from '../../components/StatusBadge';
import { dateTime, months, rub } from '../../lib/format';
import { PURPOSE_TITLE } from '../../lib/statuses';
import { DocumentsBlock, DoneBlock, OfferBlock, RejectedBlock, SignBlock } from './ActionBlocks';
import { StageTimeline } from './StageTimeline';

export function ApplicationPage() {
  const id = Number(useParams().id);
  const { data: app, isPending, error, refetch } = useApplication(id);
  const { data: history } = useHistory(id, app?.status);

  if (isPending) return <Loading text="Загружаем заявку…" />;
  if (error) {
    if (error instanceof ApiError && error.status === 403)
      return <ErrorState title="Нет доступа" error={new Error('Это чужая заявка — у вас нет к ней доступа.')} />;
    return <ErrorState error={error} onRetry={refetch} />;
  }
  if (app.status === 'DRAFT') return <Navigate to={`/applications/${id}/edit`} replace />;

  return (
    <Stack gap="lg">
      <Anchor component={Link} to="/" size="sm">
        <Group gap={4}>
          <IconArrowLeft size={14} /> Мои заявки
        </Group>
      </Anchor>
      <Group justify="space-between">
        <div>
          <Title order={2}>
            Заявка №{app.id} · {app.product.name}
          </Title>
          <Text c="dimmed">
            {app.company.name} · {rub(app.amount)} на {months(app.term_months)}
          </Text>
        </div>
        <StatusBadge status={app.status} label={app.status_label} />
      </Group>

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 5 }} order={{ base: 2, md: 1 }}>
          <Stack>
            {history ? <StageTimeline app={app} history={history} /> : <Loading />}
            <Details app={app} />
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 7 }} order={{ base: 1, md: 2 }}>
          <Stack gap="lg">
            <NextActionPanel app={app} />
            <Chat applicationId={app.id} role="client" title="Вопрос по заявке" placeholder="Напишите специалисту…" />
          </Stack>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}

/** Ответ на три вопроса: что происходит, сколько ждать, нужно ли что-то от меня — и сам блок действия. */
function NextActionPanel({ app }: { app: Application }) {
  const na = app.next_action;
  return (
    <Paper p={{ base: 'md', sm: 'xl' }} className={na.action_required ? 'needs-action' : undefined}>
      <Stack>
        <Text size="sm" c="dimmed" fw={600} tt="uppercase">
          Что дальше
        </Text>
        <Title order={3}>{na.title}</Title>
        <Text>{na.description}</Text>

        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xs">
          <Fact icon={<IconClockHour4 size={16} />} label="Сколько ждать" value={na.wait_text ?? (na.action_required ? 'зависит от вас' : '—')} />
          <Fact
            icon={<IconHandClick size={16} />}
            label="Нужно ли что-то от вас"
            value={
              na.action_required ? (
                <Badge color="accent" variant="filled" tt="none">
                  Да, ваше действие
                </Badge>
              ) : (
                'Нет, ничего не нужно'
              )
            }
          />
        </SimpleGrid>

        {na.code === 'wait' && (
          <Group gap="xs" c="dimmed">
            <Loader size="xs" />
            <Text size="sm">Страница обновится сама, перезагружать не нужно</Text>
          </Group>
        )}
        {na.code === 'review_offer' && app.decision && <OfferBlock app={app} />}
        {na.code === 'sign' && <SignBlock app={app} />}
        {na.code === 'done' && <DoneBlock app={app} />}
        {na.code === 'rejected' && <RejectedBlock app={app} />}
        {na.code === 'upload_documents' && <DocumentsBlock app={app} />}
        {na.code === 'cancelled' && (
          <Button component={Link} to="/new" variant="light" w="fit-content">
            Подобрать кредит заново
          </Button>
        )}
      </Stack>
    </Paper>
  );
}

function Fact({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <Paper p="xs" radius="md" bg="gray.0">
      <Group gap={6} c="dimmed">
        {icon}
        <Text size="xs">{label}</Text>
      </Group>
      <Text size="sm" fw={500} component="div" mt={2}>
        {value}
      </Text>
    </Paper>
  );
}

function Details({ app }: { app: Application }) {
  return (
    <Paper p="xl">
      <Group gap={6} mb="xs">
        <IconInfoCircle size={18} />
        <Title order={5}>Данные заявки</Title>
      </Group>
      <Stack gap={4}>
        <Row label="Компания" value={app.company.name} />
        <Row label="Кредит" value={app.product.name} />
        <Row label="Цель" value={PURPOSE_TITLE[app.purpose]} />
        <Row label="Сумма" value={rub(app.amount)} />
        <Row label="Срок" value={months(app.term_months)} />
        <Row label="Выручка за 12 мес." value={rub(app.revenue_12m)} />
        <Row label="Создана" value={dateTime(app.created_at)} />
      </Stack>
    </Paper>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <Group justify="space-between" gap="xs" wrap="nowrap">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text size="sm" ta="right">
        {value}
      </Text>
    </Group>
  );
}
