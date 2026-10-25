// Знак «Оборот»: замкнутое кольцо «О» — деньги в обороте — и стрелка роста внутри.
// Тот же рисунок лежит в public/favicon.svg (значок вкладки) и docs/logo.svg (README).
import { Group, Text } from '@mantine/core';

export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Оборот" style={{ flex: 'none', display: 'block' }}>
      <rect width="64" height="64" rx="16" fill="var(--mantine-color-accent-6)" />
      <circle cx="32" cy="32" r="17" fill="none" stroke="#fff" strokeWidth="6" />
      <path d="M32 41V24M25.5 30L32 23.5L38.5 30" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Знак + название. caption — подпись серым рядом (скрывается на телефоне). */
export function Logo({ size = 34, caption, textSize = 'xl' }: { size?: number; caption?: string; textSize?: string }) {
  return (
    <Group gap={10} wrap="nowrap">
      <LogoMark size={size} />
      <Text fw={800} size={textSize} style={{ letterSpacing: '-0.02em' }} lh={1}>
        Оборот
      </Text>
      {caption && (
        <Text size="sm" c="dimmed" visibleFrom="sm">
          {caption}
        </Text>
      )}
    </Group>
  );
}
