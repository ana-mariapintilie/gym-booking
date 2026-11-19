// Where the browser finds the two services.
// These values are for docker compose on your laptop. The deploy pipeline
// overwrites this file with the Azure URLs, so nothing else needs changing.
window.GYM_CONFIG = {
  scheduleUrl: "http://localhost:8001",
  bookingsUrl: "http://localhost:8002",
};
