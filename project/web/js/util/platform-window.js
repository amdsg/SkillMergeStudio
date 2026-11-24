export const ROW_HEIGHT = 44;
export const BUFFER = 4;

export function windowSlice(total, scrollTop, height, rowHeight = ROW_HEIGHT, buffer = BUFFER) {
  const start = Math.min(total, Math.max(0, Math.floor(scrollTop / rowHeight) - buffer));
  const visible = Math.ceil(height / rowHeight) + buffer * 2;
  const end = Math.min(total, start + visible);
  return { start, end, offset: start * rowHeight, totalHeight: total * rowHeight, domCount: Math.max(0, end - start) };
}