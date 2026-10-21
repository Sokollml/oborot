// Блок «Предодобренные лимиты» на главной клиента.
// Одно согласие → лимиты по всем компаниям сразу; сверху — лучшее предложение крупным баннером,
// ниже — компактный список по компаниям с подробностями.
import { Badge, Button, Checkbox, Flex, Group, Modal, Paper, Stack, Table, Text, ThemeIcon, Title } from '@mantine/core';
import { IconSparkles } from '@tabler/icons-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, errorText } from '../api/client';
import type { MyCompany } from '../api/types';
import { ago, rub } from '../lib/format';
import { Term } from '../lib/glossary';
import { useIsMobile } from '../lib/responsive';
import { PotentialCard } from './PotentialCard';

const PURPOSE_BY_PRODUCT: Record<string, string> = { EXPRESS: 'urgent', WORKING: 'stock_salary' };

function useCalculateAll() {
  const qc = useQueryClient();
  return useMutation({
    // Лимиты по компаниям считаются параллельно — на экране это пара секунд.
    mutationFn: (ids: number[]) => Promise.all(ids.map((id) => api.post<MyCompany>(`/companies/${id}/potential`, { consent: true }))),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['companies'] }),
  });
}

function shortStatus(c: MyCompany) {
  const p = c.potential;
  if (!p) return <Text size="sm" c="dimmed">не рассчитан</Text>;
  if (p.status === 'ok') return <Text fw={800}>до {rub(p.max_amount)}</Text>;
  const label = { no_account: 'нет счёта в банке', unavailable: 'не удалось рассчитать', none: 'нет предложения' }[p.status] ?? p.title;
  return (
    <Badge variant="light" color={p.status === 'unavailable' ? 'orange' : 'gray'} tt="none">
      {label}
    </Badge>
  );
}

export function PotentialSection({ companies }: { companies: MyCompany[] }) {
  const calcAll = useCalculateAll();
  const navigate = useNavigate();
  const [consent, setConsent] = useState(false);
  const [details, setDetails] = useState<MyCompany | null>(null);
  const mobile = useIsMobile();

  const calculated = companies.filter((c) => c.potential);
  const ok = calculated.filter((c) => c.potential?.status === 'ok');
  const best = ok.sort((a, b) => (b.potential?.max_amount ?? 0) - (a.potential?.max_amount ?? 0))[0];
  const bestOffer = best?.potential?.offers?.reduce((x, y) => (y.amount > x.amount ? y : x));

  // Ещё ничего не считали — один призыв с согласием.
  if (calculated.length === 0) {
    return (
      <Paper p={{ base: 'lg', sm: 'xl' }} className="hero-dark">
        <Flex direction={{ base: 'column', sm: 'row' }} justify="space-between" align={{ base: 'stretch', sm: 'center' }} gap="lg">
          <Stack gap="xs" maw={620}>
            <Group gap="xs">
              <ThemeIcon size={28} radius="md" color="accent">
                <IconSparkles size={16} />
              </ThemeIcon>
              <Text fw={700} c="gray.4" size="sm">
                Для клиентов банка
              </Text>
            </Group>
            <Title order={2} c="white">
              Узнайте, сколько банк готов дать вашему бизнесу
            </Title>
            <Text c="gray.4">
              Посчитаем <Term k="potential">предодобренный лимит</Term> по оборотам на счетах ваших компаний ({companies.length}) и кредитной истории.
              Без анкеты и документов — пара секунд.
            </Text>
            <Checkbox
              mt="xs"
              checked={consent}
              onChange={(e) => setConsent(e.currentTarget.checked)}
              styles={{ label: { color: 'white' } }}
              label={
                <>
                  Согласен на запрос кредитной истории в <Term k="bki">БКИ</Term>
                </>
              }
            />
            {calcAll.error && <Text c="red.3">{errorText(calcAll.error)}</Text>}
          </Stack>
          <Button size="lg" disabled={!consent} loading={calcAll.isPending} onClick={() => calcAll.mutate(companies.map((c) => c.id))}>
            Рассчитать лимиты
          </Button>
        </Flex>
      </Paper>
    );
  }

  return (
    <Stack gap="md">
      {best && bestOffer && (
        <Paper p={{ base: 'lg', sm: 'xl' }} className="hero-dark">
          <Flex direction={{ base: 'column', sm: 'row' }} justify="space-between" align={{ base: 'stretch', sm: 'center' }} gap="md">
            <div>
              <Text c="gray.4" size="sm" fw={600}>
                {best.name} · <Term k="potential">предодобрено</Term>
              </Text>
              <Title order={1} c="white" mt={4}>
                до {rub(best.potential?.max_amount)}
              </Title>
              <Text c="gray.4" mt={4}>
                {bestOffer.product_name} на {bestOffer.term_months} мес., от {bestOffer.rate}% · платёж от {rub(bestOffer.monthly_payment)} в месяц.
                Документы не нужны.
              </Text>
            </div>
            <Button
              size="lg"
              onClick={() =>
                navigate(
                  `/apply?product=${bestOffer.product_code}&amount=${bestOffer.amount}&term=${bestOffer.term_months}&purpose=${PURPOSE_BY_PRODUCT[bestOffer.product_code] ?? 'stock_salary'}&inn=${best.inn}`,
                )
              }
            >
              Оформить
            </Button>
          </Flex>
        </Paper>
      )}

      <Paper p={0} style={{ overflow: 'hidden' }}>
        <Group justify="space-between" px={mobile ? 'md' : 'xl'} pt="lg" pb="xs">
          <Title order={4}>Лимиты по компаниям</Title>
          <Button
            variant="subtle"
            size="compact-sm"
            color="gray"
            loading={calcAll.isPending}
            onClick={() => calcAll.mutate(companies.map((c) => c.id))}
          >
            Пересчитать все
          </Button>
        </Group>
        <Table verticalSpacing="sm" horizontalSpacing={mobile ? 'md' : 'xl'} highlightOnHover>
          <Table.Tbody>
            {companies.map((c) => (
              <Table.Tr key={c.id} style={{ cursor: 'pointer' }} onClick={() => setDetails(c)}>
                <Table.Td>
                  <Text fw={600}>{c.name}</Text>
                  <Text size="xs" c="dimmed">
                    ИНН {c.inn}
                  </Text>
                </Table.Td>
                <Table.Td>{shortStatus(c)}</Table.Td>
                <Table.Td c="dimmed" fz="xs" visibleFrom="sm">
                  {c.potential?.calculated_at ? `рассчитано ${ago(c.potential.calculated_at)}` : ''}
                </Table.Td>
                <Table.Td ta="right" visibleFrom="sm">
                  <Button variant="default" size="compact-sm">
                    Подробнее
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Paper>

      <Modal opened={details !== null} onClose={() => setDetails(null)} size="lg" centered fullScreen={mobile} withCloseButton title={<b>Предодобренный лимит</b>}>
        {details && <PotentialCard company={companies.find((c) => c.id === details.id) ?? details} />}
      </Modal>
    </Stack>
  );
}
