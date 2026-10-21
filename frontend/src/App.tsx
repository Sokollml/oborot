import { useEffect, useState } from 'react';
import { Badge, Container, Group, Paper, Stack, Text, Title } from '@mantine/core';

type ApiState = 'loading' | 'ok' | 'error';

// Временная стартовая страница фазы 0: показывает, что фронтенд собран,
// а nginx проксирует /api на бэкенд.
export function App() {
  const [api, setApi] = useState<ApiState>('loading');

  useEffect(() => {
    fetch('/api/health')
      .then((r) => setApi(r.ok ? 'ok' : 'error'))
      .catch(() => setApi('error'));
  }, []);

  return (
    <Container size="sm" py={80}>
      <Paper withBorder p="xl">
        <Stack gap="sm">
          <Title order={1}>Ступени</Title>
          <Text c="dimmed">Финансирование для малого бизнеса — заявка, статус и решение в одном кабинете.</Text>
          <Group gap="xs">
            <Text size="sm">Связь с сервером:</Text>
            {api === 'loading' && <Badge color="gray">проверяем…</Badge>}
            {api === 'ok' && <Badge color="green">есть</Badge>}
            {api === 'error' && <Badge color="red">нет связи</Badge>}
          </Group>
        </Stack>
      </Paper>
    </Container>
  );
}
