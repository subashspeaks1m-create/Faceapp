// Candidate/committed edit state. The candidate is what the sliders change; it
// never becomes part of history until Apply. Export reads the committed entry.

import { type Adjustments, IDENTITY, normalizeAdjustments, sameAdjustments } from './model.ts';

export const MAX_HISTORY = 100;

export interface EditorState {
  readonly history: readonly Adjustments[]; // history[0] is always the unedited source
  readonly index: number;
  readonly candidate: Adjustments;
  readonly candidateRevision: number;
}

export type EditorAction =
  | { readonly type: 'edit'; readonly patch: Partial<Adjustments> }
  | { readonly type: 'apply' }
  | { readonly type: 'discard' }
  | { readonly type: 'undo' }
  | { readonly type: 'redo' }
  | { readonly type: 'reset' };

export function initialEditorState(): EditorState {
  return { history: [IDENTITY], index: 0, candidate: IDENTITY, candidateRevision: 0 };
}

export function committed(state: EditorState): Adjustments {
  const entry = state.history[state.index];
  if (entry === undefined) throw new Error('history index out of range');
  return entry;
}

export function isDirty(state: EditorState): boolean {
  return !sameAdjustments(state.candidate, committed(state));
}

export const canUndo = (s: EditorState): boolean => isDirty(s) || s.index > 0;
export const canRedo = (s: EditorState): boolean => !isDirty(s) && s.index < s.history.length - 1;

function withCandidate(state: EditorState, candidate: Adjustments): EditorState {
  return { ...state, candidate, candidateRevision: state.candidateRevision + 1 };
}

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case 'edit':
      return withCandidate(state, normalizeAdjustments({ ...state.candidate, ...action.patch }));
    case 'reset':
      return withCandidate(state, IDENTITY);
    case 'discard':
      return isDirty(state) ? withCandidate(state, committed(state)) : state;
    case 'apply': {
      if (!isDirty(state)) return state;
      let history = [...state.history.slice(0, state.index + 1), state.candidate];
      if (history.length > MAX_HISTORY) history = [history[0] ?? IDENTITY, ...history.slice(history.length - MAX_HISTORY + 1)];
      return { ...state, history, index: history.length - 1 };
    }
    case 'undo': {
      // With an unapplied candidate, Undo only drops the candidate.
      if (isDirty(state)) return withCandidate(state, committed(state));
      if (state.index === 0) return state;
      const index = state.index - 1;
      return withCandidate({ ...state, index }, state.history[index] ?? IDENTITY);
    }
    case 'redo': {
      if (!canRedo(state)) return state;
      const index = state.index + 1;
      return withCandidate({ ...state, index }, state.history[index] ?? IDENTITY);
    }
  }
}
