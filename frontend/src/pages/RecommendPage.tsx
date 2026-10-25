// Экран 3. Подбор продукта: три вопроса карточками → рекомендация с объяснением и платежом, альтернативы ниже.
import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  NumberInput,
  Paper,
  SimpleGrid,
  Slider,
  Stack,
  Text,
  ThemeIcon,
  Title,
  UnstyledButton,
} from '@mantine/core';
import { IconBolt, IconBuildingFactory2, IconCheck, IconPackage } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { errorText } from '../api/client';
import { useRecommend } from '../api/queries';
import type { ProductOption, Purpose } from '../api/types';
import { months, rate, rub } from '../lib/format';
import { Term } from '../lib/glossary';
import { PURPOSES } from '../lib/statuses';

const PURPOSE_ICONS = { stock_salary: IconPackage, equipment: IconBuildingFactory2, urgent: IconBolt };

// Ползунок суммы — по «удобным» шагам, а не линейно: от 100 тыс. до 50 млн.
const AMOUNT_STEPS = [100_000, 300_000, 500_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000, 5_000_000, 7_000_000, 10_000_000, 15_000_000, 20_000_000, 30_000_000, 50_000_000];
const short = (v: number) => (v >= 1_000_000 ? `${v / 1_000_000} млн` : `${v / 1000} тыс.`);

export function RecommendPage() {
  const [purpose, setPurpose] = useState<Purpose | null>(null);
  const [amount, setAmount] = useState(2_000_000);
  const [term, setTerm] = useState(12);
  const recommend = useRecommend();
  const navigate = useNavigate();
  // Поменяли цель, сумму или срок — старая рекомендация уже не про то, убираем её до нового расчёта.
  const { reset } = recommend;
  useEffect(() => reset(), [purpose, amount, term, reset]);

  const stepIndex = AMOUNT_STEPS.reduce((best, v, i) => (Math.abs(v - amount) < Math.abs(AMOUNT_STEPS[best] - amount) ? i : best), 0);

  const apply = (o: ProductOption) =>
    navigate(`/apply?product=${o.product.code}&amount=${o.amount}&term=${o.term_months}&purpose=${purpose}`);

  return (
    <Stack gap="lg" maw={960}>
      <div>
        <Title order={2}>Подберём кредит под вашу задачу</Title>
        <Text c="dimmed">Три вопроса — и вы увидите подходящий вариант и примерный платёж. Это ни к чему не обязывает.</Text>
      </div>

      <Paper p="xl">
        <Text fw={600} mb="sm">
          1. На что нужны деньги?
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          {PURPOSES.map((p) => {
            const Icon = PURPOSE_ICONS[p.value];
            const active = purpose === p.value;
            return (
              <UnstyledButton
                key={p.value}
                onClick={() => setPurpose(p.value)}
                p="md"
                style={{
                  borderRadius: 16,
                  boxShadow: active ? 'inset 0 0 0 2px var(--mantine-color-accent-6)' : undefined,
                  background: active ? 'var(--mantine-color-accent-0)' : 'var(--mantine-color-gray-0)',
                }}
                aria-pressed={active}
              >
                <Group wrap="nowrap" align="flex-start">
                  <ThemeIcon variant={active ? 'filled' : 'light'} size="lg">
                    <Icon size={20} />
                  </ThemeIcon>
                  <div>
                    <Text fw={600}>{p.title}</Text>
                    <Text size="sm" c="dimmed">
                      {p.value === 'urgent' ? (
                        <>
                          Закрыть <Term k="cashGap">кассовый разрыв</Term>: деньги нужны сейчас, оплата придёт позже
                        </>
                      ) : (
                        p.hint
                      )}
                    </Text>
                  </div>
                </Group>
              </UnstyledButton>
            );
          })}
        </SimpleGrid>
      </Paper>

      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Paper p="xl">
          <Text fw={600} mb="sm">
            2. Сколько нужно?
          </Text>
          <NumberInput
            value={amount}
            onChange={(v) => setAmount(typeof v === 'number' ? v : 0)}
            min={100_000}
            max={50_000_000}
            step={100_000}
            thousandSeparator=" "
            suffix=" ₽"
            hideControls
            size="md"
            mb="lg"
            aria-label="Сумма"
          />
          <Slider
            value={stepIndex}
            onChange={(i) => setAmount(AMOUNT_STEPS[i])}
            min={0}
            max={AMOUNT_STEPS.length - 1}
            step={1}
            label={(i) => short(AMOUNT_STEPS[i])}
            marks={[0, 5, 9, 13].map((i) => ({ value: i, label: short(AMOUNT_STEPS[i]) }))}
            mb="lg"
          />
        </Paper>
        <Paper p="xl">
          <Text fw={600} mb="sm">
            3. На какой срок?
          </Text>
          <Text size="xl" fw={600} mb="lg">
            {months(term)}
          </Text>
          <Slider
            value={term}
            onChange={setTerm}
            min={3}
            max={60}
            step={1}
            label={(v) => months(v)}
            marks={[12, 24, 36, 48, 60].map((v) => ({ value: v, label: `${v / 12} ${v === 12 ? 'год' : v < 60 ? 'года' : 'лет'}` }))}
            mb="lg"
          />
        </Paper>
      </SimpleGrid>

      <Group>
        <Button
          size="md"
          disabled={!purpose || amount < 1}
          loading={recommend.isPending}
          onClick={() => purpose && recommend.mutate({ purpose, amount, term_months: term })}
        >
          Подобрать
        </Button>
        {!purpose && (
          <Text size="sm" c="dimmed">
            Сначала выберите, на что нужны деньги
          </Text>
        )}
      </Group>

      {recommend.error && <Alert color="red">{errorText(recommend.error)}</Alert>}

      {recommend.data && (
        <Stack gap="md">
          <ProductCard option={recommend.data.recommended} recommended onApply={apply} />
          {recommend.data.alternatives.length > 0 && (
            <>
              <Text fw={600} mt="sm">
                Другие варианты
              </Text>
              <SimpleGrid cols={{ base: 1, md: 2 }}>
                {recommend.data.alternatives.map((o) => (
                  <ProductCard key={o.product.code} option={o} onApply={apply} />
                ))}
              </SimpleGrid>
            </>
          )}
        </Stack>
      )}
    </Stack>
  );
}

function ProductCard({ option, recommended, onApply }: { option: ProductOption; recommended?: boolean; onApply: (o: ProductOption) => void }) {
  const p = option.product;
  return (
    <Card padding="xl" className={recommended ? 'needs-action' : undefined}>
      <Stack gap="sm">
        <Group justify="space-between">
          <Group gap="xs">
            <Title order={recommended ? 3 : 4}>{p.name}</Title>
            {recommended && (
              <Badge leftSection={<IconCheck size={12} />} tt="none">
                Подходит лучше всего
              </Badge>
            )}
          </Group>
          {!option.fits && (
            <Badge color="gray" variant="light" tt="none">
              Нужно изменить сумму или срок
            </Badge>
          )}
        </Group>
        <Text size="sm">{option.reason}</Text>
        <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="xs">
          <Fact label="Сумма" value={rub(option.amount)} />
          <Fact label="Срок" value={months(option.term_months)} />
          <Fact label={<Term k="rate">Ставка</Term>} value={`от ${rate(option.rate_from)}`} />
        </SimpleGrid>
        <Group justify="space-between" align="flex-end">
          <div>
            <Text size="sm" c="dimmed">
              Примерный платёж в месяц (<Term k="annuity">равными частями</Term>)
            </Text>
            <Text size="xl" fw={700}>
              от {rub(option.monthly_payment_from)}
            </Text>
          </div>
          <Button variant={recommended ? 'filled' : 'light'} onClick={() => onApply(option)}>
            {option.fits ? 'Оформить заявку' : 'Оформить с этими условиями'}
          </Button>
        </Group>
        <Text size="xs" c="dimmed">
          {p.needs_collateral ? (
            <>
              Понадобится <Term k="collateral">залог</Term>. Заявку рассмотрит специалист.
            </>
          ) : (
            'Без залога. Точные условия — после проверки заявки.'
          )}
        </Text>
      </Stack>
    </Card>
  );
}

function Fact({ label, value }: { label: ReactNode; value: string }) {
  return (
    <div>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={500}>{value}</Text>
    </div>
  );
}
