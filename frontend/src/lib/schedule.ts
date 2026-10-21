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
