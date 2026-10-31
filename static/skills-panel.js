/* skills-panel.js - Skills 面板（独立模块，不依赖现有 app.js） */
(function () {
    "use strict";

    // ============================================================
    // 常量：每个 skill 的示例 kwargs（点 "填充示例" 一键填入）
    // ============================================================
    const SKILL_EXAMPLES = {
        daily_pipeline:        { topic: "机甲少女站在废墟中", count: 2, skip_wechat: true },
        github_repo_daily:     { force_publish: false, skip_illustration: false },
        image_curator:         { directory: "output", max_images: 3 },
        image_generator:       { prompt: "一只在星空下的白猫", width: 1024, height: 1024 },
        local_model_manage:    { action: "list" },
        music_generator:       { topic: "海边日落", emotion: "peaceful", duration: 20, arrangement: "chinese" },
        music_player:          { action: "scan_local" },
        news_aggregator:       { top_n: 3 },
        novel_writer:          { genre: "科幻", title: "星河", outline: "人类在星际中发现神秘信号", characters: "船长李卓", chapter_count: 1, words_per_chapter: 500 },
        radio_player:          { action: "list" },
        search_engine:         { action: "search", query: "水墨山水", kind: "images", limit: 5 },
        social_auto_upload:    { action: "list_platforms" },
        tech_hot_article:      { topic: "AI Agent 应用落地", words: 1000, images: 1 },
        video_generator:       { prompt: "海边日落", duration: 10 },
        video_player:          { action: "search", query: "海边日落", limit: 5 },
        video_sniffer:         { action: "analyze", url: "https://www.bilibili.com/video/BV1GJ411x7h7" },
        voice_assistant:       { action: "tts", text: "你好，欢迎使用 PromptForge", voice: "zh-CN-XiaoxiaoNeural" },
        wechat_formatter:      { md_path: "output/xxx/article.md", theme: "newspaper" },
    };

    // skill 名字 → 图标
    const SKILL_ICONS = {
        daily_pipeline: "📅", github_repo_daily: "🐙", image_curator: "🖼️",
        image_generator: "🎨", local_model_manage: "📦", music_generator: "🎵",
        music_player: "🎧", news_aggregator: "📰", novel_writer: "📖",
        radio_player: "📻", search_engine: "🔍", social_auto_upload: "📤",
        tech_hot_article: "📝", video_generator: "🎬", video_player: "📺",
        video_sniffer: "🎯", voice_assistant: "🔊", wechat_formatter: "📱",
    };

    // ============================================================
    // Token 获取（兼容多种存储方式）
    // ============================================================
    function getToken() {
        try {
            return (
                localStorage.getItem("pf_token") ||
                localStorage.getItem("pf_web_token") ||
                localStorage.getItem("token") ||
                new URLSearchParams(location.search).get("token") ||
                ""
            );
        } catch (e) {
            return "";
        }
    }

    function apiUrl(path) {
        const t = getToken();
        const sep = path.includes("?") ? "&" : "?";
        return path + (t ? `${sep}token=${encodeURIComponent(t)}` : "");
    }

    function apiHeaders() {
        const h = { "Content-Type": "application/json" };
        const t = getToken();
        if (t) h["x-pf-token"] = t;
        return h;
    }

    // ============================================================
    // 结果回显（尝试找现有聊天容器）
    // ============================================================
    function tryAppendToChat(html) {
        const selectors = ["#chat", "#messages", ".chat", ".chat-container", ".messages", "#chat-box"];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
                const wrapper = document.createElement("div");
                wrapper.innerHTML = html;
                el.appendChild(wrapper);
                el.scrollTop = el.scrollHeight;
                return true;
            }
        }
        return false;
    }

    // ============================================================
    // DOM 构建
    // ============================================================
    let state = {
        skills: [],
        loading: false,
        filter: "",
        expanded: null,   // 当前展开的 skill name
    };

    function createUI() {
        // 浮动触发按钮
        const btn = document.createElement("button");
        btn.className = "pf-skills-trigger";
        btn.innerHTML = "🎯";
        btn.title = "Skills";
        btn.onclick = openPanel;
        document.body.appendChild(btn);

        // 遮罩
        const backdrop = document.createElement("div");
        backdrop.className = "pf-skills-backdrop";
        backdrop.onclick = closePanel;
        document.body.appendChild(backdrop);

        // 抽屉
        const drawer = document.createElement("div");
        drawer.className = "pf-skills-drawer";
        drawer.innerHTML = `
            <div class="pf-skills-header">
                <h2>🎯 Skills <span id="pf-skills-count" style="color:#888;font-weight:400;font-size:14px"></span></h2>
                <button class="pf-skills-close" id="pf-skills-close">×</button>
            </div>
            <div class="pf-skills-search">
                <input type="text" id="pf-skills-filter" placeholder="搜索 skill 名称或关键词..." />
            </div>
            <div class="pf-skills-list" id="pf-skills-list">
                <div class="pf-loading">加载 Skills...</div>
            </div>
        `;
        document.body.appendChild(drawer);

        document.getElementById("pf-skills-close").onclick = closePanel;
        document.getElementById("pf-skills-filter").oninput = (e) => {
            state.filter = e.target.value.trim().toLowerCase();
            renderList();
        };
    }

    // ============================================================
    // 打开 / 关闭
    // ============================================================
    function openPanel() {
        document.querySelector(".pf-skills-drawer").classList.add("open");
        document.querySelector(".pf-skills-backdrop").classList.add("open");
        if (state.skills.length === 0) loadSkills();
    }

    function closePanel() {
        document.querySelector(".pf-skills-drawer").classList.remove("open");
        document.querySelector(".pf-skills-backdrop").classList.remove("open");
    }

    // ============================================================
    // 加载 skills
    // ============================================================
    async function loadSkills() {
        state.loading = true;
        renderList();
        try {
            const r = await fetch(apiUrl("/api/skills"), { headers: apiHeaders() });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const json = await r.json();
            if (json.status !== "success") throw new Error(json.message || "加载失败");
            state.skills = json.data || [];
            document.getElementById("pf-skills-count").textContent = `(${state.skills.length})`;

            // 更新触发按钮徽章
            const trigger = document.querySelector(".pf-skills-trigger");
            if (trigger) {
                trigger.classList.add("badge");
                trigger.dataset.badge = state.skills.length;
            }
        } catch (e) {
            state.skills = [];
            const list = document.getElementById("pf-skills-list");
            if (list) list.innerHTML = `<div class="pf-loading" style="color:#f87171">加载失败: ${escapeHtml(e.message)}</div>`;
        } finally {
            state.loading = false;
            renderList();
        }
    }

    // ============================================================
    // 渲染列表
    // ============================================================
    function renderList() {
        const list = document.getElementById("pf-skills-list");
        if (!list || state.loading) return;

        let skills = state.skills;
        if (state.filter) {
            skills = skills.filter(s =>
                s.name.toLowerCase().includes(state.filter) ||
                (s.system_hint || "").toLowerCase().includes(state.filter) ||
                (s.keywords || []).some(k => k.toLowerCase().includes(state.filter))
            );
        }

        if (skills.length === 0) {
            list.innerHTML = `<div class="pf-loading">${state.skills.length ? "无匹配 skill" : "暂无 skill"}</div>`;
            return;
        }

        list.innerHTML = skills.map(s => renderCard(s)).join("");

        // 绑定卡片点击
        list.querySelectorAll(".pf-skill-head").forEach(head => {
            head.onclick = () => toggleCard(head.closest(".pf-skill-card"));
        });

        // 恢复展开状态
        if (state.expanded) {
            const card = list.querySelector(`[data-skill="${state.expanded}"]`);
            if (card) card.classList.add("expanded");
        }
    }

    function renderCard(s) {
        const icon = SKILL_ICONS[s.name] || "🎯";
        const hint = s.system_hint || "";
        const kws = (s.keywords || []).slice(0, 4);
        const kwText = kws.length ? kws.map(k => `「${k}」`).join(" ") : "";
        const example = SKILL_EXAMPLES[s.name];
        const exampleJson = example ? JSON.stringify(example, null, 2) : "{}";
        const exampleBtn = example ? `<button class="pf-btn-secondary" data-action="fill" data-skill-name="${escapeHtml(s.name)}">填充示例</button>` : "";

        return `
            <div class="pf-skill-card" data-skill="${escapeHtml(s.name)}">
                <div class="pf-skill-head">
                    <div class="pf-skill-icon">${icon}</div>
                    <div class="pf-skill-info">
                        <div class="pf-skill-name">${escapeHtml(s.name)}</div>
                        ${hint ? `<div class="pf-skill-hint">${escapeHtml(hint)}</div>` : ""}
                        ${kwText ? `<div class="pf-skill-kw">${escapeHtml(kwText)}</div>` : ""}
                    </div>
                </div>
                <div class="pf-skill-body">
                    <label>kwargs（JSON 格式，留空 {{}} 表示用默认参数）</label>
                    <textarea data-kwargs="${escapeHtml(s.name)}">${escapeHtml(exampleJson)}</textarea>
                    <div class="pf-skill-actions">
                        ${exampleBtn}
                        <button class="pf-btn-primary" data-action="run" data-skill-name="${escapeHtml(s.name)}">执行</button>
                    </div>
                    <div class="pf-skill-result" data-result="${escapeHtml(s.name)}"></div>
                </div>
            </div>
        `;
    }

    function toggleCard(card) {
        const name = card.dataset.skill;
        const isExpanded = card.classList.contains("expanded");
        // 关闭其他
        card.parentElement.querySelectorAll(".pf-skill-card").forEach(c => c.classList.remove("expanded"));
        if (!isExpanded) {
            card.classList.add("expanded");
            state.expanded = name;
        } else {
            state.expanded = null;
        }
    }

    // ============================================================
    // 执行 skill
    // ============================================================
    async function runSkill(skillName, card) {
        const textarea = card.querySelector(`textarea[data-kwargs="${cssEscape(skillName)}"]`);
        const resultEl = card.querySelector(`div[data-result="${cssEscape(skillName)}"]`);
        const runBtn = card.querySelector(`button[data-action="run"][data-skill-name="${cssEscape(skillName)}"]`);

        let kwargs = {};
        const raw = (textarea.value || "").trim();
        if (raw) {
            try {
                kwargs = JSON.parse(raw);
                if (typeof kwargs !== "object" || Array.isArray(kwargs)) throw new Error("kwargs 必须是 JSON 对象 {}");
            } catch (e) {
                showResult(resultEl, "error", `JSON 解析失败: ${e.message}`);
                return;
            }
        }

        runBtn.disabled = true;
        runBtn.textContent = "执行中...";
        resultEl.classList.add("show");
        resultEl.className = "pf-skill-result show";
        resultEl.textContent = "⏳ 执行中，请稍候...";

        const t0 = Date.now();
        try {
            const r = await fetch(apiUrl("/api/run_skill"), {
                method: "POST",
                headers: apiHeaders(),
                body: JSON.stringify({ skill_name: skillName, kwargs }),
            });
            const json = await r.json();
            const elapsed = ((Date.now() - t0) / 1000).toFixed(1);

            if (json.status === "success") {
                showResult(resultEl, "success", formatResult(json, elapsed), json);
                // 尝试追加到聊天区
                const chatHtml = `<div style="padding:8px 12px;background:#242424;border-radius:8px;margin:8px 0">
                    <div style="color:#4ade80;font-size:12px;margin-bottom:4px">✅ ${escapeHtml(skillName)} 完成 (${elapsed}s)</div>
                    ${formatResultForChat(json)}
                </div>`;
                tryAppendToChat(chatHtml);
            } else {
                showResult(resultEl, "error", `❌ 失败: ${json.message || json.error || "未知错误"}`, json);
            }
        } catch (e) {
            showResult(resultEl, "error", `❌ 请求失败: ${e.message}`);
        } finally {
            runBtn.disabled = false;
            runBtn.textContent = "执行";
        }
    }

    function formatResult(json, elapsed) {
        const d = json.result || {};
        // 如果 result 本身是 {status, result: {...}}，再剥一层
        const inner = (d.result && typeof d.result === "object") ? d.result : d;

        const lines = [`✅ 完成 (${elapsed}s)`];
        const artifactKeys = ["image_path", "video_path", "audio_file", "article_md", "article_html",
                              "article_docx", "article_pdf", "report_file", "novel_file", "audio_file",
                              "preview_path", "output_dir", "repo_url", "saved_to"];
        const others = [];
        for (const [k, v] of Object.entries(inner)) {
            if (artifactKeys.includes(k) && v) {
                lines.push(`📄 ${k}: ${v}`);
            } else if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
                others.push(`${k}: ${v}`);
            }
        }
        if (others.length) {
            lines.push("");
            lines.push(...others);
        }
        return lines.join("\n");
    }

    function formatResultForChat(json) {
        const d = json.result || {};
        const inner = (d.result && typeof d.result === "object") ? d.result : d;
        const parts = [];

        // 图片
        const imgPath = inner.image_path || inner.article_html && null;
        if (imgPath) {
            const url = apiUrl(`/api/file?path=${encodeURIComponent(imgPath)}`);
            parts.push(`<img src="${url}" loading="lazy" style="max-width:100%;border-radius:8px;margin-top:6px" onclick="window.open('${url}')">`);
        }
        // 音频
        if (inner.audio_file) {
            const url = apiUrl(`/api/file?path=${encodeURIComponent(inner.audio_file)}`);
            parts.push(`<audio controls src="${url}" style="width:100%;margin-top:6px"></audio>`);
        }
        // 文件链接
        for (const key of ["article_md", "article_html", "article_pdf", "report_file", "novel_file", "preview_path", "video_path"]) {
            const p = inner[key];
            if (p) {
                const url = apiUrl(`/api/file?path=${encodeURIComponent(p)}`);
                parts.push(`<a href="${url}" target="_blank" style="color:#4a9eff;font-size:12px;display:block;margin-top:4px;word-break:break-all">📄 ${key}: ${escapeHtml(p)}</a>`);
            }
        }
        if (parts.length === 0) {
            parts.push(`<div style="font-size:12px;color:#888">${escapeHtml(JSON.stringify(inner).slice(0, 200))}</div>`);
        }
        return parts.join("");
    }

    function showResult(el, type, text, json) {
        el.classList.add("show");
        el.className = `pf-skill-result show ${type}`;
        el.innerHTML = `<div style="white-space:pre-wrap">${escapeHtml(text)}</div>`;
        // 追加图片/音频
        if (type === "success" && json) {
            const chatParts = formatResultForChat(json);
            if (chatParts) {
                const div = document.createElement("div");
                div.innerHTML = chatParts;
                el.appendChild(div);
            }
        }
    }

    // ============================================================
    // 工具
    // ============================================================
    function escapeHtml(s) {
        return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        }[c]));
    }

    function cssEscape(s) {
        if (window.CSS && window.CSS.escape) return window.CSS.escape(s);
        return String(s).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
    }

    // ============================================================
    // 事件委托（填充示例 / 执行按钮）
    // ============================================================
    document.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-action]");
        if (!btn) return;
        const action = btn.dataset.action;
        const skillName = btn.dataset.skillName;
        if (!skillName) return;

        const card = btn.closest(".pf-skill-card");
        if (!card) return;

        if (action === "fill") {
            const example = SKILL_EXAMPLES[skillName];
            if (example) {
                const ta = card.querySelector(`textarea[data-kwargs="${cssEscape(skillName)}"]`);
                if (ta) ta.value = JSON.stringify(example, null, 2);
            }
        } else if (action === "run") {
            runSkill(skillName, card);
        }
    });

    // ============================================================
    // 初始化
    // ============================================================
    function init() {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", createUI);
        } else {
            createUI();
        }
    }

    init();
})();