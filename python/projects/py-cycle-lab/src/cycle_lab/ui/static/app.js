let dashboard = null;
let compareSelected = new Set(["沪深300", "纳指100", "美债"]);
let compareGroup = "all";
let valuationFilter = "all";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function showToast(text) {
  const toast = $("#toast");
  toast.textContent = text;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 12000);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function linesFromTextarea(value) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function conditionObjects(lines) {
  return lines.map((line) => ({ label: line.replace(/^\[[ xX✓-]\]\s*/, ""), met: /^\[[xX✓]\]/.test(line) }));
}

function switchPage(pageId) {
  $$(".page").forEach((page) => page.classList.toggle("active", page.id === pageId));
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.page === pageId));
  const label = {
    overview: "总览",
    cycle: "周期",
    valuation: "估值",
    compare: "对比",
    scenario: "情景",
    watchlist: "观察清单",
    lab: "实验室",
    reports: "复盘",
    settings: "设置",
  }[pageId];
  $("#page-title").textContent = label || "总览";
}

function toneClass(tone) {
  return `tone-${tone || "neutral"}`;
}

function renderKpis(kpis) {
  $("#kpi-grid").innerHTML = kpis
    .map(
      (item) => `
      <article class="kpi-card ${toneClass(item.tone)}" data-action="kpi-detail" data-label="${escapeHtml(item.label)}">
        <div class="kpi-label">${escapeHtml(item.label)}</div>
        <div class="kpi-row">
          <div class="kpi-value">${escapeHtml(item.value)}</div>
          <div class="kpi-state">${escapeHtml(item.state)}</div>
        </div>
        <div class="kpi-meta">较上期 ${escapeHtml(item.delta)} · 可在估值/周期页查看证据</div>
      </article>
    `,
    )
    .join("");
}

function pathFor(values, width, height, pad = 18) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((value, index) => {
      const x = pad + (index / (values.length - 1)) * (width - pad * 2);
      const y = height - pad - ((value - min) / span) * (height - pad * 2);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function renderLineChart(target, series, options = {}) {
  const width = 560;
  const height = options.height || 210;
  const values = series.values || series.spread || [];
  if (!values.length) {
    target.innerHTML = `<div class="panel-subtitle">No chart data available</div>`;
    return;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const zero =
    min <= 0 && max >= 0
      ? `<line class="axis" x1="18" y1="${height - 18 - ((0 - min) / (max - min || 1)) * (height - 36)}" x2="${
          width - 18
        }" y2="${height - 18 - ((0 - min) / (max - min || 1)) * (height - 36)}" />`
      : "";
  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${options.label || "chart"}">
      <line class="axis" x1="18" y1="${height - 18}" x2="${width - 18}" y2="${height - 18}" />
      ${zero}
      <path class="${options.className || "line-spread"}" d="${pathFor(values, width, height)}" />
      <text x="18" y="18" fill="#6b7280" font-size="12">${escapeHtml(options.caption || "")}</text>
      <text x="${width - 18}" y="${height - 4}" text-anchor="end" fill="#9ca3af" font-size="11">
        ${series.dates[0].slice(0, 4)} - ${series.dates[series.dates.length - 1].slice(0, 4)}
      </text>
    </svg>
  `;
}

function renderRegimeChart(target, regime) {
  const width = 520;
  const height = 210;
  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="regime probability">
      <line class="axis" x1="18" y1="${height - 18}" x2="${width - 18}" y2="${height - 18}" />
      <path class="line-expansion" d="${pathFor(regime.expansion, width, height)}" />
      <path class="line-slowdown" d="${pathFor(regime.slowdown, width, height)}" />
      <path class="line-stress" d="${pathFor(regime.stress, width, height)}" />
      <text x="18" y="18" fill="#0f766e" font-size="12">Expansion</text>
      <text x="112" y="18" fill="#2563eb" font-size="12">Slowdown</text>
      <text x="210" y="18" fill="#dc2626" font-size="12">Stress</text>
      <text x="${width - 18}" y="${height - 4}" text-anchor="end" fill="#9ca3af" font-size="11">${escapeHtml(regime.current)}</text>
    </svg>
  `;
}

function levelDot(level) {
  return `<span class="status-dot dot-${level}"></span>`;
}

function renderRisks(risks) {
  $("#risk-list").innerHTML = risks
    .map(
      (item) => `
      <div class="risk-item" data-action="risk-detail" data-title="${escapeHtml(item.title)}">
        <div class="risk-title">${levelDot(item.level)}${escapeHtml(item.title)}</div>
        <div class="risk-detail">${escapeHtml(item.detail)}</div>
      </div>
    `,
    )
    .join("");
}

function scoreClass(value) {
  if (value === null || value === undefined) return "score-mid";
  if (value <= 35) return "score-good";
  if (value <= 60) return "score-mid";
  if (value <= 75) return "score-warn";
  return "score-risk";
}

function scoreCell(value) {
  const label = value === null || value === undefined ? "N/A" : `${value}%`;
  return `<td class="score-cell"><span class="score-pill ${scoreClass(value)}">${label}</span></td>`;
}

function renderAssetTable(target, assets) {
  target.innerHTML = `
    <thead>
      <tr>
        <th>资产</th><th>PE分位</th><th>PB分位</th><th>ERP</th><th>情绪</th><th>趋势</th><th>动作</th>
      </tr>
    </thead>
    <tbody>
      ${assets
        .map(
          (asset) => `
          <tr class="clickable-row" data-action="asset-detail" data-asset="${escapeHtml(asset.name)}">
            <td><strong>${escapeHtml(asset.name)}</strong></td>
            ${scoreCell(asset.pe)}
            ${scoreCell(asset.pb)}
            ${scoreCell(asset.erp)}
            ${scoreCell(asset.sentiment)}
            ${scoreCell(asset.trend)}
            <td><span class="chip neutral">${escapeHtml(asset.action || "观察")}</span></td>
          </tr>
        `,
        )
        .join("")}
    </tbody>
  `;
}

function conditionHtml(condition) {
  return `
    <div class="condition">
      <span class="check ${condition.met ? "met" : ""}">${condition.met ? "✓" : ""}</span>
      ${escapeHtml(condition.label)}
    </div>
  `;
}

function hypothesisCard(item, compact = false) {
  return `
    <article class="${compact ? "hypothesis-card" : "watch-card"}">
      <div class="hypothesis-head">
        <div>
          <div class="asset-name">${escapeHtml(item.asset)}</div>
          <div class="thesis">${escapeHtml(item.thesis)}</div>
        </div>
        <span class="chip caution">${escapeHtml(item.action)}</span>
      </div>
      ${(item.conditions || []).map(conditionHtml).join("")}
      ${
        compact
          ? ""
          : `
        <h4>风险清单</h4>
        <div class="thesis">${(item.risks || []).map((risk) => `· ${escapeHtml(risk)}`).join("<br />")}</div>
        ${item.review_notes ? `<h4>复盘备注</h4><div class="thesis">${escapeHtml(item.review_notes)}</div>` : ""}
        <div class="card-actions">
          <button class="tiny-button" data-action="edit-hypothesis" data-id="${item.hypothesis_id}">编辑</button>
          <button class="tiny-button" data-action="snapshot" data-id="${item.hypothesis_id}">保存证据快照</button>
          <button class="tiny-button" data-action="delete-hypothesis" data-id="${item.hypothesis_id}">删除</button>
        </div>
      `
      }
    </article>
  `;
}

function renderHypotheses(items) {
  $("#hypothesis-list").innerHTML = items.map((item) => hypothesisCard(item, true)).join("");
  $("#watchlist-board").innerHTML = items.map((item) => hypothesisCard(item, false)).join("");
}

function renderSnapshots(items) {
  const target = $("#snapshot-list");
  if (!items.length) {
    target.innerHTML = `<div class="timeline-item"><div class="timeline-body">还没有证据快照。点击观察清单里的“保存证据快照”开始留痕。</div></div>`;
    return;
  }
  target.innerHTML = items
    .slice(0, 8)
    .map(
      (item) => `
      <article class="timeline-item">
        <div class="timeline-meta">${escapeHtml(item.created_at)} · ${escapeHtml(item.state)}</div>
        <div class="timeline-title">Snapshot ${escapeHtml(item.snapshot_id)}</div>
        <div class="timeline-body">${escapeHtml(item.note || "保存当时的市场状态、资产分位和风险信号。")}</div>
      </article>
    `,
    )
    .join("");
}

function renderMetrics(target, metrics) {
  target.innerHTML = Object.entries(metrics || {})
    .map(([key, value]) => `<div class="metric-row"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
}

function renderLab(lab) {
  renderMetrics($("#sample-in"), lab.sample_in);
  renderMetrics($("#sample-out"), lab.sample_out);
  $("#lab-diagnosis").textContent = lab.diagnosis;
}

function renderExperiments(items) {
  $("#experiment-history").innerHTML = items
    .map(
      (item) => `
      <article class="timeline-item">
        <div class="timeline-meta">${escapeHtml(item.updated_at)} · ${escapeHtml(item.status)}</div>
        <div class="timeline-title">${escapeHtml(item.name)}</div>
        <div class="timeline-body">特征：${escapeHtml(item.features)}\n标签：${escapeHtml(item.label)}\nCV：${escapeHtml(item.cv_method)}\n诊断：${escapeHtml(item.diagnosis)}</div>
      </article>
    `,
    )
    .join("");
}

function renderBriefs(items) {
  $("#brief-history").innerHTML = items.length
    ? items
        .map(
          (item) => `
        <article class="timeline-item">
          <div class="timeline-meta">${escapeHtml(item.created_at)} · ${escapeHtml(item.source)}</div>
          <div class="timeline-title">${escapeHtml(item.title)}</div>
          <div class="timeline-body">${escapeHtml(item.content)}</div>
        </article>
      `,
        )
        .join("")
    : `<div class="timeline-item"><div class="timeline-body">还没有 LLM 简报。可在总览页生成。</div></div>`;
}

function renderReviews(items) {
  $("#review-history").innerHTML = items.length
    ? items
        .map(
          (item) => `
        <article class="timeline-item">
          <div class="timeline-meta">${escapeHtml(item.updated_at)} · ${escapeHtml(item.review_month)}</div>
          <div class="timeline-title">月度复盘</div>
          <div class="timeline-body">${escapeHtml(item.summary)}\n\n${(item.decisions || []).map((d) => `· ${d}`).join("\n")}</div>
        </article>
      `,
        )
        .join("")
    : `<div class="timeline-item"><div class="timeline-body">还没有月度复盘。</div></div>`;
}

function renderIntegrations(data) {
  const cards = [data.llm, data.psql]
    .map(
      (item) => `
      <article class="integration-card">
        <div class="hypothesis-head">
          <div class="asset-name">${escapeHtml(item.name)}</div>
          <span class="chip ${item.configured ? "opportunity" : "neutral"}">${escapeHtml(item.status)}</span>
        </div>
        <pre>${escapeHtml(JSON.stringify(item.details, null, 2))}</pre>
      </article>
    `,
    )
    .join("");
  $("#integration-grid").innerHTML = cards;
  if (dashboard?.storage) {
    $("#storage-card").innerHTML = `
      <article class="integration-card">
        <div class="asset-name">${escapeHtml(dashboard.storage.engine)}</div>
        <pre>${escapeHtml(dashboard.storage.path)}</pre>
      </article>
    `;
  }
  if ($("#refresh-status")) {
    const log = dashboard?.data_refresh;
    $("#refresh-status").innerHTML = log
      ? `
      <article class="timeline-item">
        <div class="timeline-meta">${escapeHtml(log.finished_at)} · ${escapeHtml(log.source)}</div>
        <div class="timeline-title">${escapeHtml(log.status)}</div>
        <div class="timeline-body">${escapeHtml(log.message || "")}</div>
      </article>
    `
      : `<div class="timeline-item"><div class="timeline-body">尚未刷新真实数据。</div></div>`;
  }
}

function openDrawer(eyebrow, title, bodyHtml) {
  $("#drawer-eyebrow").textContent = eyebrow;
  $("#drawer-title").textContent = title;
  $("#drawer-body").innerHTML = bodyHtml;
  $("#detail-drawer").classList.add("open");
  $("#detail-drawer").setAttribute("aria-hidden", "false");
}

function closeDrawer() {
  $("#detail-drawer").classList.remove("open");
  $("#detail-drawer").setAttribute("aria-hidden", "true");
}

function assetByName(name) {
  return (dashboard?.assets || []).find((asset) => asset.name === name);
}

function relatedHypotheses(assetName) {
  return (dashboard?.watchlist || []).filter((item) => item.asset.includes(assetName) || assetName.includes(item.asset.replace("ETF", "")));
}

function assetInterpretation(asset) {
  const rich = [];
  if (asset.pe !== null && asset.pe <= 35) rich.push("估值处于历史偏低区域，适合进入长期观察或分批关注。");
  if (asset.pe !== null && asset.pe >= 75) rich.push("估值处于偏高分位，需要避免把长期叙事误当成安全边际。");
  if (asset.sentiment >= 75) rich.push("情绪较拥挤，新增仓位需要更强的假设证据。");
  if (asset.erp >= 65) rich.push("相对风险溢价具备一定吸引力。");
  if (!rich.length) rich.push("当前处于中性区域，适合结合个人配置目标继续观察。");
  return rich.join("");
}

function openAssetDetail(name) {
  const asset = assetByName(name);
  if (!asset) return;
  const hypotheses = relatedHypotheses(asset.name);
  openDrawer(
    "Asset Detail",
    asset.name,
    `
      <div class="drawer-section">
        <div class="drawer-section-title">当前动作</div>
        <span class="chip neutral">${escapeHtml(asset.action || "观察")}</span>
        <div class="timeline-body" style="margin-top:10px">${escapeHtml(assetInterpretation(asset))}</div>
      </div>
      <div class="drawer-section">
        <div class="drawer-section-title">数据来源</div>
        <div class="timeline-body">${escapeHtml(asset.source || "unknown")}\n更新时间：${escapeHtml(asset.updated_at || "unknown")}</div>
      </div>
      <div class="mini-score-grid">
        <div class="mini-score"><span>PE分位</span><strong>${asset.pe ?? "N/A"}</strong></div>
        <div class="mini-score"><span>PB分位</span><strong>${asset.pb ?? "N/A"}</strong></div>
        <div class="mini-score"><span>ERP</span><strong>${asset.erp ?? "N/A"}</strong></div>
        <div class="mini-score"><span>情绪</span><strong>${asset.sentiment ?? "N/A"}</strong></div>
      </div>
      <div class="drawer-section">
        <div class="drawer-section-title">关联投资假设</div>
        ${
          hypotheses.length
            ? hypotheses.map((item) => `<div class="timeline-body">· ${escapeHtml(item.asset)}：${escapeHtml(item.thesis)}</div>`).join("")
            : `<div class="timeline-body">还没有关联假设。可以在观察清单中为该资产创建一条。</div>`
        }
      </div>
      <div class="button-row">
        <button class="secondary-button" data-action="compare-add" data-asset="${escapeHtml(asset.name)}">加入对比</button>
        <button class="secondary-button" data-action="new-hypothesis-for-asset" data-asset="${escapeHtml(asset.name)}">创建假设</button>
      </div>
    `,
  );
}

function openKpiDetail(label) {
  const mapping = {
    周期温度: ["周期", "收益率曲线、regime 概率、风险信号共同决定周期温度。", "cycle"],
    估值吸引力: ["估值", "PE/PB/ERP 等指标转为历史分位后形成长期机会评分。", "valuation"],
    情绪拥挤度: ["情绪", "情绪分位越高，短期拥挤风险越高，不代表长期价值消失。", "valuation"],
    现金吸引力: ["现金", "现金吸引力来自利率、风险资产估值和组合防守需求。", "compare"],
  };
  const item = mapping[label] || [label, "该指标由多个底层证据共同构成。", "overview"];
  openDrawer(
    "Score Decomposition",
    label,
    `
      <div class="drawer-section">
        <div class="drawer-section-title">${escapeHtml(item[0])}</div>
        <div class="timeline-body">${escapeHtml(item[1])}</div>
      </div>
      <div class="drawer-section">
        <div class="drawer-section-title">使用方式</div>
        <div class="timeline-body">把它当作状态识别，而不是预测信号。点击“进入模块”查看更完整证据链。</div>
      </div>
      <button class="primary-button" data-action="go-page" data-page="${item[2]}">进入模块</button>
    `,
  );
}

function openRiskDetail(title) {
  const item = (dashboard?.risk_signals || []).find((risk) => risk.title === title);
  if (!item) return;
  openDrawer(
    "Risk Evidence",
    item.title,
    `
      <div class="drawer-section">
        <div class="drawer-section-title">风险解释</div>
        <div class="timeline-body">${escapeHtml(item.detail)}</div>
      </div>
      <div class="drawer-section">
        <div class="drawer-section-title">产品动作</div>
        <div class="timeline-body">风险信号不会直接导出买卖建议。它用于提醒：新增仓位是否需要更高安全边际，观察清单假设是否需要复盘。</div>
      </div>
      <button class="secondary-button" data-action="go-page" data-page="cycle">查看周期证据</button>
    `,
  );
}

const periodDetails = {
  2000: {
    title: "2000: 高估值与曲线反转",
    body: "相似点：成长资产估值偏热，期限利差对后续风险重新定价给出提前信号。\n不同点：当前市场结构、政策工具和盈利集中度不同，不能机械套用。",
  },
  2006: {
    title: "2006: 信贷后周期",
    body: "相似点：期限利差压缩，资产价格对周期风险反应滞后。\n不同点：今天的资产负债表结构、银行体系压力和政策反应速度不同。",
  },
  2019: {
    title: "2019: 增长放缓与政策观察",
    body: "相似点：增长预期走弱，政策路径成为资产定价关键变量。\n不同点：当前通胀与利率背景更复杂。",
  },
};

function openPeriodDetail(period) {
  const item = periodDetails[period];
  if (!item) return;
  openDrawer(
    "Historical Similarity",
    item.title,
    `<div class="drawer-section"><div class="drawer-section-title">阶段解读</div><div class="timeline-body">${escapeHtml(item.body)}</div></div>`,
  );
}

function visibleAssets() {
  const assets = dashboard?.assets || [];
  if (valuationFilter === "equity") {
    return assets.filter((asset) => ["沪深300", "中证500", "纳指100", "标普500"].includes(asset.name));
  }
  if (valuationFilter === "defense") {
    return assets.filter((asset) => ["黄金", "美债", "现金"].includes(asset.name));
  }
  return assets;
}

function renderCompareSelector() {
  $("#compare-selector").innerHTML = (dashboard?.assets || [])
    .map(
      (asset) => `
      <button class="selector-pill ${compareSelected.has(asset.name) ? "active" : ""}" data-action="toggle-compare" data-asset="${escapeHtml(asset.name)}">
        ${escapeHtml(asset.name)}
      </button>
    `,
    )
    .join("");
}

function renderCompareTable() {
  const selected = (dashboard?.assets || []).filter((asset) => compareSelected.has(asset.name));
  const columnsByGroup = {
    all: ["pe", "pb", "erp", "sentiment", "trend"],
    valuation: ["pe", "pb", "erp"],
    sentiment: ["sentiment"],
    trend: ["trend"],
  };
  const labels = { pe: "PE分位", pb: "PB分位", erp: "ERP", sentiment: "情绪", trend: "趋势" };
  const columns = columnsByGroup[compareGroup] || columnsByGroup.all;
  $("#compare-table").innerHTML = `
    <thead><tr><th>资产</th>${columns.map((col) => `<th>${labels[col]}</th>`).join("")}<th>动作</th></tr></thead>
    <tbody>
      ${selected
        .map(
          (asset) => `
          <tr class="clickable-row" data-action="asset-detail" data-asset="${escapeHtml(asset.name)}">
            <td><strong>${escapeHtml(asset.name)}</strong></td>
            ${columns.map((col) => scoreCell(asset[col])).join("")}
            <td><span class="chip neutral">${escapeHtml(asset.action || "观察")}</span></td>
          </tr>
        `,
        )
        .join("")}
    </tbody>
  `;
  const cheap = selected.filter((asset) => asset.pe !== null && asset.pe <= 40).map((asset) => asset.name);
  const crowded = selected.filter((asset) => asset.sentiment >= 75).map((asset) => asset.name);
  $("#compare-insight").textContent = `解读：${cheap.length ? `${cheap.join("、")}估值更靠近观察/分批关注区。` : "所选资产估值未明显进入低分位。"} ${
    crowded.length ? `${crowded.join("、")}情绪偏拥挤，新增仓位需要更强纪律。` : "所选资产情绪拥挤度整体可控。"
  }`;
}

function renderCompare() {
  renderCompareSelector();
  renderCompareTable();
}

function actionForScenario(asset, rateShock, valuationShift, sentimentShift) {
  const pe = asset.pe === null ? null : Math.max(0, Math.min(100, asset.pe + valuationShift + Math.max(0, rateShock) / 25));
  const sentiment = Math.max(0, Math.min(100, (asset.sentiment ?? 50) + sentimentShift));
  if (pe !== null && pe <= 35 && sentiment <= 65) return "分批关注";
  if (sentiment >= 80 || (pe !== null && pe >= 78)) return "暂停追买";
  if (rateShock >= 75 && ["纳指100", "标普500"].includes(asset.name)) return "谨慎";
  return "观察";
}

function renderScenario() {
  const rateShock = Number($("#rate-shock").value);
  const valuationShift = Number($("#valuation-shift").value);
  const sentimentShift = Number($("#sentiment-shift").value);
  $("#rate-shock-label").textContent = `${rateShock >= 0 ? "+" : ""}${rateShock}bp`;
  $("#valuation-shift-label").textContent = `${valuationShift >= 0 ? "+" : ""}${valuationShift}`;
  $("#sentiment-shift-label").textContent = `${sentimentShift >= 0 ? "+" : ""}${sentimentShift}`;
  const assets = dashboard?.assets || [];
  $("#scenario-output").innerHTML = assets
    .map((asset) => {
      const next = actionForScenario(asset, rateShock, valuationShift, sentimentShift);
      return `
        <article class="timeline-item">
          <div class="timeline-title">${escapeHtml(asset.name)}</div>
          <div class="timeline-body">${escapeHtml(asset.action || "观察")} -> ${escapeHtml(next)}</div>
        </article>
      `;
    })
    .join("");
  const triggered = (dashboard?.watchlist || []).map((item) => {
    const matched = (item.conditions || []).filter((condition) => {
      const text = condition.label;
      return (sentimentShift < 0 && text.includes("情绪")) || (valuationShift < 0 && /PE|PB|估值/.test(text));
    });
    return { item, matched };
  });
  $("#scenario-triggers").innerHTML =
    triggered
      .filter((row) => row.matched.length)
      .map(
        (row) => `
        <article class="timeline-item">
          <div class="timeline-title">${escapeHtml(row.item.asset)}</div>
          <div class="timeline-body">${row.matched.map((condition) => `· ${escapeHtml(condition.label)}`).join("\n")}</div>
        </article>
      `,
      )
      .join("") || `<div class="timeline-item"><div class="timeline-body">当前情景未明显触发观察清单条件。</div></div>`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${path} failed with ${response.status}`);
  }
  return response.json();
}

async function loadIntegrations() {
  const data = await api("/api/integrations");
  renderIntegrations(data);
}

async function loadDashboard() {
  dashboard = await api("/api/dashboard");
  $("#freshness").textContent = `更新 ${dashboard.as_of}`;
  $("#market-state").textContent = dashboard.state;
  renderKpis(dashboard.kpis);
  renderLineChart($("#yield-chart"), dashboard.yield_curve, {
    caption: "10Y-2Y spread",
    className: "line-spread",
  });
  renderLineChart($("#cycle-yield-chart"), dashboard.yield_curve, {
    caption: "Yield curve spread and recession-risk context",
    className: "line-spread",
    height: 350,
  });
  renderRegimeChart($("#regime-chart"), dashboard.regime);
  renderRisks(dashboard.risk_signals);
  renderAssetTable($("#asset-table"), dashboard.assets);
  renderAssetTable($("#valuation-table"), visibleAssets());
  renderHypotheses(dashboard.watchlist);
  renderSnapshots(dashboard.snapshots || []);
  renderLab(dashboard.lab);
  renderBriefs(dashboard.briefs || []);
  renderReviews(dashboard.reviews || []);
  renderExperiments(await api("/api/experiments"));
  renderCompare();
  renderScenario();
}

function resetHypothesisForm() {
  $("#hypothesis-form-title").textContent = "新建投资假设";
  $("#hypothesis-id").value = "";
  $("#hypothesis-form").reset();
}

function editHypothesis(id) {
  const item = dashboard.watchlist.find((candidate) => candidate.hypothesis_id === id);
  if (!item) return;
  $("#hypothesis-form-title").textContent = `编辑：${item.asset}`;
  $("#hypothesis-id").value = item.hypothesis_id;
  $("#hypothesis-asset").value = item.asset;
  $("#hypothesis-action").value = item.action;
  $("#hypothesis-thesis").value = item.thesis;
  $("#hypothesis-conditions").value = (item.conditions || [])
    .map((condition) => `${condition.met ? "[x]" : "[ ]"} ${condition.label}`)
    .join("\n");
  $("#hypothesis-risks").value = (item.risks || []).join("\n");
  $("#hypothesis-notes").value = item.review_notes || "";
  switchPage("watchlist");
}

function newHypothesisForAsset(assetName) {
  resetHypothesisForm();
  $("#hypothesis-asset").value = `${assetName}ETF`;
  $("#hypothesis-thesis").value = `${assetName} 的长期配置价值需要结合估值、情绪和周期状态持续验证。`;
  $("#hypothesis-conditions").value = "[ ] 估值分位进入观察区\n[ ] 情绪未进入极端拥挤\n[ ] 周期风险没有继续恶化";
  $("#hypothesis-risks").value = "盈利预期下修\n利率或风险偏好变化\n估值继续压缩";
  closeDrawer();
  switchPage("watchlist");
}

async function saveHypothesis(event) {
  event.preventDefault();
  const id = $("#hypothesis-id").value;
  const payload = {
    asset: $("#hypothesis-asset").value,
    action: $("#hypothesis-action").value,
    thesis: $("#hypothesis-thesis").value,
    conditions: conditionObjects(linesFromTextarea($("#hypothesis-conditions").value)),
    risks: linesFromTextarea($("#hypothesis-risks").value),
    review_notes: $("#hypothesis-notes").value,
  };
  await api(id ? `/api/watchlist/${id}` : "/api/watchlist", {
    method: id ? "PUT" : "POST",
    body: JSON.stringify(payload),
  });
  resetHypothesisForm();
  await loadDashboard();
  showToast("投资假设已保存。");
}

async function createSnapshot(id) {
  const note = window.prompt("为这次证据快照写一句备注：", "保存当前周期、估值、情绪和风险状态。") || "";
  await api(`/api/watchlist/${id}/snapshots`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
  await loadDashboard();
  showToast("证据快照已保存。");
}

async function deleteHypothesis(id) {
  if (!window.confirm("确认删除这个投资假设及其快照？")) return;
  await api(`/api/watchlist/${id}`, { method: "DELETE" });
  await loadDashboard();
  showToast("投资假设已删除。");
}

async function saveExperiment(event) {
  event.preventDefault();
  await api("/api/experiments", {
    method: "POST",
    body: JSON.stringify({
      name: $("#experiment-name").value,
      features: $("#experiment-features").value,
      label: $("#experiment-label").value,
      cv_method: $("#experiment-cv").value,
      diagnosis: $("#experiment-diagnosis").value,
      status: "待验证",
    }),
  });
  await loadDashboard();
  showToast("实验记录已保存。");
}

async function saveReview(event) {
  event.preventDefault();
  await api("/api/reviews", {
    method: "POST",
    body: JSON.stringify({
      review_month: $("#review-month").value,
      summary: $("#review-summary").value,
      decisions: linesFromTextarea($("#review-decisions").value),
    }),
  });
  $("#review-form").reset();
  await loadDashboard();
  showToast("月度复盘已保存。");
}

async function generateBrief() {
  if (!dashboard) return;
  showToast("正在调用 LLM 生成研究简报...");
  const data = await api("/api/insight", {
    method: "POST",
    body: JSON.stringify(dashboard),
  });
  if (data.ok) {
    await loadDashboard();
    showToast(data.content);
  } else {
    showToast(data.error);
  }
}

async function refreshRealData() {
  showToast("正在刷新真实数据，可能需要几十秒...");
  const result = await api("/api/data/refresh", {
    method: "POST",
    body: JSON.stringify({ start_date: "20100101" }),
  });
  await loadDashboard();
  await loadIntegrations();
  showToast(result.ok ? `真实数据刷新完成：${result.as_of}，资产 ${result.assets} 个。` : `刷新失败：${result.error}`);
}

function bindEvents() {
  $$(".nav-item").forEach((item) => item.addEventListener("click", () => switchPage(item.dataset.page)));
  $("#ai-brief-button").addEventListener("click", generateBrief);
  $("#refresh-real-data-button")?.addEventListener("click", refreshRealData);
  $("#drawer-close")?.addEventListener("click", closeDrawer);
  $("#hypothesis-form").addEventListener("submit", saveHypothesis);
  $("#reset-hypothesis-form").addEventListener("click", resetHypothesisForm);
  $("#experiment-form").addEventListener("submit", saveExperiment);
  $("#review-form").addEventListener("submit", saveReview);
  ["#rate-shock", "#valuation-shift", "#sentiment-shift"].forEach((selector) => {
    $(selector)?.addEventListener("input", renderScenario);
  });
  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const id = button.dataset.id;
    if (button.dataset.action === "edit-hypothesis") editHypothesis(id);
    if (button.dataset.action === "snapshot") createSnapshot(id);
    if (button.dataset.action === "delete-hypothesis") deleteHypothesis(id);
    if (button.dataset.action === "asset-detail") openAssetDetail(button.dataset.asset);
    if (button.dataset.action === "risk-detail") openRiskDetail(button.dataset.title);
    if (button.dataset.action === "kpi-detail") openKpiDetail(button.dataset.label);
    if (button.dataset.action === "period-detail") openPeriodDetail(button.dataset.period);
    if (button.dataset.action === "go-page") {
      closeDrawer();
      switchPage(button.dataset.page);
    }
    if (button.dataset.action === "compare-add") {
      compareSelected.add(button.dataset.asset);
      closeDrawer();
      renderCompare();
      switchPage("compare");
    }
    if (button.dataset.action === "new-hypothesis-for-asset") newHypothesisForAsset(button.dataset.asset);
    if (button.dataset.action === "toggle-compare") {
      if (compareSelected.has(button.dataset.asset)) compareSelected.delete(button.dataset.asset);
      else compareSelected.add(button.dataset.asset);
      renderCompare();
    }
  });
  $("#valuation-filters")?.addEventListener("click", (event) => {
    const segment = event.target.closest("[data-filter]");
    if (!segment) return;
    valuationFilter = segment.dataset.filter;
    $$("#valuation-filters .segment").forEach((item) => item.classList.toggle("active", item === segment));
    renderAssetTable($("#valuation-table"), visibleAssets());
  });
  $("#compare-indicator-tabs")?.addEventListener("click", (event) => {
    const segment = event.target.closest("[data-group]");
    if (!segment) return;
    compareGroup = segment.dataset.group;
    $$("#compare-indicator-tabs .segment").forEach((item) => item.classList.toggle("active", item === segment));
    renderCompareTable();
  });
}

bindEvents();
loadDashboard()
  .then(loadIntegrations)
  .catch((error) => showToast(`Load failed: ${error}`));
