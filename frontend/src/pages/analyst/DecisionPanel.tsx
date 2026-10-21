// Панель решения специалиста: одобрить / изменить условия / запросить документы / отказать.
// Комментарий обязателен. При изменении условий платёж пересчитывается на лету.
import { Alert, Button, Checkbox, Group, NumberInput, Paper, SegmentedControl, SimpleGrid, Stack, Text, Textarea, Title } from '@mantine/core';
import { IconBulb, IconCheck } from '@tabler/icons-react';
import { useEffect, useState } from 'react';

import { errorText } from '../../api/client';
import { useAnalystDecision } from '../../api/queries';
import type { AnalystCard } from '../../api/types';
import { annuity, months, rate as fmtRate, rub } from '../../lib/format';
import { Term } from '../../lib/glossary';
import { useIsMobile } from '../../lib/responsive';
import { DOC_TYPES } from '../../lib/statuses';

type Mode = 'approve' | 'change' | 'request_docs' | 'reject';

const STATUS_HINT: Record<string, string> = {
  SUBMITTED: 'Заявка ещё проходит автоматическую проверку.',
  CHECKING: 'Заявка ещё проходит автоматическую проверку.',
  SCORING: 'Заявка ещё проходит автоматическую проверку.',
  INFO_REQUESTED: 'Ждём документы от клиента. Когда он их загрузит, заявка вернётся к вам.',
  SIGNING: 'Клиент принял предложение и подписывает договор.',
  ISSUED: 'Кредит выдан.',
  CANCELLED: 'Клиент отменил заявку.',
};

export function RecommendationCard({ card, onUse }: { card: AnalystCard; onUse?: () => void }) {
  const r = card.recommendation;
  return (
    <Paper p="xl" bg="dark.9" c="white" style={{ background: '#0b1f35' }}>
      <Group gap={8} mb="xs">
        <IconBulb size={20} color="#ffcf4d" />
        <Text size="sm" fw={600} c="gray.4">
          Рекомендация системы
        </Text>
      </Group>
      <Title order={3} c="white">
        {r.title}
      </Title>
      <Text size="sm" c="gray.3" mt={4}>
        {r.text}
      </Text>
      {r.amount != null && (
        <Text size="sm" mt="sm" c="white">
          {rub(r.amount)} на {months(r.term_months)}, {fmtRate(r.rate)}, платёж {rub(r.monthly_payment)}
        </Text>
      )}
      {onUse && card.available_actions.length > 0 && (
        <Button mt="md" variant="white" color="dark" size="sm" onClick={onUse}>
          Подставить в решение
        </Button>
      )}
    </Paper>
  );
}

export function DecisionPanel({ card, preset }: { card: AnalystCard; preset: number }) {
  const app = card.application;
  const actions = card.available_actions;
  const decision = useAnalystDecision(app.id);
  const rec = card.recommendation;
  const mobile = useIsMobile();

  const defaultRate = rec.rate ?? app.product.base_rate;
  const [mode, setMode] = useState<Mode>('approve');
  const [amount, setAmount] = useState<number>(app.amount ?? 0);
  const [term, setTerm] = useState<number>(app.term_months ?? 12);
  const [rateValue, setRateValue] = useState<number>(defaultRate);
  const [docs, setDocs] = useState<string[]>(['bank_statement']);
  const [reason, setReason] = useState('');
  const [comment, setComment] = useState('');
  const [done, setDone] = useState<string | null>(null);

  // «Подставить в решение» из рекомендации системы
  useEffect(() => {
    if (!preset) return;
    if (rec.action === 'request_docs' && actions.includes('request_docs')) setMode('request_docs');
    else if (rec.action === 'reject' && actions.includes('reject')) setMode('reject');
    else if (rec.amount != null) {
      setMode(rec.amount === app.amount ? 'approve' : 'change');
      setAmount(rec.amount);
      setTerm(rec.term_months ?? term);
      setRateValue(rec.rate ?? defaultRate);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset]);

  if (actions.length === 0) {
    return (
      <Paper p="xl">
        <Title order={4} mb={4}>
          Решение
        </Title>
        <Text c="dimmed">{STATUS_HINT[app.status] ?? 'Сейчас решение специалиста не требуется.'}</Text>
      </Paper>
    );
  }

  const modes: { value: Mode; label: string }[] = [
    ...(actions.includes('approve') ? [{ value: 'approve' as Mode, label: 'Одобрить' }, { value: 'change' as Mode, label: 'Изменить' }] : []),
    ...(actions.includes('request_docs') ? [{ value: 'request_docs' as Mode, label: 'Документы' }] : []),
    ...(actions.includes('reject') ? [{ value: 'reject' as Mode, label: 'Отказать' }] : []),
  ];
  const current = modes.some((m) => m.value === mode) ? mode : modes[0].value;
  const terms = current === 'approve' ? { amount: app.amount ?? 0, term: app.term_months ?? 1, rate: defaultRate } : { amount, term, rate: rateValue };
  const payment = terms.amount && terms.term && terms.rate ? annuity(terms.amount, terms.rate, terms.term) : null;

  const submit = () => {
    setDone(null);
    const base = { comment };
    const body =
      current === 'request_docs'
        ? { ...base, action: 'request_docs' as const, doc_types: docs }
        : current === 'reject'
          ? { ...base, action: 'reject' as const, client_reason: reason || null }
          : { ...base, action: 'approve' as const, amount: terms.amount, term_months: terms.term, rate: terms.rate };
    decision.mutate(body, {
      onSuccess: () => {
        setDone('Решение сохранено — клиент уже видит его в кабинете');
        setComment('');
        setReason('');
      },
    });
  };

  const commentMissing = comment.trim().length === 0;
  const title = app.status === 'OFFER' ? 'Изменить решение' : app.status === 'REJECTED' ? 'Пересмотреть отказ' : 'Решение';

  return (
    <Paper p="xl">
      <Stack>
        <Title order={4}>{title}</Title>
        {app.status === 'OFFER' && (
          <Text size="sm" c="dimmed">
            Клиент ещё не принял предложение — условия можно изменить или отозвать.
          </Text>
        )}
        <SegmentedControl fullWidth value={current} onChange={(v) => setMode(v as Mode)} data={modes} radius="md" orientation={mobile ? 'vertical' : 'horizontal'} />

        {current === 'approve' && (
          <Paper bg="gray.0" p="md" radius="lg">
            <Text size="sm">
              Одобрить как просил клиент: <b>{rub(app.amount)}</b> на <b>{months(app.term_months)}</b>, ставка {fmtRate(defaultRate)}.
            </Text>
          </Paper>
        )}

        {current === 'change' && (
          <SimpleGrid cols={{ base: 1, xs: 3 }} spacing="sm" className="on-gray">
            <NumberInput label="Сумма" value={amount} onChange={(v) => setAmount(Number(v) || 0)} thousandSeparator=" " suffix=" ₽" hideControls step={50_000} />
            <NumberInput label="Срок, мес." value={term} onChange={(v) => setTerm(Number(v) || 0)} min={app.product.min_term} max={app.product.max_term} />
            <NumberInput label={<Term k="rate">Ставка, %</Term>} value={rateValue} onChange={(v) => setRateValue(Number(v) || 0)} decimalScale={1} step={0.5} min={1} max={60} />
          </SimpleGrid>
        )}

        {(current === 'approve' || current === 'change') && payment && (
          <Group justify="space-between" p="md" bg="accent.0" style={{ borderRadius: 16 }}>
            <Text size="sm">
              <Term k="annuity">Платёж в месяц</Term>
            </Text>
            <Text fw={800} size="lg">
              {rub(payment)}
            </Text>
          </Group>
        )}
        {current === 'change' && (
          <Text size="xs" c="dimmed">
            Лимиты «{app.product.name}»: {rub(app.product.min_amount)} – {rub(app.product.max_amount)}, {app.product.min_term}–{app.product.max_term} мес.
          </Text>
        )}

        {current === 'request_docs' && (
          <Checkbox.Group label="Какие документы нужны" value={docs} onChange={setDocs}>
            <Stack gap="xs" mt="xs">
              {DOC_TYPES.map((d) => (
                <Checkbox key={d.value} value={d.value} label={d.label} />
              ))}
            </Stack>
          </Checkbox.Group>
        )}

        {current === 'reject' && (
          <Textarea
            label="Причина для клиента"
            description="Простыми словами, без внутренних терминов. Если пусто — клиент увидит комментарий ниже."
            value={reason}
            onChange={(e) => setReason(e.currentTarget.value)}
            autosize
            minRows={2}
          />
        )}

        <Textarea
          label="Комментарий специалиста"
          description="Обязательно: попадёт в историю заявки"
          placeholder="Например: выручка подтверждена выпиской, нагрузка приемлемая"
          value={comment}
          onChange={(e) => setComment(e.currentTarget.value)}
          autosize
          minRows={2}
          withAsterisk
        />

        {decision.error && <Alert color="red">{errorText(decision.error)}</Alert>}
        {done && (
          <Alert color="green" icon={<IconCheck size={18} />}>
            {done}
          </Alert>
        )}

        <Button
          size="lg"
          color={current === 'reject' ? 'dark' : 'accent'}
          disabled={commentMissing || (current === 'request_docs' && docs.length === 0)}
          loading={decision.isPending}
          onClick={submit}
        >
          {current === 'reject' ? 'Отказать' : current === 'request_docs' ? 'Запросить документы' : current === 'change' ? 'Одобрить с новыми условиями' : 'Одобрить'}
        </Button>
        {commentMissing && (
          <Text size="xs" c="dimmed" ta="center">
            Чтобы принять решение, напишите комментарий
          </Text>
        )}
      </Stack>
    </Paper>
  );
}
