import React, { useState, useEffect } from "react";
import minimalScenario from "./minimalScenario.json";

function App() {
  // Generate 8760 hourly load values
  const hourlyLoads = Array(8760).fill(10);

  // Initialize scenario state as stringified JSON with minimalScenario but replace loads_kw with full year hourly loads
  const initialScenario = JSON.stringify(
    {
      ...minimalScenario,
      ElectricLoad: {
        loads_kw: hourlyLoads,
      },
    },
    null,
    2
  );

  const [scenario, setScenario] = useState(initialScenario);

  const [runUuid, setRunUuid] = useState(null);
  const [status, setStatus] = useState("");
  const [queue, setQueue] = useState(null);
  const [outputs, setOutputs] = useState(null);
  const [error, setError] = useState("");

  // Polling configuration
  const baseDelay = parseInt(
    process.env.REACT_APP_POLL_BASE_DELAY || "5000",
    10
  );
  const maxWait = parseInt(
    process.env.REACT_APP_MAX_POLL_TIME || String(5 * 60 * 1000),
    10
  );

  const submit = async () => {
    setError("");
    let parsed;
    try {
      parsed = JSON.parse(scenario);
    } catch (e) {
      setError("Scenario JSON is invalid: " + e.message);
      return;
    }

    setStatus("Submitting…");
    try {
      const res = await fetch("/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      if (!res.ok) {
        const err = await res.json();
        setError(err.error || res.statusText);
        setStatus("Error");
        return;
      }
      const { run_uuid } = await res.json();
      setRunUuid(run_uuid);
      setOutputs(null);
      setStatus("Queued: " + run_uuid);
    } catch (e) {
      setError(e.message);
      setStatus("Error");
    }
  };

  // Poll for status with backoff once we have a runUuid
  useEffect(() => {
    if (!runUuid) return;

    let delay = baseDelay;
    let timeoutId;
    const startTime = Date.now();

    const poll = async () => {
      if (Date.now() - startTime >= maxWait) {
        setError(`Polling timed out after ${Math.round(maxWait / 1000)} seconds.`);
        setStatus("Timeout");
        return;
      }

      try {
        const res = await fetch(`/status/${runUuid}`);
        if (!res.ok) {
          const err = await res.json();
          setError(err.error || res.statusText);
          return;
        }
        const data = await res.json();
        console.log("Polling response:", data); // Log full response for debugging

        const s = data?.status || data?.data?.status || "";
        setStatus(s);

        if (s === "Completed") {
          setOutputs(data?.outputs || data?.data?.outputs || null);
          return;
        }

        if (s === "Queued" || s === "Running") {
          delay = Math.min(delay * 2, maxWait);
        } else {
          delay = baseDelay;
        }
      } catch (e) {
        setError(e.message);
        return;
      }

      timeoutId = setTimeout(poll, delay);
    };

    timeoutId = setTimeout(poll, delay);
    return () => clearTimeout(timeoutId);
  }, [runUuid, baseDelay, maxWait]);

  return (
    <div style={{ padding: 20, fontFamily: "sans-serif" }}>
      <h2>REopt MVP</h2>
      <textarea
        style={{ width: "100%", height: 200 }}
        value={scenario}
        onChange={(e) => setScenario(e.target.value)}
      />
      <br />
      <button onClick={submit}>Run REopt</button>
      {error && <p style={{ color: "red" }}>Error: {error}</p>}
      <p>Status: {status}</p>
      {outputs && (
        <pre style={{ background: "#f0f0f0", padding: 10 }}>
          {JSON.stringify(outputs, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default App;
