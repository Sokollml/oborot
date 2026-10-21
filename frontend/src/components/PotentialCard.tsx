// Предодобренный лимит для компании на обслуживании в банке: «Вам доступно до X ₽» — без анкеты и документов.
import { Alert, Anchor, Button, Checkbox, Collapse, Group, List, Paper, SimpleGrid, Stack, Text, ThemeIcon, Title } from '@mantine/core';
import { IconBuildingBank, IconChevronDown, IconRefresh, IconSparkles } from '@tabler/icons-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { errorText } from '../api/client';
import { useCalculatePotential } from '../api/queries';
import type { MyCompany } from '../api/types';
import { ago, months, rub } from '../lib/format';
import { Term } from '../lib/glossary';

const PURPOSE_BY_PRODUCT: Record<string, string> = { EXPRESS: 'urgent', WORKING: 'stock_salary' };

export function PotentialCard({ company }: { company: MyCompany }) {
  const calc = useCalculatePotential();
  const navigate = useNavigate();
  const [consent, setConsent] = useState(false);
  const [details, setDetails] = useState(false);
  const p = company.potential;
  const offers = p?.offers ?? [];
  const drivers = p?.drivers ?? [];
  const tips = p?.tips ?? [];

  const header = (
    <Group gap="xs" wrap="nowrap">
      <ThemeIcon variant="light" color="gray" size={32} radius="md">
        <IconBuildingBank size={18} />
      </ThemeIcon>
      <div style={{ minWidth: 0 }}>
        <Text fw={700} truncate>
          {company.name}
        </Text>
        <Text size="xs" c="dimmed">
          ИНН {company.inn}
        </Text>
      </div>
    </Group>
  );

  // Ещё не считали — предлагаем узнать лимит за пару секунд.
  if (!p) {
    return (
      <Paper p="xl">
        <Stack gap="sm">
          {header}
          <Title order={4}>Узнайте, сколько мы готовы дать</Title>
          <Text size="sm" c="dimmed">
            Посчитаем <Term k="potential">предодобренный лимит</Term> по <Term k="turnover">оборотам на счёте</Term> и кредитной
            истории. Без анкеты и документов — займёт пару секунд.
          </Text>
          <Checkbox
            size="sm"
            checked={consent}
            onChange={(e) => setConsent(e.currentTarget.checked)}
            label={
              <>
                Согласен на запрос кредитной истории в <Term k="bki">БКИ</Term>
              </>
            }
          />
          {calc.error && <Alert color="red">{errorText(calc.error)}</Alert>}
          <Button leftSection={<IconSparkles size={18} />} disabled={!consent} loading={calc.isPending} onClick={() => calc.mutate(company.id)} w="fit-content">
            Рассчитать лимит
          </Button>
        </Stack>
      </Paper>
    );
  }

  const ok = p.status === 'ok';
  return (
    <Paper p="xl" className={ok ? 'potential-ok' : undefined}>
      <Stack gap="sm">
        <Group justify="space-between" wrap="nowrap">
          {header}
          <Button
            variant="subtle"
            color="gray"
            size="compact-sm"
            leftSection={<IconRefresh size={14} />}
            loading={calc.isPending}
            onClick={() => calc.mutate(company.id)}
          >
            Пересчитать
          </Button>
        </Group>

        {ok ? (
          <>
            <div>
              <Text size="sm" c="dimmed">
                <Term k="potential">Предодобрено</Term>
              </Text>
              <Title order={2} c="accent.6">
                до {rub(p.max_amount)}
              </Title>
            </div>
            <Text size="sm">{p.text}</Text>
            <SimpleGrid cols={offers.length > 1 ? 2 : 1} spacing="sm">
              {offers.map((o) => (
                <Paper key={o.product_code} bg="gray.0" p="md" radius="lg">
                  <Text size="sm" fw={600}>
                    {o.product_name}
                  </Text>
                  <Text fw={800} size="lg">
                    до {rub(o.amount)}
                  </Text>
                  <Text size="xs" c="dimmed">
                    на {months(o.term_months)}, от {o.rate}% · платёж от {rub(o.monthly_payment)}
                  </Text>
                  <Button
                    mt="sm"
                    size="xs"
                    fullWidth
                    onClick={() =>
                      navigate(
                        `/apply?product=${o.product_code}&amount=${o.amount}&term=${o.term_months}&purpose=${PURPOSE_BY_PRODUCT[o.product_code] ?? 'stock_salary'}&inn=${company.inn}`,
                      )
                    }
                  >
                    Оформить
                  </Button>
                </Paper>
              ))}
            </SimpleGrid>
          </>
        ) : (
          <>
            <Title order={4}>{p.title}</Title>
            <Text size="sm" c="dimmed">
              {p.text}
            </Text>
            <Button variant="default" onClick={() => navigate('/new')} w="fit-content">
              Подать заявку
            </Button>
          </>
        )}

        {(drivers.length > 0 || tips.length > 0) && (
          <>
            <Anchor component="button" type="button" size="sm" onClick={() => setDetails((d) => !d)}>
              <Group gap={4}>
                Из чего сложился лимит и как его увеличить
                <IconChevronDown size={14} style={{ transform: details ? 'rotate(180deg)' : undefined }} />
              </Group>
            </Anchor>
            <Collapse expanded={details}>
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                <div>
                  <Text size="xs" fw={700} c="dimmed" tt="uppercase" mb={4}>
                    Помогло
                  </Text>
                  <List size="sm" spacing={2}>
                    {p.revenue_12m != null && <List.Item>Поступления на счёт за год: {rub(p.revenue_12m)}</List.Item>}
                    {drivers.map((d) => (
                      <List.Item key={d}>{d}</List.Item>
                    ))}
                  </List>
                </div>
                <div>
                  <Text size="xs" fw={700} c="dimmed" tt="uppercase" mb={4}>
                    Как увеличить
                  </Text>
                  <List size="sm" spacing={2}>
                    {tips.map((t) => (
                      <List.Item key={t}>{t}</List.Item>
                    ))}
                  </List>
                </div>
              </SimpleGrid>
            </Collapse>
          </>
        )}
        {p.calculated_at && (
          <Text size="xs" c="dimmed">
            Рассчитано {ago(p.calculated_at)}. Это предварительная оценка — точное решение после заявки.
          </Text>
        )}
      </Stack>
    </Paper>
  );
}
