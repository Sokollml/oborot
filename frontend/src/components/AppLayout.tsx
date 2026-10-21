// Оболочка кабинета в духе интернет-банка: шапка, слева меню разделов, справа — содержимое.
import { AppShell, Box, Button, Group, NavLink, Stack, Text, ThemeIcon, UnstyledButton } from '@mantine/core';
import { IconChartBar, IconHome2, IconListCheck, IconLogout, IconPlus, IconStairsUp, IconWallet } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { useLogout, useMe } from '../api/queries';
import { NotificationBell } from './NotificationBell';

type Item = { to: string; label: string; icon: ReactNode; match: (path: string) => boolean };

const CLIENT_MENU: Item[] = [
  { to: '/', label: 'Главная', icon: <IconHome2 size={20} />, match: (p) => p === '/' || p.startsWith('/applications') },
  { to: '/loans', label: 'Мои кредиты', icon: <IconWallet size={20} />, match: (p) => p.startsWith('/loans') },
  { to: '/new', label: 'Получить финансирование', icon: <IconPlus size={20} />, match: (p) => p === '/new' || p === '/apply' },
];

const ANALYST_MENU: Item[] = [
  { to: '/analyst', label: 'Очередь заявок', icon: <IconListCheck size={20} />, match: (p) => p === '/analyst' || p.startsWith('/analyst/applications') },
  { to: '/analyst/stats', label: 'Аналитика', icon: <IconChartBar size={20} />, match: (p) => p.startsWith('/analyst/stats') },
];

export function AppLayout() {
  const { data: user } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const isAnalyst = user?.role === 'analyst';
  const menu = isAnalyst ? ANALYST_MENU : CLIENT_MENU;

  return (
    <AppShell header={{ height: 64 }} navbar={{ width: 248, breakpoint: 0 }} bg="gray.0">
      <AppShell.Header className="app-header">
        <Group h="100%" px="lg" justify="space-between">
          <UnstyledButton component={Link} to={isAnalyst ? '/analyst' : '/'}>
            <Group gap={8}>
              <ThemeIcon size={34} radius="md">
                <IconStairsUp size={20} />
              </ThemeIcon>
              <Text fw={800} size="xl" style={{ letterSpacing: '-0.02em' }}>
                Ступени
              </Text>
              <Text size="sm" c="dimmed">
                {isAnalyst ? '· кабинет специалиста' : '· для бизнеса'}
              </Text>
            </Group>
          </UnstyledButton>
          <Group gap="sm">
            <NotificationBell linkPrefix={isAnalyst ? '/analyst/applications/' : '/applications/'} />
            <Text size="sm" fw={600}>
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
      </AppShell.Header>

      <AppShell.Navbar p="sm" className="app-navbar">
        <Stack gap={4}>
          {menu.map((item) => (
            <NavLink
              key={item.to}
              component={Link}
              to={item.to}
              label={item.label}
              leftSection={item.icon}
              active={item.match(pathname)}
              className="app-navlink"
            />
          ))}
        </Stack>
        <Box mt="auto" p="sm">
          <Text size="xs" c="dimmed">
            Демо-стенд хакатона. Все данные синтетические.
          </Text>
        </Box>
      </AppShell.Navbar>

      <AppShell.Main>
        <Box px="xl" py="xl" maw={1180}>
          <Outlet />
        </Box>
      </AppShell.Main>
    </AppShell>
  );
}
