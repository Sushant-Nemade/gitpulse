import "./dashboard.css";
import { Chart, registerables } from "chart.js";
import {
  createIcons,
  Activity,
  Users,
  UserMinus,
  GitFork,
  History,
  RefreshCw,
  Settings,
  Download,
  X,
  Search,
} from "lucide";
import { z } from "zod";

Chart.register(...registerables);
const iconSet = {
  Activity,
  Users,
  UserMinus,
  GitFork,
  History,
  RefreshCw,
  Settings,
  Download,
  X,
  Search,
};
const identity = z.object({
  id: z.number().int().positive(),
  login: z.string().regex(/^[A-Za-z0-9-]{1,39}$/),
  first_seen: z.string().optional(),
  lost_at: z.string().optional(),
});
const event = z.object({
  id: z.number().int(),
  relation: z.enum(["followers", "following"]),
  github_id: z.number().int(),
  login: z.string(),
  kind: z.enum(["baseline", "added", "removed", "renamed"]),
  observed_at: z.string(),
});
const repository = z.object({
  id: z.number().int(),
  name: z.string().max(100),
  language: z.string().nullable(),
  stars: z.number().int().nonnegative(),
  forks: z.number().int().nonnegative(),
  issues: z.number().int().nonnegative(),
});
const schema = z.object({
  username: z.string(),
  revision: z.number().int(),
  last_sync: z.string().nullable(),
  source: z.enum(["fixture", "github"]),
  followers: z.array(identity).max(5000),
  following: z.array(identity).max(5000),
  lost: z.array(identity).max(5000),
  events: z.array(event).max(1000),
  repositories: z.array(repository).max(5000),
});
type Report = z.infer<typeof schema>;
type View =
  "overview" | "followers" | "following" | "lost" | "events" | "repositories";
const names: Record<View, string> = {
  overview: "Overview",
  followers: "Followers",
  following: "Following",
  lost: "Lost followers",
  events: "History",
  repositories: "Repositories",
};
let report: Report | null = null;
let view: View = "overview";
let query = "";
let sort = "newest";
let chart: Chart | null = null;
let origin = "";
let token = "";
let busy = false;
const app = document.querySelector<HTMLDivElement>("#app")!;
app.innerHTML = `
  <aside><div class="brand"><i data-lucide="activity"></i><h1>GitPulse</h1></div><p class="side-label">WORKSPACE</p><nav aria-label="Views">
  ${Object.entries(names)
    .map(
      ([key, title]) =>
        `<button data-view="${key}" class="nav-button"><i data-lucide="${key === "overview" ? "activity" : key === "lost" ? "user-minus" : key === "events" ? "history" : key === "repositories" ? "git-fork" : "users"}"></i><span>${title}</span></button>`,
    )
    .join("")}
  </nav><div class="side-bottom"><span class="signal"></span> Single-account workspace</div></aside>
  <main><header><div><p class="eyebrow">AUDIENCE INTELLIGENCE</p><h2 id="heading">Overview</h2></div><div class="tools"><span id="source" class="source">Loading</span><button id="connection" class="icon-button" title="API connection" aria-label="API connection"><i data-lucide="settings"></i></button><button id="sync" class="primary"><i data-lucide="refresh-cw"></i>Sync now</button></div></header>
  <div class="account-line"><span id="account">GitHub audience</span><span id="updated"></span></div>
  <div id="notice" role="status" hidden></div><div id="metrics" class="metrics"></div>
  <section id="trend"><div class="section-title"><h3>Observed audience changes</h3><span>Gains / losses</span></div><div class="chart"><canvas id="chart" aria-label="Audience change history" role="img"></canvas></div></section>
  <section class="records"><div class="section-title"><h3 id="list-title">Current followers</h3><div class="list-tools"><label class="search"><i data-lucide="search"></i><input id="search" placeholder="Search" aria-label="Search records" maxlength="100"></label><select id="sort" aria-label="Sort records"><option value="newest">Newest observed</option><option value="oldest">Oldest observed</option><option value="name">Name A-Z</option></select><button id="export" class="icon-button" title="Export CSV" aria-label="Export CSV"><i data-lucide="download"></i></button></div></div><div id="results" aria-live="polite">Loading records...</div><p id="record-count" class="muted"></p></section>
  <footer>Original implementation inspired by <a href="https://github.com/KalyanM45/GitPulse">GitPulse</a><span>Observation dates are not actual follow dates.</span></footer></main>
  <dialog id="dialog"><form id="connect-form"><div class="dialog-heading"><h3>API connection</h3><button type="button" id="close" class="icon-button" aria-label="Close connection"><i data-lucide="x"></i></button></div><label>Server URL<input id="server" type="url" required></label><label>Access token<input id="token" type="password" autocomplete="off" required minlength="32"></label><div class="dialog-actions"><button type="button" id="disconnect">Sample data</button><button class="primary" type="submit">Connect</button></div></form></dialog>`;

function icons(): void {
  createIcons({ icons: iconSet });
}
function date(value: string | undefined | null): string {
  return value
    ? new Date(value).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "Not observed yet";
}
function message(text: string): void {
  const notice = document.querySelector<HTMLElement>("#notice")!;
  notice.hidden = !text;
  notice.textContent = text;
}
function cell(text: string, className = ""): HTMLTableCellElement {
  const element = document.createElement("td");
  element.textContent = text;
  element.className = className;
  return element;
}
function cleanCSV(value: string): string {
  const safe = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return `"${safe.replaceAll('"', '""')}"`;
}

function render(): void {
  if (!report) return;
  document.querySelector("#heading")!.textContent = names[view];
  document.querySelector("#account")!.textContent = report.username;
  document.querySelector("#updated")!.textContent =
    `Last observation ${date(report.last_sync)}`;
  document.querySelector("#source")!.textContent =
    report.source === "fixture" ? "Sample data" : "Connected account";
  document
    .querySelectorAll<HTMLButtonElement>("[data-view]")
    .forEach((button) => {
      button.classList.toggle("active", button.dataset.view === view);
      button.setAttribute(
        "aria-current",
        button.dataset.view === view ? "page" : "false",
      );
    });
  const metrics = document.querySelector("#metrics")!;
  metrics.replaceChildren();
  for (const [label, value, subtitle] of [
    ["Followers", report.followers.length, "Currently observed"],
    ["Following", report.following.length, "Currently observed"],
    ["Lost followers", report.lost.length, "Not currently following"],
    [
      "Repository stars",
      report.repositories.reduce((sum, repo) => sum + repo.stars, 0),
      "Public repositories",
    ],
  ] as const) {
    const item = document.createElement("div");
    item.className = "metric";
    const caption = document.createElement("span");
    caption.textContent = label;
    const number = document.createElement("strong");
    number.textContent = value.toLocaleString();
    const detail = document.createElement("small");
    detail.textContent = subtitle;
    item.append(caption, number, detail);
    metrics.append(item);
  }
  document.querySelector<HTMLElement>("#trend")!.hidden = view !== "overview";
  if (view === "overview") {
    chart?.destroy();
    const days = [
      ...new Set(report.events.map((item) => item.observed_at.slice(0, 10))),
    ]
      .sort()
      .slice(-14);
    chart = new Chart(document.querySelector<HTMLCanvasElement>("#chart")!, {
      type: "bar",
      data: {
        labels: days,
        datasets: [
          {
            label: "Gained",
            backgroundColor: "#138b64",
            borderRadius: 2,
            data: days.map(
              (day) =>
                report!.events.filter(
                  (item) =>
                    item.relation === "followers" &&
                    item.kind === "added" &&
                    item.observed_at.startsWith(day),
                ).length,
            ),
          },
          {
            label: "Lost",
            backgroundColor: "#e26a55",
            borderRadius: 2,
            data: days.map(
              (day) =>
                report!.events.filter(
                  (item) =>
                    item.relation === "followers" &&
                    item.kind === "removed" &&
                    item.observed_at.startsWith(day),
                ).length,
            ),
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
        plugins: { legend: { position: "bottom" } },
      },
    });
  }
  const selected = view === "overview" ? "followers" : view;
  document.querySelector('option[value="newest"]')!.textContent =
    selected === "following" ? "GitHub response order" : "Newest observed";
  const records = report[selected].filter((item) =>
    JSON.stringify(item).toLowerCase().includes(query),
  );
  records.sort((left, right) => {
    if (selected === "following" && sort === "newest") return 0;
    const nameLeft = "login" in left ? left.login : left.name;
    const nameRight = "login" in right ? right.login : right.name;
    if (sort === "name") return nameLeft.localeCompare(nameRight);
    const timeLeft =
      "observed_at" in left
        ? left.observed_at
        : "first_seen" in left
          ? (left.first_seen ?? "")
          : "lost_at" in left
            ? (left.lost_at ?? "")
            : "";
    const timeRight =
      "observed_at" in right
        ? right.observed_at
        : "first_seen" in right
          ? (right.first_seen ?? "")
          : "lost_at" in right
            ? (right.lost_at ?? "")
            : "";
    return (sort === "oldest" ? 1 : -1) * timeLeft.localeCompare(timeRight);
  });
  document.querySelector("#list-title")!.textContent =
    selected === "followers" ? "Current followers" : names[selected];
  const results = document.querySelector("#results")!;
  results.replaceChildren();
  if (!records.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = query ? "No matching records" : "No records observed";
    results.append(empty);
  } else {
    const table = document.createElement("table");
    const header = document.createElement("thead");
    const headerRow = document.createElement("tr");
    const columns =
      selected === "repositories"
        ? ["Repository", "Language", "Stars", "Forks", "Open issues"]
        : selected === "events"
          ? ["Account", "Relationship", "Change", "Observed"]
          : [
              "Account",
              "GitHub ID",
              selected === "lost" ? "Lost observed" : "First observed",
            ];
    for (const title of columns) {
      const heading = document.createElement("th");
      heading.textContent = title;
      headerRow.append(heading);
    }
    header.append(headerRow);
    table.append(header);
    const body = document.createElement("tbody");
    for (const item of records.slice(0, 200)) {
      const row = document.createElement("tr");
      if ("stars" in item)
        row.append(
          cell(item.name, "name"),
          cell(item.language ?? "Unspecified"),
          cell(String(item.stars)),
          cell(String(item.forks)),
          cell(String(item.issues)),
        );
      else if ("observed_at" in item)
        row.append(
          cell(item.login, "name"),
          cell(item.relation),
          cell(item.kind, `change ${item.kind}`),
          cell(date(item.observed_at)),
        );
      else
        row.append(
          cell(item.login, "name"),
          cell(String(item.id), "mono"),
          cell(date("lost_at" in item ? item.lost_at : item.first_seen)),
        );
      body.append(row);
    }
    table.append(body);
    results.append(table);
  }
  document.querySelector("#record-count")!.textContent =
    `${Math.min(records.length, 200)} of ${records.length} matching records`;
  document.querySelector<HTMLButtonElement>("#sync")!.disabled = busy;
  icons();
}

async function loadSample(): Promise<void> {
  const response = await fetch(new URL("./demo.json", import.meta.url), {
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("Sample data unavailable");
  report = schema.parse(await response.json());
  render();
}
async function request(path: string, method = "GET"): Promise<Report> {
  const response = await fetch(`${origin}/api/${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
    credentials: "omit",
    signal: AbortSignal.timeout(method === "POST" ? 120000 : 10000),
  });
  if (!response.ok)
    throw new Error(
      `Request failed (${response.status}); previous view preserved`,
    );
  return schema.parse(await response.json());
}
document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) =>
  button.addEventListener("click", () => {
    view = button.dataset.view as View;
    query = "";
    document.querySelector<HTMLInputElement>("#search")!.value = "";
    render();
  }),
);
document
  .querySelector<HTMLInputElement>("#search")!
  .addEventListener("input", (event) => {
    query = (event.target as HTMLInputElement).value.trim().toLowerCase();
    render();
  });
document
  .querySelector<HTMLSelectElement>("#sort")!
  .addEventListener("change", (event) => {
    sort = (event.target as HTMLSelectElement).value;
    render();
  });
const dialog = document.querySelector<HTMLDialogElement>("#dialog")!;
document.querySelector("#connection")!.addEventListener("click", () => {
  document.querySelector<HTMLInputElement>("#server")!.value =
    origin || location.origin;
  dialog.showModal();
});
document
  .querySelector("#close")!
  .addEventListener("click", () => dialog.close());
document.querySelector("#disconnect")!.addEventListener("click", async () => {
  origin = "";
  token = "";
  document.querySelector<HTMLInputElement>("#token")!.value = "";
  dialog.close();
  try {
    await loadSample();
    message("");
  } catch {
    message("Sample data unavailable");
  }
});
document
  .querySelector("#connect-form")!
  .addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const candidate = new URL(
        document.querySelector<HTMLInputElement>("#server")!.value,
      );
      if (
        candidate.username ||
        candidate.password ||
        candidate.search ||
        candidate.hash ||
        candidate.pathname !== "/" ||
        (candidate.protocol !== "https:" &&
          !(
            candidate.protocol === "http:" &&
            ["127.0.0.1", "localhost", "[::1]"].includes(candidate.hostname)
          ))
      )
        throw new Error("Use an HTTPS API origin or local loopback server");
      origin = candidate.origin;
      token = document.querySelector<HTMLInputElement>("#token")!.value;
      report = await request("state");
      render();
      message("");
      dialog.close();
      document.querySelector<HTMLInputElement>("#token")!.value = "";
    } catch (error) {
      token = "";
      origin = "";
      message(error instanceof Error ? error.message : "Connection failed");
    }
  });
document.querySelector("#sync")!.addEventListener("click", async () => {
  if (!token) {
    document.querySelector<HTMLButtonElement>("#connection")!.click();
    return;
  }
  busy = true;
  render();
  message("Syncing account...");
  try {
    report = await request("sync", "POST");
    message("Sync completed");
  } catch (error) {
    message(error instanceof Error ? error.message : "Sync failed");
  } finally {
    busy = false;
    render();
  }
});
document.querySelector("#export")!.addEventListener("click", () => {
  if (!report) return;
  const selected = view === "overview" ? "followers" : view;
  const rows = report[selected].filter((row) =>
    JSON.stringify(row).toLowerCase().includes(query),
  );
  if (!rows.length) {
    message("No records to export");
    return;
  }
  const keys = Object.keys(rows[0]);
  const csv = [
    keys.map(cleanCSV).join(","),
    ...rows.map((row) =>
      keys
        .map((key) => cleanCSV(String(Reflect.get(row, key) ?? "")))
        .join(","),
    ),
  ].join("\r\n");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(
    new Blob([csv], { type: "text/csv;charset=utf-8" }),
  );
  link.download = `gitpulse-${selected}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
});
icons();
loadSample().catch(() => {
  message("Sample data unavailable. Reload to retry.");
  document.querySelector("#results")!.textContent = "Unable to load records";
});
