const formatNumber = (value) =>
  new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 0,
  }).format(Math.round(value));

const formatDateTime = (date) =>
  new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);

const formatTime = (date) =>
  new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);


const generateId = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `id-${Math.random().toString(16).slice(2)}-${Date.now()}`;
};

const createSampleHistory = () => {
  const now = Date.now();
  const records = [
    {
      id: "WS-10473",
      timestamp: new Date(now - 12 * 60 * 1000),
      plate: "А123ВС77",
      cargo: "Щебень",
      gross: 38620,
      tare: 10860,
      limit: 40000,
      driver: "Сергеев П. В.",
    },
    {
      id: "WS-10472",
      timestamp: new Date(now - 38 * 60 * 1000),
      plate: "Е904КХ99",
      cargo: "Металл",
      gross: 42850,
      tare: 11220,
      limit: 41000,
      driver: "Исаев А. П.",
    },
    {
      id: "WS-10471",
      timestamp: new Date(now - 68 * 60 * 1000),
      plate: "В562ОР50",
      cargo: "Песок",
      gross: 36410,
      tare: 9800,
      limit: 38000,
      driver: "Гришин С. К.",
    },
    {
      id: "WS-10470",
      timestamp: new Date(now - 96 * 60 * 1000),
      plate: "М311РС77",
      cargo: "Асфальт",
      gross: 41290,
      tare: 10220,
      limit: 39000,
      driver: "Белов В. И.",
    },
    {
      id: "WS-10469",
      timestamp: new Date(now - 152 * 60 * 1000),
      plate: "К145СО43",
      cargo: "Щепа",
      gross: 29840,
      tare: 8840,
      limit: 32000,
      driver: "Поляков С. И.",
    },
  ];

  return records.map((record) => {
    const net = record.gross - record.tare;
    const status = record.gross <= record.limit ? "normal" : "overload";
    return { ...record, net, status };
  });
};

const createSampleAlerts = () => {
  const now = Date.now();
  return [
    {
      id: generateId(),
      timestamp: new Date(now - 6 * 60 * 1000),
      text: "Сессия WS-10473 завершена без превышений",
      level: "info",
    },
    {
      id: generateId(),
      timestamp: new Date(now - 32 * 60 * 1000),
      text: "Внимание: перегруз по сеансу WS-10472 (+1 850 кг)",
      level: "warning",
    },
    {
      id: generateId(),
      timestamp: new Date(now - 80 * 60 * 1000),
      text: "Калибровка весов завершена успешно",
      level: "info",
    },
  ];
};

const state = {
  session: null,
  weightTimer: null,
  history: createSampleHistory(),
  alerts: createSampleAlerts(),
  filter: "all",
};

const refs = {
  form: document.getElementById("vehicleForm"),
  resetForm: document.getElementById("resetForm"),
  limitInput: document.getElementById("limit"),
  tareInput: document.getElementById("tare"),
  currentWeight: document.getElementById("currentWeight"),
  weightLimit: document.getElementById("weightLimit"),
  gaugeProgress: document.getElementById("gaugeProgress"),
  gaugeNeedle: document.getElementById("gaugeNeedle"),
  badge: document.getElementById("sessionBadge"),
  startBtn: document.getElementById("startBtn"),
  completeBtn: document.getElementById("completeBtn"),
  sessionId: document.getElementById("sessionId"),
  sessionStart: document.getElementById("sessionStart"),
  grossWeight: document.getElementById("grossWeight"),
  tareWeight: document.getElementById("tareWeight"),
  netWeight: document.getElementById("netWeight"),
  historyTable: document.getElementById("historyTable"),
  historyFilter: document.getElementById("historyFilter"),
  exportHistory: document.getElementById("exportHistory"),
  alertsList: document.getElementById("alertsList"),
  clearAlerts: document.getElementById("clearAlerts"),
  navLinks: document.querySelectorAll(".nav__link"),
};

const gaugeLength = refs.gaugeProgress.getTotalLength();
refs.gaugeProgress.style.strokeDasharray = `0 ${gaugeLength}`;

const updateBadge = (mode) => {
  const map = {
    idle: { text: "Ожидание", className: "badge--idle" },
    active: { text: "Идёт взвешивание", className: "badge--active" },
    success: { text: "Взвешивание завершено", className: "badge--success" },
    danger: { text: "Обнаружен перегруз", className: "badge--danger" },
  };

  const { text, className } = map[mode] ?? map.idle;
  refs.badge.textContent = text;
  refs.badge.className = `badge ${className}`;
};

const updateGauge = (weight, limit) => {
  const safeLimit = Math.max(limit || 1, 1);
  const ratio = Math.min(weight / safeLimit, 1.35);
  const dash = Math.max(ratio, 0) * gaugeLength;
  refs.gaugeProgress.style.strokeDasharray = `${dash} ${gaugeLength}`;
  const rotation = -90 + Math.min(ratio, 1.2) * 180;
  refs.gaugeNeedle.style.transform = `rotate(${rotation}deg)`;
  refs.currentWeight.textContent = formatNumber(weight);
  refs.weightLimit.textContent = formatNumber(safeLimit);
};

const renderHistory = () => {
  refs.historyTable.innerHTML = "";
  const fragment = document.createDocumentFragment();
  const template = document.getElementById("historyRowTemplate");

  state.history
    .filter((item) => {
      if (state.filter === "all") return true;
      return item.status === state.filter;
    })
    .sort((a, b) => b.timestamp - a.timestamp)
    .forEach((item) => {
      const row = template.content.cloneNode(true);
      const [date, id, plate, cargo, gross, net, status] = row.querySelectorAll(
        "td"
      );
      date.textContent = formatDateTime(item.timestamp);
      id.textContent = item.id;
      plate.textContent = item.plate;
      cargo.textContent = item.cargo;
      gross.textContent = `${formatNumber(item.gross)} кг`;
      net.textContent = `${formatNumber(item.net)} кг`;

      const pill = document.createElement("span");
      pill.classList.add("status-pill");
      if (item.status === "normal") {
        pill.classList.add("status-pill--ok");
        pill.textContent = "В норме";
      } else {
        pill.classList.add("status-pill--warn");
        pill.textContent = "Перегруз";
      }
      status.appendChild(pill);
      fragment.appendChild(row);
    });

  refs.historyTable.appendChild(fragment);
};

const renderAlerts = () => {
  refs.alertsList.innerHTML = "";
  const fragment = document.createDocumentFragment();
  const template = document.getElementById("alertTemplate");

  state.alerts
    .sort((a, b) => b.timestamp - a.timestamp)
    .forEach((alert) => {
      const item = template.content.firstElementChild.cloneNode(true);
      item.querySelector(".alert__time").textContent = formatTime(alert.timestamp);
      item.querySelector(".alert__text").textContent = alert.text;
      item.classList.remove("alert--info", "alert--warning");
      if (alert.level === "warning") {
        item.classList.add("alert--warning");
      } else {
        item.classList.add("alert--info");
      }
      fragment.appendChild(item);
    });

  if (!state.alerts.length) {
    const empty = document.createElement("li");
    empty.className = "alert alert--info";
    empty.textContent = "Нет активных событий";
    fragment.appendChild(empty);
  }

  refs.alertsList.appendChild(fragment);
};

const pushAlert = (text, level = "info") => {
  state.alerts.unshift({
    id: generateId(),
    timestamp: new Date(),
    text,
    level,
  });
  renderAlerts();
};

const resetMetrics = () => {
  refs.sessionId.textContent = "—";
  refs.sessionStart.textContent = "—";
  refs.grossWeight.textContent = "0 кг";
  refs.netWeight.textContent = "0 кг";
  refs.tareWeight.textContent = "0 кг";
  updateGauge(0, Number(refs.limitInput.value) || 40000);
};

const stopSimulation = () => {
  if (state.weightTimer) {
    clearInterval(state.weightTimer);
    state.weightTimer = null;
  }
};

const simulateWeight = () => {
  if (!state.session) return;
  const { targetGross } = state.session;

  state.weightTimer = setInterval(() => {
    if (!state.session) return;
    const diff = targetGross - state.session.currentWeight;
    const step = Math.max(diff * 0.18, 150);
    const noise = Math.random() * 120;
    state.session.currentWeight = Math.min(
      targetGross,
      state.session.currentWeight + step + noise
    );
    refs.grossWeight.textContent = `${formatNumber(state.session.currentWeight)} кг`;
    const tare = state.session.tare || 0;
    refs.tareWeight.textContent = `${formatNumber(tare)} кг`;
    const net = Math.max(state.session.currentWeight - tare, 0);
    refs.netWeight.textContent = `${formatNumber(net)} кг`;
    updateGauge(state.session.currentWeight, state.session.limit);

    if (Math.abs(targetGross - state.session.currentWeight) < 50) {
      stopSimulation();
    }
  }, 600);
};

const startSession = () => {
  if (!refs.form.reportValidity() || state.session) return;

  const data = new FormData(refs.form);
  const tare = Number(data.get("tare")) || 0;
  const limit = Number(data.get("limit")) || 40000;
  const session = {
    id: `WS-${Math.floor(Math.random() * 100000)}`,
    plate: (data.get("plate") || "").toUpperCase(),
    driver: data.get("driver") || "—",
    cargo: data.get("cargo") || "—",
    notes: data.get("notes") || "",
    tare,
    limit,
    start: new Date(),
    targetGross: limit * (0.75 + Math.random() * 0.45),
    currentWeight: 0,
  };

  state.session = session;
  refs.sessionId.textContent = session.id;
  refs.sessionStart.textContent = formatDateTime(session.start);
  refs.tareWeight.textContent = `${formatNumber(tare)} кг`;
  updateGauge(0, limit);
  updateBadge("active");
  refs.startBtn.disabled = true;
  refs.completeBtn.disabled = false;
  simulateWeight();
  pushAlert(`Начато взвешивание ${session.plate} (${session.id})`);
};

const finishSession = () => {
  if (!state.session) return;
  stopSimulation();
  const session = state.session;
  const gross = Math.round(session.currentWeight || session.targetGross);
  const tare = session.tare || 0;
  const net = Math.max(gross - tare, 0);
  const status = gross <= session.limit ? "normal" : "overload";

  state.history.push({
    id: session.id,
    timestamp: new Date(),
    plate: session.plate,
    cargo: session.cargo,
    gross,
    tare,
    net,
    limit: session.limit,
    status,
  });

  renderHistory();
  updateBadge(status === "normal" ? "success" : "danger");
  refs.startBtn.disabled = false;
  refs.completeBtn.disabled = true;
  pushAlert(
    status === "normal"
      ? `Сессия ${session.id} завершена. Перегруз не обнаружен.`
      : `Перегруз по сессии ${session.id}: превышение ${formatNumber(
          gross - session.limit
        )} кг`,
    status === "normal" ? "info" : "warning"
  );

  state.session = null;
  setTimeout(() => {
    resetMetrics();
    updateBadge("idle");
  }, 2500);
};

const resetForm = () => {
  if (state.session) return;
  refs.form.reset();
  const defaultLimit = 40000;
  refs.limitInput.value = defaultLimit;
  refs.tareWeight.textContent = `${formatNumber(0)} кг`;
  refs.netWeight.textContent = `${formatNumber(0)} кг`;
  updateGauge(0, defaultLimit);
};

const exportHistory = () => {
  if (!state.history.length) return;
  const header = [
    "Дата",
    "Номер",
    "Госномер",
    "Груз",
    "Брутто, кг",
    "Тара, кг",
    "Нетто, кг",
    "Статус",
  ];

  const rows = state.history
    .sort((a, b) => b.timestamp - a.timestamp)
    .map((item) => [
      formatDateTime(item.timestamp),
      item.id,
      item.plate,
      item.cargo,
      formatNumber(item.gross),
      formatNumber(item.tare),
      formatNumber(item.net),
      item.status === "normal" ? "В норме" : "Перегруз",
    ]);

  const csv = [header, ...rows]
    .map((row) => row.map((cell) => `"${cell}"`).join(";"))
    .join("\n");

  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `weighing-history-${Date.now()}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const initNavigation = () => {
  refs.navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      refs.navLinks.forEach((item) => item.classList.remove("active"));
      link.classList.add("active");
    });
  });
};

const init = () => {
  resetMetrics();
  renderHistory();
  renderAlerts();
  updateBadge("idle");
  initNavigation();

  refs.startBtn.addEventListener("click", startSession);
  refs.completeBtn.addEventListener("click", finishSession);
  refs.resetForm.addEventListener("click", resetForm);
  refs.tareInput.addEventListener("input", (event) => {
    const value = Number(event.target.value);
    const tare = value > 0 ? value : 0;
    if (state.session) {
      state.session.tare = tare;
      const net = Math.max((state.session.currentWeight ?? 0) - tare, 0);
      refs.tareWeight.textContent = `${formatNumber(tare)} кг`;
      refs.netWeight.textContent = `${formatNumber(net)} кг`;
    } else {
      refs.tareWeight.textContent = `${formatNumber(tare)} кг`;
      refs.netWeight.textContent = `${formatNumber(0)} кг`;
    }
  });

  refs.limitInput.addEventListener("input", (event) => {
    const value = Number(event.target.value);
    const limit = value > 0 ? value : 40000;
    if (state.session) {
      state.session.limit = limit;
    }
    updateGauge(state.session?.currentWeight ?? 0, limit);
  });
  refs.historyFilter.addEventListener("change", (event) => {
    state.filter = event.target.value;
    renderHistory();
  });
  refs.exportHistory.addEventListener("click", exportHistory);
  refs.clearAlerts.addEventListener("click", () => {
    state.alerts = [];
    renderAlerts();
  });
};

document.addEventListener("DOMContentLoaded", init);
