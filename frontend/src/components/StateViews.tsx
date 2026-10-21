// Единые состояния экрана: загрузка, ошибка (в том числе без сети) и пустой список.
import type { ReactNode } from 'react';
import { Alert, Button, Center, Group, Loader, Paper, Stack, Text, ThemeIcon, Title } from '@mantine/core';
import { IconAlertTriangle, IconInbox, IconWifiOff } from '@tabler/icons-react';

import { ApiError, errorText } from '../api/client';

export function Loading({ text = 'Загружаем…' }: { text?: string }) {
  return (
    <Center py={60}>
      <Group gap="sm">
        <Loader size="sm" />
        <Text c="dimmed">{text}</Text>
      </Group>
    </Center>
  );
}

export function ErrorState({ error, onRetry, title }: { error: unknown; onRetry?: () => void; title?: string }) {
  const offline = error instanceof ApiError && error.status === 0;
  return (
    <Alert
      color={offline ? 'orange' : 'red'}
      icon={offline ? <IconWifiOff size={18} /> : <IconAlertTriangle size={18} />}
      title={title ?? (offline ? 'Нет связи с сервером' : 'Не получилось загрузить')}
    >
      <Stack gap="xs" align="flex-start">
        <Text size="sm">{errorText(error)}</Text>
        {onRetry && (
          <Button size="xs" variant="white" color={offline ? 'orange' : 'red'} onClick={onRetry}>
            Повторить
          </Button>
        )}
      </Stack>
    </Alert>
  );
}

export function EmptyState({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return (
    <Paper p="xl">
      <Stack align="center" gap="xs" py="md">
        <ThemeIcon size={48} radius="xl" variant="light" color="gray">
          <IconInbox size={26} />
        </ThemeIcon>
        <Title order={4}>{title}</Title>
        <Text c="dimmed" ta="center" maw={420}>
          {text}
        </Text>
        {action}
      </Stack>
    </Paper>
  );
}
