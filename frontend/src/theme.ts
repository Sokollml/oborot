// Визуальный язык: яркий красный акцент, графитовый текст, белые карточки на светло-сером фоне,
// крупные скругления и плотная жирная типографика. Без логотипов и названий реальных банков.
import {
  Badge,
  Button,
  Card,
  Checkbox,
  createTheme,
  Modal,
  NumberInput,
  Paper,
  PasswordInput,
  Select,
  Textarea,
  TextInput,
  Tooltip,
  type MantineColorsTuple,
} from '@mantine/core';

// Основной красный — #EF3124 (индекс 6).
const accent: MantineColorsTuple = [
  '#fff0ee',
  '#ffdcd8',
  '#fdb6ae',
  '#f98d81',
  '#f4675a',
  '#f14b3c',
  '#ef3124',
  '#d5271b',
  '#bd2016',
  '#a3170f',
];

// Нейтральные: фон страницы #F3F4F5, графитовый текст #0B1F35.
const gray: MantineColorsTuple = [
  '#f3f4f5',
  '#ebedef',
  '#dcdfe3',
  '#c6cbd1',
  '#a3abb5',
  '#828b96',
  '#6d7683',
  '#4f5966',
  '#2f3a48',
  '#0b1f35',
];

const inputDefaults = { variant: 'filled', radius: 'md', size: 'md' } as const;

export const theme = createTheme({
  primaryColor: 'accent',
  primaryShade: 6,
  colors: { accent, gray },
  black: '#0b1f35',
  defaultRadius: 'md',
  fontFamily: '"Manrope Variable", Manrope, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  headings: {
    fontFamily: '"Manrope Variable", Manrope, system-ui, sans-serif',
    fontWeight: '800',
    sizes: {
      h1: { fontSize: '40px', lineHeight: '1.15' },
      h2: { fontSize: '30px', lineHeight: '1.2' },
      h3: { fontSize: '22px', lineHeight: '1.25' },
      h4: { fontSize: '18px', lineHeight: '1.3' },
    },
  },
  radius: { xs: '6px', sm: '8px', md: '12px', lg: '16px', xl: '24px' },
  components: {
    Button: Button.extend({ defaultProps: { radius: 'md', fw: 700 } as never }),
    Paper: Paper.extend({ defaultProps: { radius: 'xl' } }),
    Card: Card.extend({ defaultProps: { radius: 'xl' } }),
    Modal: Modal.extend({ defaultProps: { radius: 'xl', overlayProps: { backgroundOpacity: 0.4, blur: 2 } } }),
    Badge: Badge.extend({ defaultProps: { radius: 'sm' } }),
    Tooltip: Tooltip.extend({ defaultProps: { color: 'dark', radius: 'md' } }),
    Checkbox: Checkbox.extend({ defaultProps: { radius: 'sm', size: 'md' } }),
    TextInput: TextInput.extend({ defaultProps: inputDefaults }),
    PasswordInput: PasswordInput.extend({ defaultProps: inputDefaults }),
    NumberInput: NumberInput.extend({ defaultProps: inputDefaults }),
    Select: Select.extend({ defaultProps: inputDefaults }),
    Textarea: Textarea.extend({ defaultProps: inputDefaults }),
  },
});
