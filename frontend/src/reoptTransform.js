export function reoptToDailySeries(results, dayIndex = 0, tph = 1) {
  if (!results) return [];
  const outputs = results.outputs || {};
  const load = outputs?.ElectricLoad?.load_series_kw || [];
  const pv_to_load = outputs?.PV?.electric_to_load_series_kw || [];
  const pv_to_storage = outputs?.PV?.electric_to_storage_series_kw || [];
  const pv_to_grid = outputs?.PV?.electric_to_grid_series_kw || [];
  const es_to_load = outputs?.ElectricStorage?.electric_to_load_series_kw || [];
  const es_to_grid = outputs?.ElectricStorage?.electric_to_grid_series_kw || [];
  const es_to_storage =
    outputs?.ElectricStorage?.electric_to_storage_series_kw ||
    outputs?.ElectricStorage?.load_to_storage_series_kw ||
    [];
  const util_to_load =
    outputs?.ElectricUtility?.electric_to_load_series_kw || [];
  const util_export = outputs?.ElectricUtility?.export_series_kw || [];

  const stepsPerDay = 24 * tph;
  const start = dayIndex * stepsPerDay;
  const data = [];
  for (let i = 0; i < stepsPerDay; i++) {
    const idx = start + i;
    data.push({
      hour: i / tph,
      load: load[idx] ?? 0,
      solar:
        -((pv_to_load[idx] ?? 0) +
          (pv_to_storage[idx] ?? 0) +
          (pv_to_grid[idx] ?? 0)),
      bess:
        (es_to_storage[idx] ?? 0) -
        ((es_to_load[idx] ?? 0) + (es_to_grid[idx] ?? 0)),
      utility: (util_to_load[idx] ?? 0) - (util_export[idx] ?? 0),
    });
  }
  return data;
}
