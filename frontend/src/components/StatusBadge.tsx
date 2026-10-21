import { Badge } from '@mantine/core';

import type { AppStatus } from '../api/types';
import { STATUS_COLOR } from '../lib/statuses';

export function StatusBadge({ status, label }: { status: AppStatus; label: string }) {
  return (
    <Badge color={STATUS_COLOR[status]} variant="light" size="lg" radius="sm" tt="none">
      {label}
    </Badge>
  );
}
