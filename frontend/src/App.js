import React, { useState, useEffect } from "react";

function App() {
  // put a valid 8760‐hr load or your own Scenario here
  const [scenario, setScenario] = useState(
    JSON.stringify(
      {
        Site: {
          latitude: 40,
          longitude: -105,
          ElectricLoad: { loads_kw: Array(8760).fill(10) }
        }
      },
      null,
      2
    )
  );

  const [runUuid, setRunUuid] = useState(null);
  const [status, setStatus] = useState("");
  const [outputs, setOutputs] = useState(null);
  const [error, setError] = useState("");

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
        body: JSON.stringify(parsed)
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
      try {
        const res = await fetch(`/status/${runUuid}`);
        if (!res.ok) {
          const err = await res.json();
          setError(err.error || res.statusText);
          clearInterval(id);
          return;
        }
        const data = await res.json();
        const s = data.data.status;
        setStatus(s);
        if (s === "Completed") {
          clearInterval(id);
          setOutputs(data.data.outputs);
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
        onChange={e => setScenario(e.target.value)}
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
