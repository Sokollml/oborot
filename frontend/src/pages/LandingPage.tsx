// Публичная страница продукта: первое, что видит человек без входа. Витрина в духе банковского сайта —
// предложение, продукты, калькулятор платежа, как это работает, частые вопросы.
import { Accordion, Box, Button, Container, Flex, Group, Paper, SimpleGrid, Slider, Stack, Text, ThemeIcon, Title } from '@mantine/core';
import { IconBolt, IconBuildingBank, IconClockHour4, IconFileOff, IconSparkles, IconStairsUp } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { useProducts } from '../api/queries';
import { annuity, months, rub } from '../lib/format';
import { Term } from '../lib/glossary';
import { useIsMobile } from '../lib/responsive';

const STEPS = [
  { title: 'Узнайте лимит', text: 'Клиентам банка считаем предодобренную сумму по оборотам на счёте — без анкеты и документов.' },
  { title: 'Подайте заявку', text: 'ИНН — и данные компании подтянутся сами. Четыре коротких шага, черновик сохраняется.' },
  { title: 'Следите за статусом', text: 'Лента этапов в реальном времени: что происходит, сколько ждать, нужно ли что-то от вас.' },
  { title: 'Подпишите и получите', text: 'Подпись кодом прямо в кабинете — деньги на счёте компании.' },
];

const FAQ = [
  ['Нужны ли документы?', 'Клиентам банка обычно нет: выручку видим по оборотам счёта. Если что-то понадобится, попросим загрузить прямо в кабинете.'],
  ['Сколько ждать решения?', 'Простые заявки решаются автоматически за пару минут. Если заявку смотрит специалист — обычно до одного рабочего дня.'],
  ['Почему могут отказать?', 'Мы всегда объясняем причину простыми словами и подсказываем, что можно сделать: например, снизить сумму или вернуться позже.'],
  ['Можно ли погасить досрочно?', 'Да, в любой день, полностью или частично, без комиссии.'],
];

export function LandingPage() {
  const { data: products } = useProducts();
  const [amount, setAmount] = useState(2_000_000);
  const [term, setTerm] = useState(12);
  const mobile = useIsMobile();

  // Калькулятор: самый подходящий беззалоговый продукт по сумме и сроку и платёж по его базовой ставке.
  const calc = useMemo(() => {
    const fits = (products ?? []).filter((p) => !p.needs_collateral && amount >= p.min_amount && amount <= p.max_amount && term >= p.min_term && term <= p.max_term);
    const product = fits.sort((a, b) => a.base_rate - b.base_rate)[0] ?? (products ?? []).find((p) => amount <= p.max_amount && term <= p.max_term);
    return product ? { product, payment: annuity(amount, product.base_rate, term) } : null;
  }, [products, amount, term]);

  return (
    <Box bg="gray.0" mih="100vh">
      <Box bg="white" style={{ boxShadow: '0 1px 0 #ebedef' }}>
        <Container size="lg" h={64}>
          <Group h="100%" justify="space-between">
            <Group gap={8}>
              <ThemeIcon size={34} radius="md">
                <IconStairsUp size={20} />
              </ThemeIcon>
              <Text fw={800} size="xl">
                Ступени
              </Text>
              <Text size="sm" c="dimmed" visibleFrom="sm">
                · кредиты для бизнеса
              </Text>
            </Group>
            <Button component={Link} to="/login">
              Войти
            </Button>
          </Group>
        </Container>
      </Box>

      <Container size="lg" py={{ base: 'md', sm: 48 }}>
        <Stack gap={mobile ? 32 : 56}>
          {/* Главное предложение */}
          <Paper p={{ base: 'lg', md: 48 }} className="hero-dark">
            <Flex direction={{ base: 'column', md: 'row' }} justify="space-between" align={{ base: 'stretch', md: 'flex-end' }} gap={{ base: 'lg', md: 48 }}>
              <Stack gap="md" maw={620}>
                <Group gap="xs">
                  <ThemeIcon size={28} radius="md">
                    <IconSparkles size={16} />
                  </ThemeIcon>
                  <Text c="gray.4" fw={600} size="sm">
                    Для малого бизнеса и ИП
                  </Text>
                </Group>
                <Title order={1} c="white" fz={{ base: 30, sm: 48 }}>
                  Деньги на бизнес — решение за минуты
                </Title>
                <Text c="gray.4" size="lg">
                  Узнайте лимит без документов, подайте заявку за 4 шага и следите за решением в реальном времени. Без визита в офис.
                </Text>
                <Group mt="sm">
                  <Button size="lg" component={Link} to="/login">
                    Узнать свой лимит
                  </Button>
                  <Button size="lg" variant="white" color="dark" component="a" href="#calc">
                    Рассчитать платёж
                  </Button>
                </Group>
              </Stack>
              <SimpleGrid cols={1} spacing="sm" miw={{ md: 240 }}>
                <HeroFact icon={<IconBolt size={18} />} title="до 50 млн ₽" text="три продукта под разные задачи" />
                <HeroFact icon={<IconClockHour4 size={18} />} title="от 2 минут" text="автоматическое решение" />
                <HeroFact icon={<IconFileOff size={18} />} title="без документов" text="клиентам банка — по оборотам" />
              </SimpleGrid>
            </Flex>
          </Paper>

          {/* Продукты */}
          <Stack gap="md">
            <Title order={2}>Кредиты для бизнеса</Title>
            <SimpleGrid cols={{ base: 1, sm: 3 }}>
              {(products ?? []).map((p) => (
                <Paper key={p.code} p="xl">
                  <Stack gap="xs" h="100%">
                    <Title order={3}>{p.name}</Title>
                    <Text size="sm" c="dimmed">
                      {p.description}
                    </Text>
                    <SimpleGrid cols={2} mt="sm" spacing="xs">
                      <Fact label="Сумма" value={`до ${rub(p.max_amount)}`} />
                      <Fact label="Срок" value={`до ${months(p.max_term)}`} />
                      <Fact label={<Term k="rate">Ставка</Term>} value={`от ${p.base_rate}%`} />
                      <Fact label={<Term k="collateral">Залог</Term>} value={p.needs_collateral ? 'нужен' : 'не нужен'} />
                    </SimpleGrid>
                  </Stack>
                </Paper>
              ))}
            </SimpleGrid>
          </Stack>

          {/* Калькулятор */}
          <Paper p={{ base: 'lg', sm: 'xl' }} id="calc">
            <SimpleGrid cols={{ base: 1, md: 2 }} spacing={{ base: "lg", md: 48 }}>
              <Stack gap="lg">
                <Title order={2}>Рассчитайте платёж</Title>
                <div>
                  <Group justify="space-between" mb={6}>
                    <Text fw={600}>Сумма</Text>
                    <Text fw={800}>{rub(amount)}</Text>
                  </Group>
                  <Slider value={amount} onChange={setAmount} min={100_000} max={15_000_000} step={100_000} label={null} />
                </div>
                <div>
                  <Group justify="space-between" mb={6}>
                    <Text fw={600}>Срок</Text>
                    <Text fw={800}>{months(term)}</Text>
                  </Group>
                  <Slider value={term} onChange={setTerm} min={3} max={36} step={1} label={null} />
                </div>
              </Stack>
              <Paper bg="gray.0" p="xl" radius="xl">
                {calc ? (
                  <Stack gap="xs">
                    <Text c="dimmed" size="sm">
                      Подойдёт: <b>{calc.product.name}</b>
                    </Text>
                    <Text size="sm" c="dimmed">
                      Платёж в месяц (<Term k="annuity">равными частями</Term>)
                    </Text>
                    <Text fz={{ base: 32, sm: 40 }} fw={800} lh={1.1}>
                      от {rub(calc.payment)}
                    </Text>
                    <Text size="sm" c="dimmed">
                      по ставке от {calc.product.base_rate}% годовых. Точные условия — после проверки заявки.
                    </Text>
                    <Button mt="md" size="md" component={Link} to="/login" w="fit-content">
                      Оформить заявку
                    </Button>
                  </Stack>
                ) : (
                  <Text c="dimmed">Измените сумму или срок — подберём подходящий кредит.</Text>
                )}
              </Paper>
            </SimpleGrid>
          </Paper>

          {/* Как это работает */}
          <Stack gap="md">
            <Title order={2}>Как это работает</Title>
            <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
              {STEPS.map((s, i) => (
                <Paper key={s.title} p="xl">
                  <ThemeIcon size={36} radius="xl" variant="light">
                    <Text fw={800}>{i + 1}</Text>
                  </ThemeIcon>
                  <Title order={4} mt="md">
                    {s.title}
                  </Title>
                  <Text size="sm" c="dimmed" mt={4}>
                    {s.text}
                  </Text>
                </Paper>
              ))}
            </SimpleGrid>
          </Stack>

          {/* Частые вопросы */}
          <Stack gap="md">
            <Title order={2}>Частые вопросы</Title>
            <Paper p="md">
              <Accordion variant="default" chevronPosition="right">
                {FAQ.map(([q, a]) => (
                  <Accordion.Item key={q} value={q}>
                    <Accordion.Control>
                      <Text fw={600}>{q}</Text>
                    </Accordion.Control>
                    <Accordion.Panel>
                      <Text size="sm">{a}</Text>
                    </Accordion.Panel>
                  </Accordion.Item>
                ))}
              </Accordion>
            </Paper>
          </Stack>

          <Group justify="space-between" c="dimmed" gap="xs">
            <Group gap={6} wrap="nowrap">
              <IconBuildingBank size={16} />
              <Text size="xs">Демо-проект хакатона. Данные, компании и решения синтетические.</Text>
            </Group>
            <Text size="xs" component={Link} to="/login" c="dimmed">
              Вход для специалистов банка
            </Text>
          </Group>
        </Stack>
      </Container>
    </Box>
  );
}

function HeroFact({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <Paper p="md" radius="lg" style={{ background: 'rgba(255,255,255,0.08)' }}>
      <Group gap="sm" wrap="nowrap">
        <ThemeIcon size={36} radius="md" color="accent">
          {icon}
        </ThemeIcon>
        <div>
          <Text c="white" fw={800}>
            {title}
          </Text>
          <Text c="gray.4" size="xs">
            {text}
          </Text>
        </div>
      </Group>
    </Paper>
  );
}

function Fact({ label, value }: { label: ReactNode; value: string }) {
  return (
    <div>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700} size="sm">
        {value}
      </Text>
    </div>
  );
}
