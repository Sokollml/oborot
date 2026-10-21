import { createTheme, type MantineColorsTuple } from '@mantine/core';

// Сдержанный красный акцент. Свой оттенок, без фирменных цветов какого-либо банка.
const accent: MantineColorsTuple = [
  '#fff0f0',
  '#ffdede',
  '#f9bbbb',
  '#f39494',
  '#ee7373',
  '#eb5d5d',
  '#e94f4f',
  '#cf4041',
  '#b93739',
  '#a22b2f',
];

export const theme = createTheme({
  primaryColor: 'accent',
  colors: { accent },
  defaultRadius: 'md',
  fontFamily: 'Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
});
