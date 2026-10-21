// Мобильная вёрстка: всё, что уже 768 px (брейкпоинт sm в Mantine), считаем телефоном.
import { useMediaQuery } from '@mantine/hooks';

export function useIsMobile(): boolean {
  return useMediaQuery('(max-width: 47.99em)') ?? false;
}
