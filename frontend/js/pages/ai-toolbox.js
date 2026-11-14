import { api } from "../api.js";
import { icon, refreshIcons } from "../components/icons.js";
import { aiBanner, aiResultFooter } from "../components/ai-display.js";
import { createImageUploader } from "../components/upload.js";
import { showToast, toastError } from "../components/toast.js";
import { getMeta } from "../services/store.js";
import { copyText, renderRichMarkdown } from "../markdown.js";
import {
  emptyState,
  escapeHTML,
  formatMinutes,
  nl2br,
} from "../ui.js";

const TOOLS = [
  {
    id: "essay",
    label: "作文批改",
    title: "英语作文批改",
    icon: "spell-check",
    short: "拼写、语法、时态、结构与修改建议",
    description:
      "粘贴作文或上传图片。系统会检查拼写、语法、时态、句式、词汇和结构，并给出一版保持原作者水平的修改稿。",
  },
  {
    id: "polish",
    label: "表达润色",
    title: "英语表达润色",
    icon: "wand-sparkles",
    short: "简单版 / 自然版 / 进阶版",
    description:
      "在保留原意的前提下提供三个难度版本。进阶版会控制在中学生实际可用的范围内，不堆砌生僻词。",
  },
  {
    id: "sentence",
    label: "长难句分析",
    title: "英文长难句分析",
    icon: "split",
    short: "主句、从句、主谓宾与修饰成分",
    description:
      "拆解英文长句的句子结构，识别主句、从句、主谓宾与修饰成分，帮助理解而不只是给出翻译。",
  },
  {
    id: "grammar",
    label: "语法诊断",
    title: "语法诊断",
    icon: "search-check",
    short: "定位错误并解释原因",
    description:
      "输入一句英语句子，找出语法、拼写、时态或标点错误，解释错误原因并给出修改版本。",
  },
  {
    id: "questions",
    label: "AI 出题",
    title: "AI 出题练习",
    icon: "list-plus",
    short: "按学科、知识点和难度生成练习",
    description:
      "选择学科、输入知识点和难度，生成练习题、答案与解析。适合在复习后做一次主动回忆。",
  },
  {
    id: "grading",
    label: "AI 阅卷",
    title: "主观题阅卷辅助",
    icon: "clipboard-check",
    short: "对照参考答案找得分点与遗漏",
    description:
      "输入题目、参考答案与学生答案，梳理可能命中的得分点、遗漏内容和改进建议。这不是正式考试评分。",
  },
];

let activeTool = "essay";
let controller = null;
let pageRoot = null;
let essayUploader = null;
const requests = new Map();

function currentAI() {
  return getMeta()?.ai || null;
}

function enginePill(label, engine) {
  if (!engine) {
    return `<span class="engine-pill is-unavailable">${escapeHTML(label)} · 未配置</span>`;
  }
  const mode = engine.effective_mode;
  const modeClass = mode === "live" ? "is-live" : mode === "demo" ? "is-demo" : "is-unavailable";
  const modeLabel = mode === "live" ? "真实模型" : mode === "demo" ? "演示模式" : "未配置";
  return `<span class="engine-pill ${modeClass}">
    <span class="engine-dot"></span>${escapeHTML(label)} · ${modeLabel}
    <small>${escapeHTML(engine.provider || "")}${engine.model ? ` / ${escapeHTML(engine.model)}` : ""}</small>
  </span>`;
}

function renderPage(container) {
  const ai = currentAI();
  const demoOrUnavailable =
    ai &&
    [ai.text?.effective_mode, ai.vision?.effective_mode].some(
      (mode) => mode === "demo" || mode === "unavailable"
    );
  container.innerHTML = `
    <div class="page-shell">
      <header class="page-header">
        <div class="page-heading">
          <h1>AI 学习工具</h1>
          <p class="page-subtitle">选择一个工具，输入材料后开始分析。所有结果都需要你核对。</p>
        </div>
        <div class="page-actions">
          <a class="btn btn-secondary" href="#/settings">${icon("sliders-horizontal")}<span>AI 配置</span></a>
        </div>
      </header>

      <div class="toolbox-status-bar">
        <div class="toolbox-engine-group">
          ${enginePill("文本分析", ai?.text)}
          ${enginePill("图片理解", ai?.vision)}
        </div>
        <div class="toolbox-status-note">
          <span>${
            demoOrUnavailable
              ? "未完整配置真实模型。每次结果都会明确标记为演示模式。"
              : "模型已连接。请核对关键事实与原文。"
          }</span>
        </div>
      </div>

      <div class="toolbox-layout">
        <aside class="toolbox-nav card" role="tablist" aria-label="AI 工具">
          ${TOOLS.map(
            (tool) => `<button type="button" class="toolbox-nav-item ${
              activeTool === tool.id ? "is-active" : ""
            }" data-ai-tool="${tool.id}" role="tab" aria-selected="${activeTool === tool.id}">
              <span class="toolbox-nav-icon">${icon(tool.icon)}</span>
              <span><strong>${tool.label}</strong><small>${tool.short}</small></span>
              ${icon("chevron-right", "toolbox-nav-arrow")}
            </button>`
          ).join("")}
          <div class="toolbox-nav-footer">
            <span>${icon("shield-check")} API Key 只保存在后端</span>
            <a href="#/settings" class="text-link">查看配置状态 ${icon("arrow-right")}</a>
          </div>
        </aside>

        <div class="toolbox-main">
          ${TOOLS.map((tool) => renderToolPanel(tool, ai)).join("")}
        </div>
      </div>
    </div>
  `;
  pageRoot = container;
  refreshIcons(container);
  bindTabs(container);
  bindEssay(container);
  bindPolish(container);
  bindSentence(container);
  bindGrammar(container);
  bindQuestions(container);
  bindGrading(container);
}

function renderToolPanel(tool, ai) {
  return `<section class="tool-panel card ${activeTool === tool.id ? "is-active" : ""}" data-tool-panel="${tool.id}" role="tabpanel" ${
    activeTool === tool.id ? "" : "hidden"
  }>
    <div class="tool-panel-header">
      <span class="tool-panel-icon">${icon(tool.icon)}</span>
      <div>
        <div class="tool-panel-title-row"><h2>${tool.title}</h2></div>
        <p>${tool.description}</p>
      </div>
    </div>
    ${toolForm(tool.id)}
    <div class="tool-result" data-tool-result="${tool.id}">
      ${toolPlaceholder(tool.id)}
    </div>
  </section>`;
}

function toolForm(toolId) {
  if (toolId === "essay") {
    return `<form class="tool-form" data-tool-form="essay">
      <div class="form-grid">
        <label class="field field-span-2">
          <span class="field-label">作文文本</span>
          <textarea class="input textarea essay-input" name="text" rows="8" maxlength="30000" placeholder="粘贴你的英语作文。也可以只上传作文图片。"></textarea>
          <span class="field-hint">支持纯文本或图片作为输入；图片识别依赖视觉模型。</span>
        </label>
        <div class="field field-span-2">
          <span class="field-label">或上传作文图片</span>
          <div data-essay-upload></div>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit" data-submit>${icon("sparkles")}<span>开始批改</span></button>
        <span class="form-caption">AI 会保留原文意思，不替你重写一篇超难度作文。</span>
      </div>
    </form>`;
  }
  if (toolId === "polish") {
    return `<form class="tool-form" data-tool-form="polish">
      <label class="field">
        <span class="field-label">需要润色的英文表达</span>
        <textarea class="input textarea" name="text" rows="6" maxlength="10000" placeholder="例如：I think this book is very good because it is very interesting."></textarea>
        <span class="field-hint">一句话或一段话都可以。请保留自己的表达意图。</span>
      </label>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit" data-submit>${icon("wand-sparkles")}<span>生成三个版本</span></button>
      </div>
    </form>`;
  }
  if (toolId === "sentence") {
    return `<form class="tool-form" data-tool-form="sentence">
      <label class="field">
        <span class="field-label">英文句子</span>
        <textarea class="input textarea" name="sentence" rows="4" maxlength="3000" placeholder="The book that I bought yesterday is very interesting."></textarea>
      </label>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit" data-submit>${icon("split")}<span>分析句子结构</span></button>
      </div>
    </form>`;
  }
  if (toolId === "grammar") {
    return `<form class="tool-form" data-tool-form="grammar">
      <label class="field">
        <span class="field-label">英语句子</span>
        <textarea class="input textarea" name="sentence" rows="4" maxlength="3000" placeholder="例如：He go to school yesterday."></textarea>
        <span class="field-hint">只分析你输入的句子；不会扩展成一段新的文章。</span>
      </label>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit" data-submit>${icon("search-check")}<span>诊断语法</span></button>
      </div>
    </form>`;
  }
  if (toolId === "questions") {
    return `<form class="tool-form" data-tool-form="questions">
      <div class="form-grid">
        <label class="field">
          <span class="field-label">学科 *</span>
          <input class="input" name="subject" required maxlength="30" placeholder="数学" value="数学">
        </label>
        <label class="field">
          <span class="field-label">知识点 *</span>
          <input class="input" name="topic" required maxlength="120" placeholder="例如：二次函数顶点式">
        </label>
        <label class="field">
          <span class="field-label">难度</span>
          <select class="input" name="difficulty">
            <option value="easy">简单</option>
            <option value="medium" selected>中等</option>
            <option value="hard">较难</option>
          </select>
        </label>
        <label class="field">
          <span class="field-label">题目数量</span>
          <select class="input" name="count">
            <option value="1">1 题</option>
            <option value="2">2 题</option>
            <option value="3" selected>3 题</option>
            <option value="5">5 题</option>
          </select>
        </label>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit" data-submit>${icon("list-plus")}<span>生成练习题</span></button>
        <span class="form-caption">生成的答案与解析也需要核对，不等于老师命题。</span>
      </div>
    </form>`;
  }
  return `<form class="tool-form" data-tool-form="grading">
    <div class="form-grid">
      <label class="field field-span-2">
        <span class="field-label">题目 *</span>
        <textarea class="input textarea" name="question" rows="3" required maxlength="10000" placeholder="输入主观题题目"></textarea>
      </label>
      <label class="field">
        <span class="field-label">参考答案 *</span>
        <textarea class="input textarea" name="reference_answer" rows="6" required maxlength="10000" placeholder="粘贴参考答案或得分点"></textarea>
      </label>
      <label class="field">
        <span class="field-label">学生答案</span>
        <textarea class="input textarea" name="student_answer" rows="6" maxlength="10000" placeholder="粘贴学生作答，可留空查看遗漏点"></textarea>
      </label>
      <label class="field">
        <span class="field-label">满分</span>
        <input class="input" type="number" name="max_score" min="1" max="1000" step="0.5" value="100">
      </label>
    </div>
    <div class="form-actions">
      <button class="btn btn-primary" type="submit" data-submit>${icon("clipboard-check")}<span>分析得分点</span></button>
      <span class="form-caption">仅供学习反馈，不替代老师的正式阅卷。</span>
    </div>
  </form>`;
}

function toolPlaceholder(toolId) {
  const messages = {
    essay: ["spell-check", "作文批改结果会显示在这里", "包含综合评价、逐条修改建议、修改后版本与结构分析。"],
    polish: ["wand-sparkles", "三个润色版本会显示在这里", "简单版、自然版、进阶版都会保留原意，并说明主要改动。"],
    sentence: ["split", "句子结构分析会显示在这里", "包含主句、从句、主谓宾、修饰成分与结构说明。"],
    grammar: ["search-check", "语法诊断结果会显示在这里", "明确错误、解释原因，并区分确定问题与需要人工确认的部分。"],
    questions: ["list-plus", "生成的练习会显示在这里", "题目、答案与解析都会给出。"],
    grading: ["clipboard-check", "得分点分析会显示在这里", "包含可能命中的得分点、遗漏点、建议与粗略估分。"],
  };
  const [iconName, title, description] = messages[toolId];
  return `<div class="tool-placeholder">
    <span class="tool-placeholder-icon">${icon(iconName)}</span>
    <div><strong>${title}</strong><p>${description}</p></div>
  </div>`;
}

function bindTabs(container) {
  container.querySelectorAll("[data-ai-tool]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTool = button.dataset.aiTool;
      container.querySelectorAll("[data-ai-tool]").forEach((item) => {
        const active = item.dataset.aiTool === activeTool;
        item.classList.toggle("is-active", active);
        item.setAttribute("aria-selected", String(active));
      });
      container.querySelectorAll("[data-tool-panel]").forEach((panel) => {
        const active = panel.dataset.toolPanel === activeTool;
        panel.classList.toggle("is-active", active);
        panel.hidden = !active;
      });
      refreshIcons(container);
    });
  });
}

function getResult(container, tool) {
  return container.querySelector(`[data-tool-result="${tool}"]`);
}

function setResultLoading(resultEl, tool, label = "AI 正在分析…") {
  resultEl.innerHTML = `<div class="tool-loading">
    <span class="spinner spinner-lg"></span>
    <strong>${escapeHTML(label)}</strong>
    <p>正在等待模型返回结构化结果。这可能需要几秒到一分钟。</p>
    <div class="tool-loading-steps"><span></span><span></span><span></span></div>
  </div>`;
}

function setResultError(resultEl, error) {
  const settingsHint =
    error?.code === "AI_NOT_CONFIGURED"
      ? ` <a href="#/settings" class="text-link">前往设置查看配置说明</a>`
      : "";
  resultEl.innerHTML = `<div class="ai-error-panel" role="alert">
    <span class="ai-error-icon">${icon("alert-circle")}</span>
    <div><strong>分析没有完成</strong><p>${escapeHTML(
      error?.message || "发生未知错误，请稍后重试。"
    )}</p><p class="muted-note">错误码：${escapeHTML(error?.code || "UNKNOWN")}${settingsHint}</p></div>
  </div>`;
  refreshIcons(resultEl);
}

async function performRequest({ key, button, resultEl, request, loadingLabel, renderResult }) {
  requests.get(key)?.abort();
  const requestController = new AbortController();
  requests.set(key, requestController);
  const original = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `<span class="spinner"></span><span>${escapeHTML(loadingLabel || "分析中…")}</span>`;
  setResultLoading(resultEl, key, loadingLabel);
  try {
    const response = await request(requestController.signal);
    renderResult(response.data, response.ai, resultEl);
    refreshIcons(resultEl);
  } catch (error) {
    if (error.name === "AbortError") return;
    setResultError(resultEl, error);
  } finally {
    requests.delete(key);
    button.disabled = false;
    button.innerHTML = original;
    refreshIcons(button);
  }
}

function validateText(value, message) {
  if (!String(value || "").trim()) {
    toastError(new Error(message));
    return false;
  }
  return true;
}

function bindEssay(container) {
  const form = container.querySelector('[data-tool-form="essay"]');
  const panel = form.closest("[data-tool-panel]");
  const resultEl = getResult(container, "essay");
  essayUploader = createImageUploader({
    label: "上传作文图片",
    hint: "支持 JPG / PNG / WebP，最大 8 MB。可只上传图片，也可同时粘贴文本。",
  });
  form.querySelector("[data-essay-upload]").appendChild(essayUploader.el);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = form.elements.text.value.trim();
    const file = essayUploader.getFile();
    if (!text && !file) {
      toastError(new Error("请输入作文文本或上传作文图片"));
      return;
    }
    const button = form.querySelector("[data-submit]");
    const perform = async (signal) => {
      let imageUrl = null;
      if (file) {
        setResultLoading(resultEl, "essay", "正在上传作文图片…");
        const uploadResponse = await api.upload(file, { signal });
        imageUrl = uploadResponse.data.url;
      }
      return api.post(
        "/ai/essay/review",
        { text: text || null, image_url: imageUrl },
        { signal, timeout: 120000 }
      );
    };
    await performRequest({
      key: "essay",
      button,
      resultEl,
      request: perform,
      loadingLabel: file ? "正在识别并批改作文…" : "正在批改作文…",
      renderResult: (data, ai) => {
        resultEl.innerHTML = renderEssayResult(data, ai);
        attachCopyButtons(resultEl);
        renderMarkdownNodes(resultEl);
      },
    });
  });
}

function renderEssayResult(data, ai) {
  const corrections = data.corrections || [];
  const certain = corrections.filter((item) => item.certainty === "certain");
  const review = corrections.filter((item) => item.certainty !== "certain");
  const correctionCard = (item) => `<article class="correction-card">
    <div class="correction-meta">
      <span class="category-tag">${escapeHTML(item.category || "其他")}</span>
      <span class="certainty-tag ${item.certainty === "certain" ? "is-certain" : "is-review"}">${
        item.certainty === "certain" ? "较明确错误" : "建议人工确认"
      }</span>
    </div>
    <div class="correction-text">
      <span class="original-text">${escapeHTML(item.original || "—")}</span>
      <span class="correction-arrow">${icon("arrow-right")}</span>
      <span class="suggested-text">${escapeHTML(item.suggestion || "—")}</span>
    </div>
    <p>${escapeHTML(item.explanation || "")}</p>
  </article>`;
  return `<div class="ai-result-content">
    ${aiBanner(ai)}
    <div class="essay-score-head">
      <div class="score-orb"><strong>${data.overall?.score ?? "—"}</strong><span>/ 100</span></div>
      <div class="essay-score-copy">
        <span class="overall-level">${escapeHTML(data.overall?.level || "评价")}</span>
        <h3>综合评价</h3>
        <p>${escapeHTML(data.overall?.summary || "")}</p>
        <span class="muted-note">${data.word_count || 0} 个英文单词 · ${
          corrections.length
        } 条反馈</span>
      </div>
    </div>
    ${
      data.recognized_text
        ? `<details class="result-details"><summary>${icon("scan-text")} 查看识别出的原文</summary><div class="pre-wrap-text">${escapeHTML(
            data.recognized_text
          )}</div></details>`
        : ""
    }
    <div class="essay-section">
      <div class="section-heading-row"><h3>逐条修改建议</h3><span class="count-badge">${corrections.length}</span></div>
      ${
        corrections.length
          ? `<div class="correction-groups">
              ${
                certain.length
                  ? `<div><p class="group-label"><span class="gen-dot is-certain"></span>较明确问题 · ${certain.length}</p>${certain
                      .map(correctionCard)
                      .join("")}</div>`
                  : ""
              }
              ${
                review.length
                  ? `<div><p class="group-label"><span class="gen-dot is-review"></span>建议核对 · ${review.length}</p>${review
                      .map(correctionCard)
                      .join("")}</div>`
                  : ""
              }
            </div>`
          : `<p class="muted-note">未发现明确错误。这不代表文章完美，仍需人工通读。</p>`
      }
    </div>
    <div class="essay-section">
      <div class="section-heading-row"><h3>修改后版本</h3><button type="button" class="btn btn-secondary btn-sm" data-copy="corrected">${icon("copy")} 复制</button></div>
      <div class="corrected-essay">${escapeHTML(data.corrected_text || "")}</div>
    </div>
    <div class="two-column-insights">
      ${renderStringGroup("文章结构 · 优点", data.structure?.strengths, "check")}
      ${renderStringGroup("文章结构 · 可改进", data.structure?.improvements, "arrow-up-right")}
      ${renderStringGroup("词汇使用 · 优点", data.word_usage?.strengths, "check")}
      ${renderStringGroup("词汇使用 · 可改进", data.word_usage?.improvements, "arrow-up-right")}
    </div>
    ${
      data.next_steps?.length
        ? `<div class="essay-section"><h3>下一步练习</h3><ol class="next-steps">${data.next_steps
            .map((item) => `<li>${escapeHTML(item)}</li>`)
            .join("")}</ol></div>`
        : ""
    }
    ${aiResultFooter(ai, { warnings: data.warnings })}
  </div>`;
}

function renderStringGroup(title, items, iconName = "check") {
  return `<div class="mini-insight-card">
    <h4>${icon(iconName)} ${escapeHTML(title)}</h4>
    ${
      items?.length
        ? `<ul>${items.map((item) => `<li>${escapeHTML(item)}</li>`).join("")}</ul>`
        : '<p class="muted-note">暂无</p>'
    }
  </div>`;
}

function bindPolish(container) {
  const form = container.querySelector('[data-tool-form="polish"]');
  const resultEl = getResult(container, "polish");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = form.elements.text.value.trim();
    if (!validateText(text, "请输入需要润色的英文表达")) return;
    const button = form.querySelector("[data-submit]");
    await performRequest({
      key: "polish",
      button,
      resultEl,
      request: (signal) => api.post("/ai/express/polish", { text }, { signal }),
      loadingLabel: "正在生成三个版本…",
      renderResult: (data, ai) => {
        resultEl.innerHTML = renderPolishResult(data, ai);
        attachCopyButtons(resultEl);
      },
    });
  });
}

function renderPolishResult(data, ai) {
  const versions = [
    { key: "simple", label: "简单版", tone: "simple", description: "保留原句结构，优先清楚" },
    { key: "natural", label: "自然版", tone: "natural", description: "更自然的中学生表达" },
    { key: "advanced", label: "进阶版", tone: "advanced", description: "小幅提升，不超纲" },
  ];
  return `<div class="ai-result-content">
    ${aiBanner(ai)}
    <p class="ai-summary-text">${escapeHTML(data.meaning_notes || "")}</p>
    <div class="polish-versions">
      ${versions
        .map((version) => {
          const item = data[version.key] || {};
          return `<article class="polish-card polish-${version.tone}">
            <div class="polish-card-head"><span class="version-badge">${version.label}</span><button type="button" class="icon-button" data-copy="${version.key}" title="复制 ${version.label}" aria-label="复制 ${version.label}">${icon("copy")}</button></div>
            <p class="polish-text">${escapeHTML(item.text || "—")}</p>
            <p class="polish-explanation">${escapeHTML(item.explanation || version.description)}</p>
          </article>`;
        })
        .join("")}
    </div>
    ${aiResultFooter(ai, { warnings: data.warnings })}
  </div>`;
}

function bindSentence(container) {
  const form = container.querySelector('[data-tool-form="sentence"]');
  const resultEl = getResult(container, "sentence");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const sentence = form.elements.sentence.value.trim();
    if (!validateText(sentence, "请输入要分析的英文句子")) return;
    const button = form.querySelector("[data-submit]");
    await performRequest({
      key: "sentence",
      button,
      resultEl,
      request: (signal) => api.post("/ai/sentence/analyze", { sentence }, { signal }),
      loadingLabel: "正在拆解句子结构…",
      renderResult: (data, ai) => {
        resultEl.innerHTML = renderSentenceResult(data, ai);
      },
    });
  });
}

function renderSentenceResult(data, ai) {
  const components = data.components || {};
  const clauses = data.clauses || [];
  return `<div class="ai-result-content">
    ${aiBanner(ai)}
    <div class="sentence-original">“${escapeHTML(data.original || "")}”</div>
    <div class="main-clause-card">
      <span class="eyebrow">MAIN CLAUSE · 主句</span>
      <strong>${escapeHTML(data.main_clause || "模型未识别出清晰主句")}</strong>
    </div>
    <div class="component-grid">
      <div class="component-cell"><span>主语</span><strong>${escapeHTML(components.subject || "—")}</strong></div>
      <div class="component-cell"><span>谓语</span><strong>${escapeHTML(components.predicate || "—")}</strong></div>
      <div class="component-cell"><span>宾语</span><strong>${escapeHTML(components.object || "—")}</strong></div>
      <div class="component-cell"><span>修饰成分</span><strong>${escapeHTML(
        [...(components.attributes || []), ...(components.adverbials || [])].join("；") || "—"
      )}</strong></div>
    </div>
    ${
      clauses.length
        ? `<div class="essay-section"><h3>从句与分句</h3><div class="clause-list">${clauses
            .map(
              (clause, index) => `<div class="clause-row">
                <span class="clause-index">${index + 1}</span>
                <div><span class="clause-type">${escapeHTML(clause.type)}</span><p>${escapeHTML(
                  clause.text
                )}</p><small>${escapeHTML(clause.function || "")}</small></div>
              </div>`
            )
            .join("")}</div></div>`
        : ""
    }
    <div class="essay-section">
      <h3>结构说明</h3>
      <p class="prose-text">${nl2br(data.structure_summary || "")}</p>
      ${
        data.translation
          ? `<div class="translation-box"><span>参考翻译</span><p>${escapeHTML(data.translation)}</p></div>`
          : ""
      }
    </div>
    ${
      data.key_points?.length
        ? `<div class="essay-section"><h3>理解关键点</h3><ul class="bullet-list">${data.key_points
            .map((item) => `<li>${icon("dot")} ${escapeHTML(item)}</li>`)
            .join("")}</ul></div>`
        : ""
    }
    ${data.caution ? `<div class="notice-box notice-info">${icon("info")} ${escapeHTML(data.caution)}</div>` : ""}
    ${aiResultFooter(ai, { warnings: data.warnings })}
  </div>`;
}

function bindGrammar(container) {
  const form = container.querySelector('[data-tool-form="grammar"]');
  const resultEl = getResult(container, "grammar");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const sentence = form.elements.sentence.value.trim();
    if (!validateText(sentence, "请输入要诊断的英语句子")) return;
    const button = form.querySelector("[data-submit]");
    await performRequest({
      key: "grammar",
      button,
      resultEl,
      request: (signal) => api.post("/ai/grammar/check", { sentence }, { signal }),
      loadingLabel: "正在检查语法…",
      renderResult: (data, ai) => {
        resultEl.innerHTML = renderGrammarResult(data, ai);
      },
    });
  });
}

function renderGrammarResult(data, ai) {
  return `<div class="ai-result-content">
    ${aiBanner(ai)}
    <div class="grammar-summary ${data.is_correct ? "is-correct" : "has-issues"}">
      <span>${icon(data.is_correct ? "check-circle-2" : "alert-circle")}</span>
      <div>
        <strong>${data.is_correct ? "未发现明显错误" : `发现 ${data.issues?.length || 0} 处可能问题`}</strong>
        <p>${escapeHTML(data.overall || "")}</p>
      </div>
    </div>
    <div class="grammar-compare">
      <div><span class="compare-label">原句</span><p>${escapeHTML(data.original || "")}</p></div>
      <div class="compare-arrow">${icon("arrow-right")}</div>
      <div><span class="compare-label accent">修改后</span><p>${escapeHTML(data.corrected_text || "")}</p></div>
    </div>
    ${
      data.issues?.length
        ? `<div class="grammar-issues">
            ${data.issues
              .map(
                (issue) => `<article class="grammar-issue">
                  <div class="correction-meta"><span class="category-tag">${escapeHTML(issue.type || "语法")}</span>
                    <span class="certainty-tag ${issue.certainty === "certain" ? "is-certain" : "is-review"}">${
                      issue.certainty === "certain" ? "较明确" : "需人工确认"
                    }</span></div>
                  <div class="correction-text"><span class="original-text">${escapeHTML(
                    issue.original
                  )}</span><span class="correction-arrow">→</span><span class="suggested-text">${escapeHTML(
                    issue.suggestion
                  )}</span></div>
                  <p>${escapeHTML(issue.explanation || "")}</p>
                </article>`
              )
              .join("")}
          </div>`
        : ""
    }
    ${aiResultFooter(ai, { warnings: data.warnings })}
  </div>`;
}

function bindQuestions(container) {
  const form = container.querySelector('[data-tool-form="questions"]');
  const resultEl = getResult(container, "questions");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const subject = String(formData.get("subject") || "").trim();
    const topic = String(formData.get("topic") || "").trim();
    if (!subject || !topic) {
      toastError(new Error("请填写学科和知识点"));
      return;
    }
    const button = form.querySelector("[data-submit]");
    await performRequest({
      key: "questions",
      button,
      resultEl,
      request: (signal) =>
        api.post(
          "/ai/questions/generate",
          {
            subject,
            topic,
            difficulty: formData.get("difficulty"),
            count: Number(formData.get("count") || 3),
          },
          { signal, timeout: 120000 }
        ),
      loadingLabel: "正在生成练习与解析…",
      renderResult: (data, ai) => {
        resultEl.innerHTML = renderQuestionsResult(data, ai);
        renderMarkdownNodes(resultEl);
      },
    });
  });
}

function renderQuestionsResult(data, ai) {
  return `<div class="ai-result-content">
    ${aiBanner(ai)}
    <div class="question-set-header">
      <div><span class="eyebrow">PRACTICE SET</span><h3>${escapeHTML(data.subject)} · ${escapeHTML(
        data.topic
      )}</h3><p>${escapeHTML(
        { easy: "简单", medium: "中等", hard: "较难" }[data.difficulty] || data.difficulty
      )} · ${data.questions?.length || 0} 道练习</p></div>
      <span class="question-count-badge">${data.questions?.length || 0}</span>
    </div>
    <div class="question-list">
      ${(data.questions || [])
        .map(
          (question) => `<article class="question-card">
            <div class="question-head"><span class="question-number">${question.number}</span><span class="question-type">${escapeHTML(
              question.type || "练习"
            )}</span></div>
            <div class="question-body" data-markdown-content="${escapeHTML(question.question)}"></div>
            ${
              question.options?.length
                ? `<div class="question-options">${question.options
                    .map((option) => `<p>${escapeHTML(option)}</p>`)
                    .join("")}</div>`
                : ""
            }
            <details class="answer-details">
              <summary>${icon("eye")} 查看答案与解析</summary>
              <div class="answer-content">
                <div class="answer-line"><span>答案</span><div class="answer-rich" data-markdown-content="${escapeHTML(
                  question.answer
                )}"></div></div>
                <div class="answer-line"><span>解析</span><div class="answer-rich" data-markdown-content="${escapeHTML(
                  question.explanation
                )}"></div></div>
              </div>
            </details>
          </article>`
        )
        .join("")}
    </div>
    ${aiResultFooter(ai, { warnings: data.warnings })}
  </div>`;
}

function bindGrading(container) {
  const form = container.querySelector('[data-tool-form="grading"]');
  const resultEl = getResult(container, "grading");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const question = String(formData.get("question") || "").trim();
    const reference = String(formData.get("reference_answer") || "").trim();
    if (!question || !reference) {
      toastError(new Error("请填写题目和参考答案"));
      return;
    }
    const button = form.querySelector("[data-submit]");
    await performRequest({
      key: "grading",
      button,
      resultEl,
      request: (signal) =>
        api.post(
          "/ai/grading/assist",
          {
            question,
            reference_answer: reference,
            student_answer: String(formData.get("student_answer") || "").trim(),
            max_score: Number(formData.get("max_score") || 100),
          },
          { signal, timeout: 120000 }
        ),
      loadingLabel: "正在分析得分点…",
      renderResult: (data, ai) => {
        resultEl.innerHTML = renderGradingResult(data, ai);
        renderMarkdownNodes(resultEl);
      },
    });
  });
}

function renderGradingResult(data, ai) {
  const percentage = data.max_score ? Math.round((data.score / data.max_score) * 100) : 0;
  return `<div class="ai-result-content">
    ${aiBanner(ai)}
    <div class="grading-score-row">
      <div class="score-orb grading-orb"><strong>${data.score}</strong><span>/ ${data.max_score}</span></div>
      <div class="grading-score-copy">
        <span class="overall-level">${escapeHTML(data.level || "粗略估算")}</span>
        <h3>${percentage}% 得分率</h3>
        <p>${escapeHTML(data.comment || "")}</p>
        <span class="muted-note">置信度：${escapeHTML(
          { high: "较高", medium: "中等", low: "低" }[data.confidence] || data.confidence || "低"
        )} · 仅供学习反馈</span>
      </div>
    </div>
    <div class="points-columns">
      <div class="points-card is-hit"><h4>${icon("check-circle-2")} 可能命中</h4>
        ${
          data.matched_points?.length
            ? `<ul>${data.matched_points
                .map((item) => `<li><strong>${escapeHTML(item.point)}</strong><p>${escapeHTML(item.evidence || "")}</p></li>`)
                .join("")}</ul>`
            : '<p class="muted-note">没有识别到明确命中的得分点。</p>'
        }
      </div>
      <div class="points-card is-missing"><h4>${icon("circle-alert")} 可能遗漏</h4>
        ${
          data.missing_points?.length
            ? `<ul>${data.missing_points
                .map((item) => `<li><strong>${escapeHTML(item.point)}</strong><p>${escapeHTML(item.suggestion || "")}</p></li>`)
                .join("")}</ul>`
            : '<p class="muted-note">没有发现明确的遗漏点。</p>'
        }
      </div>
    </div>
    ${
      data.improvement?.length
        ? `<div class="essay-section"><h3>下一次可以这样改</h3><ul class="bullet-list">${data.improvement
            .map((item) => `<li>${icon("arrow-right")} ${escapeHTML(item)}</li>`)
            .join("")}</ul></div>`
        : ""
    }
    ${aiResultFooter(ai, { warnings: data.warnings })}
  </div>`;
}

function attachCopyButtons(container) {
  container.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      let value = "";
      if (button.dataset.copy === "corrected") {
        value = container.querySelector(".corrected-essay")?.textContent || "";
      } else {
        const polishedCard = button.closest(".polish-card");
        value = polishedCard?.querySelector(".polish-text")?.textContent || "";
      }
      if (!value) return;
      try {
        await copyText(value);
        showToast("已复制到剪贴板");
      } catch {
        toastError(new Error("复制失败，请手动选择文本"));
      }
    });
  });
}

function renderMarkdownNodes(container) {
  container.querySelectorAll("[data-markdown-content]").forEach((node) => {
    const raw = node.dataset.markdownContent || "";
    renderRichMarkdown(node, raw);
    node.removeAttribute("data-markdown-content");
  });
}

function cleanup() {
  controller?.abort();
  controller = null;
  essayUploader = null;
  requests.forEach((requestController) => requestController.abort());
  requests.clear();
  pageRoot = null;
}

export default {
  title: "AI 工具箱",
  render: async function render(container) {
    controller?.abort();
    controller = new AbortController();
    activeTool = activeTool || "essay";
    renderPage(container);
  },
  cleanup,
};
