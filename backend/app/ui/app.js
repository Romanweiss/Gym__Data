const API_BASE = "/api";

const STANDARD_MEASUREMENTS = [
  { type: "body_weight", label: "Body weight", unit: "kg" },
  { type: "waist", label: "Waist", unit: "cm" },
  { type: "chest", label: "Chest", unit: "cm" },
  { type: "biceps", label: "Biceps", unit: "cm" },
  { type: "shoulders", label: "Shoulders", unit: "cm" },
  { type: "neck", label: "Neck", unit: "cm" },
  { type: "hips", label: "Hips", unit: "cm" },
  { type: "thigh", label: "Thigh", unit: "cm" },
  { type: "calf", label: "Calf", unit: "cm" },
  { type: "forearm", label: "Forearm", unit: "cm" },
];

document.addEventListener("DOMContentLoaded", () => {
  wireNavigation();
  renderMeasurementInputs();
  setDefaultMeasuredAt();
  wireMeasurementForm();
  loadWorkspace().catch((error) => showWorkspaceError(error));
});

function wireNavigation() {
  const buttons = document.querySelectorAll(".nav-link");
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");

      const targetView = button.dataset.view;
      document.querySelectorAll(".view").forEach((view) => {
        view.classList.toggle("active", view.dataset.view === targetView);
      });
    });
  });
}

function renderMeasurementInputs() {
  const container = document.getElementById("measurement-inputs");
  container.innerHTML = STANDARD_MEASUREMENTS.map(
    (measurement) => `
      <div class="measurement-input-row">
        <label>
          ${measurement.label}
          <input data-measurement-type="${measurement.type}" data-unit="${measurement.unit}" type="number" step="0.1" min="0" placeholder="Enter ${measurement.label.toLowerCase()}" />
        </label>
        <label>
          Unit
          <input type="text" value="${measurement.unit}" disabled />
        </label>
        <label>
          Raw note
          <input data-measurement-raw="${measurement.type}" type="text" placeholder="Optional raw value" />
        </label>
      </div>
    `,
  ).join("");
}

function setDefaultMeasuredAt() {
  const input = document.getElementById("measured-at");
  if (!input) {
    return;
  }
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  input.value = now.toISOString().slice(0, 16);
}

function wireMeasurementForm() {
  const form = document.getElementById("measurement-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = document.getElementById("measurement-form-message");
    message.textContent = "Saving measurement session...";

    const measuredAt = document.getElementById("measured-at").value;
    const notes = document.getElementById("measurement-notes").value || null;
    const contextTimeOfDay = document.getElementById("context-time-of-day").value;
    const fastingState = document.getElementById("fasting-state").checked;
    const beforeTraining = document.getElementById("before-training").checked;

    const measurements = STANDARD_MEASUREMENTS.map((measurement) => {
      const input = document.querySelector(`[data-measurement-type="${measurement.type}"]`);
      const rawInput = document.querySelector(`[data-measurement-raw="${measurement.type}"]`);
      const value = input.value === "" ? null : Number(input.value);
      if (value === null || Number.isNaN(value)) {
        return null;
      }
      return {
        measurement_type: measurement.type,
        value_numeric: value,
        unit: measurement.unit,
        raw_value: rawInput.value || null,
      };
    }).filter(Boolean);

    if (!measurements.length) {
      message.textContent = "Enter at least one measurement value before saving.";
      return;
    }

    const payload = {
      measured_at: measuredAt,
      measured_date: measuredAt.slice(0, 10),
      context_time_of_day: contextTimeOfDay,
      fasting_state: fastingState,
      before_training: beforeTraining,
      notes,
      measurements,
    };

    try {
      const response = await fetch(`${API_BASE}/measurements/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Measurement session save failed.");
      }
      message.textContent = `Saved ${data.measurement_session.measurement_session_id}. Reloading workspace...`;
      form.reset();
      setDefaultMeasuredAt();
      await loadWorkspace();
      await loadMeasurementDetail(data.measurement_session.measurement_session_id);
    } catch (error) {
      message.textContent = error.message;
    }
  });
}

async function loadWorkspace() {
  setWorkspaceStatus("Loading overview, measurements, and progress...");
  const [overview, highlights, measurements, latest, timeline] = await Promise.all([
    fetchJson(`${API_BASE}/profile/current/overview`),
    fetchJson(`${API_BASE}/profile/current/progress-highlights`),
    fetchJson(`${API_BASE}/measurements/?limit=20`),
    fetchJson(`${API_BASE}/measurements/latest`),
    fetchJson(`${API_BASE}/profile/current/timeline?limit=20`),
  ]);

  renderOverview(overview, highlights);
  renderMeasurements(measurements);
  renderProgress(latest, timeline);
  setWorkspaceStatus("Workspace ready.");
}

function renderOverview(overview, highlights) {
  const overdue = overview.measurement_overdue;
  const overduePill = document.getElementById("overdue-pill");
  overduePill.textContent = overdue.recommended_now
    ? `Measurement recommended now (${overdue.days_since_last_measurement} days)`
    : `Measurement cadence healthy (${overdue.days_since_last_measurement} days)`;
  overduePill.className = `pill ${overdue.recommended_now ? "warn" : "ok"}`;

  const cards = [
    metricCard("Latest workout", overview.latest_workout?.workout_date || "n/a", overview.latest_workout?.title_raw || "No workout yet"),
    metricCard("Latest measurement", overview.latest_measurement?.measured_date || "n/a", overview.latest_measurement?.measurement_session_id || "No measurement yet"),
    metricCard("Body weight", formatLatestMeasurement(highlights.measurement_highlights.body_weight), deltaText(highlights.measurement_highlights.body_weight)),
    metricCard("Waist", formatLatestMeasurement(highlights.measurement_highlights.waist), deltaText(highlights.measurement_highlights.waist)),
    metricCard("Chest", formatLatestMeasurement(highlights.measurement_highlights.chest), deltaText(highlights.measurement_highlights.chest)),
    metricCard("Biceps", formatLatestMeasurement(highlights.measurement_highlights.biceps), deltaText(highlights.measurement_highlights.biceps)),
  ];
  document.getElementById("overview-cards").innerHTML = cards.join("");

  renderList(
    document.getElementById("recent-workouts"),
    overview.recent_workouts.map(
      (item) => `
        <div class="list-item">
          <strong>${item.workout_date}</strong>
          <div class="list-meta">${item.title_raw}</div>
          <div class="muted">${item.set_count} sets · ${Number(item.total_volume_kg || 0).toFixed(1)} kg volume</div>
        </div>
      `,
    ),
    "No recent workouts.",
  );

  renderList(
    document.getElementById("recent-measurements"),
    overview.recent_measurements.map(
      (item) => `
        <div class="list-item">
          <strong>${item.measured_date}</strong>
          <div class="list-meta">${item.measurement_session_id}</div>
          <div class="muted">${item.measurement_value_count} values${item.body_weight_value ? ` · ${item.body_weight_value} ${item.body_weight_unit}` : ""}</div>
        </div>
      `,
    ),
    "No recent measurements.",
  );

  const weeklySnapshot = overview.weekly_workout_load_snapshot;
  document.getElementById("weekly-load-snapshot").innerHTML = weeklySnapshot
    ? `
        <strong>Week of ${weeklySnapshot.week_start}</strong>
        <div class="muted">${weeklySnapshot.workouts_total} workouts · ${weeklySnapshot.set_count} sets · ${weeklySnapshot.total_reps} reps</div>
        <div class="muted">${Number(weeklySnapshot.total_volume_kg || 0).toFixed(1)} kg total volume</div>
        <div class="muted">${weeklySnapshot.cardio_minutes} cardio min · ${weeklySnapshot.recovery_minutes} recovery min</div>
      `
    : '<div class="empty-state">No weekly load data available.</div>';

  const highlightCards = Object.entries(highlights.measurement_highlights).map(([key, value]) => {
    const label = STANDARD_MEASUREMENTS.find((item) => item.type === key)?.label || key;
    return metricCard(label, formatLatestMeasurement(value), deltaText(value));
  });
  document.getElementById("progress-highlights").innerHTML = highlightCards.join("");
}

function renderMeasurements(measurementsResponse) {
  const list = document.getElementById("measurement-session-list");
  const items = measurementsResponse.items || [];
  if (!items.length) {
    list.innerHTML = '<div class="empty-state">No measurement sessions available.</div>';
    document.getElementById("measurement-session-detail").innerHTML = "No measurement detail available.";
    return;
  }

  list.innerHTML = items.map(
    (item) => `
      <div class="list-item">
        <button type="button" data-session-id="${item.measurement_session_id}">
          <strong>${item.measured_date}</strong>
          <div class="list-meta">${item.measurement_session_id}</div>
          <div class="muted">${item.measurement_value_count} values${item.body_weight_value ? ` · ${item.body_weight_value} ${item.body_weight_unit}` : ""}</div>
        </button>
      </div>
    `,
  ).join("");

  list.querySelectorAll("[data-session-id]").forEach((button) => {
    button.addEventListener("click", () => loadMeasurementDetail(button.dataset.sessionId));
  });

  loadMeasurementDetail(items[0].measurement_session_id).catch((error) => {
    document.getElementById("measurement-session-detail").textContent = error.message;
  });
}

async function loadMeasurementDetail(measurementSessionId) {
  const detail = await fetchJson(`${API_BASE}/measurements/${measurementSessionId}`);
  document.getElementById("measurement-session-detail").innerHTML = `
    <strong>${detail.measured_date}</strong>
    <div class="muted">${detail.measurement_session_id} · ${detail.context_time_of_day}</div>
    <div class="muted">${detail.notes || "No notes."}</div>
    <div class="grid mini-cards">
      ${detail.measurements.map((item) => metricCard(
        labelForMeasurement(item.measurement_type_canonical),
        `${item.value_numeric} ${item.unit}`,
        item.delta_value_numeric || item.parse_note || item.measurement_type_raw,
      )).join("")}
    </div>
  `;
}

function renderProgress(latestResponse, timelineResponse) {
  const select = document.getElementById("custom-measurement-select");
  const latestItems = latestResponse.items || [];
  const measurementTypes = latestItems.map((item) => item.measurement_type_canonical);
  select.innerHTML = measurementTypes.map(
    (type) => `<option value="${type}">${labelForMeasurement(type)}</option>`,
  ).join("");

  renderTimeline(timelineResponse.items || []);

  const defaultCharts = ["body_weight", "waist", "chest", "biceps"];
  Promise.all(defaultCharts.map((type) => fetchJson(`${API_BASE}/measurements/progress?measurement_type=${encodeURIComponent(type)}`)))
    .then((responses) => {
      const chartCards = responses.map((response, index) => renderChartCard(defaultCharts[index], response.items || []));
      document.getElementById("progress-charts").innerHTML = chartCards.join("");
      defaultCharts.forEach((type) => renderChartSvg(type, responses[defaultCharts.indexOf(type)].items || []));
    });

  select.addEventListener("change", async () => {
    const response = await fetchJson(`${API_BASE}/measurements/progress?measurement_type=${encodeURIComponent(select.value)}`);
    const customCardId = "custom-measurement-chart";
    let container = document.getElementById(customCardId);
    if (!container) {
      document.getElementById("progress-charts").insertAdjacentHTML("beforeend", renderChartCard(select.value, response.items || [], customCardId));
      container = document.getElementById(customCardId);
    } else {
      container.outerHTML = renderChartCard(select.value, response.items || [], customCardId);
    }
    renderChartSvg(customCardId, response.items || []);
  });

  if (measurementTypes.length) {
    select.value = measurementTypes[0];
    select.dispatchEvent(new Event("change"));
  }
}

function renderTimeline(items) {
  renderList(
    document.getElementById("profile-timeline"),
    items.map((item) => `
      <div class="timeline-item">
        <strong>${item.event_date} · ${item.event_type === "workout" ? "Workout" : "Measurement"}</strong>
        <div class="timeline-meta">${item.title}</div>
        <div class="muted">${summarizeTimelineItem(item)}</div>
      </div>
    `),
    "Timeline is empty.",
  );
}

function renderChartCard(measurementType, items, cardId = measurementType) {
  const latest = items[items.length - 1];
  return `
    <div class="chart-card" id="${cardId}">
      <h3>${labelForMeasurement(measurementType)}</h3>
      <div class="chart-meta">
        <span>${latest ? `${latest.value_numeric} ${latest.unit}` : "No data"}</span>
        <span>${latest?.delta_value_numeric ?? "n/a"} delta</span>
      </div>
      <svg class="chart-svg" data-chart-target="${cardId}"></svg>
    </div>
  `;
}

function renderChartSvg(targetId, items) {
  const svg = document.querySelector(`[data-chart-target="${targetId}"]`);
  if (!svg) {
    return;
  }
  const width = 320;
  const height = 200;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  if (!items.length) {
    svg.innerHTML = `<text x="24" y="100" fill="#5a6764">No data for this series yet.</text>`;
    return;
  }

  const values = items.map((item) => Number(item.value_numeric));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  const points = items.map((item, index) => {
    const x = 24 + (index * (width - 48)) / Math.max(items.length - 1, 1);
    const normalized = (Number(item.value_numeric) - min) / span;
    const y = height - 28 - normalized * (height - 56);
    return { x, y, label: item.measured_date, value: item.value_numeric };
  });

  const polyline = points.map((point) => `${point.x},${point.y}`).join(" ");
  const dots = points.map((point) => `
    <circle class="chart-dot" cx="${point.x}" cy="${point.y}" r="4"></circle>
  `).join("");

  svg.innerHTML = `
    <polyline class="chart-line" points="${polyline}"></polyline>
    ${dots}
    <text x="24" y="20" fill="#5a6764">${min.toFixed(1)}</text>
    <text x="${width - 64}" y="20" fill="#5a6764">${max.toFixed(1)}</text>
  `;
}

function renderList(container, items, emptyText) {
  container.innerHTML = items.length ? items.join("") : `<div class="empty-state">${emptyText}</div>`;
}

function metricCard(label, value, subvalue) {
  return `
    <div class="metric-card">
      <div class="label">${label}</div>
      <div class="value">${value || "n/a"}</div>
      <div class="subvalue">${subvalue || ""}</div>
    </div>
  `;
}

function formatLatestMeasurement(item) {
  if (!item) {
    return "n/a";
  }
  return `${item.latest_value_numeric} ${item.unit}`;
}

function deltaText(item) {
  if (!item || item.delta_value_numeric === null || item.delta_value_numeric === undefined) {
    return "No previous value";
  }
  const sign = item.delta_value_numeric > 0 ? "+" : "";
  return `${sign}${item.delta_value_numeric} vs previous`;
}

function summarizeTimelineItem(item) {
  if (item.event_type === "measurement_session") {
    const bodyWeight = item.summary.body_weight_value
      ? `${item.summary.body_weight_value} ${item.summary.body_weight_unit}`
      : "no body weight";
    return `${item.summary.measurement_value_count} values · ${bodyWeight}`;
  }
  const split = Array.isArray(item.summary.split_normalized)
    ? item.summary.split_normalized.join(", ")
    : "";
  return `${item.summary.source_quality}${split ? ` · ${split}` : ""}`;
}

function labelForMeasurement(type) {
  return STANDARD_MEASUREMENTS.find((item) => item.type === type)?.label || type;
}

function setWorkspaceStatus(message) {
  const node = document.getElementById("workspace-status");
  if (node) {
    node.textContent = message;
  }
}

function showWorkspaceError(error) {
  setWorkspaceStatus(error.message);
  const node = document.getElementById("overview-cards");
  if (node) {
    node.innerHTML = `<div class="metric-card"><div class="label">Workspace error</div><div class="value">Cannot load data</div><div class="subvalue">${error.message}</div></div>`;
  }
}

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `Request failed for ${url}`);
  }
  return data;
}
