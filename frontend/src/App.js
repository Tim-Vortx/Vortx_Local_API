import React, { useState, useEffect, useRef } from "react";
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

  // Max polling attempts and interval
  const maxAttempts = 60; // e.g., 5 minutes max (60 * 5s)
  const attemptsRef = useRef(0);

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
    attemptsRef.current = 0; // reset attempts on new submit

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

  // poll every 5s once we have a runUuid
  useEffect(() => {
    if (!runUuid) return;
    const id = setInterval(async () => {
      if (attemptsRef.current >= maxAttempts) {
        setError("Polling timed out after 5 minutes.");
        setStatus("Timeout");
        clearInterval(id);
        return;
      }
      attemptsRef.current += 1;

      try {
        const res = await fetch(`/status/${runUuid}`);
        if (!res.ok) {
          const err = await res.json();
          setError(err.error || res.statusText);
          clearInterval(id);
          return;
        }
        const data = await res.json();
        console.log("Polling response:", data); // Log full response for debugging

        // Safely access status
        const s = data?.status || data?.data?.status || "";
        setStatus(s);

        if (s === "Completed") {
          clearInterval(id);
          // Safely access outputs
          setOutputs(data?.outputs || data?.data?.outputs || null);
        }
      } catch (e) {
        setError(e.message);
        clearInterval(id);
      }
    }, 5000);
    return () => clearInterval(id);
  }, [runUuid]);

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
