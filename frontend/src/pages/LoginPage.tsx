// Экран 1. Вход. В демо-режиме — подсказка с тестовыми аккаунтами (клик подставляет данные).
import { zodResolver } from '@hookform/resolvers/zod';
import { Alert, Anchor, Badge, Button, Center, Container, Group, Paper, PasswordInput, Stack, Text, TextInput, ThemeIcon, Title } from '@mantine/core';
import { IconInfoCircle, IconStairsUp } from '@tabler/icons-react';
import { useForm } from 'react-hook-form';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { errorText } from '../api/client';
import { useLogin, useMe, useMeta } from '../api/queries';

const schema = z.object({
  email: z.string().trim().min(1, 'Введите email').email('Похоже, в email опечатка'),
  password: z.string().min(1, 'Введите пароль'),
});
type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const { data: me } = useMe();
  const { data: meta } = useMeta();
  const login = useLogin();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from;
  const { register, handleSubmit, setValue, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });

  if (me) return <Navigate to={me.role === 'analyst' ? '/analyst' : '/'} replace />;

  const onSubmit = handleSubmit((values) =>
    login.mutate(values, {
      onSuccess: (user) => navigate(user.role === 'analyst' ? '/analyst' : from && from !== '/login' ? from : '/', { replace: true }),
    }),
  );

  return (
    <Center mih="100vh" bg="gray.0">
      <Container size={440} w="100%">
        <Stack gap="lg">
          <Group justify="center" gap="xs">
            <ThemeIcon size={40} radius="md">
              <IconStairsUp size={26} />
            </ThemeIcon>
            <Title order={1}>Ступени</Title>
          </Group>
          <Text ta="center" c="dimmed">
            Кредит для бизнеса онлайн: подбор, заявка и решение в одном кабинете
          </Text>

          <Paper shadow="sm" p="xl" component="form" onSubmit={onSubmit} noValidate>
            <Stack>
              <TextInput label="Email" placeholder="you@company.ru" autoComplete="username" {...register('email')} error={formState.errors.email?.message} />
              <PasswordInput label="Пароль" autoComplete="current-password" {...register('password')} error={formState.errors.password?.message} />
              {login.error && <Alert color="red">{errorText(login.error)}</Alert>}
              <Button type="submit" size="md" loading={login.isPending}>
                Войти
              </Button>
            </Stack>
          </Paper>

          {meta?.demo_mode && (
            <Alert variant="light" color="gray" radius="xl" icon={<IconInfoCircle size={18} />} title="Демо-режим: тестовые аккаунты">
              <Stack gap={6}>
                {(meta.demo_accounts ?? []).map((a) => (
                  <Group key={a.email} justify="space-between" wrap="nowrap">
                    <Anchor
                      component="button"
                      type="button"
                      size="sm"
                      onClick={() => {
                        setValue('email', a.email);
                        setValue('password', meta.demo_password ?? '');
                      }}
                    >
                      {a.email}
                    </Anchor>
                    <Badge size="sm" variant="light" color={a.role === 'analyst' ? 'indigo' : 'gray'} tt="none">
                      {a.role === 'analyst' ? 'специалист' : 'клиент'}
                    </Badge>
                  </Group>
                ))}
                <Text size="xs" c="dimmed">
                  Пароль для всех: <b>{meta.demo_password}</b>. Нажмите на email, чтобы подставить.
                </Text>
              </Stack>
            </Alert>
          )}
        </Stack>
      </Container>
    </Center>
  );
}
