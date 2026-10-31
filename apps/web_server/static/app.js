(() => {
    const $ = (id) => document.getElementById(id);
    const chat = $('chat');
    const input = $('input');
    const sendBtn = $('send-btn');
    const statusBar = $('status-bar');
    const connStatus = $('conn-status');

    let ws = null;
    let reconnectDelay = 1000;
    let pendingSkills = null;

    // ---------- 连接 ----------
    function connect() {
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        ws = new WebSocket(`${proto}://${location.host}/ws`);

        ws.onopen = () => {
            connStatus.textContent = '在线';
            connStatus.classList.remove('offline');
            reconnectDelay = 1000;
        };

        ws.onclose = () => {
            connStatus.textContent = '断线, 重连中...';
            connStatus.classList.add('offline');
            setTimeout(connect, reconnectDelay);
            reconnectDelay = Math.min(reconnectDelay * 2, 10000);
        };

        ws.onerror = () => {
            connStatus.textContent = '连接错误';
            connStatus.classList.add('offline');
        };

        ws.onmessage = (e) => {
            try {
                handleEvent(JSON.parse(e.data));
            } catch (err) {
                console.error('解析失败:', err, e.data);
            }
        };
    }

    // ---------- 事件 ----------
    function handleEvent(ev) {
        switch (ev.type) {
            case 'message':
                appendMessage(ev.role || 'assistant', ev.content || '');
                break;
            case 'status':
                setStatus(ev.text || '');
                break;
            case 'artifact':
                appendArtifact(ev.kind || '', ev.path || '');
                break;
            case 'error':
                appendMessage('assistant', '❌ ' + (ev.message || ''));
                setStatus('');
                break;
            case 'skill_start':
                setStatus(`🚀 ${ev.name}  ${JSON.stringify(ev.kwargs || {})}`);
                break;
            case 'skill_done':
                setStatus('');
                break;
            case 'skills_list':
                showSkills(ev.skills || []);
                break;
        }
    }

    // ---------- 渲染 ----------
    function appendMessage(role, content) {
        const el = document.createElement('div');
        el.className = `msg ${role}`;
        const b = document.createElement('div');
        b.className = 'bubble';
        b.textContent = content;
        el.appendChild(b);
        chat.appendChild(el);
        chat.scrollTop = chat.scrollHeight;
    }

    function appendArtifact(kind, path) {
        const el = document.createElement('div');
        el.className = 'msg assistant';

        const isImage = (kind === 'image' || kind === 'image_path' ||
                         /\.(png|jpe?g|webp|gif|bmp)$/i.test(path));
        const fileUrl = '/api/file?path=' + encodeURIComponent(path);

        if (isImage) {
            const img = document.createElement('img');
            img.src = fileUrl;
            img.loading = 'lazy';
            img.className = 'artifact-image';
            img.onclick = () => window.open(fileUrl, '_blank');
            el.appendChild(img);
        }

        const link = document.createElement('a');
        link.textContent = `📄 ${kind}: ${path}`;
        link.href = fileUrl;
        link.target = '_blank';
        link.rel = 'noopener';
        link.className = 'artifact-link';
        el.appendChild(link);

        chat.appendChild(el);
        chat.scrollTop = chat.scrollHeight;
    }

    function setStatus(text) {
        if (!text) {
            statusBar.textContent = '';
            statusBar.classList.add('hidden');
        } else {
            statusBar.textContent = text;
            statusBar.classList.remove('hidden');
        }
    }

    function showSkills(skills) {
        const old = document.getElementById('skills-modal');
        if (old) old.remove();

        const modal = document.createElement('div');
        modal.id = 'skills-modal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <strong>Skills (${skills.length})</strong>
                    <button id="modal-close">×</button>
                </div>
                <div class="modal-body" id="skills-list"></div>
            </div>`;
        document.body.appendChild(modal);

        const list = document.getElementById('skills-list');
        skills.forEach(s => {
            const item = document.createElement('div');
            item.className = 'skill-item';
            item.innerHTML = `
                <div class="skill-name">${escapeHtml(s.name)}</div>
                <div class="skill-meta">${escapeHtml(s.source)} · ${s.keywords.length} kw${s.system_hint ? ' · ' + escapeHtml(s.system_hint) : ''}</div>`;
            item.onclick = () => {
                sendSkill(s.name);
                modal.remove();
            };
            list.appendChild(item);
        });
        document.getElementById('modal-close').onclick = () => modal.remove();
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    // ---------- 发送 ----------
    function sendText() {
        const text = input.value.trim();
        if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({ action: 'text', text }));
        appendMessage('user', text);
        input.value = '';
        input.style.height = 'auto';
    }

    function sendSkill(name, kwargs = {}) {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({ action: 'skill', name, kwargs }));
        appendMessage('user', `/skill ${name}`);
    }

    function sendAction(action) {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({ action }));
    }

    // ---------- 交互 ----------
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendText();
        }
    });

    sendBtn.onclick = sendText;

    const sidebar = $('sidebar');
    $('menu-btn').onclick = () => sidebar.classList.toggle('hidden');
    $('sidebar-close').onclick = () => sidebar.classList.add('hidden');

    sidebar.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const act = btn.dataset.action;
        if (act === 'list-skills') sendAction('list_skills');
        else if (act === 'clear-chat') chat.innerHTML = '';
        else if (act === 'cancel') sendAction('cancel');
        sidebar.classList.add('hidden');
    });

    connect();
})();