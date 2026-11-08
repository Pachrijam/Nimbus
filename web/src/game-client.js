export function createGameClient({ onSnapshot, onError }) {
  let session = null;
  let project = null;
  let requestInFlight = false;
  let connectionError = "";
  let pendingEvents = [];

  function queueEvent(event) {
    pendingEvents.push(event);
  }

  async function syncGame(inputEpoch) {
    if (!session || requestInFlight || connectionError || !pendingEvents.length) return;
    requestInFlight = true;
    const events = pendingEvents;
    pendingEvents = [];
    try {
      const result = await fetch("/api/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session, events }),
      }).then((response) => response.json());
      onSnapshot(result.game, inputEpoch);
    } catch (error) {
      connectionError = error.message;
      onError(connectionError);
    } finally {
      requestInFlight = false;
    }
  }

  function connect() {
    session = crypto.randomUUID();
    onSnapshot({ state: "READY", level: 1, comparison: null }, 0);
  }

  return { connected: true, connect, queueEvent, syncGame };
}
