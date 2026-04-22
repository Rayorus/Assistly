// ═══════════════════════════════════════════════════════════════
// OverlayOS — AI Assistant Engine
// ═══════════════════════════════════════════════════════════════

const App = (() => {
  // ── State ──────────────────────────────────────────────────
  const state = {
    mode: 'idle',          // idle | listening | processing | responding
    micOn: false,
    eyeOn: false,
    settingsOpen: false,
    messages: [],
    recognition: null,
    synth: window.speechSynthesis,
    interimText: '',
    aiCursor: { x: window.innerWidth / 2, y: window.innerHeight / 2, visible: false, target: null },
    settings: {
      voice: true,
      theme: 'dark',
      speed: 1.0,
      apiKey: '',
      model: 'gpt-4o-mini',
    },
  };

  // ── DOM refs (filled on init) ─────────────────────────────
  let $nav, $micBtn, $eyeBtn, $setBtn, $closeBtn,
      $panel, $chatArea, $emptyState, $msgList, $inputArea, $inputField, $sendBtn,
      $startBtn, $statusDot, $statusText,
      $settingsPanel, $aiCursor, $cursorLabel, $highlight;

  // ── Helpers ───────────────────────────────────────────────
  const qs  = s => document.querySelector(s);
  const qsa = s => document.querySelectorAll(s);
  const el  = (tag, cls, html) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html) e.innerHTML = html;
    return e;
  };

  function setMode(mode) {
    state.mode = mode;
    updateStatusUI();
    document.body.dataset.mode = mode;
  }

  // ── Init ──────────────────────────────────────────────────
  function init() {
    injectExtraDOM();
    cacheDOM();
    bindEvents();
    initSpeech();
    setMode('idle');
    animateEntrance();
  }

  function injectExtraDOM() {
    // AI Cursor overlay
    const cur = el('div', 'ai-cursor');
    cur.id = 'aiCursor';
    cur.innerHTML = `
      <div class="ai-cursor-ring"></div>
      <div class="ai-cursor-dot"></div>
      <div class="ai-cursor-label" id="cursorLabel"></div>`;
    document.body.appendChild(cur);

    // Highlight box
    const hl = el('div', 'ai-highlight');
    hl.id = 'aiHighlight';
    document.body.appendChild(hl);

    // Settings dropdown
    const sp = el('div', 'settings-panel glass-panel');
    sp.id = 'settingsPanel';
    sp.innerHTML = `
      <h3>Settings</h3>
      <label class="s-row">
        <span>Voice Output</span>
        <input type="checkbox" id="sVoice" checked>
      </label>
      <label class="s-row">
        <span>Speech Rate</span>
        <input type="range" id="sSpeed" min="0.5" max="2" step="0.1" value="1">
      </label>
      <label class="s-row">
        <span>API Key</span>
        <input type="password" id="sApiKey" placeholder="sk-..." spellcheck="false">
      </label>
      <label class="s-row">
        <span>Model</span>
        <select id="sModel">
          <option value="gpt-4o-mini">GPT-4o Mini</option>
          <option value="gpt-4o">GPT-4o</option>
          <option value="gpt-4.1-mini">GPT-4.1 Mini</option>
        </select>
      </label>
      <label class="s-row">
        <span>Theme</span>
        <select id="sTheme">
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </select>
      </label>`;
    document.body.appendChild(sp);

    // Message list + input inside aside
    const aside = qs('aside');
    const contentDiv = aside.querySelector('.flex-1');
    contentDiv.id = 'chatArea';

    // Create message container
    const ml = el('div', 'msg-list hidden');
    ml.id = 'msgList';
    contentDiv.insertBefore(ml, contentDiv.firstChild);

    // Wrap empty state
    const es = contentDiv.querySelector('.w-16');
    const esParent = es.parentElement || contentDiv;
    const emptyWrap = el('div', 'empty-state');
    emptyWrap.id = 'emptyState';
    // Move empty-state children
    const emptyKids = [
      contentDiv.querySelector('.w-16'),
      contentDiv.querySelector('h3'),
      contentDiv.querySelector('p'),
    ].filter(Boolean);
    emptyKids.forEach(k => emptyWrap.appendChild(k));
    contentDiv.appendChild(emptyWrap);

    // Text input bar
    const bar = el('div', 'input-bar');
    bar.id = 'inputArea';
    bar.innerHTML = `
      <input type="text" id="inputField" placeholder="Type a message..." autocomplete="off">
      <button id="sendBtn" class="send-btn">
        <span class="material-symbols-outlined" style="font-size:20px">send</span>
      </button>`;
    const bottomDiv = aside.querySelector('.mt-auto');
    bottomDiv.appendChild(bar);

    // Interim text display
    const interim = el('div', 'interim-text hidden');
    interim.id = 'interimText';
    interim.innerHTML = '<span class="pulse-dot"></span><span id="interimContent"></span>';
    contentDiv.appendChild(interim);
  }

  function cacheDOM() {
    $nav          = qs('nav');
    const btns    = $nav.querySelectorAll('button');
    $micBtn       = btns[0];
    $eyeBtn       = btns[1];
    $setBtn       = btns[2];
    $closeBtn     = btns[3];
    $panel        = qs('aside');
    $chatArea     = qs('#chatArea');
    $emptyState   = qs('#emptyState');
    $msgList      = qs('#msgList');
    $inputArea    = qs('#inputArea');
    $inputField   = qs('#inputField');
    $sendBtn      = qs('#sendBtn');
    $startBtn     = $panel.querySelector('.mt-auto button:first-child');
    $statusDot    = $nav.querySelector('.w-2');
    // Get the "Ready to assist" span specifically
    const navSpans = $nav.querySelectorAll('span:not(.material-symbols-outlined)');
    $statusText   = navSpans.length > 1 ? navSpans[1] : navSpans[0];
    $settingsPanel= qs('#settingsPanel');
    $aiCursor     = qs('#aiCursor');
    $cursorLabel  = qs('#cursorLabel');
    $highlight    = qs('#aiHighlight');

    // Add IDs for accessibility
    $micBtn.id  = 'micBtn';
    $eyeBtn.id  = 'eyeBtn';
    $setBtn.id  = 'setBtn';
    $closeBtn.id= 'closeBtn';
  }

  // ── Event Binding ─────────────────────────────────────────
  function bindEvents() {
    $micBtn.addEventListener('click', toggleMic);
    $eyeBtn.addEventListener('click', toggleEye);
    $setBtn.addEventListener('click', toggleSettings);
    $closeBtn.addEventListener('click', closeOverlay);
    $startBtn.addEventListener('click', toggleMic);
    $sendBtn.addEventListener('click', sendText);
    $inputField.addEventListener('keydown', e => { if (e.key === 'Enter') sendText(); });

    // Settings inputs
    document.addEventListener('click', e => {
      if (state.settingsOpen && !$settingsPanel.contains(e.target) && e.target !== $setBtn && !$setBtn.contains(e.target)) {
        toggleSettings();
      }
    });

    qs('#sVoice')?.addEventListener('change', e => { state.settings.voice = e.target.checked; });
    qs('#sSpeed')?.addEventListener('input', e => { state.settings.speed = parseFloat(e.target.value); });
    qs('#sApiKey')?.addEventListener('change', e => { state.settings.apiKey = e.target.value.trim(); });
    qs('#sModel')?.addEventListener('change', e => { state.settings.model = e.target.value; });
    qs('#sTheme')?.addEventListener('change', e => {
      state.settings.theme = e.target.value;
      document.documentElement.className = e.target.value === 'light' ? '' : 'dark';
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'm' || e.key === 'M') toggleMic();
      if (e.key === 'e' || e.key === 'E') toggleEye();
      if (e.key === 'Escape') {
        if (state.settingsOpen) toggleSettings();
        else if (state.micOn) toggleMic();
      }
    });
  }

  // ── Mic / Speech Recognition ──────────────────────────────
  function initSpeech() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { console.warn('Speech Recognition not supported'); return; }
    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = 'en-US';

    rec.onresult = e => {
      let interim = '', final_ = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) final_ += t;
        else interim += t;
      }
      if (interim) showInterim(interim);
      if (final_) {
        hideInterim();
        addMessage('user', final_.trim());
        processUserInput(final_.trim());
      }
    };
    rec.onerror = e => {
      console.warn('Speech error:', e.error);
      if (e.error !== 'no-speech' && e.error !== 'aborted') {
        setMode('idle');
        state.micOn = false;
        updateMicUI();
      }
    };
    rec.onend = () => {
      if (state.micOn) {
        try { rec.start(); } catch(e) {}
      }
    };
    state.recognition = rec;
  }

  function toggleMic() {
    state.micOn = !state.micOn;
    if (state.micOn) {
      setMode('listening');
      try { state.recognition?.start(); } catch(e) {}
      showConversation();
    } else {
      setMode('idle');
      state.recognition?.stop();
      hideInterim();
    }
    updateMicUI();
  }

  function updateMicUI() {
    const icon = $micBtn.querySelector('.material-symbols-outlined');
    if (state.micOn) {
      $micBtn.classList.add('mic-active');
      icon.textContent = 'mic';
      $startBtn.innerHTML = `<span class="material-symbols-outlined text-[20px]">stop</span> Stop Listening`;
      $startBtn.classList.add('!bg-red-500', 'hover:!bg-red-600');
      $startBtn.classList.remove('shadow-[0_4px_14px_rgba(0,122,255,0.4)]');
      $startBtn.classList.add('shadow-[0_4px_14px_rgba(239,68,68,0.4)]');
    } else {
      $micBtn.classList.remove('mic-active');
      icon.textContent = 'mic';
      $startBtn.innerHTML = `<span class="material-symbols-outlined text-[20px]">mic</span> Start Talking`;
      $startBtn.classList.remove('!bg-red-500', 'hover:!bg-red-600', 'shadow-[0_4px_14px_rgba(239,68,68,0.4)]');
      $startBtn.classList.add('shadow-[0_4px_14px_rgba(0,122,255,0.4)]');
    }
  }

  // ── Eye / Screen Awareness ────────────────────────────────
  function toggleEye() {
    state.eyeOn = !state.eyeOn;
    const icon = $eyeBtn.querySelector('.material-symbols-outlined');
    if (state.eyeOn) {
      $eyeBtn.classList.add('eye-active');
      icon.textContent = 'visibility';
      showToast('Screen awareness enabled');
    } else {
      $eyeBtn.classList.remove('eye-active');
      icon.textContent = 'visibility_off';
      hideAICursor();
      showToast('Screen awareness disabled');
    }
  }

  // ── Settings ──────────────────────────────────────────────
  function toggleSettings() {
    state.settingsOpen = !state.settingsOpen;
    $settingsPanel.classList.toggle('open', state.settingsOpen);
    $setBtn.classList.toggle('settings-active', state.settingsOpen);
  }

  // ── Close ─────────────────────────────────────────────────
  function closeOverlay() {
    $nav.style.animation = 'fadeSlideUp .3s ease reverse forwards';
    $panel.style.animation = 'fadeSlideRight .3s ease forwards';
    setTimeout(() => {
      $nav.style.display = 'none';
      $panel.style.display = 'none';
    }, 300);
  }

  // ── Conversation ──────────────────────────────────────────
  function showConversation() {
    $emptyState.classList.add('hidden');
    $msgList.classList.remove('hidden');
    // Switch layout from centered empty-state to top-aligned messages
    $chatArea.classList.remove('items-center', 'justify-center', 'text-center');
    $chatArea.classList.add('items-stretch', 'justify-start');
    $chatArea.style.overflow = 'hidden';
  }

  function addMessage(role, text) {
    showConversation();
    state.messages.push({ role, text, time: new Date() });
    const msg = el('div', `msg msg-${role}`);
    const avatar = role === 'user'
      ? '<div class="msg-avatar user-av">You</div>'
      : '<div class="msg-avatar ai-av"><span class="material-symbols-outlined" style="font-size:16px">smart_toy</span></div>';
    msg.innerHTML = `${avatar}<div class="msg-bubble ${role}-bubble"><p></p><span class="msg-time">${new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span></div>`;
    // Typewriter for AI
    const p = msg.querySelector('p');
    if (role === 'assistant') {
      typeWriter(p, text, 18);
    } else {
      p.textContent = text;
    }
    $msgList.appendChild(msg);
    requestAnimationFrame(() => {
      msg.classList.add('msg-enter');
      $msgList.scrollTop = $msgList.scrollHeight;
    });
  }

  function typeWriter(el, text, speed) {
    let i = 0;
    const iv = setInterval(() => {
      el.textContent += text[i];
      i++;
      $msgList.scrollTop = $msgList.scrollHeight;
      if (i >= text.length) clearInterval(iv);
    }, speed);
  }

  function showInterim(text) {
    const it = qs('#interimText');
    const ic = qs('#interimContent');
    it.classList.remove('hidden');
    ic.textContent = text;
    $chatArea.scrollTop = $chatArea.scrollHeight;
  }

  function hideInterim() {
    qs('#interimText')?.classList.add('hidden');
  }

  // ── Process Input ─────────────────────────────────────────
  function sendText() {
    const text = $inputField.value.trim();
    if (!text) return;
    $inputField.value = '';
    addMessage('user', text);
    processUserInput(text);
  }

  async function processUserInput(text) {
    setMode('processing');
    const lower = text.toLowerCase();

    // Build context
    let context = '';
    if (state.eyeOn) {
      context = '\n[Screen awareness is active — user can see highlighted elements]';
    }

    try {
      let reply;
      if (state.settings.apiKey) {
        reply = await callOpenAI(text, context);
      } else {
        reply = getLocalResponse(lower);
      }

      setMode('responding');
      addMessage('assistant', reply.text);

      // AI Cursor guidance
      if (reply.cursor && state.eyeOn) {
        showAICursor(reply.cursor.x, reply.cursor.y, reply.cursor.label);
      }

      // TTS
      if (state.settings.voice) {
        speak(reply.text);
      }

      setTimeout(() => {
        if (state.micOn) setMode('listening');
        else setMode('idle');
      }, reply.text.length * 20 + 1000);

    } catch (err) {
      addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
      setMode(state.micOn ? 'listening' : 'idle');
    }
  }

  // ── OpenAI API ────────────────────────────────────────────
  async function callOpenAI(text, context) {
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.settings.apiKey}`,
      },
      body: JSON.stringify({
        model: state.settings.model,
        messages: [
          { role: 'system', content: `You are OverlayOS, a helpful desktop AI assistant. You guide users visually on their screen. Be concise and friendly.${context}` },
          ...state.messages.slice(-6).map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.text })),
          { role: 'user', content: text },
        ],
        max_tokens: 200,
      }),
    });
    const data = await res.json();
    return { text: data.choices?.[0]?.message?.content || 'I couldn\'t process that.', cursor: null };
  }

  // ── Local Fallback AI ─────────────────────────────────────
  function getLocalResponse(input) {
    const responses = [
      { match: /hello|hi|hey/, text: "Hey there! I'm your AI assistant. How can I help you today?", cursor: null },
      { match: /open.*(browser|chrome|firefox)/, text: "I'd move my cursor to your browser icon on the taskbar. Look for the highlighted area!", cursor: { x: window.innerWidth / 2, y: window.innerHeight - 30, label: 'Click here to open browser' } },
      { match: /open.*(settings|preference)/, text: "Let me guide you to the Settings. I'll highlight where to click.", cursor: { x: 50, y: window.innerHeight - 30, label: 'Open Start Menu → Settings' } },
      { match: /search|find|look/, text: "I'll highlight the search bar for you. Click where my cursor is pointing!", cursor: { x: window.innerWidth / 4, y: 20, label: 'Click here to search' } },
      { match: /type|write|enter/, text: "Click on the text field I'm highlighting, then type your message.", cursor: { x: window.innerWidth / 2, y: window.innerHeight / 2, label: 'Type here' } },
      { match: /help|what can you/, text: "I can guide you on screen! Try saying: 'Open browser', 'Search for something', or 'Help me with settings'. When screen awareness is on, I'll visually point to elements.", cursor: null },
      { match: /thank|thanks/, text: "You're welcome! Let me know if you need anything else.", cursor: null },
      { match: /stop|quit|exit/, text: "Alright, I'll stand by. Just call me when you need help!", cursor: null },
      { match: /screen|see|what.*(see|show)/, text: "With screen awareness enabled, I can analyze what's on your screen and guide you to the right buttons and menus. Try enabling the eye icon!", cursor: null },
      { match: /click|button|press/, text: "I'll show you exactly where to click. Follow my glowing cursor!", cursor: { x: window.innerWidth / 3, y: window.innerHeight / 3, label: 'Click here' } },
    ];
    const found = responses.find(r => r.match.test(input));
    if (found) return found;
    return {
      text: `I heard: "${input}". I can help you navigate your screen, open apps, find settings, and more. Try asking me to open something or guide you!`,
      cursor: null
    };
  }

  // ── TTS ───────────────────────────────────────────────────
  function speak(text) {
    state.synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = state.settings.speed;
    u.pitch = 1;
    u.volume = 0.8;
    const voices = state.synth.getVoices();
    const preferred = voices.find(v => v.name.includes('Google') || v.name.includes('Samantha')) || voices[0];
    if (preferred) u.voice = preferred;
    state.synth.speak(u);
  }

  // ── AI Cursor ─────────────────────────────────────────────
  function showAICursor(x, y, label) {
    state.aiCursor.visible = true;
    $aiCursor.classList.add('visible');
    $cursorLabel.textContent = label || '';

    // Animate to position
    const startX = state.aiCursor.x, startY = state.aiCursor.y;
    const duration = 800;
    const startTime = performance.now();

    function animate(now) {
      const elapsed = now - startTime;
      const t = Math.min(elapsed / duration, 1);
      const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

      const cx = startX + (x - startX) * ease;
      const cy = startY + (y - startY) * ease;
      $aiCursor.style.transform = `translate(${cx}px, ${cy}px)`;
      state.aiCursor.x = cx;
      state.aiCursor.y = cy;

      if (t < 1) requestAnimationFrame(animate);
      else {
        // Show highlight at destination
        showHighlight(x - 40, y - 20, 200, 50);
      }
    }
    requestAnimationFrame(animate);

    // Auto-hide after 5 seconds
    setTimeout(hideAICursor, 5000);
  }

  function hideAICursor() {
    state.aiCursor.visible = false;
    $aiCursor.classList.remove('visible');
    $highlight.classList.remove('visible');
  }

  function showHighlight(x, y, w, h) {
    $highlight.style.left = x + 'px';
    $highlight.style.top = y + 'px';
    $highlight.style.width = w + 'px';
    $highlight.style.height = h + 'px';
    $highlight.classList.add('visible');
  }

  // ── Status UI ─────────────────────────────────────────────
  function updateStatusUI() {
    const map = {
      idle:       { color: 'bg-gray-400',   glow: 'rgba(156,163,175,0.5)', text: 'Ready to assist' },
      listening:  { color: 'bg-green-500',   glow: 'rgba(34,197,94,0.6)',   text: 'Listening...' },
      processing: { color: 'bg-yellow-400',  glow: 'rgba(250,204,21,0.6)',  text: 'Processing...' },
      responding: { color: 'bg-blue-500',    glow: 'rgba(59,130,246,0.6)',  text: 'Speaking...' },
    };
    const s = map[state.mode] || map.idle;
    $statusDot.className = `w-2 h-2 rounded-full ${s.color}`;
    $statusDot.style.boxShadow = `0 0 8px ${s.glow}`;
    if ($statusText) $statusText.textContent = s.text;

    // Pulse animation for listening
    if (state.mode === 'listening') {
      $statusDot.classList.add('status-pulse');
    } else {
      $statusDot.classList.remove('status-pulse');
    }
  }

  // ── Toast ─────────────────────────────────────────────────
  function showToast(msg) {
    const t = el('div', 'toast', msg);
    document.body.appendChild(t);
    requestAnimationFrame(() => t.classList.add('show'));
    setTimeout(() => {
      t.classList.remove('show');
      setTimeout(() => t.remove(), 300);
    }, 2000);
  }

  // ── Entrance Animation ────────────────────────────────────
  function animateEntrance() {
    $nav.style.animation = 'fadeSlideDown .5s cubic-bezier(.16,1,.3,1) forwards';
    $panel.style.animation = 'fadeSlideLeft .6s cubic-bezier(.16,1,.3,1) .15s both';
  }

  // Public API
  return { init };
})();

document.addEventListener('DOMContentLoaded', App.init);
