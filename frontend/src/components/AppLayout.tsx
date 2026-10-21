import { AppShell, Button, Container, Group, Text, ThemeIcon, UnstyledButton } from '@mantine/core';
import { IconLogout, IconStairsUp } from '@tabler/icons-react';
import { Link, Outlet, useNavigate } from 'react-router-dom';

import { useLogout, useMe } from '../api/queries';
import { NotificationBell } from './NotificationBell';

export function AppLayout() {
  const { data: user } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const isAnalyst = user?.role === 'analyst';

  return (
    <AppShell header={{ height: 64 }} bg="gray.0">
      <AppShell.Header className="app-header">
        <Container size="lg" h="100%">
          <Group h="100%" justify="space-between">
            <UnstyledButton component={Link} to={isAnalyst ? '/analyst' : '/'}>
              <Group gap={8}>
                <ThemeIcon size={34} radius="md">
                  <IconStairsUp size={20} />
                </ThemeIcon>
                <Text fw={800} size="xl" style={{ letterSpacing: "-0.02em" }}>
                  Ступени
                </Text>
                {isAnalyst && (
                  <Text size="sm" c="dimmed">
                    · кабинет специалиста
                  </Text>
                )}
              </Group>
            </UnstyledButton>
            <Group gap="sm">
              <NotificationBell linkPrefix={isAnalyst ? '/analyst/applications/' : '/applications/'} />
              <Text size="sm" visibleFrom="sm">
                {user?.full_name}
              </Text>
              <Button
                variant="subtle"
                color="gray"
                size="sm"
                leftSection={<IconLogout size={16} />}
                onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}
              >
                Выйти
              </Button>
            </Group>
          </Group>
        </Container>
      </AppShell.Header>
      <AppShell.Main>
        <Container size="lg" py="xl">
          <Outlet />
        </Container>
      </AppShell.Main>
    </AppShell>
  );
}
