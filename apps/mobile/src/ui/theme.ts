import { Platform } from 'react-native';
import tokens from '../../../../assets/design-tokens.json';

export const colors = tokens.colors;
export const radii = tokens.radii;
export const space = (step: 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7): number => tokens.spacing[step] ?? 8;
export const touchMin = Platform.OS === 'ios' ? tokens.touch_min.ios : tokens.touch_min.android;

type TypeKey = 'h1' | 'h2' | 'body' | 'label' | 'caption';
export function type(key: TypeKey): { fontSize: number; lineHeight: number; fontWeight: '400' | '500' | '600' | '700' } {
  const t = tokens.typography[key];
  const w = t.weight >= 650 ? '700' : t.weight >= 600 ? '600' : t.weight >= 500 ? '500' : '400';
  return { fontSize: t.size, lineHeight: t.line_height, fontWeight: w };
}
