// EVOL Bottom Bar Injector
// Injects 🧬 EVOL button + manual phase trigger popover into the chat bottom actions bar

const EVOL_BUTTON_CLASS = 'evol-bottom-btn-injected';

const PHASES = [
  { id: 'absorb', label: '📥 Absorb' },
  { id: 'reflect', label: '🪞 Reflect' },
  { id: 'speak', label: '🗣️ Express' },
  { id: 'explore', label: '🌐 Explore' },
  { id: 'memorize', label: '💾 Memorize' },
  { id: 'cycle', label: '🧬 Full Cycle', highlight: true },
];

function buildPopover() {
  const div = document.createElement('div');
  div.className = 'evol-popover';
  div.innerHTML = `
    <div class="evol-popover-header">
      <span>🧬 Manual Phase Trigger</span>
      <button class="evol-popover-close" title="Close">✕</button>
    </div>
    <div class="evol-phase-buttons">
      ${PHASES.map(p => {
        const cls = p.highlight ? 'evol-phase-btn full-cycle' : 'evol-phase-btn';
        return `<button class="${cls}" data-phase="${p.id}">${p.label}</button>`;
      }).join('')}
    </div>
    <div style="color:#666;font-size:9px;margin-top:8px;">
      Click a phase to run it — results appear in chat
    </div>
  `;

  div.querySelector('.evol-popover-close').addEventListener('click', () => div.remove());

  div.querySelectorAll('.evol-phase-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const phase = btn.dataset.phase;
      div.remove();
      const command = '/evol_' + phase;
      try {
        const store = Alpine.store('chatInput');
        if (store) {
          store.message = command;
          store.adjustTextareaHeight();
          store.sendMessage();
        }
      } catch(e) {
        console.error('EVOL: failed to send phase command', e);
      }
    });
  });

  // Click outside to close
  document.addEventListener('click', function closePopover(e) {
    if (!div.contains(e.target) && !e.target.closest('.' + EVOL_BUTTON_CLASS)) {
      div.remove();
      document.removeEventListener('click', closePopover);
    }
  });

  return div;
}

function buildButton() {
  const wrapper = document.createElement('span');
  wrapper.className = 'evol-bottom-wrapper';
  wrapper.style.cssText = 'position:relative;display:inline-flex;align-items:center;';

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'text-button ' + EVOL_BUTTON_CLASS;
  btn.style.cssText = `
    display:inline-flex;align-items:center;gap:4px;padding:2px 10px;
    background:linear-gradient(135deg,#7C4DFF,#E040FB);
    color:white;border:none;border-radius:12px;
    font-size:0.6rem;font-weight:bold;cursor:pointer;
    opacity:0.9;transition:opacity 0.2s;
  `;
  btn.innerHTML = '<span style="font-size:14px;">🧬</span><span>EVOL</span>';
  btn.addEventListener('mouseenter', () => { btn.style.opacity = '1'; });
  btn.addEventListener('mouseleave', () => { btn.style.opacity = '0.9'; });

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    // Remove any existing popover
    document.querySelectorAll('.evol-popover').forEach(p => p.remove());
    // Create and position popover
    const popover = buildPopover();
    popover.style.cssText = `
      position:absolute;bottom:calc(100% + 8px);right:0;
      background:#1a1a2e;border:1px solid #7C4DFF;border-radius:12px;
      padding:12px;min-width:300px;max-width:440px;
      box-shadow:0 4px 24px rgba(124,77,255,0.35);z-index:9999;
    `;
    wrapper.appendChild(popover);
  });

  wrapper.appendChild(btn);
  return wrapper;
}

function injectButton(container) {
  if (!(container instanceof HTMLElement)) return;
  if (container.querySelector('.' + EVOL_BUTTON_CLASS)) return;
  container.appendChild(buildButton());
}

function scan(root = document) {
  for (const bar of root.querySelectorAll('.chat-bottom-actions-bar')) {
    injectButton(bar);
  }
}

export default async function initEvolBottomBar() {
  scan();

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (!(node instanceof Element)) continue;
        if (node.matches?.('.chat-bottom-actions-bar')) {
          injectButton(node);
          continue;
        }
        if (node.querySelectorAll) {
          scan(node);
        }
      }
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });
}
