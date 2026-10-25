// Оболочка кабинета в духе интернет-банка: шапка, слева меню разделов, справа — содержимое.
// На телефоне (уже 768 px) боковое меню прячется, а разделы переезжают в нижнюю панель вкладок,
// как в мобильных банковских приложениях.
import { ActionIcon, AppShell, Box, Button, Group, NavLink, Stack, Text, UnstyledButton } from '@mantine/core';
import { IconChartBar, IconHome2, IconListCheck, IconLogout, IconPlus, IconWallet } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { useLogout, useMe } from '../api/queries';
import { useIsMobile } from '../lib/responsive';
import { Logo } from './Logo';
import { NotificationBell } from './NotificationBell';

type Item = { to: string; label: string; short: string; icon: ReactNode; match: (path: string) => boolean };

const CLIENT_MENU: Item[] = [
  { to: '/', label: 'Главная', short: 'Главная', icon: <IconHome2 size={20} />, match: (p) => p === '/' || p.startsWith('/applications') },
  { to: '/loans', label: 'Мои кредиты', short: 'Кредиты', icon: <IconWallet size={20} />, match: (p) => p.startsWith('/loans') },
  { to: '/new', label: 'Получить финансирование', short: 'Новая заявка', icon: <IconPlus size={20} />, match: (p) => p === '/new' || p === '/apply' },
];

const ANALYST_MENU: Item[] = [
  { to: '/analyst', label: 'Очередь заявок', short: 'Очередь', icon: <IconListCheck size={20} />, match: (p) => p === '/analyst' || p.startsWith('/analyst/applications') },
  { to: '/analyst/stats', label: 'Аналитика', short: 'Аналитика', icon: <IconChartBar size={20} />, match: (p) => p.startsWith('/analyst/stats') },
];

export function AppLayout() {
  const { data: user } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const mobile = useIsMobile();
  const isAnalyst = user?.role === 'analyst';
  const menu = isAnalyst ? ANALYST_MENU : CLIENT_MENU;
  const doLogout = () => logout.mutate(undefined, { onSuccess: () => navigate('/login') });

  return (
    <AppShell
      header={{ height: mobile ? 56 : 64 }}
      navbar={{ width: 248, breakpoint: 'sm', collapsed: { mobile: true } }}
      footer={{ height: 64, collapsed: !mobile }}
      bg="gray.0"
    >
      <AppShell.Header className="app-header">
        <Group h="100%" px={mobile ? 'md' : 'lg'} justify="space-between" wrap="nowrap">
          <UnstyledButton component={Link} to={isAnalyst ? '/analyst' : '/'}>
            <Logo size={mobile ? 30 : 34} caption={isAnalyst ? '· кабинет специалиста' : '· для бизнеса'} />
          </UnstyledButton>
          <Group gap={mobile ? 4 : 'sm'} wrap="nowrap">
            <NotificationBell linkPrefix={isAnalyst ? '/analyst/applications/' : '/applications/'} />
            <Text size="sm" fw={600} visibleFrom="sm">
              {user?.full_name}
            </Text>
            {mobile ? (
              <ActionIcon variant="subtle" color="gray" size="lg" onClick={doLogout} aria-label="Выйти">
                <IconLogout size={20} />
              </ActionIcon>
            ) : (
              <Button variant="subtle" color="gray" size="sm" leftSection={<IconLogout size={16} />} onClick={doLogout}>
                Выйти
              </Button>
            )}
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
        <Box px={mobile ? 'md' : 'xl'} py={mobile ? 'md' : 'xl'} maw={1180}>
          <Outlet />
        </Box>
      </AppShell.Main>

      {/* Нижняя панель вкладок — только на телефоне */}
      <AppShell.Footer className="app-tabbar">
        <Group h="100%" grow gap={0} wrap="nowrap">
          {menu.map((item) => {
            const active = item.match(pathname);
            return (
              <UnstyledButton key={item.to} component={Link} to={item.to} className="app-tab" data-active={active || undefined}>
                <Stack gap={2} align="center">
                  {item.icon}
                  <Text size="xs" fw={600} lh={1}>
                    {item.short}
                  </Text>
                </Stack>
              </UnstyledButton>
            );
          })}
        </Group>
      </AppShell.Footer>
    </AppShell>
  );
}
