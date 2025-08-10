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
  // const util_export = outputs?.ElectricUtility?.export_series_kw || [];

  const gen_to_load = outputs?.Generator?.electric_to_load_series_kw || [];
  const gen_export = outputs?.Generator?.electric_to_grid_series_kw || [];

  const chp_to_load = outputs?.CHP?.electric_to_load_series_kw || [];
  const chp_export = outputs?.CHP?.electric_to_grid_series_kw || [];

  const year =
    results?.inputs?.Scenario?.analysis_year ||
    results?.inputs?.Financial?.analysis_year ||
    2017;

  // IMPORTANT: Use local midnight for base timestamp rather than UTC so that
  // solar production aligns with local daytime hours. Previously we used
  // Date.UTC(...) which shifted timestamps by the local timezone offset and
  // made solar appear to generate overnight in the chart.
  const baseTimestamp = new Date(year, 0, 1).getTime();

  const stepsPerDay = 24 * tph;
  const start = dayIndex * stepsPerDay;
  const data = [];

  for (let i = 0; i < stepsPerDay; i++) {
    const idx = start + i;
    const ts = baseTimestamp + (idx * 3600 * 1000) / tph; // each step = 1/tph hour
    // Clamp tiny numerical noise (e.g., 1e-9) to zero to avoid phantom nighttime PV
    const clamp = (v) => (Math.abs(v) < 1e-6 ? 0 : v);
    data.push({
      timestamp: ts,
  // Hour of day in decimal (e.g., for sub-hourly resolution). This allows the
  // chart to display a consistent 0–24 hour axis independent of the viewer's
  // local timezone so solar output appears in daylight hours.
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
    });
  }

  return data;
}

