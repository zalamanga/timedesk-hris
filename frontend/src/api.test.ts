import { describe, expect, it } from 'vitest';
import { dateLabel, duration, localInput, wib } from './api';

describe('WIB display helpers',()=>{
  it('formats elapsed duration without wrapping hours',()=>{expect(duration(90061)).toBe('25:01:01');expect(duration(-1)).toBe('00:00:00');});
  it('converts UTC to Jakarta input',()=>{expect(localInput('2026-10-28T17:30:00Z')).toBe('2026-10-29T00:30');});
  it('shows the actual local date across midnight',()=>{expect(wib('2026-10-28T17:30:00Z')).toContain('29');expect(wib('2026-10-28T17:30:00Z')).toContain('00.30');});
  it('builds local day labels without UTC date drift',()=>{expect(dateLabel('2026-10-29')).toContain('29');});
});
