let latestData = null;
let historyData = null;
let chart = null;

const ALL_ORGANIZERS = "__all__";
const UNKNOWN_ORGANIZER = "Organisateur inconnu";

async function loadJson(path) {
  const response = await fetch(path, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Impossible de charger ${path}`);
  }

  return response.json();
}

async function init() {
  latestData = await loadJson("./data/latest.json");
  historyData = await loadJson("./data/history.json");

  document
    .getElementById("organizer-select")
    .addEventListener("change", () => {
      populateEvents();
      renderAll();
    });

  document
    .getElementById("event-select")
    .addEventListener("change", renderAll);

  populateOrganizers();
  populateEvents();
  renderAll();
  updateLastUpdate();
}

function getEventUrls(organizer = ALL_ORGANIZERS) {
  const eventUrls = new Set([
    ...Object.keys(latestData.events || {}),
    ...Object.keys(historyData.events || {})
  ]);

  return [...eventUrls].sort((a, b) =>
    simplifyEventName(a).localeCompare(simplifyEventName(b), "fr")
  ).filter(eventUrl =>
    organizer === ALL_ORGANIZERS ||
    getEventOrganizers(eventUrl).includes(organizer)
  );
}

function getOrganizerNames() {
  const organizers = new Set();

  for (const eventUrl of getEventUrls()) {
    for (const organizer of getEventOrganizers(eventUrl)) {
      organizers.add(organizer);
    }
  }

  return [...organizers].sort((a, b) => a.localeCompare(b, "fr"));
}

function populateOrganizers() {
  const select = document.getElementById("organizer-select");
  select.innerHTML = "";

  const allOption = document.createElement("option");
  allOption.value = ALL_ORGANIZERS;
  allOption.textContent = "Tous les organisateurs";
  select.appendChild(allOption);

  for (const organizer of getOrganizerNames()) {
    const option = document.createElement("option");
    option.value = organizer;
    option.textContent = organizer;
    select.appendChild(option);
  }
}

function populateEvents() {
  const organizer = document.getElementById("organizer-select").value;
  const select = document.getElementById("event-select");
  const selectedEventUrl = select.value;
  const eventUrls = getEventUrls(organizer);

  select.innerHTML = "";

  for (const eventUrl of eventUrls) {
    const option = document.createElement("option");
    option.value = eventUrl;
    option.textContent = simplifyEventName(eventUrl);
    select.appendChild(option);
  }

  if (eventUrls.includes(selectedEventUrl)) {
    select.value = selectedEventUrl;
  }
}

function simplifyEventName(url) {
  const slug = url
    .split("/")
    .filter(Boolean)
    .at(-1);

  return slug
    .split("-")
    .map(word =>
      word.charAt(0).toUpperCase() +
      word.slice(1)
    )
    .join(" ");
}


function renderAll() {
  renderSummary();
  renderChart();
  renderLatestTable();
}

function renderSummary() {
  const eventUrl = document.getElementById("event-select").value;
  const tickets = getLatestTickets(eventUrl);

  const totalAvailable = tickets.reduce(
    (sum, ticket) => sum + (ticket.available_count || 0),
    0
  );

  const latestTimestamp = tickets
    .map(t => t.scraped_at)
    .filter(Boolean)
    .sort()
    .at(-1);

  document.getElementById("summary").innerHTML = `
    <div class="metric">
      <div class="label">Places disponibles</div>
      <div class="value">${totalAvailable}</div>
    </div>

    <div class="metric">
      <div class="label">Tickets suivis</div>
      <div class="value">${tickets.length}</div>
    </div>

    <div class="metric">
      <div class="label">Dernière mesure</div>
      <div class="value">${formatDate(latestTimestamp)}</div>
    </div>
  `;
}

function renderChart() {
  const eventUrl = document.getElementById("event-select").value;
  const eventHistory = historyData.events?.[eventUrl];

  if (!eventHistory) {
    return;
  }

  const tickets = eventHistory.tickets || {};

  const allTimestamps = collectAllTimestamps(tickets);

  const datasets = [];

  for (const [ticketName, points] of Object.entries(tickets)) {
    const pointsByTimestamp = new Map(
      points.map(p => [p.timestamp, p.available_count])
    );

    datasets.push({
      label: ticketName,
      data: allTimestamps.map(timestamp => pointsByTimestamp.get(timestamp) ?? null),
      tension: 0.25,
      spanGaps: true
    });
  }

  const totalDataset = {
    label: "Total disponible",
    data: allTimestamps.map(timestamp => {
      let total = 0;

      for (const points of Object.values(tickets)) {
        const point = points.find(p => p.timestamp === timestamp);

        if (
          point &&
          point.available_count !== null &&
          point.available_count !== undefined
        ) {
          total += point.available_count;
        }
      }

      return total;
    }),
    tension: 0.25,
    spanGaps: true,
    borderWidth: 4
  };

  datasets.unshift(totalDataset);

  const labels = allTimestamps.map(timestamp => formatDate(timestamp));
  const ctx = document.getElementById("availability-chart");

  if (chart) {
    chart.destroy();
  }

  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets
    },
    options: {
      responsive: true,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          labels: {
            color: "#f2f4f8"
          }
        },
        tooltip: {
          mode: "index",
          intersect: false
        }
      },
      scales: {
        x: {
          ticks: {
            color: "#9aa4b2",
            maxRotation: 45
          },
          grid: {
            color: "#2c3340"
          }
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: "#9aa4b2"
          },
          grid: {
            color: "#2c3340"
          },
          title: {
            display: true,
            text: "Places restantes",
            color: "#9aa4b2"
          }
        }
      }
    }
  });
}

function collectAllTimestamps(tickets) {
  const timestamps = new Set();

  for (const points of Object.values(tickets)) {
    for (const point of points) {
      timestamps.add(point.timestamp);
    }
  }

  return [...timestamps].sort();
}

function renderLatestTable() {
  const eventUrl = document.getElementById("event-select").value;
  const tickets = getLatestTickets(eventUrl);

  const rows = tickets.map(ticket => {
    const status = getTicketStatus(ticket);

    return `
      <tr>
        <td>${escapeHtml(ticket.name)}</td>
        <td>${formatCount(ticket.available_count)}</td>
        <td class="${status.className}">${status.text}</td>
        <td>${escapeHtml(status.message)}</td>
        <td>${formatDate(ticket.scraped_at)}</td>
      </tr>
    `;
  }).join("");

  document.getElementById("latest-table").innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Ticket</th>
          <th>Places</th>
          <th>Statut</th>
          <th>Message</th>
          <th>Mesure</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
  `;
}

function getTicketStatus(ticket) {
  if (!ticket.ok) {
    return {
      className: "status-error",
      text: "Erreur",
      message: ticket.error || ""
    };
  }

  if (ticket.available_count === 0 && isSoldOutWarning(ticket.warning)) {
    return {
      className: "status-sold-out",
      text: "Épuisé",
      message: ""
    };
  }

  if (ticket.warning) {
    return {
      className: "status-warning",
      text: "Warning",
      message: ticket.warning
    };
  }

  if (ticket.available_count === 0) {
    return {
      className: "status-sold-out",
      text: "Épuisé",
      message: ""
    };
  }

  return {
    className: "status-ok",
    text: "OK",
    message: ""
  };
}

function isSoldOutWarning(warning) {
  return warning === "Bouton + introuvable, ticket probablement non achetable ou sold-out";
}

function updateLastUpdate() {
  const timestamps = [];

  for (const event of Object.values(latestData.events || {})) {
    for (const ticket of event.tickets || []) {
      if (ticket.scraped_at) {
        timestamps.push(ticket.scraped_at);
      }
    }
  }

  for (const event of Object.values(historyData.events || {})) {
    for (const points of Object.values(event.tickets || {})) {
      for (const point of points) {
        if (point.timestamp) {
          timestamps.push(point.timestamp);
        }
      }
    }
  }

  timestamps.sort();

  const latest = timestamps[timestamps.length - 1];

  document.getElementById("last-update").textContent =
    latest ? `Dernière mise à jour : ${formatDate(latest)}` : "Aucune donnée";
}

function getLatestTickets(eventUrl) {
  const latestTickets = latestData.events?.[eventUrl]?.tickets;

  if (latestTickets?.length) {
    return latestTickets;
  }

  return getLatestTicketsFromHistory(eventUrl);
}

function getLatestTicketsFromHistory(eventUrl) {
  const eventHistory = historyData.events?.[eventUrl];

  if (!eventHistory) {
    return [];
  }

  return Object.entries(eventHistory.tickets || {})
    .map(([name, points]) => {
      const latestPoint = [...points]
        .filter(point => point.timestamp)
        .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
        .at(-1);

      if (!latestPoint) {
        return null;
      }

      return {
        name,
        available_count: latestPoint.available_count,
        ok: latestPoint.ok,
        error: latestPoint.error,
        warning: latestPoint.warning,
        scraped_at: latestPoint.timestamp
      };
    })
    .filter(Boolean);
}

function getEventOrganizers(eventUrl) {
  const organizer = [
    latestData.events?.[eventUrl]?.organizer,
    historyData.events?.[eventUrl]?.organizer
  ].find(Boolean);

  if (!organizer) {
    return [UNKNOWN_ORGANIZER];
  }

  return organizer
    .split(",")
    .map(value => value.trim())
    .filter(Boolean);
}

function formatDate(value) {
  if (!value) return "—";

  return new Date(value).toLocaleString("fr-FR", {
    dateStyle: "short",
    timeStyle: "short"
  });
}

function formatCount(value) {
  if (value === null || value === undefined) return "—";
  return String(value);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

init().catch(error => {
  document.body.innerHTML = `
    <main class="container">
      <h1>Erreur</h1>
      <p>${escapeHtml(error.message)}</p>
    </main>
  `;
});
