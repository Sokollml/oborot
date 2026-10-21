// Блоки «Что дальше» для каждого состояния заявки: предложение, подпись, деньги, отказ, документы.
import { Alert, Button, FileButton, Group, List, Modal, Paper, PinInput, SimpleGrid, Stack, Table, Text, ThemeIcon, Title } from '@mantine/core';
import { IconBulb, IconCircleCheck, IconFileText, IconUpload, IconX } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { errorText } from '../../api/client';
import { useAcceptOffer, useCloneApplication, useDeclineOffer, useSign, useUploadDocument } from '../../api/queries';
import type { Application } from '../../api/types';
import { annuity, months, rate, rub } from '../../lib/format';
import { Term } from '../../lib/glossary';

function ConfirmButton(props: {
  label: string;
  title: string;
  text: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  loading: boolean;
  variant?: string;
  color?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant={props.variant} color={props.color} onClick={() => setOpen(true)}>
        {props.label}
      </Button>
      <Modal opened={open} onClose={() => setOpen(false)} title={props.title} centered>
        <Stack>
          <Text>{props.text}</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setOpen(false)}>
              Назад
            </Button>
            <Button
              color={props.color}
              loading={props.loading}
              onClick={() => {
                props.onConfirm();
                setOpen(false);
              }}
            >
              {props.confirmLabel}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}

// ---------- Предложение ----------

export function OfferBlock({ app }: { app: Application }) {
  const accept = useAcceptOffer(app.id);
  const decline = useDeclineOffer(app.id);
  const d = app.decision!;
  const counter = d.type === 'counter';
  const error = accept.error ?? decline.error;

  return (
    <Stack>
      {counter ? (
        <Table withTableBorder withColumnBorders verticalSpacing="sm" fz="md">
          <Table.Thead>
            <Table.Tr>
              <Table.Th />
              <Table.Th>Вы просили</Table.Th>
              <Table.Th bg="accent.0">Мы предлагаем</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            <Table.Tr>
              <Table.Td c="dimmed">Сумма</Table.Td>
              <Table.Td>{rub(app.amount)}</Table.Td>
              <Table.Td fw={700} bg="accent.0">
                {rub(d.amount)}
              </Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Td c="dimmed">Срок</Table.Td>
              <Table.Td>{months(app.term_months)}</Table.Td>
              <Table.Td bg="accent.0">{months(d.term)}</Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Td c="dimmed">Платёж в месяц</Table.Td>
              <Table.Td>≈ {rub(annuity(app.amount ?? 0, d.rate ?? 0, app.term_months ?? 1))}</Table.Td>
              <Table.Td fw={700} bg="accent.0">
                {rub(d.monthly_payment)}
              </Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Td c="dimmed">
                <Term k="rate">Ставка</Term>
              </Table.Td>
              <Table.Td colSpan={2} ta="center">
                {rate(d.rate)}
              </Table.Td>
            </Table.Tr>
          </Table.Tbody>
        </Table>
      ) : (
        <SimpleGrid cols={2} spacing="md">
          <Big label="Сумма" value={rub(d.amount)} />
          <Big label="Срок" value={months(d.term)} />
          <Big label={<Term k="rate">Ставка</Term>} value={rate(d.rate)} />
          <Big label={<Term k="annuity">Платёж в месяц</Term>} value={rub(d.monthly_payment)} accent />
        </SimpleGrid>
      )}

      {d.reasons.length > 0 && (
        <div>
          <Text fw={600} size="sm" mb={4}>
            {counter ? 'Почему такие условия' : 'Почему одобрили'}
          </Text>
          <List size="sm" spacing={4}>
            {d.reasons.map((r) => (
              <List.Item key={r}>{r}</List.Item>
            ))}
          </List>
        </div>
      )}

      {error && <Alert color="red">{errorText(error)}</Alert>}
      <Group>
        <ConfirmButton
          label="Принять предложение"
          title="Принять предложение?"
          text={`${rub(d.amount)} на ${months(d.term)}, платёж ${rub(d.monthly_payment)} в месяц. Дальше — подписание договора кодом.`}
          confirmLabel="Да, принимаю"
          onConfirm={() => accept.mutate()}
          loading={accept.isPending}
        />
        <ConfirmButton
          label="Отказаться"
          title="Отказаться от предложения?"
          text="Заявка будет закрыта. Если передумаете — можно подать новую."
          confirmLabel="Отказаться"
          onConfirm={() => decline.mutate()}
          loading={decline.isPending}
          variant="default"
          color="red"
        />
      </Group>
    </Stack>
  );
}

function Big({ label, value, accent }: { label: ReactNode; value: string; accent?: boolean }) {
  return (
    <Paper p="sm" radius="md" bg={accent ? 'accent.0' : 'gray.0'}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text size="lg" fw={700}>
        {value}
      </Text>
    </Paper>
  );
}

// ---------- Подписание ----------

export function SignBlock({ app }: { app: Application }) {
  const [code, setCode] = useState('');
  const sign = useSign(app.id);
  return (
    <Stack>
      <Paper p="md" radius="md" bg="gray.0">
        <Text size="sm" c="dimmed">
          Код подтверждения
        </Text>
        <Text size="xl" fw={700} ff="monospace" style={{ letterSpacing: 4 }}>
          {app.signing_code}
        </Text>
        <Text size="xs" c="dimmed">
          Это демо: в настоящем сервисе код пришёл бы в защищённое приложение. Здесь он показан на экране.
        </Text>
      </Paper>
      <Text size="sm">
        Договор: {rub(app.decision?.amount)} на {months(app.decision?.term)}, {rate(app.decision?.rate)}, платёж {rub(app.decision?.monthly_payment)} в месяц.
      </Text>
      <Group align="flex-end">
        <div>
          <Text size="sm" mb={4}>
            Введите код
          </Text>
          <PinInput length={6} type="number" oneTimeCode value={code} onChange={setCode} error={!!sign.error} />
        </div>
        <Button onClick={() => sign.mutate({ code })} disabled={code.length !== 6} loading={sign.isPending}>
          Подписать договор
        </Button>
      </Group>
      {sign.error && <Alert color="red">{errorText(sign.error)}</Alert>}
    </Stack>
  );
}

// ---------- Деньги зачислены ----------

export function DoneBlock({ app }: { app: Application }) {
  return (
    <Stack align="flex-start">
      <Group>
        <ThemeIcon size={48} radius="xl" color="green">
          <IconCircleCheck size={30} />
        </ThemeIcon>
        <div>
          <Text size="xl" fw={700}>
            {rub(app.decision?.amount)}
          </Text>
          <Text c="dimmed">на расчётном счёте {app.company.name}</Text>
        </div>
      </Group>
      <Text size="sm">
        Платёж {rub(app.decision?.monthly_payment)} в месяц, {months(app.decision?.term)}. Первый платёж — примерно через месяц.
      </Text>
      <Button component={Link} to="/" variant="light">
        К моим заявкам
      </Button>
    </Stack>
  );
}

// ---------- Отказ (экран 6) ----------

export function RejectedBlock({ app }: { app: Application }) {
  const clone = useCloneApplication(app.id);
  const navigate = useNavigate();
  const d = app.decision;
  return (
    <Stack>
      {d && d.reasons.length > 0 && (
        <div>
          <Text fw={600} mb={4}>
            Почему
          </Text>
          <List spacing={6} icon={<IconX size={16} color="var(--mantine-color-red-6)" />}>
            {d.reasons.map((r) => (
              <List.Item key={r}>{r}</List.Item>
            ))}
          </List>
        </div>
      )}
      {d && d.advice.length > 0 && (
        <Alert color="blue" variant="light" icon={<IconBulb size={18} />} title="Что можно сделать">
          <List size="sm" spacing={4}>
            {d.advice.map((a) => (
              <List.Item key={a}>{a}</List.Item>
            ))}
          </List>
        </Alert>
      )}
      {clone.error && <Alert color="red">{errorText(clone.error)}</Alert>}
      <Group>
        <Button
          loading={clone.isPending}
          onClick={() => clone.mutate(undefined, { onSuccess: (created) => navigate(`/applications/${created.id}/edit?step=1`) })}
        >
          Подать заново с этими данными
        </Button>
        <Button component={Link} to="/new" variant="default">
          Подобрать другой кредит
        </Button>
      </Group>
    </Stack>
  );
}

// ---------- Документы ----------

const MAX_FILE = 10 * 1024 * 1024;
const ACCEPT = 'application/pdf,image/jpeg,image/png';

function DocumentRow({ app, doc }: { app: Application; doc: Application['documents'][number] }) {
  const upload = useUploadDocument(app.id);
  const [localError, setLocalError] = useState<string | null>(null);
  const uploaded = doc.status === 'uploaded';

  const pick = (file: File | null) => {
    setLocalError(null);
    if (!file) return;
    // Проверяем сразу в браузере, чтобы не ждать ответа сервера (сервер всё равно проверит ещё раз).
    if (!['application/pdf', 'image/jpeg', 'image/png'].includes(file.type)) return setLocalError('Подходят только PDF, JPG или PNG');
    if (file.size > MAX_FILE) return setLocalError('Файл больше 10 МБ — сожмите его или загрузите по частям');
    upload.mutate({ documentRequestId: doc.id, file });
  };

  return (
    <Paper p="md" radius="lg" bg={uploaded ? '#ebf8ef' : 'gray.0'}>
      <Group justify="space-between" wrap="nowrap">
        <Group gap="sm" wrap="nowrap">
          <ThemeIcon size={36} radius="md" color={uploaded ? 'green' : 'gray'} variant={uploaded ? 'filled' : 'light'}>
            {uploaded ? <IconCircleCheck size={20} /> : <IconFileText size={20} />}
          </ThemeIcon>
          <div>
            <Text fw={600} size="sm">
              {doc.doc_type === 'bank_statement' ? <Term k="statement">{doc.title}</Term> : doc.title}
            </Text>
            <Text size="xs" c="dimmed">
              {uploaded ? `Загружен: ${doc.file_name}` : 'PDF, JPG или PNG, до 10 МБ'}
            </Text>
          </div>
        </Group>
        {!uploaded && (
          <FileButton onChange={pick} accept={ACCEPT}>
            {(props) => (
              <Button {...props} leftSection={<IconUpload size={16} />} loading={upload.isPending}>
                Загрузить
              </Button>
            )}
          </FileButton>
        )}
      </Group>
      {(localError || upload.error) && (
        <Text size="sm" c="red" mt="xs">
          {localError ?? errorText(upload.error)}
        </Text>
      )}
    </Paper>
  );
}

export function DocumentsBlock({ app }: { app: Application }) {
  const pending = app.documents.filter((d) => d.status !== 'uploaded');
  const reason = app.decision?.type === 'info' ? app.decision.reasons[0] : null;
  return (
    <Stack gap="sm">
      {reason && (
        <Alert color="blue" variant="light" icon={<IconBulb size={18} />}>
          {reason}
        </Alert>
      )}
      {app.documents.map((doc) => (
        <DocumentRow key={doc.id} app={app} doc={doc} />
      ))}
      {pending.length > 0 && app.documents.length > 1 && (
        <Text size="xs" c="dimmed">
          Осталось загрузить: {pending.length}. Проверка продолжится сама, как только будут все документы.
        </Text>
      )}
    </Stack>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <Title order={4}>{children}</Title>;
}
