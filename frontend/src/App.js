import React, { useState, useEffect, useMemo } from "react";
import { reoptToDailySeries, transformReoptOutputs } from "./reoptTransform";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper } from '@mui/material';
import {
  Container,
  Typography,
  TextField,
  Button,
  Box,
  FormControlLabel,
  Checkbox,
  MenuItem,
  Card,
  CardContent,
  Tabs,
  Tab,
  FormControl,
  FormLabel,
  RadioGroup,
  Radio,
  Select,
  InputLabel,
} from "@mui/material";
import { LocalizationProvider, DatePicker } from "@mui/x-date-pickers";
import { AdapterDateFns } from "@mui/x-date-pickers/AdapterDateFns";
import PowerGraph from "./PowerGraph";
import LocationInput from "./LocationInput";
import SummaryCards from "./SummaryCards";
import EconomicsTable from "./EconomicsTable";
import PerformanceTable from "./PerformanceTable";
import ResiliencePanel from "./ResiliencePanel";
import EmissionsPanel from "./EmissionsPanel";
import PaymentScheduleTable from "./PaymentScheduleTable";

// Default constants (previously sourced from minimalScenario.json)
const DEFAULT_PV_COST_PER_KW = 900; // $/kW fallback
const DEFAULT_ANNUAL_KWH = 200000; // Used to seed a flat initial load profile
const DEFAULT_FINANCIAL = {
  elec_cost_escalation_rate_fraction: 0.03,
  offtaker_discount_rate_fraction: 0.1,
  analysis_years: 25,
  offtaker_tax_rate_fraction: 0.2,
  om_cost_escalation_rate_fraction: 0.02,
};

// Normalized 8760-hour load shapes for various facility types
const BASE_SHAPES = {
  industrial: normalizeShape(
    Array.from({ length: 8760 }, (_, i) => {
      const hour = i % 24;
      const day = Math.floor(i / 24);
      const seasonal = 0.8 + 0.1 * Math.sin((2 * Math.PI * day) / 365);
      const diurnal = 0.7 + 0.3 * (hour >= 6 && hour < 18 ? 1 : 0.5);
      return seasonal * diurnal;
    }),
  ),
  manufacturing: normalizeShape(
    Array.from({ length: 8760 }, (_, i) => {
      const hour = i % 24;
      const day = Math.floor(i / 24);
      const weekday = day % 7 < 5;
      const seasonal = 0.7 + 0.2 * Math.sin((2 * Math.PI * day) / 365);
      const base = weekday
        ? hour >= 7 && hour < 19
          ? 1
          : 0.3
        : hour >= 8 && hour < 16
        ? 0.5
        : 0.2;
      return seasonal * base;
    }),
  ),
  cold_storage: normalizeShape(
    Array.from({ length: 8760 }, (_, i) => {
      const hour = i % 24;
      const day = Math.floor(i / 24);
      const seasonal = 0.9 + 0.1 * Math.sin((2 * Math.PI * day) / 365);
      const diurnal = 0.85 + 0.15 * Math.cos((2 * Math.PI * hour) / 24);
      return seasonal * diurnal;
    }),
  ),
};

function normalizeShape(arr) {
  const max = Math.max(...arr);
  return arr.map((v) => v / max);
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

function validateTariff(tariff, schema) {
  if (!tariff || typeof tariff !== "object") return false;
  const tariffSchema = schema?.components?.schemas?.ElectricTariff;
  const variants = tariffSchema?.oneOf;
  if (!Array.isArray(variants)) return true;
  return variants.some((v) => {
    const required = v.required || [];
    return required.every((k) => tariff[k] !== undefined);
  });
}

function App() {
  const [location, setLocation] = useState("");
  const [sizingMode, setSizingMode] = useState("optimal");
  const [pvMaxKw, setPvMaxKw] = useState("0");
  const [pvCost, setPvCost] = useState(String(DEFAULT_PV_COST_PER_KW));
  const [storageMaxKw, setStorageMaxKw] = useState("0");
  const [storageMaxKwh, setStorageMaxKwh] = useState("0");

  const [usePv, setUsePv] = useState(false);
  const [useStorage, setUseStorage] = useState(false);
  const [useGenerator, setUseGenerator] = useState(false);

  const [generatorMaxKw, setGeneratorMaxKw] = useState("0");
  const [generatorFuelCostPerGallon, setGeneratorFuelCostPerGallon] =
    useState("3");
  const [generatorFuelCostPerMmbtu, setGeneratorFuelCostPerMmbtu] = useState("6");
  const [generatorFuelType, setGeneratorFuelType] = useState("diesel");

  const [bessCanExport, setBessCanExport] = useState(false);
  const [bessSolarOnly, setBessSolarOnly] = useState(false);
  const [solarCanExport, setSolarCanExport] = useState(false);
  const [genCanExport, setGenCanExport] = useState(false);
  const [genChargeBess, setGenChargeBess] = useState(false);
  const [tariffs, setTariffs] = useState([]);
  const [urdbLabel, setUrdbLabel] = useState("");
  const [showAllTariffs, setShowAllTariffs] = useState(false);
  const [offGrid, setOffGrid] = useState(false);
  const [schema, setSchema] = useState(null);

  const initialLoads = useMemo(
    () => Array(8760).fill(DEFAULT_ANNUAL_KWH / 8760),
    [],
  );
  const [loads, setLoads] = useState(initialLoads);
  const [loadYear, setLoadYear] = useState("2017");
  const [loadSummary, setLoadSummary] = useState(() =>
    summarizeLoads(initialLoads),
  );
  const [loadTab, setLoadTab] = useState(0);
  const [loadFileName, setLoadFileName] = useState("");
  const [peakLoad, setPeakLoad] = useState("0");
  const [genLoadFactor, setGenLoadFactor] = useState("0.5");
  const [siteType, setSiteType] = useState("industrial");

  const startDate = useMemo(
    () => new Date(parseInt(loadYear, 10) || 0, 0, 1),
    [loadYear],
  );
  const [selectedDate, setSelectedDate] = useState(startDate);

  const [runUuid, setRunUuid] = useState(null);
  const [status, setStatus] = useState("");
  const [outputs, setOutputs] = useState(null);
  const [results, setResults] = useState(null);
  const [dailyData, setDailyData] = useState([]);
  const graphData = useMemo(
    () =>
      dailyData.map((d) => ({
        timestamp: d.timestamp,
        load: d.load,
        // Utility energy serving load plus charging storage
        utility: (d.utility_to_load || 0) + (d.utility_to_bess || 0),
        // Solar gross (to load + to storage)
        solar: (d.solar_to_load || 0) + (d.solar_to_bess || 0),
        solar_to_load: d.solar_to_load || 0,
        solar_to_bess: d.solar_to_bess || 0,
  bess: d.bess_to_load || 0, // legacy key
  bess_discharge: d.bess_to_load || 0,
  bess_charge_solar: -(d.solar_to_bess || 0),
  bess_charge_grid: -(d.utility_to_bess || 0),
  bess_charge_gen: -(d.gen_to_bess || 0),
        genset: (d.diesel_to_load || 0) + (d.ng_to_load || 0),
        // Net utility import (include charging minus all exports)
        net_utility:
          ((d.utility_to_load || 0) + (d.utility_to_bess || 0)) -
          ((d.solar_export || 0) + (d.bess_export || 0) + (d.diesel_export || 0) + (d.ng_export || 0)),
      })),
    [dailyData],
  );
  const [structured, setStructured] = useState(null);
  const [scenario, setScenario] = useState("");
  const [dayIndex, setDayIndex] = useState("0");
  const [tph, setTph] = useState(1);
  const [error, setError] = useState("");
  const [tab, setTab] = useState(0); // 0: Utility & Load Data, 1: Microgrid Design, 2: Financial Outputs, 3: Performance Data

  useEffect(() => {
    const loadSchema = async () => {
      try {
        const res = await fetch("/schema");
        const data = await res.json();
        setSchema(data);
      } catch (e) {
        console.error("Schema fetch failed", e);
      }
    };
    loadSchema();
  }, []);

  useEffect(() => {
    setSelectedDate(startDate);
  }, [startDate]);

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
    const baseShape = BASE_SHAPES[siteType] || BASE_SHAPES.industrial;
    const avgNorm = baseShape.reduce((a, b) => a + b, 0) / 8760;
    const targetAverage = lf * peak;
    const a = (targetAverage - peak) / (avgNorm - 1);
    const b = peak - a;
    const arr = baseShape.map((v) => a * v + b);
    const peakCheck = Math.max(...arr);
    const avgCheck = arr.reduce((a, b) => a + b, 0) / 8760;
    console.assert(
      Math.abs(peakCheck - peak) < 1e-6,
      `Peak ${peakCheck} != ${peak}`,
    );
    console.assert(
      Math.abs(avgCheck - targetAverage) < 1e-6,
      `Average ${avgCheck} != ${targetAverage}`,
    );
    console.assert(
      arr.some((v) => v !== arr[0]),
      "Generated load profile is flat",
    );
    setLoadYear(String(new Date().getFullYear()));
    setLoads(arr);
  };

  const fetchTariffs = async (loc) => {
    setError("");
    setTariffs([]);
    const locationToUse = loc !== undefined ? loc : location;
    if (!locationToUse.trim()) {
      setError("Location is required to fetch tariffs");
      return;
    }
    try {
      const geoRes = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(locationToUse)}`,
      );
      const geoData = await geoRes.json();
      if (!geoData.length) {
        setError("Location not found");
        return;
      }
      const lat = parseFloat(geoData[0].lat);
      const lon = parseFloat(geoData[0].lon);
      const res = await fetch(`/urdb?lat=${lat}&lon=${lon}`);
      const data = await res.json();
      if (Array.isArray(data)) {
        setTariffs(data);
      } else if (data?.error) {
        setError(data.error);
      } else {
        setError("Unexpected tariff response shape");
      }
    } catch (e) {
      setError(`Tariff fetch failed: ${e.message}`);
    }
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

    if (!urdbLabel) {
      setError("Please select an electric tariff");
      setStatus("Error");
      return;
    }

    const scenario = {
      Site: { latitude: lat, longitude: lon },
      ElectricLoad: {
        year: parseInt(loadYear, 10),
        loads_kw: loads,
        annual_kwh: summary.total,
      },
      ElectricTariff: { urdb_label: urdbLabel },
      ElectricUtility: {}, // Kept empty unless future UI fields populate it
      Financial: { ...DEFAULT_FINANCIAL },
      Settings: { off_grid_flag: offGrid },
    };

    if (!validateTariff(scenario.ElectricTariff, schema)) {
      setError("ElectricTariff is invalid");
      setStatus("Error");
      return;
    }

    if (usePv) {
      scenario.PV = {
        ...(sizingMode === "optimal"
          ? { max_kw: parseFloat(pvMaxKw) }
          : {
              existing_kw: parseFloat(pvMaxKw),
              max_kw: parseFloat(pvMaxKw),
            }),
        installed_cost_per_kw: parseFloat(pvCost || "0"),
        can_export: solarCanExport,
      };
    }

    if (useStorage) {
      scenario.ElectricStorage = {
        ...(sizingMode === "optimal"
          ? {
              max_kw: parseFloat(storageMaxKw),
              max_kwh: parseFloat(storageMaxKwh),
            }
          : {
              existing_kw: parseFloat(storageMaxKw),
              existing_kwh: parseFloat(storageMaxKwh),
              max_kw: parseFloat(storageMaxKw),
              max_kwh: parseFloat(storageMaxKwh),
            }),
        can_export: bessCanExport,
        charge_from_pv_only: bessSolarOnly,
      };
    }

    if (useGenerator) {
      scenario.Generator = {
        ...(sizingMode === "optimal"
          ? { max_kw: parseFloat(generatorMaxKw) }
          : {
              existing_kw: parseFloat(generatorMaxKw),
              max_kw: parseFloat(generatorMaxKw),
            }),
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
        const res = await fetch(`/status/${encodeURIComponent(runUuid)}`, {
          headers: {},
        });
        const text = await res.text();
        let data = null;
        try {
          data = JSON.parse(text);
        } catch {}
        if (!res.ok) {
          console.error("Status request failed", {
            runUuid,
            status: res.status,
            body: text,
          });
          const body = (data && data.error) || text || res.statusText;
          const message = `Status check failed for run ${runUuid} (HTTP ${res.status}): ${body}`;
          setError(message);
          setStatus("Error");
          return;
        }
        if (!data) {
          setError(text || "Invalid JSON response");
          setStatus("Error");
          return;
        }
        if (data.error) {
          setError(
            data.details ? `${data.error}: ${data.details}` : data.error,
          );
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

  // Fetch detailed results and build daily chart data
  useEffect(() => {
    if (!runUuid || !outputs) return;
    const fetchResults = async () => {
      try {
        const res = await fetch(`/results/${encodeURIComponent(runUuid)}`);
        const data = await res.json();
        setResults(data);
        const structuredData = transformReoptOutputs(data);
        setStructured(structuredData);
        const names = Object.keys(structuredData.scenarios || {});
        setScenario((s) => s || names[0] || "");
        const steps = data?.outputs?.Settings?.time_steps_per_hour || 1;
        setTph(steps);
        setDailyData(
          reoptToDailySeries(data, parseInt(dayIndex, 10) || 0, steps),
        );
      } catch (e) {
        console.error("Results fetch failed", e);
      }
    };
    fetchResults();
  }, [runUuid, outputs]);

  useEffect(() => {
    if (!results) return;
    setDailyData(
      reoptToDailySeries(results, parseInt(dayIndex, 10) || 0, tph),
    );
  }, [results, dayIndex, tph]);

  useEffect(() => {
    if (tab !== 3) {
      setDayIndex("0");
      setSelectedDate(startDate);
    }
  }, [tab, startDate]);

  const utilityLoadPanel = (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Card>
        <CardContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Typography variant="h6">Site</Typography>
          <LocationInput
            value={location}
            onValueCommit={(val) => {
              setLocation(val);
              setUrdbLabel("");
              setTariffs([]);
            }}
            onFindTariffs={(val) => fetchTariffs(val)}
          />
          {/* Tariff filtering toggle */}
          {tariffs.length > 0 && (
            <FormControlLabel
              control={<Checkbox checked={showAllTariffs} onChange={e=>setShowAllTariffs(e.target.checked)} />}
              label="Show all tariffs (include residential & others)"
            />
          )}
          {tariffs.length > 0 && (
            <Typography variant="caption" sx={{ mt: -1 }}>
              Showing {showAllTariffs ? 'all' : 'top 20 non-residential'} (filtered from {tariffs.length})
            </Typography>
          )}
          {tariffs.length > 0 && (
            <TariffSelect
              tariffs={tariffs}
              showAll={showAllTariffs}
              value={urdbLabel}
              onChange={setUrdbLabel}
            />
          )}
          {urdbLabel && (
            <TariffDetails tariff={tariffs.find(t => t.label === urdbLabel)} />
          )}
        </CardContent>
      </Card>
      <Card>
        <CardContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Typography variant="h6">Load Profile</Typography>
          <Tabs value={loadTab} onChange={(e, v) => setLoadTab(v)}>
            <Tab label="Upload CSV" />
            <Tab label="Generate" />
          </Tabs>
          <TextField
            label="Load Year"
            type="number"
            value={loadYear}
            onChange={(e) => setLoadYear(e.target.value)}
            onBlur={() =>
              setLoadYear(String(parseInt(loadYear, 10) || 0))
            }
          />
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
                onBlur={() =>
                  setPeakLoad(String(parseFloat(peakLoad) || 0))
                }
              />
              <TextField
                label="Load Factor"
                type="number"
                value={genLoadFactor}
                onChange={(e) => setGenLoadFactor(e.target.value)}
                onBlur={() =>
                  setGenLoadFactor(String(parseFloat(genLoadFactor) || 0))
                }
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
        </CardContent>
      </Card>
    </Box>
  );

  const microgridDesignPanel = (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <FormControl component="fieldset">
        <FormLabel component="legend">Sizing Mode</FormLabel>
        <RadioGroup
          row
          value={sizingMode}
          onChange={(e) => setSizingMode(e.target.value)}
        >
          <FormControlLabel
            value="optimal"
            control={<Radio />}
            label="Find Optimal Sizing"
          />
          <FormControlLabel
            value="existing"
            control={<Radio />}
            label="Model Selected Design"
          />
        </RadioGroup>
      </FormControl>
      <Card>
        <CardContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
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
                label={sizingMode === "optimal" ? "Max kW" : "Existing kW"}
                type="number"
                fullWidth
                value={pvMaxKw}
                onChange={(e) => setPvMaxKw(e.target.value)}
                onBlur={() =>
                  setPvMaxKw(String(parseFloat(pvMaxKw) || 0))
                }
              />
            </>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
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
                label={sizingMode === "optimal" ? "Max kW" : "Existing kW"}
                type="number"
                fullWidth
                value={storageMaxKw}
                onChange={(e) => setStorageMaxKw(e.target.value)}
                onBlur={() =>
                  setStorageMaxKw(String(parseFloat(storageMaxKw) || 0))
                }
              />
              <TextField
                label={sizingMode === "optimal" ? "Max kWh" : "Existing kWh"}
                type="number"
                fullWidth
                value={storageMaxKwh}
                onChange={(e) => setStorageMaxKwh(e.target.value)}
                onBlur={() =>
                  setStorageMaxKwh(String(parseFloat(storageMaxKwh) || 0))
                }
              />
            </>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
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
                label={sizingMode === "optimal" ? "Max kW" : "Existing kW"}
                type="number"
                fullWidth
                value={generatorMaxKw}
                onChange={(e) => setGeneratorMaxKw(e.target.value)}
                onBlur={() =>
                  setGeneratorMaxKw(String(parseFloat(generatorMaxKw) || 0))
                }
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
        <CardContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Typography variant="h6">Cost Estimates</Typography>
          {usePv && (
            <TextField
              label="PV Cost per kW ($)"
              type="number"
              fullWidth
              value={pvCost}
              onChange={(e) => setPvCost(e.target.value)}
              onBlur={() => setPvCost(String(parseFloat(pvCost) || 0))}
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
              onBlur={() =>
                setGeneratorFuelCostPerGallon(
                  String(parseFloat(generatorFuelCostPerGallon) || 0),
                )
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
              onBlur={() =>
                setGeneratorFuelCostPerMmbtu(
                  String(parseFloat(generatorFuelCostPerMmbtu) || 0),
                )
              }
            />
          )}
          {useGenerator && generatorFuelType === "diesel_and_natural_gas" && (
            <>
              <TextField
                label="Diesel Fuel Cost ($/gal)"
                type="number"
                fullWidth
                value={generatorFuelCostPerGallon}
                onChange={(e) =>
                  setGeneratorFuelCostPerGallon(e.target.value)
                }
                onBlur={() =>
                  setGeneratorFuelCostPerGallon(
                    String(parseFloat(generatorFuelCostPerGallon) || 0),
                  )
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
                onBlur={() =>
                  setGeneratorFuelCostPerMmbtu(
                    String(parseFloat(generatorFuelCostPerMmbtu) || 0),
                  )
                }
              />
            </>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
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
        <Button variant="contained" onClick={submit} disabled={!urdbLabel}>
          Run REopt
        </Button>
      </Box>
    </Box>
  );

  const scenarioOptions = Object.keys(structured?.scenarios || {});
  const currentScenario = structured?.scenarios?.[scenario] || null;
  const financialOutputsPanel = !currentScenario ? (
    <Typography>No financial results available.</Typography>
  ) : (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {scenarioOptions.length > 1 && (
        <FormControl size="small" sx={{ maxWidth: 200 }}>
          <InputLabel>Scenario</InputLabel>
          <Select
            value={scenario}
            label="Scenario"
            onChange={(e) => setScenario(e.target.value)}
          >
            {scenarioOptions.map((s) => (
              <MenuItem key={s} value={s}>
                {s}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}
      <SummaryCards data={currentScenario.financial} />
      <EconomicsTable data={currentScenario.financial} />
      <PerformanceTable data={currentScenario.performance} />
      <ResiliencePanel data={currentScenario.resilience} />
      <EmissionsPanel data={currentScenario.emissions} />
      <PaymentScheduleTable data={currentScenario.payments} />
    </Box>
  );

  const performancePanel = (
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
          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <DatePicker
              label="Date"
              views={["month", "day"]}
              format="MM/dd"
              value={selectedDate}
              onChange={(newValue) => {
                if (newValue) {
                  setSelectedDate(newValue);
                  const diff = Math.floor(
                    (newValue - startDate) / (24 * 60 * 60 * 1000),
                  );
                  setDayIndex(
                    String(Math.min(364, Math.max(0, diff))),
                  );
                }
              }}
              slotProps={{ textField: { sx: { mb: 2 } } }}
            />
          </LocalizationProvider>
          <PowerGraph data={graphData} />
        </Box>
      )}
    </Box>
  );

  return (
    <Container sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom>
        REopt MVP
      </Typography>
      <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label="Utility & Load Data" />
        <Tab label="Microgrid Design" />
        <Tab label="Financial Outputs" />
        <Tab label="Performance Data & Visualizations" />
      </Tabs>
      {tab === 0 && utilityLoadPanel}
      {tab === 1 && microgridDesignPanel}
      {tab === 2 && financialOutputsPanel}
      {tab === 3 && performancePanel}
    </Container>
  );
}

export default App;

// Tariff dropdown with filtering logic
function TariffSelect({ tariffs, showAll, value, onChange }) {
  const filtered = React.useMemo(() => {
    if (showAll) return tariffs;
    // Exclude residential sector
    const nonRes = tariffs.filter(t => !/residential/i.test(t.sector || ''));
    // Heuristic ranking
    const ranked = nonRes.map(t => {
      const energyPeriods = Array.isArray(t.energyratestructure) ? t.energyratestructure.length : 0;
      const demandPeriods = Array.isArray(t.demandratestructure) ? t.demandratestructure.length : 0;
      const sector = (t.sector || '').toLowerCase();
      let score = 0;
      if (/industrial|large/.test(sector)) score += 6;
      else if (/commercial|general/.test(sector)) score += 5;
      else if (/municipal|government/.test(sector)) score += 3;
      if (demandPeriods) score += 3;
      if (energyPeriods > 1) score += 1;
      // Recency: later startdate (epoch) => small bonus scaled
      if (t.startdate) score += (t.startdate / 1e9); // keep modest influence
      return { t, score };
    }).sort((a,b)=> b.score - a.score);
    const top = ranked.slice(0,20).map(r => r.t);
    return top;
  }, [tariffs, showAll]);

  // Ensure selected value appears even if not in filtered list
  const displayList = React.useMemo(() => {
    if (!value) return filtered;
    if (filtered.some(t => t.label === value)) return filtered;
    const found = tariffs.find(t => t.label === value);
    return found ? [found, ...filtered] : filtered;
  }, [filtered, value, tariffs]);

  return (
    <TextField
      select
      label="Electric Tariff"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      fullWidth
    >
      {displayList.map(t => (
        <MenuItem key={t.label} value={t.label}>
          {t.name || t.label}
        </MenuItem>
      ))}
    </TextField>
  );
}

// Tariff details with tiered Time-of-Use breakdown
function TariffDetails({ tariff }) {
  const [detail, setDetail] = React.useState(tariff);
  const attemptedRef = React.useRef(false);
  React.useEffect(() => {
    setDetail(tariff);
    attemptedRef.current = false; // reset attempt if user selects new tariff
  }, [tariff]);
  React.useEffect(() => {
    if (!detail) return;
    const hasStructures = Array.isArray(detail.energyratestructure) || Array.isArray(detail.demandratestructure);
    if (hasStructures) return; // already have what we need
    if (attemptedRef.current) return; // avoid refetch loop if API does not provide structures
    attemptedRef.current = true;
    // Fetch full detail if missing structures
    const controller = new AbortController();
    fetch(`/urdb/${encodeURIComponent(detail.label)}`, { signal: controller.signal })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d && !d.error) {
          // Only update if new object actually has structures; else keep original to prevent re-render loop
            if (Array.isArray(d.energyratestructure) || Array.isArray(d.demandratestructure)) {
              setDetail(d);
            }
        }
      })
      .catch(() => {});
    return () => controller.abort();
  }, [detail]);
  if (!detail) return null;
  const tariffObj = detail;
  const energyPeriods = Array.isArray(tariffObj.energyratestructure) ? [...tariffObj.energyratestructure] : [];
  const demandPeriods = Array.isArray(tariffObj.demandratestructure) ? [...tariffObj.demandratestructure] : [];
  const energySeasonMap = tariffObj.energyweekdayschedule || tariffObj.energyweekendschedule ? true : false;
  const demandSeasonMap = tariffObj.demandweekdayschedule || tariffObj.demandweekendschedule ? true : false;

  const getFirstRate = (periods) => {
    if (!Array.isArray(periods)) return null;
    for (const p of periods) {
      if (Array.isArray(p)) {
        for (const b of p) {
          if (b && b.rate != null) return b.rate;
        }
      } else if (p && p.rate != null) {
        return p.rate;
      }
    }
    return null;
  };
  const energyRate = getFirstRate(energyPeriods);
  const demandRate = getFirstRate(demandPeriods);

  const buildTierRows = (periods, isDemand=false) => {
    const rows = [];
    periods.forEach((period, pIdx) => {
      if (!Array.isArray(period)) {
        // Some APIs may return object for single period; skip if not list
        return;
      }
      period.forEach((block, bIdx) => {
        // A tier may itself be an array of component objects (generation, delivery, etc.)
        let components = [];
        if (Array.isArray(block)) {
          components = block.filter(c => c && typeof c === 'object');
        } else if (block && typeof block === 'object') {
          components = [block];
        }
        if (!components.length) return;
        // classify components
        let gen = 0, del = 0, other = 0, maxVal = null;
        components.forEach(c => {
          const r = (c.rate != null ? c.rate : 0) + (c.adj != null ? c.adj : 0);
          if (c.max != null) {
            // Use the smallest non-null max to represent tier cap
            maxVal = maxVal == null ? c.max : Math.min(maxVal, c.max);
          }
          const name = (c.name || '').toLowerCase();
          if (/gen(eration)?/.test(name)) gen += r;
          else if (/(deliv|dist|trans|wires)/.test(name)) del += r;
          else other += r;
        });
        const total = gen + del + other;
        rows.push({
          period: pIdx + 1,
            tier: bIdx + 1,
            rate: total,
            gen: gen || null,
            delivery: del || null,
            other: other || null,
            max: maxVal,
            units: isDemand ? '$/kW' : '$/kWh'
        });
      });
    });
    return rows;
  };
  // Fallback: if no periods but flat fields exist
  if (!energyPeriods.length && Array.isArray(tariffObj.flatenergyratestructure)) {
    energyPeriods.push(tariffObj.flatenergyratestructure);
  }
  if (!demandPeriods.length && Array.isArray(tariffObj.flatdemandratestructure)) {
    demandPeriods.push(tariffObj.flatdemandratestructure);
  }
  const energyTiers = buildTierRows(energyPeriods, false);
  const demandTiers = buildTierRows(demandPeriods, true);

  // Derive first-tier generation/delivery breakdown if available
  let firstGen=null, firstDel=null, firstTotal=energyRate;
  if (energyTiers.length) {
    const ft = energyTiers[0];
    firstTotal = ft.rate;
    if (ft.gen != null) firstGen = ft.gen;
    if (ft.delivery != null) firstDel = ft.delivery;
  }

  // ---- TOU Schedule Interpretation ----
  // URDB schedules: energyweekdayschedule[month][hour] => period index (1-based) or 0
  function buildHourMap(schedule) {
    const map = {};
    if (!Array.isArray(schedule) || !schedule.length) return map;
    schedule.forEach(monthArr => {
      if (!Array.isArray(monthArr) || monthArr.length !== 24) return;
      monthArr.forEach((p, hr) => {
        if (p == null) return;
        const period = p; // keep as-is (often 1+)
        if (period === 0) return; // 0 sometimes means no TOU assignment
        map[period] = map[period] || new Set();
        map[period].add(hr);
      });
    });
    // Convert sets to sorted arrays
    Object.keys(map).forEach(k => {
      map[k] = Array.from(map[k]).sort((a,b)=>a-b);
    });
    return map;
  }
  function hoursToRanges(hours) {
    if (!hours || !hours.length) return '';
    const ranges=[]; let start=hours[0]; let prev=hours[0];
    for (let i=1;i<=hours.length;i++) {
      const h=hours[i];
      if (h!==prev+1) {
        ranges.push(start===prev? `${start}`: `${start}-${prev+1}`); // treat end as exclusive hour
        start=h; prev=h;
      } else {
        prev=h;
      }
    }
    return ranges.join(', ');
  }
  const weekdayHourMap = buildHourMap(tariffObj.energyweekdayschedule);
  const weekendHourMap = buildHourMap(tariffObj.energyweekendschedule);
  // First-tier rate per period (total) using first occurrence of that period in energyTiers
  const periodRates = {};
  energyTiers.forEach(t => {
    if (periodRates[t.period] == null) periodRates[t.period] = t.rate;
  });
  const periodEntries = Object.keys({ ...weekdayHourMap, ...weekendHourMap })
    .map(p => ({
      period: parseInt(p,10),
      weekdayHours: hoursToRanges(weekdayHourMap[p]),
      weekendHours: hoursToRanges(weekendHourMap[p]),
      rate: periodRates[p] != null ? periodRates[p] : null,
    }))
    .sort((a,b)=>a.period-b.period);
  // Classification: Peak (highest rate), Off-Peak (lowest), others Mid-Peak
  if (periodEntries.length >= 2) {
    const sortedByRate = periodEntries.filter(e=>e.rate!=null).slice().sort((a,b)=>b.rate-a.rate);
    if (sortedByRate.length) sortedByRate[0].classification = 'Peak';
    if (sortedByRate.length>1) sortedByRate[sortedByRate.length-1].classification = 'Off-Peak';
    sortedByRate.forEach(e=>{ if (!e.classification) e.classification = 'Mid-Peak'; });
  }

  // Build seasons: group contiguous months where classification hour maps match
  function monthClassificationSignature(monthIdx) {
    // Build per-classification hours for this month (weekday/weekend)
    const weekday = Array.isArray(tariffObj.energyweekdayschedule) && tariffObj.energyweekdayschedule[monthIdx] || [];
    const weekend = Array.isArray(tariffObj.energyweekendschedule) && tariffObj.energyweekendschedule[monthIdx] || [];
    const map = {}; // classification -> {wd:Set, we:Set}
    function addHours(arr, isWeekend) {
      if (!Array.isArray(arr) || arr.length!==24) return;
      arr.forEach((p,h)=>{
        if (!p) return; // skip 0
        const entry = periodEntries.find(e=>e.period===p);
        if (!entry) return;
        const cls = entry.classification || 'Period';
        map[cls] = map[cls] || {wd:new Set(), we:new Set()};
        (isWeekend? map[cls].we : map[cls].wd).add(h);
      });
    }
    addHours(weekday,false);
    addHours(weekend,true);
    // Serialize deterministic signature
    const sigObj = Object.keys(map).sort().reduce((acc,k)=>{
      const wd = Array.from(map[k].wd).sort((a,b)=>a-b);
      const we = Array.from(map[k].we).sort((a,b)=>a-b);
      acc[k] = {wd, we};
      return acc;
    },{});
    return { signature: JSON.stringify(sigObj), detail: sigObj };
  }
  const months = Array.from({length:12},(_,i)=>i);
  const monthSigs = months.map(m=>monthClassificationSignature(m));
  const seasons = [];
  let current = null;
  months.forEach(m=>{
    const {signature, detail} = monthSigs[m];
    if (!current || current.signature!==signature) {
      current = { start:m, end:m, signature, detail };
      seasons.push(current);
    } else {
      current.end = m;
    }
  });
  const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function rangesFromHourArray(arr){ return hoursToRanges(arr); }

  // Build period -> classification and rate maps for heatmap
  const periodClassMap = {}; const periodRateMap = {};
  periodEntries.forEach(p=>{ periodClassMap[p.period]=p.classification; periodRateMap[p.period]=p.rate; });
  function buildScheduleMatrix(schedule) {
    if (!Array.isArray(schedule)) return [];
    return schedule.map((monthArr, mIdx) => {
      if (!Array.isArray(monthArr) || monthArr.length !== 24) return Array(24).fill(null);
      return monthArr.map((p,h) => {
        if (!p) return null; // 0 or null = no period
        return {
          period: p,
          classification: periodClassMap[p] || 'Period',
          rate: periodRateMap[p] || null,
          hour: h,
          month: mIdx,
        };
      });
    });
  }
  const weekdayMatrix = buildScheduleMatrix(tariffObj.energyweekdayschedule);
  const weekendMatrix = buildScheduleMatrix(tariffObj.energyweekendschedule);
  const hasHeatmap = weekdayMatrix.length === 12 && weekdayMatrix.some(r=>Array.isArray(r));
  const classColors = {
    'Peak': '#d73027',
    'Mid-Peak': '#fee08b',
    'Off-Peak': '#1a9850',
    'Period': '#cccccc'
  };
  const textColorFor = (bg) => {
    if (!bg) return '#000';
    // simple luminance check
    const c = bg.substring(1);
    const r = parseInt(c.substr(0,2),16), g=parseInt(c.substr(2,2),16), b=parseInt(c.substr(4,2),16);
    const lum = 0.299*r+0.587*g+0.114*b;
    return lum < 140 ? '#fff' : '#000';
  };

  return (
  <TableContainer component={Paper} variant="outlined" sx={{ maxWidth: 640 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell colSpan={2} sx={{ fontWeight: 600 }}>Tariff Details</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          <TableRow>
            <TableCell sx={{ fontWeight: 500 }}>Label</TableCell>
      <TableCell>{tariffObj.label}</TableCell>
          </TableRow>
      {tariffObj.utility && (
            <TableRow>
              <TableCell sx={{ fontWeight: 500 }}>Utility</TableCell>
        <TableCell>{tariffObj.utility}</TableCell>
            </TableRow>
          )}
          {hasHeatmap && (
            <TableRow>
              <TableCell colSpan={2} sx={{ p:0 }}>
                <Box sx={{ mt:2 }}>
                  <Typography variant="subtitle2" sx={{ mb:1 }}>TOU Heatmap (Weekday)</Typography>
                  <Box sx={{ display:'grid', gridTemplateColumns:`80px repeat(24, 1fr)`, rowGap:0.5, columnGap:0.5, fontSize:'0.65rem' }}>
                    <Box></Box>
                    {Array.from({length:24},(_,h)=>(<Box key={h} sx={{ textAlign:'center' }}>{h}</Box>))}
                    {weekdayMatrix.map((row,m)=>(
                      <React.Fragment key={m}>
                        <Box sx={{ fontWeight:600, textAlign:'right', pr:0.5 }}>{MONTH_NAMES[m]}</Box>
                        {row.map((cell,h)=>(
                          <Box key={h} title={cell? `${MONTH_NAMES[m]} h${h}: ${cell.classification}${cell.rate!=null?` ${cell.rate.toFixed(4)} $/kWh`:''}`: 'No TOU'}
                            sx={{
                              height:20,
                              lineHeight:'20px',
                              textAlign:'center',
                              border:'1px solid #eee',
                              backgroundColor: cell? classColors[cell.classification] : '#f5f5f5',
                              color: cell? textColorFor(classColors[cell.classification]) : '#999',
                              overflow:'hidden',
                              whiteSpace:'nowrap'
                            }}>
                            {cell && cell.rate!=null ? cell.rate.toFixed(2) : ''}
                          </Box>
                        ))}
                      </React.Fragment>
                    ))}
                  </Box>
                  {weekendMatrix.length === 12 && (
                    <>
                      <Typography variant="subtitle2" sx={{ mt:2, mb:1 }}>TOU Heatmap (Weekend)</Typography>
                      <Box sx={{ display:'grid', gridTemplateColumns:`80px repeat(24, 1fr)`, rowGap:0.5, columnGap:0.5, fontSize:'0.65rem' }}>
                        <Box></Box>
                        {Array.from({length:24},(_,h)=>(<Box key={h} sx={{ textAlign:'center' }}>{h}</Box>))}
                        {weekendMatrix.map((row,m)=>(
                          <React.Fragment key={m}>
                            <Box sx={{ fontWeight:600, textAlign:'right', pr:0.5 }}>{MONTH_NAMES[m]}</Box>
                            {row.map((cell,h)=>(
                              <Box key={h} title={cell? `${MONTH_NAMES[m]} (WE) h${h}: ${cell.classification}${cell.rate!=null?` ${cell.rate.toFixed(4)} $/kWh`:''}`: 'No TOU'}
                                sx={{
                                  height:20,
                                  lineHeight:'20px',
                                  textAlign:'center',
                                  border:'1px solid #eee',
                                  backgroundColor: cell? classColors[cell.classification] : '#f5f5f5',
                                  color: cell? textColorFor(classColors[cell.classification]) : '#999',
                                  overflow:'hidden',
                                  whiteSpace:'nowrap'
                                }}>
                                {cell && cell.rate!=null ? cell.rate.toFixed(2) : ''}
                              </Box>
                            ))}
                          </React.Fragment>
                        ))}
                      </Box>
                    </>
                  )}
                  <Box sx={{ display:'flex', gap:2, mt:1, fontSize:'0.7rem' }}>
                    {Object.entries(classColors).map(([k,v])=>(
                      <Box key={k} sx={{ display:'flex', alignItems:'center', gap:0.5 }}>
                        <Box sx={{ width:14, height:14, backgroundColor:v, border:'1px solid #999' }} /> {k}
                      </Box>
                    ))}
                  </Box>
                </Box>
              </TableCell>
            </TableRow>
          )}
      {tariffObj.sector && (
            <TableRow>
              <TableCell sx={{ fontWeight: 500 }}>Sector</TableCell>
        <TableCell>{tariffObj.sector}</TableCell>
            </TableRow>
          )}
          <TableRow>
            <TableCell sx={{ fontWeight: 500 }}>Energy Rate (1st Tier)</TableCell>
            <TableCell>
              {firstTotal != null ? `${firstTotal.toFixed(4)} $/kWh` : '—'}
              {firstGen != null || firstDel != null ? (
                <span style={{ color:'#555', marginLeft:8 }}>
                  {firstGen != null && `Gen ${firstGen.toFixed(4)}`} {firstDel != null && `Del ${firstDel.toFixed(4)}`}
                </span>
              ) : null}
            </TableCell>
          </TableRow>
            <TableRow>
              <TableCell sx={{ fontWeight: 500 }}>Demand Rate (1st Tier)</TableCell>
              <TableCell>{demandRate != null ? `${demandRate.toFixed(2)} $/kW` : '—'}</TableCell>
            </TableRow>
          {energyTiers.length > 0 && (
            <TableRow>
              <TableCell colSpan={2} sx={{ p: 0 }}>
                <Table size="small" sx={{ '& td, & th': { border: 0 } }}>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Energy TOU Period</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Tier</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Up To (kWh)</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Generation ($/kWh)</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Delivery ($/kWh)</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Other ($/kWh)</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Total ($/kWh)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {energyTiers.map(r => (
                      <TableRow key={`e-${r.period}-${r.tier}`}>
                        <TableCell>{r.period}</TableCell>
                        <TableCell>{r.tier}</TableCell>
                        <TableCell>{r.max != null ? r.max : '—'}</TableCell>
                        <TableCell>{r.gen != null ? r.gen.toFixed(4) : '—'}</TableCell>
                        <TableCell>{r.delivery != null ? r.delivery.toFixed(4) : '—'}</TableCell>
                        <TableCell>{r.other != null ? r.other.toFixed(4) : (r.gen==null && r.delivery==null ? '—' : '0.0000')}</TableCell>
                        <TableCell>{r.rate.toFixed(4)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableCell>
            </TableRow>
          )}
          {seasons.length > 0 && (
            <TableRow>
              <TableCell colSpan={2} sx={{ p:0 }}>
                <Table size="small" sx={{ '& td, & th': { border:0 }, mt:1 }}>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight:600 }}>Season (Months)</TableCell>
                      <TableCell sx={{ fontWeight:600 }}>Classification</TableCell>
                      <TableCell sx={{ fontWeight:600 }}>Weekday Hours</TableCell>
                      <TableCell sx={{ fontWeight:600 }}>Weekend Hours</TableCell>
                      <TableCell sx={{ fontWeight:600 }}>First-Tier Rate ($/kWh)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {seasons.map((s, idx) => {
                      // For each classification within season detail
                      const classKeys = Object.keys(s.detail).sort((a,b)=> a.localeCompare(b));
                      return classKeys.map((cls, i2) => {
                        const wd = s.detail[cls].wd; const we = s.detail[cls].we;
                        // Find representative period entry rate: choose first period whose classification matches
                        const rateEntry = periodEntries.find(p => p.classification === cls);
                        const monthsLabel = s.start===s.end ? MONTH_NAMES[s.start] : `${MONTH_NAMES[s.start]}-${MONTH_NAMES[s.end]}`;
                        return (
                          <TableRow key={`season-${idx}-${cls}`}> 
                            <TableCell>{i2===0? monthsLabel: ''}</TableCell>
                            <TableCell>{cls}</TableCell>
                            <TableCell>{wd.length? rangesFromHourArray(wd): '—'}</TableCell>
                            <TableCell>{we.length? rangesFromHourArray(we): '—'}</TableCell>
                            <TableCell>{rateEntry && rateEntry.rate!=null ? rateEntry.rate.toFixed(4): '—'}</TableCell>
                          </TableRow>
                        );
                      });
                    })}
                  </TableBody>
                </Table>
              </TableCell>
            </TableRow>
          )}
          {demandTiers.length > 0 && (
            <TableRow>
              <TableCell colSpan={2} sx={{ p: 0 }}>
                <Table size="small" sx={{ '& td, & th': { border: 0 } }}>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Demand TOU Period</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Tier</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Up To (kW)</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Rate ($/kW)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {demandTiers.map(r => (
                      <TableRow key={`d-${r.period}-${r.tier}`}>
                        <TableCell>{r.period}</TableCell>
                        <TableCell>{r.tier}</TableCell>
                        <TableCell>{r.max != null ? r.max : '—'}</TableCell>
                        <TableCell>{r.rate.toFixed(2)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableCell>
            </TableRow>
          )}
          {energyTiers.length === 0 && demandTiers.length === 0 && (
            <TableRow>
              <TableCell colSpan={2} sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
                No rate structure fields returned. Provide OPEN_EI_API_KEY server env var to enable detailed rates.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
