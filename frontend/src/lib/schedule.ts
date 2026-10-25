// График платежей равными частями (аннуитет). Считается на клиенте по условиям решения:
// каждый месяц платёж одинаковый, внутри него доля процентов уменьшается, а доля основного долга растёт.

export type ScheduleRow = { n: number; date: Date; payment: number; principal: number; interest: number; balance: number };

export function buildSchedule(amount: number, annualRatePct: number, months: number, start: Date): ScheduleRow[] {
  const i = annualRatePct / 100 / 12;
  const payment = i === 0 ? amount / months : (amount * i) / (1 - (1 + i) ** -months);
  const rows: ScheduleRow[] = [];
  let balance = amount;
  for (let n = 1; n <= months; n++) {
    const interest = balance * i;
    // В последний месяц гасим остаток целиком, чтобы не осталось копеек от округления.
    const principal = n === months ? balance : payment - interest;
    balance -= principal;
    const date = new Date(start);
    date.setMonth(start.getMonth() + n);
    rows.push({ n, date, payment: Math.round(principal + interest), principal: Math.round(principal), interest: Math.round(interest), balance: Math.max(0, Math.round(balance)) });
  }
  return rows;
}

export const totalInterest = (rows: ScheduleRow[]) => rows.reduce((sum, r) => sum + r.interest, 0);

// ---------- Досрочное погашение ----------
// Клиент вносит дополнительную сумму в счёт основного долга и выбирает, что уменьшить:
// платёж (срок прежний) или срок (платёж прежний). Экономия — проценты, которые больше не начислятся.

export type EarlyMode = 'payment' | 'term';

export type EarlyRepayment = {
  balance: number; // основной долг сейчас
  monthsLeft: number;
  paymentNow: number;
  closes: boolean; // сумма покрывает весь долг — кредит закрывается
  newPayment: number;
  newMonths: number;
  saving: number; // сколько процентов не придётся платить
};

export function earlyRepayment(
  amount: number,
  annualRatePct: number,
  months: number,
  start: Date,
  now: Date,
  extra: number,
  mode: EarlyMode,
): EarlyRepayment {
  const rows = buildSchedule(amount, annualRatePct, months, start);
  const paid = rows.filter((r) => r.date <= now).length;
  const balance = paid > 0 ? rows[paid - 1].balance : amount;
  const left = rows.slice(paid);
  const interestBefore = totalInterest(left);
  const paymentNow = rows[0]?.payment ?? 0;
  const rest = balance - extra;

  if (rest <= 0 || left.length === 0) {
    return { balance, monthsLeft: left.length, paymentNow, closes: true, newPayment: 0, newMonths: 0, saving: interestBefore };
  }
  if (mode === 'term') {
    // Платёж прежний — гасим остаток, пока он не кончится; последний платёж выходит меньше.
    const i = annualRatePct / 100 / 12;
    let debt = rest;
    let interest = 0;
    let n = 0;
    while (debt > 0 && n < left.length) {
      const pct = debt * i;
      interest += pct;
      debt -= paymentNow - pct;
      n++;
    }
    return { balance, monthsLeft: left.length, paymentNow, closes: false, newPayment: paymentNow, newMonths: n, saving: Math.max(0, Math.round(interestBefore - interest)) };
  }
  const after = buildSchedule(rest, annualRatePct, left.length, now);
  return {
    balance,
    monthsLeft: left.length,
    paymentNow,
    closes: false,
    newPayment: after[0]?.payment ?? 0,
    newMonths: left.length,
    saving: Math.max(0, interestBefore - totalInterest(after)),
  };
}
