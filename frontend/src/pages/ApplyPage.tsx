// Экран 4. Анкета по шагам с прогрессом и автосохранением черновика.
//   Шаг 1 — компания по ИНН (данные подтягиваются из реестра, клиент подтверждает) → создаётся черновик.
//   Шаг 2 — финансы, шаг 3 — параметры кредита, шаг 4 — сводка и согласие → отправка.
// Начиная со второго шага всё, что вводит клиент, через секунду само сохраняется в черновик.
import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Checkbox,
  Divider,
  Group,
  NumberInput,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Stepper,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core';
import { IconAlertTriangle, IconBuilding, IconCheck, IconCloudCheck, IconLoader2 } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import type { Control, FieldPath } from 'react-hook-form';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { z } from 'zod';

import { errorText } from '../api/client';
import {
  useApplication,
  useCancelApplication,
  useCompanyLookup,
  useCreateApplication,
  usePatchApplication,
  useProducts,
  useSubmitApplication,
} from '../api/queries';
import type { Application, CompanyLookup, Product, Purpose } from '../api/types';
import { ErrorState, Loading } from '../components/StateViews';
import { annuity, date, months, rate, rub, time } from '../lib/format';
import { Term } from '../lib/glossary';
import { PURPOSES, PURPOSE_TITLE } from '../lib/statuses';

const STEPS = ['Компания', 'Финансы', 'Кредит', 'Отправка'];

// ---------- Шаг 1: компания (до создания черновика) ----------

function innError(inn: string): string | null {
  if (!/^\d+$/.test(inn)) return 'ИНН состоит только из цифр';
  if (inn.length !== 10 && inn.length !== 12) return 'ИНН должен быть из 10 цифр (компания) или 12 цифр (ИП)';
  return null;
}

function CompanyCard({ company }: { company: Pick<CompanyLookup, 'name' | 'inn' | 'director' | 'okved' | 'registered_at' | 'status'> & { ogrn?: string } }) {
  const inactive = company.status !== 'active';
  return (
    <Paper withBorder p="md" radius="md" bg="gray.0">
      <Stack gap={6}>
        <Group gap="xs">
          <IconBuilding size={20} />
          <Text fw={600}>{company.name}</Text>
        </Group>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={4}>
          <Text size="sm">
            <Term k="inn">ИНН</Term>: {company.inn}
          </Text>
          {company.ogrn && (
            <Text size="sm">
              <Term k="ogrn">ОГРН</Term>: {company.ogrn}
            </Text>
          )}
          <Text size="sm">Руководитель: {company.director}</Text>
          <Text size="sm">Зарегистрирована: {date(company.registered_at)}</Text>
        </SimpleGrid>
        <Text size="sm">
          Вид деятельности (<Term k="okved">ОКВЭД</Term>): {company.okved}
        </Text>
        {inactive && (
          <Alert color="orange" icon={<IconAlertTriangle size={18} />} p="xs">
            По данным <Term k="egrul">реестра</Term> компания {company.status === 'bankrupt' ? 'проходит банкротство' : 'ликвидируется'}. В таком статусе кредит, скорее всего, не одобрят.
          </Alert>
        )}
      </Stack>
    </Paper>
  );
}

function CompanyStep({ onConfirm, creating, createError }: { onConfirm: (inn: string) => void; creating: boolean; createError: unknown }) {
  const [inn, setInn] = useState('');
  const [touched, setTouched] = useState(false);
  const lookup = useCompanyLookup();
  const localError = touched ? innError(inn) : null;

  const find = () => {
    setTouched(true);
    if (!innError(inn)) lookup.mutate(inn);
  };

  return (
    <Stack>
      <Text c="dimmed">Введите ИНН — мы сами подтянем название, руководителя и вид деятельности из государственного реестра.</Text>
      <Group align="flex-start">
        <TextInput
          label={<Term k="inn">ИНН компании или ИП</Term>}
          placeholder="10 или 12 цифр"
          value={inn}
          onChange={(e) => {
            setInn(e.currentTarget.value.replace(/\s/g, ''));
            lookup.reset();
          }}
          onKeyDown={(e) => e.key === 'Enter' && find()}
          maxLength={12}
          inputMode="numeric"
          error={localError ?? (lookup.error ? errorText(lookup.error) : null)}
          w={260}
        />
        <Button mt={25} onClick={find} loading={lookup.isPending} variant="light">
          Найти
        </Button>
      </Group>
      {lookup.data && (
        <>
          <CompanyCard company={lookup.data} />
          {createError ? <Alert color="red">{errorText(createError)}</Alert> : null}
          <Group>
            <Button leftSection={<IconCheck size={18} />} onClick={() => onConfirm(lookup.data!.inn)} loading={creating}>
              Да, это моя компания — продолжить
            </Button>
            <Button variant="subtle" color="gray" onClick={() => lookup.reset()}>
              Это не она
            </Button>
          </Group>
        </>
      )}
      <Text size="xs" c="dimmed">
        Для демо: «Ромашка-Тест» — 0010000017, ИП Тестов — 001000001006, «Вектор-Тест» — 0010000024, «Закат-Тест» — 0010000031.
      </Text>
    </Stack>
  );
}

// ---------- Шаги 2–4: одна форма ----------

const required = (msg: string) => z.number({ error: msg });

const schema = z.object({
  revenue_12m: required('Укажите выручку за последние 12 месяцев').min(1, 'Выручка должна быть больше нуля'),
  revenue_prev_year: required('Укажите выручку за предыдущие 12 месяцев — если бизнесу меньше 2 лет, поставьте 0').min(0, 'Не может быть меньше нуля'),
  monthly_debt_payments: required('Укажите платежи по другим кредитам — если их нет, поставьте 0').min(0, 'Не может быть меньше нуля'),
  employees: required('Укажите число сотрудников').int('Целое число').min(0, 'Не может быть меньше нуля').max(100_000, 'Слишком много — проверьте'),
  product_code: z.string(),
  purpose: z.enum(['stock_salary', 'equipment', 'urgent']),
  amount: required('Укажите сумму кредита').min(1, 'Сумма должна быть больше нуля'),
  term_months: required('Укажите срок').int('Срок — целое число месяцев').min(1, 'Срок — хотя бы 1 месяц'),
  collateral_description: z.string().optional(),
  bki_consent: z.boolean(),
});
type FormValues = z.infer<typeof schema>;

const STEP_FIELDS: FieldPath<FormValues>[][] = [
  [],
  ['revenue_12m', 'revenue_prev_year', 'monthly_debt_payments', 'employees'],
  ['product_code', 'purpose', 'amount', 'term_months', 'collateral_description'],
  ['bki_consent'],
];

function toForm(app: Application): Partial<FormValues> {
  return {
    revenue_12m: app.revenue_12m ?? undefined,
    revenue_prev_year: app.revenue_prev_year ?? undefined,
    monthly_debt_payments: app.monthly_debt_payments ?? undefined,
    employees: app.employees ?? undefined,
    product_code: app.product.code,
    purpose: app.purpose,
    amount: app.amount ?? undefined,
    term_months: app.term_months ?? undefined,
    collateral_description: app.collateral_description ?? '',
    bki_consent: app.bki_consent,
  };
}

function MoneyField({ control, name, label, description, suffix = ' ₽' }: { control: Control<FormValues>; name: FieldPath<FormValues>; label: ReactNode; description: ReactNode; suffix?: string }) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <NumberInput
          label={label}
          description={description}
          value={(field.value as number | undefined) ?? ''}
          onChange={(v) => field.onChange(v === '' ? undefined : Number(v))}
          onBlur={field.onBlur}
          thousandSeparator=" "
          suffix={suffix}
          hideControls
          allowNegative={false}
          error={fieldState.error?.message}
        />
      )}
    />
  );
}

function payload(v: Partial<FormValues>) {
  const body = { ...v, collateral_description: v.collateral_description || null };
  // Пустые поля просто не отправляем — в черновике они остаются незаполненными.
  return Object.fromEntries(Object.entries(body).filter(([, x]) => x !== undefined && !(typeof x === 'number' && Number.isNaN(x))));
}

/**
 * Автосохранение черновика: через 800 мс после последнего изменения отправляем PATCH.
 * flush() — сохранить немедленно (перед отправкой заявки).
 */
function useAutosave(appId: number, values: Partial<FormValues>, getValues: () => FormValues) {
  const patch = usePatchApplication(appId);
  const lastSaved = useRef(JSON.stringify(payload(values))); // то, что пришло с сервера, сохранять незачем
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const flush = useCallback(async () => {
    const body = payload(getValues());
    const json = JSON.stringify(body);
    if (json === lastSaved.current) return;
    const saved = await patch.mutateAsync(body);
    lastSaved.current = json;
    setSavedAt(saved.updated_at);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getValues]);

  const valuesJson = JSON.stringify(payload(values));
  useEffect(() => {
    if (valuesJson === lastSaved.current) return;
    const timer = setTimeout(() => flush().catch(() => undefined), 800);
    return () => clearTimeout(timer);
  }, [valuesJson, flush]);

  return { saving: patch.isPending, savedAt, error: patch.error, flush };
}

export function ApplyPage() {
  const params = useParams();
  const id = params.id ? Number(params.id) : undefined;
  return id ? <DraftForm id={id} /> : <NewApplication />;
}

function NewApplication() {
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const create = useCreateApplication();
  const purpose = (search.get('purpose') as Purpose | null) ?? 'stock_salary';

  return (
    <Stack gap="lg" maw={860}>
      <Header />
      <Stepper active={0} size="sm" allowNextStepsSelect={false}>
        {STEPS.map((s) => (
          <Stepper.Step key={s} label={s} />
        ))}
      </Stepper>
      <Paper withBorder p="lg" radius="md">
        <Title order={4} mb="sm">
          Шаг 1. Ваша компания
        </Title>
        <CompanyStep
          creating={create.isPending}
          createError={create.error}
          onConfirm={(inn) =>
            create.mutate(
              {
                inn,
                product_code: search.get('product') ?? 'EXPRESS',
                purpose,
                amount: Number(search.get('amount')) || undefined,
                term_months: Number(search.get('term')) || undefined,
              },
              { onSuccess: (app) => navigate(`/applications/${app.id}/edit?step=1`, { replace: true }) },
            )
          }
        />
      </Paper>
    </Stack>
  );
}

function Header() {
  return (
    <div>
      <Title order={2}>Заявка на кредит</Title>
      <Text c="dimmed">Четыре коротких шага. Черновик сохраняется сам — можно закрыть страницу и вернуться позже.</Text>
    </div>
  );
}

function DraftForm({ id }: { id: number }) {
  const { data: app, isPending, error, refetch } = useApplication(id);
  const { data: products } = useProducts();
  if (isPending || !products) return <Loading text="Открываем черновик…" />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (app.status !== 'DRAFT') return <Navigate to={`/applications/${id}`} replace />;
  return <DraftFormInner app={app} products={products} />;
}

function DraftFormInner({ app, products }: { app: Application; products: Product[] }) {
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const step = Math.min(Math.max(Number(search.get('step')) || 1, 1), 3);
  const goto = (s: number) => setSearch({ step: String(s) }, { replace: true });

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: toForm(app),
    mode: 'onTouched',
  });
  const { control, register, trigger, setError, getValues } = form;
  const values = useWatch({ control });
  const autosave = useAutosave(app.id, values, getValues);
  const submit = useSubmitApplication(app.id);
  const cancel = useCancelApplication(app.id);

  const productCode = useWatch({ control, name: 'product_code' });
  const product = products.find((p) => p.code === productCode) ?? app.product;
  const [amount, term] = useWatch({ control, name: ['amount', 'term_months'] });
  const payment = useMemo(
    () => (amount && term ? annuity(amount, product.base_rate, term) : null),
    [amount, term, product.base_rate],
  );

  // Проверки, которые зависят от выбранного продукта (лимиты суммы и срока, залог).
  const checkProductLimits = (): boolean => {
    const v = getValues();
    let ok = true;
    if (v.amount != null && (v.amount < product.min_amount || v.amount > product.max_amount)) {
      setError('amount', { message: `Для «${product.name}» сумма от ${rub(product.min_amount)} до ${rub(product.max_amount)}` });
      ok = false;
    }
    if (v.term_months != null && (v.term_months < product.min_term || v.term_months > product.max_term)) {
      setError('term_months', { message: `Для «${product.name}» срок от ${product.min_term} до ${months(product.max_term)}` });
      ok = false;
    }
    if (product.needs_collateral && (v.collateral_description ?? '').trim().length < 5) {
      setError('collateral_description', { message: 'Опишите имущество для залога: что это и сколько примерно стоит' });
      ok = false;
    }
    return ok;
  };

  const next = async () => {
    const valid = await trigger(STEP_FIELDS[step]);
    if (!valid || (step === 2 && !checkProductLimits())) return;
    goto(step + 1);
  };

  const onSubmit = async () => {
    if (!getValues('bki_consent')) {
      setError('bki_consent', { message: 'Без согласия мы не сможем проверить кредитную историю' });
      return;
    }
    // Сначала сохраняем последние изменения, потом отправляем.
    try {
      await autosave.flush();
    } catch {
      return; // ошибку сохранения уже показывает индикатор вверху
    }
    submit.mutate(undefined, { onSuccess: () => navigate(`/applications/${app.id}`) });
  };

  return (
    <Stack gap="lg" maw={860}>
      <Group justify="space-between" align="flex-end">
        <Header />
        <SaveIndicator saving={autosave.saving} savedAt={autosave.savedAt} error={autosave.error} />
      </Group>

      <Stepper active={step} onStepClick={(s) => s > 0 && s < step && goto(s)} size="sm" allowNextStepsSelect={false}>
        {STEPS.map((s) => (
          <Stepper.Step key={s} label={s} />
        ))}
      </Stepper>

      <Paper withBorder p="lg" radius="md">
        <Stack>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              Заявка №{app.id} · {app.company.name}
            </Text>
            <Badge variant="light" color="gray" tt="none">
              Черновик
            </Badge>
          </Group>
          <Divider />

          {step === 1 && (
            <>
              <Title order={4}>Шаг 2. Финансы компании</Title>
              <Text size="sm" c="dimmed">
                Примерные цифры подойдут — точные мы сверим позже. Они нужны, чтобы предложить посильный платёж.
              </Text>
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                <MoneyField control={control} name="revenue_12m" label="Выручка за последние 12 месяцев" description="Все поступления от продаж, до вычета расходов" />
                <MoneyField control={control} name="revenue_prev_year" label="Выручка за 12 месяцев до этого" description="Чтобы понять, растёт ли бизнес. Нет данных — поставьте 0" />
                <MoneyField
                  control={control}
                  name="monthly_debt_payments"
                  label="Платежи по другим кредитам в месяц"
                  description="Кредиты, лизинг, займы компании. Если нет — 0"
                />
                <MoneyField control={control} name="employees" label="Сотрудников в штате" description="Включая руководителя" suffix="" />
              </SimpleGrid>
            </>
          )}

          {step === 2 && (
            <>
              <Title order={4}>Шаг 3. Параметры кредита</Title>
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                <Controller
                  control={control}
                  name="product_code"
                  render={({ field }) => (
                    <Select
                      label="Кредит"
                      data={products.map((p) => ({ value: p.code, label: p.name }))}
                      value={field.value}
                      onChange={(v) => v && field.onChange(v)}
                      allowDeselect={false}
                      description={product.description}
                    />
                  )}
                />
                <Controller
                  control={control}
                  name="purpose"
                  render={({ field }) => (
                    <Select
                      label="На что нужны деньги"
                      data={PURPOSES.map((p) => ({ value: p.value, label: p.title }))}
                      value={field.value}
                      onChange={(v) => v && field.onChange(v)}
                      allowDeselect={false}
                      description={PURPOSES.find((p) => p.value === field.value)?.hint}
                    />
                  )}
                />
                <MoneyField control={control} name="amount" label="Сумма" description={`От ${rub(product.min_amount)} до ${rub(product.max_amount)}`} />
                <MoneyField control={control} name="term_months" label="Срок, месяцев" description={`От ${product.min_term} до ${product.max_term} месяцев`} suffix=" мес." />
              </SimpleGrid>
              {product.needs_collateral && (
                <Textarea
                  label={
                    <>
                      Что можно оставить в <Term k="collateral">залог</Term>
                    </>
                  }
                  description="Например: «Токарный станок, 2022 г., стоит около 8 млн ₽»"
                  autosize
                  minRows={2}
                  {...register('collateral_description')}
                  error={form.formState.errors.collateral_description?.message}
                />
              )}
              {payment && (
                <Alert variant="light" color="gray">
                  Примерный платёж: <b>от {rub(payment)} в месяц</b> при ставке от {rate(product.base_rate)}. Точные условия — после проверки.
                </Alert>
              )}
            </>
          )}

          {step === 3 && (
            <>
              <Title order={4}>Шаг 4. Проверьте и отправьте</Title>
              <Summary title="Компания" onEdit={null}>
                <Text>{app.company.name}</Text>
                <Text size="sm" c="dimmed">
                  ИНН {app.company.inn} · {app.company.director}
                </Text>
              </Summary>
              <Summary title="Финансы" onEdit={() => goto(1)}>
                <Text size="sm">Выручка за 12 месяцев: {rub(values.revenue_12m)}</Text>
                <Text size="sm">Выручка за предыдущие 12 месяцев: {rub(values.revenue_prev_year)}</Text>
                <Text size="sm">Платежи по другим кредитам: {rub(values.monthly_debt_payments)} в месяц</Text>
                <Text size="sm">Сотрудников: {values.employees ?? '—'}</Text>
              </Summary>
              <Summary title="Кредит" onEdit={() => goto(2)}>
                <Text size="sm">
                  {product.name}: {rub(values.amount)} на {months(values.term_months)}
                </Text>
                <Text size="sm">Цель: {values.purpose ? PURPOSE_TITLE[values.purpose] : '—'}</Text>
                {product.needs_collateral && <Text size="sm">Залог: {values.collateral_description || '—'}</Text>}
                {payment && <Text size="sm">Примерный платёж: от {rub(payment)} в месяц</Text>}
              </Summary>
              <Controller
                control={control}
                name="bki_consent"
                render={({ field, fieldState }) => (
                  <Checkbox
                    checked={field.value}
                    onChange={(e) => field.onChange(e.currentTarget.checked)}
                    error={fieldState.error?.message}
                    label={
                      <>
                        Согласен на запрос кредитной истории компании в <Term k="bki">бюро кредитных историй</Term>
                      </>
                    }
                    description="Это нужно, чтобы принять решение. Запрос не влияет на вашу кредитную историю."
                  />
                )}
              />
              {submit.error && <Alert color="red">{errorText(submit.error)}</Alert>}
            </>
          )}

          <Divider />
          <Group justify="space-between">
            <Group>
              {step > 1 && (
                <Button variant="default" onClick={() => goto(step - 1)}>
                  Назад
                </Button>
              )}
              <Button
                variant="subtle"
                color="gray"
                loading={cancel.isPending}
                onClick={() => window.confirm('Удалить черновик? Заполненные данные не сохранятся.') && cancel.mutate(undefined, { onSuccess: () => navigate('/') })}
              >
                Отменить заявку
              </Button>
            </Group>
            {step < 3 ? (
              <Button onClick={next}>Далее</Button>
            ) : (
              <Button size="md" onClick={onSubmit} loading={submit.isPending}>
                Отправить заявку
              </Button>
            )}
          </Group>
        </Stack>
      </Paper>
    </Stack>
  );
}

function Summary({ title, onEdit, children }: { title: string; onEdit: (() => void) | null; children: ReactNode }) {
  return (
    <Paper withBorder p="sm" radius="md">
      <Group justify="space-between" mb={4}>
        <Text fw={600}>{title}</Text>
        {onEdit && (
          <Anchor component="button" type="button" size="sm" onClick={onEdit}>
            Изменить
          </Anchor>
        )}
      </Group>
      {children}
    </Paper>
  );
}

function SaveIndicator({ saving, savedAt, error }: { saving: boolean; savedAt: string | null; error: unknown }) {
  if (error) return <Text size="sm" c="red">Не удалось сохранить черновик: {errorText(error)}</Text>;
  if (saving)
    return (
      <Group gap={4}>
        <IconLoader2 size={16} />
        <Text size="sm" c="dimmed">
          Сохраняем…
        </Text>
      </Group>
    );
  if (savedAt)
    return (
      <Group gap={4}>
        <IconCloudCheck size={16} color="var(--mantine-color-green-7)" />
        <Text size="sm" c="dimmed">
          Черновик сохранён в {time(savedAt)}
        </Text>
      </Group>
    );
  return null;
}
