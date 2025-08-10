export function reoptToDailySeries(results, dayIndex = 0, tph = 1) {
  if (!results) return [];
  const outputs = results.outputs || {};

  // Helper to pick the first array among candidate keys, preferring any that have non-zero values.
  const pick = (obj, keys) => {
    if (!obj) return [];
    for (const k of keys) {
      const arr = obj[k];
      if (Array.isArray(arr) && arr.some(v => Math.abs(v) > 1e-9)) return arr;
    }
    for (const k of keys) {
      const arr = obj[k];
      if (Array.isArray(arr)) return arr;
    }
    return [];
  };

  // Series lookups with multiple possible key names (covers REopt v2/v3 variants & potential future changes)
  const load = pick(outputs?.ElectricLoad, ["load_series_kw", "electric_load_series_kw"]);

  const pv_to_load    = pick(outputs?.PV, ["electric_to_load_series_kw", "pv_to_load_series_kw"]);
  const pv_to_storage = pick(outputs?.PV, ["electric_to_storage_series_kw", "pv_to_storage_series_kw", "to_storage_series_kw"]);
  const pv_to_grid    = pick(outputs?.PV, ["electric_to_grid_series_kw", "electric_export_to_grid_series_kw", "to_grid_series_kw"]);

  const es_to_load = pick(outputs?.ElectricStorage, [
    "electric_to_load_series_kw",
    "storage_to_load_series_kw",
    "discharge_to_load_series_kw",
    "discharge_series_kw"
  ]);
  const es_to_grid = pick(outputs?.ElectricStorage, [
    "electric_to_grid_series_kw",
    "storage_to_grid_series_kw",
    "discharge_to_grid_series_kw",
    "export_to_grid_series_kw"
  ]);
  const es_soc_pct = pick(outputs?.ElectricStorage, [
    "soc_series_pct",
    "state_of_charge_series_pct",
    "soc_pct_series"
  ]);

  const util_to_load = pick(outputs?.ElectricUtility, ["electric_to_load_series_kw", "grid_to_load_series_kw"]);
  const util_to_storage = pick(outputs?.ElectricUtility, [
    "electric_to_storage_series_kw",
    "grid_to_storage_series_kw",
    "load_to_storage_series_kw",
    "from_grid_to_storage_series_kw"
  ]);

  const gen_to_load  = pick(outputs?.Generator, ["electric_to_load_series_kw", "gen_to_load_series_kw"]);
  const gen_export   = pick(outputs?.Generator, ["electric_to_grid_series_kw", "gen_to_grid_series_kw"]);
  const chp_to_load  = pick(outputs?.CHP, ["electric_to_load_series_kw", "chp_to_load_series_kw"]);
  const chp_export   = pick(outputs?.CHP, ["electric_to_grid_series_kw", "chp_to_grid_series_kw"]);

  const year =
    results?.inputs?.Scenario?.analysis_year ||
    results?.inputs?.Financial?.analysis_year ||
    2017;

  // Local midnight base
  const baseTimestamp = new Date(year, 0, 1).getTime();

  const stepsPerDay = 24 * tph;
  const start = dayIndex * stepsPerDay;
  const data = [];

  for (let i = 0; i < stepsPerDay; i++) {
    const idx = start + i;
    const ts = baseTimestamp + (idx * 3600 * 1000) / tph;
    const clamp = (v) => (Math.abs(v) < 1e-6 ? 0 : v);
    data.push({
      timestamp: ts,
      hour: i / tph,
      load: clamp(load[idx] ?? 0),
      utility_to_load: clamp(util_to_load[idx] ?? 0),
      bess_to_load: clamp(es_to_load[idx] ?? 0),
      solar_to_load: clamp(pv_to_load[idx] ?? 0),
      diesel_to_load: clamp(gen_to_load[idx] ?? 0),
      ng_to_load: clamp(chp_to_load[idx] ?? 0),
      solar_to_bess: clamp(pv_to_storage[idx] ?? 0),
      utility_to_bess: clamp(util_to_storage[idx] ?? 0),
      solar_export: clamp(pv_to_grid[idx] ?? 0),
      bess_export: clamp(es_to_grid[idx] ?? 0),
      diesel_export: clamp(gen_export[idx] ?? 0),
      ng_export: clamp(chp_export[idx] ?? 0),
      soc_pct: clamp(es_soc_pct[idx] ?? 0)
    });
  }

  return data;
}

