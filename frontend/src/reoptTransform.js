export function reoptToDailySeries(results, dayIndex = 0, tph = 1) {
  if (!results) return [];
  const outputs = results.outputs || {};

  // Core load and generation series
  const load = outputs?.ElectricLoad?.load_series_kw || [];

  const pv_to_load = outputs?.PV?.electric_to_load_series_kw || [];
  const pv_to_storage = outputs?.PV?.electric_to_storage_series_kw || [];
  const pv_to_grid = outputs?.PV?.electric_to_grid_series_kw || [];

  const es_to_load = outputs?.ElectricStorage?.electric_to_load_series_kw || [];
  const es_to_grid = outputs?.ElectricStorage?.electric_to_grid_series_kw || [];

  const util_to_load = outputs?.ElectricUtility?.electric_to_load_series_kw || [];
  const util_to_storage =
    outputs?.ElectricUtility?.electric_to_storage_series_kw ||
    outputs?.ElectricUtility?.load_to_storage_series_kw ||
    [];
  const util_export = outputs?.ElectricUtility?.export_series_kw || [];

  const gen_to_load = outputs?.Generator?.electric_to_load_series_kw || [];
  const gen_export = outputs?.Generator?.electric_to_grid_series_kw || [];

  const chp_to_load = outputs?.CHP?.electric_to_load_series_kw || [];
  const chp_export = outputs?.CHP?.electric_to_grid_series_kw || [];

  const year = results?.inputs?.Scenario?.analysis_year || 2017;
  const baseTimestamp = Date.UTC(year, 0, 1);

  const stepsPerDay = 24 * tph;
  const start = dayIndex * stepsPerDay;
  const data = [];

  for (let i = 0; i < stepsPerDay; i++) {
    const idx = start + i;
    data.push({
      timestamp: baseTimestamp + (idx * 3600 * 1000) / tph,
      load: load[idx] ?? 0,
      utility_to_load: util_to_load[idx] ?? 0,
      bess_to_load: es_to_load[idx] ?? 0,
      solar_to_load: pv_to_load[idx] ?? 0,
      diesel_to_load: gen_to_load[idx] ?? 0,
      ng_to_load: chp_to_load[idx] ?? 0,
      solar_to_bess: pv_to_storage[idx] ?? 0,
      utility_to_bess: util_to_storage[idx] ?? 0,
      solar_export: pv_to_grid[idx] ?? 0,
      bess_export: es_to_grid[idx] ?? 0,
      diesel_export: gen_export[idx] ?? 0,
      ng_export: chp_export[idx] ?? 0,
      missing: 0,
      alarms: 0,
    });
  }

  return data;
}

