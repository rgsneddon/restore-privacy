/** Every network action is a confirmable block (tab click, keystroke, …). */

export function createActionChain() {
  const blocks = [];
  let seq = 0;

  function record(kind, detail, now = new Date()) {
    seq += 1;
    const block = {
      id: `act-${seq}`,
      kind: String(kind || 'other'),
      detail: String(detail ?? ''),
      index: seq,
      timestamp: now.toISOString(),
    };
    blocks.push(block);
    return block;
  }

  function recordTabClick(tab, now) {
    return record('tab_click', tab, now);
  }

  function recordKeystroke(key, now) {
    return record('keystroke', key, now);
  }

  function confirm(id) {
    const needle = String(id ?? '').trim();
    if (!needle) {
      return { id: '', status: 'rejected', reason: 'missing_id', confirmed: false };
    }
    const block = blocks.find((b) => b.id === needle || String(b.index) === needle);
    if (!block) {
      return { id: needle, status: 'not_found', reason: 'unknown_block', confirmed: false };
    }
    return { id: needle, status: 'confirmed', block, confirmed: true };
  }

  return {
    record,
    recordTabClick,
    recordKeystroke,
    confirm,
    get blocks() {
      return blocks.slice();
    },
    get height() {
      return blocks.length;
    },
  };
}

export const actionChain = createActionChain();
