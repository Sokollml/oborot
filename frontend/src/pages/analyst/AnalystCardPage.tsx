// Кабинет специалиста, экран 2: карточка заявки + панель решения (экран 3).
import { Anchor, Box, Grid, Group, Stack, Text, Title } from '@mantine/core';
import { IconArrowLeft } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { useAnalystCard } from '../../api/queries';
import { Chat } from '../../components/Chat';
import { ErrorState, Loading } from '../../components/StateViews';
import { StatusBadge } from '../../components/StatusBadge';
import { months, rub } from '../../lib/format';
import { ChecksSection, ClientSection, DocumentsSection, HistorySection, ScoringSection } from './CardSections';
import { DecisionPanel, RecommendationCard } from './DecisionPanel';

// key={id}: при переходе на другую заявку (например, из уведомления) панель решения и черновик
// комментария сбрасываются, а не применяются к чужой заявке.
export function AnalystCardPage() {
  const { id } = useParams();
  return <AnalystCardView key={id} id={Number(id)} />;
}

function AnalystCardView({ id }: { id: number }) {
  const { data: card, isPending, error, refetch } = useAnalystCard(id);
  const [preset, setPreset] = useState(0);

  if (isPending) return <Loading text="Загружаем заявку…" />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  const app = card.application;

  return (
    <Stack gap="lg">
      <Anchor component={Link} to="/analyst" size="sm">
        <Group gap={4}>
          <IconArrowLeft size={14} /> Очередь
        </Group>
      </Anchor>
      <Group justify="space-between" align="flex-end">
        <div>
          <Title order={2}>
            Заявка №{app.id} · {app.company.name}
          </Title>
          <Text c="dimmed">
            {app.product.name} · {rub(app.amount)} на {months(app.term_months)}
          </Text>
        </div>
        <StatusBadge status={app.status} label={app.status_label} />
      </Group>

      <Grid gap="lg" align="flex-start">
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Stack gap="lg">
            <ClientSection card={card} />
            <ChecksSection checks={card.checks} />
            <ScoringSection scoring={card.scoring} />
            <DocumentsSection card={card} />
            <Chat applicationId={app.id} role="analyst" title="Переписка с клиентом" placeholder="Ответ клиенту…" />
            <HistorySection card={card} />
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Box className="sticky-desktop" style={{ position: 'sticky', top: 84 }}>
            <Stack gap="lg">
              <RecommendationCard card={card} onUse={() => setPreset((n) => n + 1)} />
              <DecisionPanel card={card} preset={preset} />
            </Stack>
          </Box>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
