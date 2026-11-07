async function api(endpoint, data) {
  const response = await fetch(`/api/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    signal: AbortSignal.timeout(10000),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new Error("Start the website with python server.py, then open http://localhost:8000.");
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Python server unavailable.");
  return result;
}

export function createGameClient({ onSnapshot, onError }) {
  let session = null;
  let pendingEvents = [];
  let requestInFlight = false;
  let connectionError = "";

  async function connect() {
    try {
      const result = await api("session", {});
      session = result.session;
      onSnapshot(result.game);
    } catch (error) {
      failConnection(error);
    }
  }

  function failConnection(error) {
    connectionError = `${error.message} Reload the page to reconnect.`;
    pendingEvents = [];
    onError(connectionError);
  }

  async function syncGame() {
    if (!session || requestInFlight || connectionError || !pendingEvents.length) return;
    requestInFlight = true;
    const events = pendingEvents;
    pendingEvents = [];
    try {
      const result = await api("update", { session, events });
      onSnapshot(result.game);
    } catch (error) {
      failConnection(error);
    } finally {
      requestInFlight = false;
    }
  }

  function queueEvent(event) {
    if (!session || connectionError) return;
    if (pendingEvents.length >= 120) {
      failConnection(new Error("Connection is too slow to keep up with the game."));
      return;
    }
    pendingEvents.push(event);
  }

  return {
    connect,
    queueEvent,
    syncGame,
    get connected() { return Boolean(session) && !connectionError; },
  };
}
