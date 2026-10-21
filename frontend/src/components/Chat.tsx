// Переписка по заявке: клиент ↔ специалист. Новые сообщения подгружаются сами раз в 5 секунд.
import { ActionIcon, Box, Group, Paper, ScrollArea, Stack, Text, Textarea, Title } from '@mantine/core';
import { IconSend } from '@tabler/icons-react';
import { useEffect, useRef, useState } from 'react';

import { errorText } from '../api/client';
import { useMessages } from '../api/queries';
import { ago } from '../lib/format';

export function Chat({ applicationId, role, title, placeholder }: { applicationId: number; role: 'client' | 'analyst'; title: string; placeholder: string }) {
  const { list, send } = useMessages(applicationId, role);
  const [text, setText] = useState('');
  const viewport = useRef<HTMLDivElement>(null);
  const messages = list.data ?? [];

  useEffect(() => {
    viewport.current?.scrollTo({ top: viewport.current.scrollHeight });
  }, [messages.length]);

  const submit = () => {
    const value = text.trim();
    if (!value) return;
    send.mutate(value, { onSuccess: () => setText('') });
  };

  return (
    <Paper p="xl">
      <Title order={4} mb="sm">
        {title}
      </Title>
      {messages.length === 0 ? (
        <Text size="sm" c="dimmed" mb="sm">
          {role === 'client' ? 'Есть вопрос по заявке? Напишите — специалист ответит здесь же.' : 'Сообщений пока нет.'}
        </Text>
      ) : (
        <ScrollArea.Autosize mah={280} viewportRef={viewport} mb="sm">
          <Stack gap="xs">
            {messages.map((m) => {
              const mine = m.author_role === role;
              return (
                <Box key={m.id} style={{ alignSelf: mine ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
                  <Paper p="sm" radius="lg" bg={mine ? 'accent.0' : 'gray.0'}>
                    <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                      {m.text}
                    </Text>
                  </Paper>
                  <Text size="xs" c="dimmed" ta={mine ? 'right' : 'left'} mt={2}>
                    {m.author_role === 'analyst' ? `Специалист · ${m.author_name}` : m.author_name} · {ago(m.created_at)}
                  </Text>
                </Box>
              );
            })}
          </Stack>
        </ScrollArea.Autosize>
      )}
      <Group align="flex-end" gap="xs" wrap="nowrap">
        <Textarea
          style={{ flex: 1 }}
          placeholder={placeholder}
          value={text}
          onChange={(e) => setText(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          autosize
          minRows={1}
          maxRows={4}
          size="sm"
          error={send.error ? errorText(send.error) : undefined}
        />
        <ActionIcon size={40} radius="md" onClick={submit} loading={send.isPending} disabled={!text.trim()} aria-label="Отправить">
          <IconSend size={18} />
        </ActionIcon>
      </Group>
    </Paper>
  );
}
