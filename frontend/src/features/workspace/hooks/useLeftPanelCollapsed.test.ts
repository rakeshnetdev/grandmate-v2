import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useLeftPanelCollapsed } from './useLeftPanelCollapsed';

describe('useLeftPanelCollapsed', () => {
  it('starts expanded with no stored preference', () => {
    const { result } = renderHook(() => useLeftPanelCollapsed());
    expect(result.current[0]).toBe(false);
  });

  it('toggles and persists the new value', () => {
    const { result } = renderHook(() => useLeftPanelCollapsed());

    act(() => result.current[1]());
    expect(result.current[0]).toBe(true);
    expect(window.localStorage.getItem('grandmate-workspace-left-collapsed')).toBe('true');

    act(() => result.current[1]());
    expect(result.current[0]).toBe(false);
  });

  it('picks up a previously stored collapsed preference on mount', () => {
    window.localStorage.setItem('grandmate-workspace-left-collapsed', 'true');

    const { result } = renderHook(() => useLeftPanelCollapsed());

    expect(result.current[0]).toBe(true);
  });
});
