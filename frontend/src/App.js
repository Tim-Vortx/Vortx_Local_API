import React, { useState, useEffect, useMemo } from "react";
import minimalScenario from "./minimalScenario.json";
import {
  Container,
  Typography,
  TextField,
  Button,
  Box,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Paper,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

// colors for the chart lines
const COLORS = [
  "#8884d8",
  "#82ca9d",
  "#ff7300",
  "#d0ed57",
  "#a4de6c",
  "#0088fe",
  "#ff0000",
];

/** Recursively render the outputs object using MUI accordions */
function RenderOutputs({ data }) {
  if (data === null || data === undefined) return null;

  if (typeof data !== "object" || Array.isArray(data)) {
    // primitive or array
    if (Array.isArray(data)) {
      const text =
        data.length > 50
          ? JSON.stringify(data.slice(0, 50)) + " …" + ` (${data.length} items)`
          : JSON.stringify(data);
      return (
        <Typography sx={{ whiteSpace: "pre-wrap" }}>{text}</Typography>
      );
    }
    return <Typography>{String(data)}</Typography>;
  }

  return (
    <Box>
      {Object.entries(data).map(([key, value]) => (
        <Accordion key={key} disableGutters>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>{key}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <RenderOutputs data={value} />
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  );
}

// Find all timeseries arrays (length 8760) within the outputs
function extractTimeSeries(outputs) {
  const series = [];
  const walk = (obj, prefix = "") => {
    if (!obj || typeof obj !== "object") return;
    Object.entries(obj).forEach(([k, v]) => {
      const path = prefix ? `${prefix}.${k}` : k;
      if (Array.isArray(v) && v.length === 8760 && v.every((n) => typeof n === "number")) {
        series.push({ key: path.replace(/\./g, "_"), label: path, values: v });
      } else if (v && typeof v === "object") {
        walk(v, path);
      }
    });
  };
  walk(outputs);
  return series;
}

function App() {
  // Generate 8760 hourly load values
  const hourlyLoads = Array(8760).fill(10);

  // Initialize scenario state as stringified JSON with minimalScenario but replace
  // loads_kw with full year hourly loads and include a specific year
  const initialScenario = JSON.stringify(
    {
      ...minimalScenario,
      ElectricLoad: {
        year: 2017,
        loads_kw: hourlyLoads,
      },
    },
    null,
    2
  );

  const [scenario, setScenario] = useState(initialScenario);

  const [runUuid, setRunUuid] = useState(null);
  const [status, setStatus] = useState("");
  const [outputs, setOutputs] = useState(null);
  const [error, setError] = useState("");
  const [day, setDay] = useState(0); // day of year for chart

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
    setOutputs(null);
    setRunUuid(null);
    let parsed;
    try {
      parsed = JSON.parse(scenario);
    } catch (e) {
      setError("Scenario JSON is invalid: " + e.message);
      return;
    }

    // Ensure the scenario includes a numeric year for ElectricLoad
    if (!parsed.ElectricLoad) {
      parsed.ElectricLoad = {};
    }
    if (typeof parsed.ElectricLoad.year !== "number") {
      parsed.ElectricLoad.year = 2017;
    }

    setStatus("Submitting…");
    try {
      const res = await fetch("/submit", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // API key is stored on the backend
        },
        body: JSON.stringify(parsed),
      });
      const text = await res.text();
      let data = null;
      try {
        data = JSON.parse(text);
      } catch {}
      if (!res.ok) {
        const message = (data && data.error) || text || res.statusText;
        setError(message);
        setStatus("Error");
        return;
      }
      if (!data) {
        setError(text || "Invalid JSON response");
        setStatus("Error");
        return;
      }
      console.log("Submit response:", data);
      const { run_uuid } = data;
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
        const res = await fetch(`/status/${runUuid}`, {
          headers: {},
        });
        const text = await res.text();
        let data = null;
        try {
          data = JSON.parse(text);
        } catch {}
        if (!res.ok) {
          const message = (data && data.error) || text || res.statusText;
          setError(message);
          setStatus("Error");
          return;
        }
        if (!data) {
          setError(text || "Invalid JSON response");
          setStatus("Error");
          return;
        }
        console.log("Polling response:", data); // Log full response for debugging

        const s = data?.status || data?.data?.status || "";
        setStatus(s);

        // Bail out on either optimal (v2) or Completed (v3) status
        if (["optimal", "completed"].includes(s.toLowerCase())) {
          setOutputs(data?.outputs || data?.data?.outputs || null);
          return;
        }

        // Always apply exponential backoff up to maxWait to avoid excessive polling
        delay = Math.min(delay * 2, maxWait);
      } catch (e) {
        setError(e.message);
        return;
      }

      timeoutId = setTimeout(poll, delay);
    };

    timeoutId = setTimeout(poll, delay);
    return () => clearTimeout(timeoutId);
  }, [runUuid, baseDelay, maxWait]);

  // Extract timeseries from outputs when available
  const timeSeries = useMemo(() => (outputs ? extractTimeSeries(outputs) : []), [outputs]);

  // Chart data for selected day
  const chartData = useMemo(() => {
    if (!timeSeries.length) return [];
    const start = day * 24;
    return Array.from({ length: 24 }, (_, hour) => {
      const idx = start + hour;
      const point = { hour };
      timeSeries.forEach((ts) => {
        point[ts.key] = ts.values[idx];
      });
      return point;
    });
  }, [timeSeries, day]);

  return (
    <Container sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom>
        REopt MVP
      </Typography>
      <TextField
        label="Scenario"
        multiline
        minRows={10}
        fullWidth
        value={scenario}
        onChange={(e) => setScenario(e.target.value)}
      />
      <Box mt={2} mb={2}>
        <Button variant="contained" onClick={submit}>
          Run REopt
        </Button>
      </Box>
      {error && (
        <Typography color="error" gutterBottom>
          Error: {error}
        </Typography>
      )}
      <Typography>Status: {status}</Typography>
      {outputs && (
        <Box mt={4}>
          <Typography variant="h5" gutterBottom>
            Outputs
          </Typography>
          <Box mb={4}>
            <Typography variant="h6">Daily Operations</Typography>
            {timeSeries.length > 0 ? (
              <>
                <TextField
                  type="number"
                  label="Day (0-364)"
                  value={day}
                  onChange={(e) =>
                    setDay(
                      Math.min(364, Math.max(0, parseInt(e.target.value || "0", 10)))
                    )
                  }
                  sx={{ mb: 2 }}
                />
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="hour" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    {timeSeries.map((ts, i) => (
                      <Line
                        type="monotone"
                        key={ts.key}
                        dataKey={ts.key}
                        name={ts.label}
                        stroke={COLORS[i % COLORS.length]}
                        dot={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </>
            ) : (
              <Typography>No timeseries data available.</Typography>
            )}
          </Box>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <RenderOutputs data={outputs} />
          </Paper>
        </Box>
      )}
    </Container>
  );
}

export default App;

