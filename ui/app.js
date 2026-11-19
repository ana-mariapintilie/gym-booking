// Static UI: plain JavaScript that calls the schedule and bookings APIs.
const CONFIG = window.GYM_CONFIG;
const TIMEOUT_MS = 30000;
const UNREACHABLE =
  "The service can't be reached right now. If nobody used it for a while, it is starting up: " +
  "please try again in a minute.";

class ApiError extends Error {}

// Calls one service and returns its JSON, or throws an ApiError with a message for the user.
async function api(baseUrl, path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let response;
  try {
    response = await fetch(baseUrl + path, {
      method: options.method || "GET",
      headers: options.body ? { "Content-Type": "application/json" } : {},
      body: options.body,
      signal: controller.signal,
    });
  } catch {
    throw new ApiError(UNREACHABLE); // down, timed out, or still starting up
  } finally {
    clearTimeout(timer);
  }
  const body = await response.json().catch(() => null);
  if (response.ok) return body;
  if (body && body.error) throw new ApiError(body.error);
  if ([502, 503, 504].includes(response.status)) throw new ApiError(UNREACHABLE);
  throw new ApiError(`Something went wrong (HTTP ${response.status}).`);
}

function post(baseUrl, path, data) {
  return api(baseUrl, path, { method: "POST", body: JSON.stringify(data) });
}

function showMessage(element, text, kind) {
  element.textContent = text;
  element.className = `message ${kind}`;
  element.hidden = false;
}

function hideMessage(element) {
  element.hidden = true;
}

function row(cells) {
  const tr = document.createElement("tr");
  for (const cell of cells) {
    const td = document.createElement("td");
    if (cell instanceof Node) td.append(cell);
    else td.textContent = cell;
    tr.append(td);
  }
  return tr;
}

function emptyRow(columns, text) {
  const tr = document.createElement("tr");
  const td = document.createElement("td");
  td.colSpan = columns;
  td.textContent = text;
  tr.append(td);
  return tr;
}

// ---- Classes page (index.html) --------------------------------------------

async function loadClasses() {
  const tbody = document.querySelector("#classes tbody");
  const message = document.getElementById("classes-message");
  try {
    const classes = await api(CONFIG.scheduleUrl, "/api/classes");
    hideMessage(message);
    if (classes.length === 0) {
      tbody.replaceChildren(emptyRow(7, "No classes yet."));
      return;
    }
    tbody.replaceChildren(...classes.map((c) => {
      const link = document.createElement("a");
      link.href = `class.html?id=${c.id}`;
      link.textContent = "View";
      return row([c.name, c.instructor, c.room, c.starts_at, c.duration_minutes, c.capacity, link]);
    }));
  } catch (error) {
    tbody.replaceChildren(emptyRow(7, "Classes could not be loaded."));
    showMessage(message, error.message, "error");
  }
}

function setUpClassesPage() {
  const form = document.getElementById("add-class");
  const message = document.getElementById("add-class-message");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await post(CONFIG.scheduleUrl, "/api/classes", Object.fromEntries(new FormData(form)));
      form.reset();
      showMessage(message, "Class added.", "ok");
      loadClasses();
    } catch (error) {
      showMessage(message, error.message, "error");
    }
  });
  loadClasses();
}

// ---- Bookings page for one class (class.html?id=N) ------------------------

const classId = Number(new URLSearchParams(location.search).get("id"));

async function loadClassDetails() {
  const title = document.getElementById("class-title");
  const details = document.getElementById("class-details");
  const message = document.getElementById("class-message");
  try {
    const c = await api(CONFIG.scheduleUrl, `/api/classes/${classId}`);
    title.textContent = `${c.name} with ${c.instructor}`;
    details.textContent = `${c.starts_at} · ${c.room} · ${c.capacity} spots`;
    hideMessage(message);
  } catch (error) {
    // The bookings list below still works: it only needs the bookings service.
    title.textContent = `Class #${classId}`;
    showMessage(message, `Class details are unavailable: ${error.message}`, "warn");
  }
}

function cancelButton(booking) {
  const button = document.createElement("button");
  button.className = "secondary";
  button.textContent = "Cancel";
  button.addEventListener("click", async () => {
    const message = document.getElementById("bookings-message");
    try {
      const result = await post(
        CONFIG.bookingsUrl, `/api/classes/${classId}/bookings/${booking.id}/cancel`, {},
      );
      const moved = result.promoted ? " The first person on the waitlist got the spot." : "";
      showMessage(message, `Booking cancelled.${moved}`, "ok");
      loadBookings();
    } catch (error) {
      showMessage(message, error.message, "error");
    }
  });
  return button;
}

function statusBadge(status) {
  const span = document.createElement("span");
  span.className = `status ${status}`;
  span.textContent = status;
  return span;
}

async function loadBookings() {
  const tbody = document.querySelector("#bookings tbody");
  try {
    const bookings = await api(CONFIG.bookingsUrl, `/api/classes/${classId}/bookings`);
    if (bookings.length === 0) {
      tbody.replaceChildren(emptyRow(5, "No bookings yet."));
      return;
    }
    tbody.replaceChildren(...bookings.map((b) => row([
      b.member_name, b.member_email, statusBadge(b.status), b.created_at,
      b.status === "cancelled" ? "" : cancelButton(b),
    ])));
  } catch (error) {
    tbody.replaceChildren(emptyRow(5, "Bookings could not be loaded."));
    showMessage(document.getElementById("bookings-message"), error.message, "error");
  }
}

function setUpClassPage() {
  if (!Number.isInteger(classId) || classId < 1) {
    showMessage(document.getElementById("class-message"), "No class selected.", "error");
    return;
  }
  const form = document.getElementById("book");
  const message = document.getElementById("book-message");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await post(
        CONFIG.bookingsUrl, `/api/classes/${classId}/bookings`,
        Object.fromEntries(new FormData(form)),
      );
      form.reset();
      const text = result.status === "confirmed"
        ? "You're booked."
        : "The class is full, so you're on the waitlist.";
      showMessage(message, text, "ok");
      loadBookings();
    } catch (error) {
      showMessage(message, error.message, "error");
    }
  });
  loadClassDetails();
  loadBookings();
}

if (document.body.dataset.page === "classes") setUpClassesPage();
if (document.body.dataset.page === "class") setUpClassPage();
