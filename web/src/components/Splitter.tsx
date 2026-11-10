import { useRef } from 'react';

/** A draggable border between two panels. `dir` is the axis the border moves along; `onDrag`
 *  receives the pointer position in px (clientX or clientY). Double-click resets. */
export default function Splitter({ dir, onDrag, onReset, label }: { dir: 'x' | 'y'; onDrag: (pos: number) => void; onReset?: () => void; label: string }) {
  const active = useRef(false);
  return (
    <div className={`splitter ${dir}`} role="separator" aria-label={label} aria-orientation={dir === 'x' ? 'vertical' : 'horizontal'} title={`${label} — drag to resize, double-click to reset`}
      data-testid={`split-${label.replace(/\s+/g, '-').toLowerCase()}`}
      onPointerDown={(e) => { active.current = true; e.currentTarget.setPointerCapture(e.pointerId); document.body.classList.add(dir === 'x' ? 'dragging-x' : 'dragging-y'); e.preventDefault(); }}
      onPointerMove={(e) => { if (active.current) onDrag(dir === 'x' ? e.clientX : e.clientY); }}
      onPointerUp={(e) => { active.current = false; try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* already released */ } document.body.classList.remove('dragging-x', 'dragging-y'); }}
      onPointerCancel={() => { active.current = false; document.body.classList.remove('dragging-x', 'dragging-y'); }}
      onDoubleClick={onReset} />
  );
}
