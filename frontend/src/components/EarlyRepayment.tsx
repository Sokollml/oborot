// Досрочное погашение в «Моих кредитах»: клиент видит, сколько сэкономит, если внесёт сумму сверх графика.
// Это расчёт: в демо деньги не списываются (в банке здесь было бы заявление на досрочное погашение).
import { Alert, Button, Modal, NumberInput, Paper, SegmentedControl, SimpleGrid, Stack, Text } from '@mantine/core';
import { IconCoins, IconInfoCircle } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';

import type { Application } from '../api/types';
import { months, rub } from '../lib/format';
import { Term } from '../lib/glossary';
import { useIsMobile } from '../lib/responsive';
import { earlyRepayment, type EarlyMode } from '../lib/schedule';

export function EarlyRepaymentButton({ loan, start }: { loan: Application; start: Date }) {
  const [open, setOpen] = useState(false);
  const mobile = useIsMobile();
  if (!loan.decision?.amount) return null;
  return (
    <>
      <Button variant="default" size="sm" leftSection={<IconCoins size={16} />} onClick={() => setOpen(true)}>
        Погасить досрочно
      </Button>
      <Modal opened={open} onClose={() => setOpen(false)} title={<b>Досрочное погашение</b>} size="lg" centered fullScreen={mobile}>
        <Calculator loan={loan} start={start} />
      </Modal>
    </>
  );
}

function Calculator({ loan, start }: { loan: Application; start: Date }) {
  const d = loan.decision!;
  const [extra, setExtra] = useState<number>(Math.round((d.amount ?? 0) / 10 / 1000) * 1000);
  const [mode, setMode] = useState<EarlyMode>('payment');
  const now = useMemo(() => new Date(), []);
  const r = useMemo(
    () => earlyRepayment(d.amount ?? 0, d.rate ?? 0, d.term ?? 1, start, now, extra || 0, mode),
    [d.amount, d.rate, d.term, start, now, extra, mode],
  );

  return (
    <Stack>
      <SimpleGrid cols={{ base: 1, xs: 2 }}>
        <Fact label={<Term k="principal">Основной долг сейчас</Term>} value={rub(r.balance)} />
        <Fact label="Осталось платежей" value={months(r.monthsLeft)} />
      </SimpleGrid>

      <NumberInput
        label="Сколько хотите внести сверх графика"
        value={extra}
        onChange={(v) => setExtra(typeof v === 'number' ? v : 0)}
        min={0}
        max={r.balance}
        step={10_000}
        thousandSeparator=" "
        suffix=" ₽"
        allowNegative={false}
        allowDecimal={false}
      />
      {!r.closes && (
        <SegmentedControl
          fullWidth
          value={mode}
          onChange={(v) => setMode(v as EarlyMode)}
          data={[
            { value: 'payment', label: 'Уменьшить платёж' },
            { value: 'term', label: 'Сократить срок' },
          ]}
        />
      )}

      {r.closes ? (
        <Alert color="green" title="Кредит будет полностью погашен">
          Не придётся платить {rub(r.saving)} процентов.
        </Alert>
      ) : (
        <SimpleGrid cols={{ base: 1, xs: 3 }}>
          <Fact label="Платёж в месяц" value={rub(r.newPayment)} was={r.newPayment !== r.paymentNow ? rub(r.paymentNow) : undefined} />
          <Fact label="Осталось платить" value={months(r.newMonths)} was={r.newMonths !== r.monthsLeft ? months(r.monthsLeft) : undefined} />
          <Fact label="Экономия на процентах" value={rub(r.saving)} accent />
        </SimpleGrid>
      )}

      <Text size="sm" c="dimmed">
        {mode === 'payment' || r.closes
          ? 'Обычно выгоднее сокращать срок — проценты начисляются меньше месяцев. Уменьшить платёж удобно, если нужно разгрузить бюджет.'
          : 'Платёж остаётся прежним, а кредит закончится раньше — так экономия на процентах максимальная.'}
      </Text>
      <Alert color="gray" icon={<IconInfoCircle size={18} />}>
        Это расчёт: на демо-стенде деньги не списываются. Досрочное погашение — в любой день, без комиссии.
      </Alert>
    </Stack>
  );
}

function Fact({ label, value, was, accent }: { label: ReactNode; value: string; was?: string; accent?: boolean }) {
  return (
    <Paper p="sm" radius="md" bg={accent ? 'accent.0' : 'gray.0'}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700}>{value}</Text>
      {was && (
        <Text size="xs" c="dimmed" td="line-through">
          {was}
        </Text>
      )}
    </Paper>
  );
}
