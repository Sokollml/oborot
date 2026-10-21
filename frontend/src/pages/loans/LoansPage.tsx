// «Мои кредиты»: выданные кредиты с ближайшим платежом и графиком.
import { Group, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { Link } from 'react-router-dom';

import { useMyLoans } from '../../api/queries';
import { LoanDetailsButtons, nextPaymentDate } from '../../components/LoanDetails';
import { EmptyState, ErrorState, Loading } from '../../components/StateViews';
import { months, rate, rub } from '../../lib/format';

export function LoansPage() {
  const { data, isPending, error, refetch } = useMyLoans();
  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Мои кредиты</Title>
        <Text c="dimmed">Платежи списываются со счёта автоматически. Погасить досрочно можно в любой день без комиссии.</Text>
      </div>
      {isPending && <Loading />}
      {error && <ErrorState error={error} onRetry={refetch} />}
      {data && data.length === 0 && (
        <EmptyState title="Кредитов пока нет" text="Когда деньги по заявке будут зачислены, кредит появится здесь — с графиком и ближайшим платежом." />
      )}
      {data?.map((loan) => (
        <Paper key={loan.id} p="xl">
          <Group justify="space-between" align="flex-start" mb="md">
            <div>
              <Title order={3}>{loan.product.name}</Title>
              <Text c="dimmed" size="sm">
                {loan.company.name} · договор по заявке{' '}
                <Text span component={Link} to={`/applications/${loan.id}`} c="accent.6" inherit>
                  №{loan.id}
                </Text>
              </Text>
            </div>
            <Text fz={28} fw={800}>
              {rub(loan.decision?.amount)}
            </Text>
          </Group>
          <SimpleGrid cols={4} spacing="sm" mb="md">
            <Cell label="Ближайший платёж" value={nextPaymentDate(loan.updated_at)} />
            <Cell label="Сумма платежа" value={rub(loan.decision?.monthly_payment)} accent />
            <Cell label="Срок" value={months(loan.decision?.term)} />
            <Cell label="Ставка" value={rate(loan.decision?.rate)} />
          </SimpleGrid>
          <LoanDetailsButtons app={loan} start={new Date(loan.updated_at)} />
        </Paper>
      ))}
    </Stack>
  );
}

function Cell({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <Paper p="sm" radius="lg" bg={accent ? 'accent.0' : 'gray.0'}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700}>{value}</Text>
    </Paper>
  );
}
