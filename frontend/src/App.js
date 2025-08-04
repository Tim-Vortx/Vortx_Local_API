import React, { useState, useEffect } from "react";

function App() {
  // put a valid 8760‐hr load or your own Scenario here
  const [scenario, setScenario] = useState(JSON.stringify({
    Site: { latitude: 40, longitude: -105 },
    ElectricLoad: { load_kw: Array(8760).fill(10) }
  }, null, 2));

  const [runUuid, setRunUuid] = useState(null);
  const [status, setStatus] = useState("");
  const [outputs, setOutputs] = useState(null);

  const submit = async () => {
    setStatus("Submitting…");
    const res = await fetch("/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: scenario
    });
    const { run_uuid } = await res.json();
    setRunUuid(run_uuid);
    setStatus("Queued: " + run_uuid);
  };

  // poll every 5s once we have a runUuid
  useEffect(() => {
    if (!runUuid) return;
    const id = setInterval(async () => {
      const res = await fetch(`/status/${runUuid}`);
      const data = await res.json();
      const s = data.data.status;
      setStatus(s);
      if (s === "Completed") {
        clearInterval(id);
        setOutputs(data.data.outputs);
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
