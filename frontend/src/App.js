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
  FormControlLabel,
  Checkbox,
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
  const [lat, setLat] = useState(minimalScenario.Site.latitude);
  const [lon, setLon] = useState(minimalScenario.Site.longitude);
  const [annualKwh, setAnnualKwh] = useState(minimalScenario.ElectricLoad.annual_kwh);
  const [doeRefName, setDoeRefName] = useState(minimalScenario.ElectricLoad.doe_reference_name);
  const [pvMaxKw, setPvMaxKw] = useState(0);
  const [pvCost, setPvCost] = useState(minimalScenario.PV.installed_cost_per_kw);
  const [storageMaxKw, setStorageMaxKw] = useState(0);
  const [storageMaxKwh, setStorageMaxKwh] = useState(0);
  const [useDiesel, setUseDiesel] = useState(false);
  const [dieselMaxKw, setDieselMaxKw] = useState(0);
  const [dieselFuelCost, setDieselFuelCost] = useState(3);
  const [useNatGas, setUseNatGas] = useState(false);
  const [natGasMaxKw, setNatGasMaxKw] = useState(0);
  const [natGasFuelCost, setNatGasFuelCost] = useState(3);
  const [energyRate, setEnergyRate] = useState(
    minimalScenario.ElectricTariff.blended_annual_energy_rate
  );
  const [demandRate, setDemandRate] = useState(
    minimalScenario.ElectricTariff.blended_annual_demand_rate
  );
  const [offGrid, setOffGrid] = useState(false);

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

    const hourlyLoads = Array(8760).fill(parseFloat(annualKwh) / 8760);

    const generators = {};
    if (useDiesel) {
      generators.GeneratorDiesel = {
        max_kw: parseFloat(dieselMaxKw),
        fuel_cost_per_gallon: parseFloat(dieselFuelCost),
        fuel_type: "diesel",
      };
    }
    if (useNatGas) {
      generators.GeneratorNatGas = {
        max_kw: parseFloat(natGasMaxKw),
        fuel_cost_per_gallon: parseFloat(natGasFuelCost),
        fuel_type: "natural_gas",
      };
    }

    const scenario = {
      Site: { latitude: parseFloat(lat), longitude: parseFloat(lon) },
      ElectricLoad: { year: 2017, loads_kw: hourlyLoads },
      ElectricTariff: {
        blended_annual_energy_rate: parseFloat(energyRate),
        blended_annual_demand_rate: parseFloat(demandRate),
      },
      ElectricUtility: minimalScenario.ElectricUtility,
      PV: {
        max_kw: parseFloat(pvMaxKw),
        installed_cost_per_kw: parseFloat(pvCost),
      },
      ElectricStorage: {
        max_kw: parseFloat(storageMaxKw),
        max_kwh: parseFloat(storageMaxKwh),
      },
      ...generators,
      Financial: minimalScenario.Financial,
      Settings: { off_grid_flag: offGrid },
    };

    setStatus("Submitting…");
    try {
      const res = await fetch("/submit", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(scenario),
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
      if (!run_uuid) {
        setError("No run_uuid returned");
        setStatus("Error");
        return;
      }
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
      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <Typography variant="h6">Site</Typography>
        <TextField
          label="Latitude"
          type="number"
          fullWidth
          value={lat}
          onChange={(e) => setLat(e.target.value)}
        />
        <TextField
          label="Longitude"
          type="number"
          fullWidth
          value={lon}
          onChange={(e) => setLon(e.target.value)}
        />
        <Typography variant="h6">Load</Typography>
        <TextField
          label="Annual kWh"
          type="number"
          fullWidth
          value={annualKwh}
          onChange={(e) => setAnnualKwh(e.target.value)}
        />
        <TextField
          label="DOE Reference Name"
          fullWidth
          value={doeRefName}
          onChange={(e) => setDoeRefName(e.target.value)}
        />
        <Typography variant="h6">PV</Typography>
        <TextField
          label="Max kW"
          type="number"
          fullWidth
          value={pvMaxKw}
          onChange={(e) => setPvMaxKw(e.target.value)}
        />
        <TextField
          label="Cost per kW ($)"
          type="number"
          fullWidth
          value={pvCost}
          onChange={(e) => setPvCost(e.target.value)}
        />
        <Typography variant="h6">Battery Storage</Typography>
        <TextField
          label="Max kW"
          type="number"
          fullWidth
          value={storageMaxKw}
          onChange={(e) => setStorageMaxKw(e.target.value)}
        />
        <TextField
          label="Max kWh"
          type="number"
          fullWidth
          value={storageMaxKwh}
          onChange={(e) => setStorageMaxKwh(e.target.value)}
        />
        <Typography variant="h6">Generators</Typography>
        <FormControlLabel
          control={<Checkbox checked={useDiesel} onChange={(e) => setUseDiesel(e.target.checked)} />}
          label="Diesel"
        />
        {useDiesel && (
          <>
            <TextField
              label="Diesel Max kW"
              type="number"
              fullWidth
              value={dieselMaxKw}
              onChange={(e) => setDieselMaxKw(e.target.value)}
            />
            <TextField
              label="Diesel Fuel Cost ($/gal)"
              type="number"
              fullWidth
              value={dieselFuelCost}
              onChange={(e) => setDieselFuelCost(e.target.value)}
            />
          </>
        )}
        <FormControlLabel
          control={<Checkbox checked={useNatGas} onChange={(e) => setUseNatGas(e.target.checked)} />}
          label="Natural Gas"
        />
        {useNatGas && (
          <>
            <TextField
              label="Natural Gas Max kW"
              type="number"
              fullWidth
              value={natGasMaxKw}
              onChange={(e) => setNatGasMaxKw(e.target.value)}
            />
            <TextField
              label="Natural Gas Fuel Cost ($/gal)"
              type="number"
              fullWidth
              value={natGasFuelCost}
              onChange={(e) => setNatGasFuelCost(e.target.value)}
            />
          </>
        )}
        <Typography variant="h6">Tariff</Typography>
        <TextField
          label="Energy Rate ($/kWh)"
          type="number"
          fullWidth
          value={energyRate}
          onChange={(e) => setEnergyRate(e.target.value)}
        />
        <TextField
          label="Demand Rate ($/kW)"
          type="number"
          fullWidth
          value={demandRate}
          onChange={(e) => setDemandRate(e.target.value)}
        />
        <FormControlLabel
          control={<Checkbox checked={offGrid} onChange={(e) => setOffGrid(e.target.checked)} />}
          label="Off Grid"
        />
      </Box>
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

