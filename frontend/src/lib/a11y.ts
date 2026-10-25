// Строка таблицы или карточка, которая открывается по клику, должна открываться и с клавиатуры:
// Tab — фокус, Enter или пробел — открыть. Рамка фокуса — в global.css ([data-clickable]).
import type { KeyboardEvent } from 'react';

export function clickable(onActivate: () => void, label?: string) {
  return {
    role: 'button',
    tabIndex: 0,
    'aria-label': label,
    'data-clickable': true,
    style: { cursor: 'pointer' },
    onClick: onActivate,
    onKeyDown: (e: KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onActivate();
      }
    },
  } as const;
}
