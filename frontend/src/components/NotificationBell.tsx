// Колокольчик уведомлений. Уведомления есть только в кабинете — никаких email и SMS.
import { ActionIcon, Button, Divider, Group, Indicator, Popover, ScrollArea, Stack, Text, UnstyledButton } from '@mantine/core';
import { IconBell } from '@tabler/icons-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useMarkAllRead, useMarkNotificationRead, useNotifications } from '../api/queries';
import { ago } from '../lib/format';

export function NotificationBell({ linkPrefix }: { linkPrefix: string }) {
  const [opened, setOpened] = useState(false);
  const { data } = useNotifications(true);
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllRead();
  const navigate = useNavigate();
  const unread = data?.unread_count ?? 0;

  return (
    <Popover opened={opened} onChange={setOpened} width={360} position="bottom-end" shadow="md" withArrow>
      <Popover.Target>
        <Indicator label={unread} size={18} disabled={unread === 0} color="accent" offset={4}>
          <ActionIcon variant="subtle" color="gray" size="lg" onClick={() => setOpened((o) => !o)} aria-label="Уведомления">
            <IconBell size={22} />
          </ActionIcon>
        </Indicator>
      </Popover.Target>
      <Popover.Dropdown p={0}>
        <Group justify="space-between" px="md" py="sm">
          <Text fw={600}>Уведомления</Text>
          {unread > 0 && (
            <Button size="compact-xs" variant="subtle" onClick={() => markAll.mutate()}>
              Прочитать все
            </Button>
          )}
        </Group>
        <Divider />
        <ScrollArea.Autosize mah={360}>
          {!data?.items.length ? (
            <Text c="dimmed" size="sm" p="md">
              Пока уведомлений нет. Мы напишем здесь, когда по заявке что-то изменится.
            </Text>
          ) : (
            <Stack gap={0}>
              {data.items.map((n) => (
                <UnstyledButton
                  key={n.id}
                  px="md"
                  py="sm"
                  style={{ borderBottom: '1px solid var(--mantine-color-gray-2)', background: n.read_at ? undefined : 'var(--mantine-color-accent-0)' }}
                  onClick={() => {
                    if (!n.read_at) markRead.mutate(n.id);
                    setOpened(false);
                    if (n.application_id) navigate(`${linkPrefix}${n.application_id}`);
                  }}
                >
                  <Text size="sm" fw={n.read_at ? 400 : 600}>
                    {n.text}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {ago(n.created_at)}
                  </Text>
                </UnstyledButton>
              ))}
            </Stack>
          )}
        </ScrollArea.Autosize>
      </Popover.Dropdown>
    </Popover>
  );
}
