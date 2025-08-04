import React, { useState, useEffect } from "react";

function App() {
  // put a valid 8760‐hr load or your own Scenario here
  const [scenario, setScenario] = useState(JSON.stringify({
    Site: {
      latitude: 40,
      longitude: -105,
      ElectricLoad: { loads_kw: Array(8760).fill(10) }
    }
  }, null, 2));

  const [runUuid, setRunUuid] = useState(null);
  const [status, setStatus] = useState("");
  const [queue, setQueue] = useState(null);
  const [outputs, setOutputs] = useState(null);

  const submit = async () => {
    setStatus("Submitting…");
    setQueue(null);
    try {
      const res = await fetch("/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: scenario
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus("Error: " + JSON.stringify(data.error || data));
        return;
      }
      setRunUuid(data.run_uuid);
      setStatus("Queued");
    } catch (e) {
      setStatus("Error: " + e.message);
    }
  };

  // poll every 5s once we have a runUuid
  useEffect(() => {
    if (!runUuid) return;
    const id = setInterval(async () => {
      try {
        const res = await fetch(`/status/${runUuid}`);
        const data = await res.json();
        if (!res.ok) {
          setStatus("Error: " + JSON.stringify(data.error || data));
          return;
        }
        setStatus(data.status);
        setQueue(data.queue);
        if (data.status === "Completed") {
          clearInterval(id);
          setOutputs(data.outputs);
        }
      } catch (e) {
        setStatus("Error: " + e.message);
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
      <br/>
      <button onClick={submit}>Run REopt</button>
      <p>
        Status: {status}
        {queue !== null && ` (Queue: ${queue})`}
      </p>
      {outputs && (
        <pre style={{ background: "#f0f0f0", padding: 10 }}>
          {JSON.stringify(outputs, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default App;
