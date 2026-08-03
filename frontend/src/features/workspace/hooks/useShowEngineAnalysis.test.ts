import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useShowEngineAnalysis } from './useShowEngineAnalysis';

describe('useShowEngineAnalysis', () => {
  it('starts off with no stored preference', () => {
    const { result } = renderHook(() => useShowEngineAnalysis());
    expect(result.current[0]).toBe(false);
  });

  it('toggles and persists the new value', () => {
    const { result } = renderHook(() => useShowEngineAnalysis());

    act(() => result.current[1]());
    expect(result.current[0]).toBe(true);
    expect(window.localStorage.getItem('grandmate-workspace-show-engine-analysis')).toBe('true');

    act(() => result.current[1]());
    expect(result.current[0]).toBe(false);
  });

  it('picks up a previously stored preference on mount', () => {
    window.localStorage.setItem('grandmate-workspace-show-engine-analysis', 'true');

    const { result } = renderHook(() => useShowEngineAnalysis());

    expect(result.current[0]).toBe(true);
  });
});
