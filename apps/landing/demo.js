/* ===========================================================
   Grasp — streaming agent demo engine
   Plays pre-programmed learning sessions inside a device frame.
   =========================================================== */
(function () {
  const device   = document.getElementById('device');
  const log       = document.getElementById('chatlog');
  const inputEl   = document.getElementById('inputfield');
  const devToggle = document.getElementById('devtoggle');
  const scChips   = document.getElementById('scenarios');
  if (!log) return;

  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let lang = 'ru';
  let token = 0;            // run token — bumps cancel running streams
  let current = 'codebase';
  const ORDER = ['codebase', 'youtube', 'topic', 'review'];

  /* ---------- helpers ---------- */
  const T = (ru, en) => (lang === 'en' ? en : ru);
  const sleep = (ms, my) => new Promise((res, rej) => {
    setTimeout(() => (my === token ? res() : rej('x')), reduce ? Math.min(ms, 60) : ms);
  });
  const guard = (my) => { if (my !== token) throw 'x'; };
  const bottom = () => { log.scrollTop = log.scrollHeight; };
  function el(tag, cls, html) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }
  function avatar() {
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="rgb(var(--accent))" stroke-width="2.6"/><circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))"/></svg>`;
  }

  /* ---------- primitive stream ops ---------- */
  async function typeInput(text, my) {
    inputEl.classList.remove('placeholder');
    inputEl.textContent = '';
    const caret = el('span', 'caret');
    inputEl.appendChild(caret);
    for (let i = 0; i < text.length; i++) {
      guard(my);
      caret.insertAdjacentText('beforebegin', text[i]);
      await sleep(16 + Math.random() * 26, my);
    }
    await sleep(420, my);
    guard(my);
    caret.remove();
  }

  function userBubble(text, file) {
    const row = el('div', 'msg user');
    const wrap = el('div', '', '');
    wrap.style.maxWidth = '85%';
    if (file) {
      wrap.appendChild(el('div', 'filechip',
        `<span style="color:rgb(var(--accent))">${file.icon}</span> ${file.label}`));
      wrap.lastChild.style.marginLeft = 'auto';
      wrap.style.display = 'flex';
      wrap.style.flexDirection = 'column';
      wrap.style.alignItems = 'flex-end';
    }
    wrap.appendChild(el('div', 'bubble-user', text));
    row.appendChild(wrap);
    log.appendChild(row);
    bottom();
  }

  // start a fresh assistant turn; returns the body container
  function newTurn() {
    const row = el('div', 'msg');
    row.appendChild(el('div', 'ava', avatar()));
    const turn = el('div', 'turn');
    turn.appendChild(el('div', 'who', 'Grasp'));
    row.appendChild(turn);
    log.appendChild(row);
    bottom();
    return turn;
  }

  async function action(turn, label, my) {
    const line = el('div', 'actline', `<span class="spin"></span><span>${label}</span>`);
    turn.appendChild(line);
    bottom();
    await sleep(680 + Math.random() * 520, my);
    guard(my);
    line.classList.add('done');
    line.querySelector('.spin').outerHTML = '<span style="color:rgb(var(--accent))">✓</span>';
    bottom();
  }

  async function say(turn, html, my) {
    const p = el('div', 'prose-a');
    turn.appendChild(p);
    // stream word by word, preserving inline markup by splitting on spaces of the source
    const parts = html.split(/(\s+)/);
    for (const w of parts) {
      guard(my);
      p.insertAdjacentHTML('beforeend', w);
      if (w.trim()) await sleep(20 + Math.random() * 26, my);
      bottom();
    }
  }

  /* ---------- artifact renderers (always-light learn surface) ---------- */
  function artCapsule(turn) {
    const a = el('div', 'art learn-surface card rounded-2xl overflow-hidden');
    a.innerHTML = `
      <div class="flex items-center gap-2 px-4 py-2.5 border-b border-line bg-sand/60">
        <span class="font-mono text-[11px] text-mute">capsule · ${T('архитектура-проекта.md', 'project-architecture.md')}</span>
        <span class="ml-auto font-mono text-[10px] text-accent px-2 py-0.5 rounded-full bg-accentsoft">${T('создана', 'created')}</span>
      </div>
      <div class="p-5">
        <div class="font-mono text-[11px] text-accent tracking-widest mb-3">${T('КАРТА МОДУЛЕЙ', 'MODULE MAP')}</div>
        <div class="font-mono text-[12.5px] leading-7 text-ink/85">
          <span class="text-accent font-semibold">apps/mcp-server</span> &nbsp;<span class="text-mute">${T('точка входа', 'entry point')}</span><br>
          &nbsp;&nbsp;│ exposes tools → Claude<br>
          &nbsp;&nbsp;▼<br>
          <span class="text-ink font-semibold">core/domain</span> &nbsp;<span class="text-mute">${T('правила, без I/O', 'rules, no I/O')}</span><br>
          &nbsp;&nbsp;├─ adapters/<span class="text-accent">db</span><br>
          &nbsp;&nbsp;└─ adapters/<span class="text-accent">llm</span>
        </div>
        <div class="mt-4 pt-3 border-t border-line text-[13px] text-mute">
          ${T('3 слоя · 9 модулей · зависимости только внутрь', '3 layers · 9 modules · dependencies point inward')}
        </div>
      </div>`;
    turn.appendChild(a);
    bottom();
  }

  function artPath(turn) {
    const rows = T(
      [['01', 'Внимание как поиск', '9 мин', null],
       ['02', 'Self-attention по шагам', '12 мин', 'практика'],
       ['03', 'Multi-head и позиции', '10 мин', null],
       ['04', 'Почему это масштабируется', '8 мин', 'ревью']],
      [['01', 'Attention as lookup', '9 min', null],
       ['02', 'Self-attention, step by step', '12 min', 'practice'],
       ['03', 'Multi-head & positions', '10 min', null],
       ['04', 'Why it scales', '8 min', 'review']]
    );
    const a = el('div', 'art learn-surface card rounded-2xl p-5');
    a.innerHTML = `
      <div class="font-mono text-[11px] text-accent tracking-widest mb-1">${T('ПЛАН ОБУЧЕНИЯ', 'LEARNING PATH')}</div>
      <div class="font-display text-lg font-bold mb-3">${T('Трансформеры — от интуиции к деталям', 'Transformers — intuition to detail')}</div>
      <div class="space-y-2">
        ${rows.map(([n, t, d, tag]) => `
          <div class="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5 bg-paper">
            <span class="font-display text-base font-bold text-mute w-6">${n}</span>
            <span class="font-medium text-[14px] text-ink flex-1">${t}</span>
            ${tag ? `<span class="font-mono text-[10px] text-accent px-2 py-0.5 rounded-full bg-accentsoft">${tag}</span>` : ''}
            <span class="font-mono text-[11px] text-mute">${d}</span>
          </div>`).join('')}
      </div>`;
    turn.appendChild(a);
    bottom();
  }

  function artTask(turn) {
    const a = el('div', 'art learn-surface card rounded-2xl p-5');
    a.innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <div class="font-mono text-[11px] text-accent tracking-widest">${T('ПРАКТИКА · РАЗМИНКА', 'PRACTICE · WARM-UP')}</div>
        <div class="font-mono text-[10px] text-mute">${T('подстроено под твой уровень', 'tuned to your level')}</div>
      </div>
      <div class="font-display text-lg font-bold mb-1">${T('Напиши makeCounter()', 'Write makeCounter()')}</div>
      <p class="text-[14px] text-ink/80 mb-3">${T(
        'Функция возвращает счётчик. Каждый вызов даёт следующее число. Два счётчика не мешают друг другу.',
        'Returns a counter. Each call yields the next number. Two counters never interfere.')}</p>
      <details class="group">
        <summary class="inline-flex items-center gap-2 text-[13px] font-mono text-accent hover:text-accentdk transition">
          <span class="transition group-open:rotate-90">▸</span> ${T('показать решение', 'reveal solution')}
        </summary>
        <pre class="mt-3 p-3.5 rounded-xl codecard font-mono text-[12.5px] overflow-x-auto whitespace-pre-wrap">function makeCounter() {
  let n = 0;            <span style="color:#8c8">// closed-over state</span>
  return () => ++n;     <span style="color:#8c8">// remembers n</span>
}
const a = makeCounter(); a(); // 1
const b = makeCounter(); b(); // 1 — independent</pre>
      </details>`;
    turn.appendChild(a);
    bottom();
  }

  function artCard(turn, my) {
    const q = T('Что произойдёт с дочерними корутинами, если отменить родительский Job?',
                'What happens to child coroutines when you cancel the parent Job?');
    const ans = T('Все дети отменяются автоматически — это и есть structured concurrency: scope владеет иерархией.',
                  'They all cancel automatically — that\'s structured concurrency: the scope owns the hierarchy.');
    const a = el('div', 'art learn-surface');
    a.innerHTML = `
      <div class="flip cursor-pointer select-none">
        <div class="flip-inner" style="height:170px">
          <div class="flip-face card rounded-2xl p-5 flex flex-col">
            <div class="flex items-center justify-between font-mono text-[11px] text-mute">
              <span>coroutines · ${T('повтор','review')}</span><span>${T('нажми, чтобы перевернуть','tap to flip')}</span>
            </div>
            <div class="flex-1 flex items-center"><p class="font-display text-[17px] font-semibold leading-snug">${q}</p></div>
          </div>
          <div class="flip-face flip-back rounded-2xl p-5 flex flex-col" style="background:rgb(var(--accentsoft));border:1px solid rgb(var(--accent)/.3)">
            <div class="font-mono text-[11px] text-accent">${T('ответ','answer')}</div>
            <div class="flex-1 flex items-center"><p class="text-[15px] text-ink leading-relaxed">${ans}</p></div>
          </div>
        </div>
      </div>
      <div class="flex gap-2 mt-3">
        <button data-r="again" class="flex-1 px-3 py-2 rounded-lg card text-[13px] font-medium btn-press">${T('Снова','Again')}</button>
        <button data-r="hard"  class="flex-1 px-3 py-2 rounded-lg card text-[13px] font-medium btn-press">${T('Трудно','Hard')}</button>
        <button data-r="good"  class="flex-1 px-3 py-2 rounded-lg card text-[13px] font-medium btn-press" style="border-color:rgb(var(--accent)/.5)">${T('Легко','Easy')}</button>
      </div>
      <div class="next mt-2.5 text-[13px] font-mono text-accent h-4"></div>`;
    const flip = a.querySelector('.flip');
    flip.onclick = (e) => { if (!e.target.closest('[data-r]')) flip.classList.toggle('flipped'); };
    const msg = T({ again: '↻ вернётся завтра', hard: '↗ через 3 дня', good: '✦ интервал вырос до 9 дней' },
                  { again: '↻ back tomorrow', hard: '↗ back in 3 days', good: '✦ interval grew to 9 days' });
    a.querySelectorAll('[data-r]').forEach(b => b.onclick = () => {
      a.querySelector('.next').textContent = msg[b.dataset.r];
    });
    turn.appendChild(a);
    bottom();
    return a;
  }

  /* ---------- scenarios ---------- */
  const SCENARIOS = {
    codebase: async (my) => {
      await typeInput(T('Вот репозиторий нашего сервиса — помоги разобраться в архитектуре',
                        'Here\'s our service repo — help me understand the architecture'), my);
      userBubble(T('Вот репозиторий нашего сервиса — помоги разобраться в архитектуре',
                   'Here\'s our service repo — help me understand the architecture'),
                 { icon: '{ }', label: 'proof-forge-v2 · 142 ' + T('файла', 'files') });
      const t = newTurn();
      await action(t, T('Читаю репозиторий…', 'Reading the repository…'), my);
      await action(t, T('Строю карту модулей…', 'Building the module map…'), my);
      await action(t, T('Определяю слои и зависимости…', 'Resolving layers & dependencies…'), my);
      await say(t, T('Это слоистая архитектура. Точка входа — <b>MCP-сервер</b>, дальше домен и адаптеры. Главное понять первым — <b>границы между слоями</b>: зависимости смотрят только внутрь.',
                     'It\'s a layered architecture. The entry point is the <b>MCP server</b>, then domain and adapters. The first thing to grasp — the <b>boundaries between layers</b>: dependencies point inward only.'), my);
      artCapsule(t);
      await sleep(500, my);
      await say(t, T('Собрал капсулу «Архитектура проекта». Изучим её по слоям — начнём с домена?',
                     'I built a "Project architecture" capsule. We\'ll study it layer by layer — start with the domain?'), my);
    },

    youtube: async (my) => {
      await typeInput('youtu.be/transformers-explained', my);
      userBubble(T('Разбери это видео и сделай из него план',
                   'Break down this video and turn it into a plan'),
                 { icon: '▶', label: 'youtu.be/transformers-explained · 38:14' });
      const t = newTurn();
      await action(t, T('Смотрю видео (38:14)…', 'Watching the video (38:14)…'), my);
      await action(t, T('Достаю ключевые идеи…', 'Extracting key ideas…'), my);
      await action(t, T('Строю план обучения…', 'Building a learning path…'), my);
      await say(t, T('Видео плотное. Разбил на 4 модуля — от интуиции к деталям, по 8–12 минут, с практикой и ревью.',
                     'Dense video. I split it into 4 modules — intuition to detail, 8–12 min each, with practice and review.'), my);
      artPath(t);
      await sleep(500, my);
      await say(t, T('Начнём с первого модуля или сразу проверим, что ты уже знаешь?',
                     'Start with module one, or check what you already know first?'), my);
    },

    topic: async (my) => {
      await typeInput(T('Помоги изучить JavaScript closures', 'Help me learn JavaScript closures'), my);
      userBubble(T('Помоги изучить JavaScript closures', 'Help me learn JavaScript closures'));
      const t = newTurn();
      await action(t, T('Смотрю твой прогресс…', 'Checking your progress…'), my);
      await action(t, T('Подбираю объяснение под уровень…', 'Tuning the explanation to your level…'), my);
      await say(t, T('Замыкание — это функция, которая <b>помнит переменные</b> из места, где была создана, даже когда вызывается в другом месте. Классика — счётчик:',
                     'A closure is a function that <b>remembers variables</b> from where it was created, even when called elsewhere. The classic example — a counter:'), my);
      artTask(t);
      await sleep(500, my);
      await say(t, T('Решишь сам — подниму сложность до боевой. Застрянешь — дам подсказку, а не ответ.',
                     'Solve it yourself and I\'ll raise the difficulty. Get stuck and I\'ll give a hint, not the answer.'), my);
    },

    review: async (my) => {
      const t = newTurn();
      await say(t, T('Пора повторить — всплыло как раз вовремя, пока не забылось 👇',
                     'Time for a review — it surfaced right on time, before you\'d forget 👇'), my);
      const card = artCard(t, my);
      await sleep(900, my);
      guard(my);
      // auto-flip to reveal the answer, then auto-rate "good"
      card.querySelector('.flip').classList.add('flipped');
      await sleep(1100, my);
      guard(my);
      card.querySelector('[data-r="good"]').click();
      await sleep(700, my);
      await say(t, T('Вспомнил уверенно — интервал вырос до 9 дней. Я веду это сам, тебе ничего не нужно планировать.',
                     'Recalled confidently — the interval grew to 9 days. I track this myself; you plan nothing.'), my);
    },
  };

  /* ---------- runner + autoplay ---------- */
  let autoTimer = null;
  const capItems = [...document.querySelectorAll('.cap-item')];
  function setChip(key) {
    [...scChips.children].forEach(b => b.classList.toggle('on', b.dataset.sc === key));
    capItems.forEach(c => c.classList.toggle('active', c.dataset.cap === key));
  }
  function resetInput() {
    inputEl.classList.add('placeholder');
    inputEl.textContent = lang === 'en' ? 'Ask, paste a link, or drop a repo…' : 'Спроси, вставь ссылку или репозиторий…';
  }
  async function run(key, { advance = true } = {}) {
    clearTimeout(autoTimer);
    current = key;
    const my = ++token;
    setChip(key);
    log.innerHTML = '';
    resetInput();
    try {
      await sleep(400, my);
      await SCENARIOS[key](my);
      if (advance) {
        autoTimer = setTimeout(() => {
          if (my !== token) return;
          const next = ORDER[(ORDER.indexOf(key) + 1) % ORDER.length];
          run(next);
        }, 3200);
      }
    } catch (e) { /* cancelled */ }
  }

  /* ---------- controls ---------- */
  devToggle.addEventListener('click', (e) => {
    const b = e.target.closest('[data-mode]');
    if (!b) return;
    [...devToggle.children].forEach(x => x.classList.toggle('on', x === b));
    device.dataset.mode = b.dataset.mode;
    if (typeof rescaleDevices === 'function') rescaleDevices();
    bottom();
  });
  scChips.addEventListener('click', (e) => {
    const b = e.target.closest('[data-sc]');
    if (!b) return;
    run(b.dataset.sc);
  });

  /* ---------- public ---------- */
  window.GraspDemo = {
    setLang(l) { lang = l; run(current); },
  };

  /* ---------- kick off when the demo scrolls into view ---------- */
  let started = false;
  const startIO = new IntersectionObserver((es) => {
    es.forEach(e => {
      if (e.isIntersecting && !started) { started = true; run('codebase'); }
    });
  }, { threshold: 0.25 });
  startIO.observe(document.getElementById('play'));
})();
