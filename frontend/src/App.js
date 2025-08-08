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
  MenuItem,
  Card,
  CardContent,
  Tabs,
  Tab,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

// colors for the chart series
const COLORS = [
  "#8884d8",
  "#82ca9d",
  "#ff7300",
  "#d0ed57",
  "#a4de6c",
  "#0088fe",
  "#ff0000",
];

// Mapping of timeseries keys to human-readable labels for the chart
const SERIES_MAP = {
  ElectricLoad_load_series_kw: "Site Load",
  ElectricUtility_electric_to_load_series_kw: "Utility Purchase",
  PV_electric_to_load_series_kw: "Solar Serves Load",
  PV_electric_to_storage_series_kw: "Solar Charges BESS",
  PV_electric_to_grid_series_kw: "Solar Export",
  ElectricStorage_electric_to_load_series_kw: "BESS Serves Load",
  ElectricStorage_electric_to_grid_series_kw: "BESS Export",
  Generator_electric_to_load_series_kw: "NG Generator Serves Load",
  Generator_electric_to_storage_series_kw: "NG Generator Charges BESS",
  Generator_electric_to_grid_series_kw: "NG Generator Export",
  NGGenerator_electric_to_load_series_kw: "NG Generator Serves Load",
  NGGenerator_electric_to_storage_series_kw: "NG Generator Charges BESS",
  NGGenerator_electric_to_grid_series_kw: "NG Generator Export",
  DieselGenerator_electric_to_load_series_kw: "Diesel Generator Serves Load",
  DieselGenerator_electric_to_storage_series_kw:
    "Diesel Generator Charges BESS",
};

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
      return <Typography sx={{ whiteSpace: "pre-wrap" }}>{text}</Typography>;
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
      if (
        Array.isArray(v) &&
        (v.length === 8760 || v.length === 35040) &&
        v.every((n) => typeof n === "number")
      ) {
        // If 35040 samples (15-min resolution), convert to hourly by averaging every 4 samples
        const hourly =
          v.length === 35040
            ? Array.from({ length: 8760 }, (_, idx) => {
                const base = idx * 4;
                return (
                  (v[base] + v[base + 1] + v[base + 2] + v[base + 3]) / 4
                );
              })
            : v;
        series.push({ key: path.replace(/\./g, "_"), label: path, values: hourly });
      } else if (v && typeof v === "object") {
        walk(v, path);
      }
    });
  };
  walk(outputs);
  return series;
}

// Parse an uploaded CSV containing hourly (8760) or 15-min (35040)
// kW load values. Optionally the first column may contain timestamps
// from which a year will be extracted.
function parseLoadCsv(text) {
  const lines = text
    .trim()
    .split(/\r?\n/)
    .filter((l) => l.trim());
  let year = 2017;
  const values = [];
  for (const line of lines) {
    const parts = line.split(/,|\s+/).filter(Boolean);
    if (!parts.length) continue;
    const maybeDate = parts[0];
    const maybeVal = parts.length > 1 ? parts[1] : parts[0];
    const num = parseFloat(maybeVal);
    if (!isNaN(num)) {
      values.push(num);
    }
    const dt = Date.parse(maybeDate);
    if (!isNaN(dt)) {
      year = new Date(dt).getFullYear();
    }
  }
  if (values.length === 35040) {
    const hourly = [];
    for (let i = 0; i < values.length; i += 4) {
      hourly.push(
        (values[i] + values[i + 1] + values[i + 2] + values[i + 3]) / 4,
      );
    }
    return { year, loads: hourly };
  }
  if (values.length === 8760) {
    return { year, loads: values };
  }
  throw new Error("Expected 8760 hourly or 35040 15-min values");
}

// Summarize an 8760 load array
function summarizeLoads(arr) {
  const total = arr.reduce((a, b) => a + b, 0);
  const peak = Math.max(...arr);
  const loadFactor = peak ? total / (peak * 8760) : 0;
  return { total, peak, loadFactor };
}

function App() {
  const [location, setLocation] = useState("");
  const [doeRefName, setDoeRefName] = useState(
    minimalScenario.ElectricLoad.doe_reference_name,
  );
  const [pvMaxKw, setPvMaxKw] = useState(0);
  const [pvCost, setPvCost] = useState(
    minimalScenario.PV.installed_cost_per_kw,
  );
  const [storageMaxKw, setStorageMaxKw] = useState(0);
  const [storageMaxKwh, setStorageMaxKwh] = useState(0);

  const [usePv, setUsePv] = useState(false);
  const [useStorage, setUseStorage] = useState(false);
  const [useGenerator, setUseGenerator] = useState(false);

  const [generatorMaxKw, setGeneratorMaxKw] = useState(0);
  const [generatorFuelCostPerGallon, setGeneratorFuelCostPerGallon] =
    useState(3);
  const [generatorFuelCostPerMmbtu, setGeneratorFuelCostPerMmbtu] = useState(6);
  const [generatorFuelType, setGeneratorFuelType] = useState("diesel");

  const [bessCanExport, setBessCanExport] = useState(false);
  const [bessSolarOnly, setBessSolarOnly] = useState(false);
  const [solarCanExport, setSolarCanExport] = useState(false);
  const [genCanExport, setGenCanExport] = useState(false);
  const [genChargeBess, setGenChargeBess] = useState(false);

  const [energyRate, setEnergyRate] = useState(
    minimalScenario.ElectricTariff.blended_annual_energy_rate,
  );
  const [demandRate, setDemandRate] = useState(
    minimalScenario.ElectricTariff.blended_annual_demand_rate,
  );
  const [offGrid, setOffGrid] = useState(false);

  const initialLoads = useMemo(
    () => Array(8760).fill(minimalScenario.ElectricLoad.annual_kwh / 8760),
    [],
  );
  const [loads, setLoads] = useState(initialLoads);
  const [loadYear, setLoadYear] = useState(2017);
  const [loadSummary, setLoadSummary] = useState(() =>
    summarizeLoads(initialLoads),
  );
  const [loadTab, setLoadTab] = useState(0);
  const [loadFileName, setLoadFileName] = useState("");
  const [peakLoad, setPeakLoad] = useState(0);
  const [genLoadFactor, setGenLoadFactor] = useState(0.5);
  const [siteType, setSiteType] = useState("industrial");

  const [runUuid, setRunUuid] = useState(null);
  const [status, setStatus] = useState("");
  const [outputs, setOutputs] = useState(null);
  const [error, setError] = useState("");
  const [day, setDay] = useState(0); // day of year for chart
  const [tab, setTab] = useState(0); // 0: Inputs, 1: Results

  // Polling configuration
  const baseDelay = parseInt(
    process.env.REACT_APP_POLL_BASE_DELAY || "5000",
    10,
  );
  const maxWait = parseInt(
    process.env.REACT_APP_MAX_POLL_TIME || String(5 * 60 * 1000),
    10,
  );

  useEffect(() => {
    setLoadSummary(summarizeLoads(loads));
  }, [loads]);

  const handleLoadFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setLoadFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const { year, loads } = parseLoadCsv(reader.result);
        setLoadYear(year);
        setLoads(loads);
      } catch (err) {
        setError(err.message);
      }
    };
    reader.readAsText(file);
  };

  const generateProfile = () => {
    const peak = parseFloat(peakLoad);
    const lf = parseFloat(genLoadFactor);
    if (!peak || !lf) return;
    const shape = Array.from({ length: 8760 }, (_, i) => {
      const hour = i % 24;
      const weekday = Math.floor(i / 24) % 7 < 5;
      switch (siteType) {
        case "manufacturing":
          return weekday && hour >= 8 && hour < 18 ? 1 : 0.3;
        case "cold_storage":
          return 0.7;
        case "industrial":
        default:
          return 0.8;
      }
    });
    const avgShape = shape.reduce((a, b) => a + b, 0) / 8760;
    const scale = lf / avgShape;
    const arr = shape.map((v) => v * scale * peak);
    setLoadYear(new Date().getFullYear());
    setLoads(arr);
  };

  const submit = async () => {
    setError("");
    setOutputs(null);
    setRunUuid(null);
    
    // Geocode the user-provided location into latitude and longitude
    if (!location.trim()) {
      setError("Location is required");
      setStatus("Error");
      return;
    }
    let lat = null;
    let lon = null;
    try {
      const geoRes = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(location)}`,
      );
      const geoData = await geoRes.json();
      if (!geoData.length) {
        setError("Location not found");
        setStatus("Error");
        return;
      }
      lat = parseFloat(geoData[0].lat);
      lon = parseFloat(geoData[0].lon);
    } catch (e) {
      setError(`Geocoding failed: ${e.message}`);
      setStatus("Error");
      return;
    }

    // Validate and summarize the load profile
    if (loads.length !== 8760) {
      setError("Load profile must contain exactly 8760 hourly values");
      setStatus("Error");
      return;
    }

    const summary = summarizeLoads(loads);
    if (Math.abs(summary.total - loadSummary.total) > 1e-6) {
      setLoadSummary(summary);
    }

    const scenario = {
      Site: { latitude: lat, longitude: lon },
      ElectricLoad: {
        year: loadYear,
        loads_kw: loads,
        annual_kwh: summary.total,
        doe_reference_name: doeRefName,
      },
      ElectricTariff: {
        blended_annual_energy_rate: parseFloat(energyRate),
        blended_annual_demand_rate: parseFloat(demandRate),
      },
      ElectricUtility: minimalScenario.ElectricUtility,
      Financial: minimalScenario.Financial,
      Settings: { off_grid_flag: offGrid },
    };

    if (usePv) {
      scenario.PV = {
        max_kw: parseFloat(pvMaxKw),
        installed_cost_per_kw: parseFloat(pvCost),
        can_export: solarCanExport,
      };
    }

    if (useStorage) {
      scenario.ElectricStorage = {
        max_kw: parseFloat(storageMaxKw),
        max_kwh: parseFloat(storageMaxKwh),
        can_export: bessCanExport,
        charge_from_pv_only: bessSolarOnly,
      };
    }

    if (useGenerator) {
      scenario.Generator = {
        max_kw: parseFloat(generatorMaxKw),
        ...(generatorFuelType !== "natural_gas"
          ? { fuel_cost_per_gallon: parseFloat(generatorFuelCostPerGallon) }
          : {}),
        ...(generatorFuelType !== "diesel"
          ? { fuel_cost_per_mmbtu: parseFloat(generatorFuelCostPerMmbtu) }
          : {}),
        fuel_type: generatorFuelType,
        can_export: genCanExport,
        can_charge_storage: genChargeBess,
      };
    }

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

  // Polling for status
  useEffect(() => {
    if (!runUuid) return;

    let delay = baseDelay;
    let timeoutId;
    const startTime = Date.now();

    const poll = async () => {
      if (Date.now() - startTime >= maxWait) {
        setError(
          `Polling timed out after ${Math.round(maxWait / 1000)} seconds.`,
        );
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
        const s = data?.status || data?.data?.status || "";
        setStatus(s);

        // Bail out on either optimal (v2) or Completed (v3) status
        if (["optimal", "completed"].includes(s.toLowerCase())) {
          setOutputs(data?.outputs || data?.data?.outputs || null);
          return;
        }

        // Exponential backoff
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
  const timeSeries = useMemo(() => {
    if (!outputs) return [];
    return extractTimeSeries(outputs)
      .filter((ts) => SERIES_MAP[ts.key])
      .map((ts) => {
        let label = SERIES_MAP[ts.key];
        if (
          ts.key.startsWith("Generator_") &&
          generatorFuelType === "diesel"
        ) {
          label = label.replace("NG Generator", "Diesel Generator");
        }
        return { ...ts, label };
      });
  }, [outputs, generatorFuelType]);

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
      <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label="Inputs" />
        <Tab label="Results" />
      </Tabs>
      {tab === 0 && (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Card>
            <CardContent
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              <Typography variant="h6">Site</Typography>
              <TextField
                label="Address or Zip Code"
                fullWidth
                value={location}
                onChange={(e) => setLocation(e.target.value)}
              />
            </CardContent>
          </Card>
          <Card>
            <CardContent
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              <Typography variant="h6">Load Profile</Typography>
              <Tabs value={loadTab} onChange={(e, v) => setLoadTab(v)}>
                <Tab label="Upload CSV" />
                <Tab label="Generate" />
              </Tabs>
              {loadTab === 0 && (
                <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <Button variant="contained" component="label">
                    Upload 8760
                    <input
                      type="file"
                      hidden
                      accept=".csv"
                      onChange={handleLoadFile}
                    />
                  </Button>
                  {loadFileName && <Typography>{loadFileName}</Typography>}
                </Box>
              )}
              {loadTab === 1 && (
                <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <TextField
                    label="Peak Load (kW)"
                    type="number"
                    value={peakLoad}
                    onChange={(e) => setPeakLoad(e.target.value)}
                  />
                  <TextField
                    label="Load Factor"
                    type="number"
                    value={genLoadFactor}
                    onChange={(e) => setGenLoadFactor(e.target.value)}
                  />
                  <TextField
                    select
                    label="Site Type"
                    value={siteType}
                    onChange={(e) => setSiteType(e.target.value)}
                  >
                    <MenuItem value="industrial">Industrial</MenuItem>
                    <MenuItem value="manufacturing">Manufacturing</MenuItem>
                    <MenuItem value="cold_storage">Cold Storage</MenuItem>
                  </TextField>
                  <Button variant="outlined" onClick={generateProfile}>
                    Generate
                  </Button>
                </Box>
              )}
              {loadSummary && (
                <Box>
                  <Typography variant="subtitle1">Summary</Typography>
                  <Typography>
                    Total Annual kWh: {loadSummary.total.toFixed(1)}
                  </Typography>
                  <Typography>
                    Peak Load: {loadSummary.peak.toFixed(1)} kW
                  </Typography>
                  <Typography>
                    Load Factor: {loadSummary.loadFactor.toFixed(2)}
                  </Typography>
                </Box>
              )}
              <TextField
                label="DOE Reference Name"
                fullWidth
                value={doeRefName}
                onChange={(e) => setDoeRefName(e.target.value)}
              />
            </CardContent>
          </Card>
          <Card>
            <CardContent
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              <Typography variant="h6">Utility Inputs</Typography>
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
            </CardContent>
          </Card>
          <Card>
            <CardContent
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              <FormControlLabel
                control={
                  <Checkbox
                    checked={usePv}
                    onChange={(e) => setUsePv(e.target.checked)}
                  />
                }
                label="Include Solar"
              />
              {usePv && (
                <>
                  <Typography variant="h6">Solar</Typography>
                  <TextField
                    label="Max kW"
                    type="number"
                    fullWidth
                    value={pvMaxKw}
                    onChange={(e) => setPvMaxKw(e.target.value)}
                  />
                </>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              <FormControlLabel
                control={
                  <Checkbox
                    checked={useStorage}
                    onChange={(e) => setUseStorage(e.target.checked)}
                  />
                }
                label="Include Battery Storage"
              />
              {useStorage && (
                <>
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
                </>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              <FormControlLabel
                control={
                  <Checkbox
                    checked={useGenerator}
                    onChange={(e) => setUseGenerator(e.target.checked)}
                  />
                }
                label="Include Generators"
              />
              {useGenerator && (
                <>
                  <Typography variant="h6">Generators</Typography>
                  <TextField
                    label="Max kW"
                    type="number"
                    fullWidth
                    value={generatorMaxKw}
                    onChange={(e) => setGeneratorMaxKw(e.target.value)}
                  />
                  <TextField
                    select
                    label="Fuel Type"
                    fullWidth
                    value={generatorFuelType}
                    onChange={(e) => setGeneratorFuelType(e.target.value)}
                  >
                    <MenuItem value="diesel">Diesel</MenuItem>
                    <MenuItem value="natural_gas">Natural Gas</MenuItem>
                    <MenuItem value="diesel_and_natural_gas">
                      Diesel &amp; Natural Gas
                    </MenuItem>
                  </TextField>
                </>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              <Typography variant="h6">Cost Estimates</Typography>
              {usePv && (
                <TextField
                  label="PV Cost per kW ($)"
                  type="number"
                  fullWidth
                  value={pvCost}
                  onChange={(e) => setPvCost(e.target.value)}
                />
              )}
              {useGenerator && generatorFuelType === "diesel" && (
                <TextField
                  label="Generator Fuel Cost ($/gal)"
                  type="number"
                  fullWidth
                  value={generatorFuelCostPerGallon}
                  onChange={(e) =>
                    setGeneratorFuelCostPerGallon(e.target.value)
                  }
                />
              )}
              {useGenerator && generatorFuelType === "natural_gas" && (
                <TextField
                  label="Generator Fuel Cost ($/MMBtu)"
                  type="number"
                  fullWidth
                  value={generatorFuelCostPerMmbtu}
                  onChange={(e) => setGeneratorFuelCostPerMmbtu(e.target.value)}
                />
              )}
              {useGenerator &&
                generatorFuelType === "diesel_and_natural_gas" && (
                  <>
                    <TextField
                      label="Diesel Fuel Cost ($/gal)"
                      type="number"
                      fullWidth
                      value={generatorFuelCostPerGallon}
                      onChange={(e) =>
                        setGeneratorFuelCostPerGallon(e.target.value)
                      }
                      sx={{ mb: 2 }}
                    />
                    <TextField
                      label="Natural Gas Fuel Cost ($/MMBtu)"
                      type="number"
                      fullWidth
                      value={generatorFuelCostPerMmbtu}
                      onChange={(e) =>
                        setGeneratorFuelCostPerMmbtu(e.target.value)
                      }
                    />
                  </>
                )}
            </CardContent>
          </Card>
          <Card>
            <CardContent
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              <Typography variant="h6">Operations</Typography>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={offGrid}
                    onChange={(e) => setOffGrid(e.target.checked)}
                  />
                }
                label="Off Grid"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={bessCanExport}
                    onChange={(e) => setBessCanExport(e.target.checked)}
                  />
                }
                label="BESS can Export"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={bessSolarOnly}
                    onChange={(e) => setBessSolarOnly(e.target.checked)}
                  />
                }
                label="BESS charges from Solar only"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={solarCanExport}
                    onChange={(e) => setSolarCanExport(e.target.checked)}
                  />
                }
                label="Solar can Export"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={genCanExport}
                    onChange={(e) => setGenCanExport(e.target.checked)}
                  />
                }
                label="Generator can Export"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={genChargeBess}
                    onChange={(e) => setGenChargeBess(e.target.checked)}
                  />
                }
                label="Generator can charge BESS"
              />
            </CardContent>
          </Card>
          <Box mt={2} mb={2}>
            <Button variant="contained" onClick={submit}>
              Run REopt
            </Button>
          </Box>
        </Box>
      )}
      {tab === 1 && (
        <Box>
          <Typography>Status: {status}</Typography>
          {error && (
            <Typography color="error" gutterBottom>
              Error: {error}
            </Typography>
          )}
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
                          Math.min(
                            364,
                            Math.max(0, parseInt(e.target.value || "0", 10)),
                          ),
                        )
                      }
                      sx={{ mb: 2 }}
                    />
                    <ResponsiveContainer width="100%" height={300}>
                      <AreaChart
                        data={chartData}
                        margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="hour" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        {timeSeries.map((ts, i) => (
                          <Area
                            type="monotone"
                            key={ts.key}
                            dataKey={ts.key}
                            name={ts.label}
                            stroke={COLORS[i % COLORS.length]}
                            fill={COLORS[i % COLORS.length]}
                            stackId="1"
                          />
                        ))}
                      </AreaChart>
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
        </Box>
      )}
    </Container>
  );
}

export default App;
