export function reoptToDailySeries(results, dayIndex = 0, tph = 1) {
  const outputs = results?.outputs || {};
  const stepsPerDay = 24 * tph;
  const start = dayIndex * stepsPerDay;

  // Helper to safely slice a series and pad missing values with zeros
  const slice = (series) => {
    const arr = Array(stepsPerDay).fill(0);
    if (Array.isArray(series)) {
      for (let i = 0; i < stepsPerDay && start + i < series.length; i++) {
        const val = series[start + i];
        arr[i] = typeof val === "number" ? val : 0;
      }
    }
    return arr;
  };

  // Load
  const load = slice(outputs?.ElectricLoad?.load_series_kw);

  // Utility
  const util = outputs?.ElectricUtility || {};
  const utilToLoad = slice(util.electric_to_load_series_kw);
  const utilToStorage = slice(util.electric_to_storage_series_kw);

  // PV
  const pv = outputs?.PV || {};
  const pvToLoad = slice(pv.electric_to_load_series_kw);
  const pvToStorage = slice(pv.electric_to_storage_series_kw);
  const pvToGrid = slice(pv.electric_to_grid_series_kw);

  // Electric Storage
  const es = outputs?.ElectricStorage || {};
  const esToLoad = slice(es.electric_to_load_series_kw);
  const esToGrid = slice(es.electric_to_grid_series_kw);

  // Generator (handle possible naming variations)
  const gen = (() => {
    const keys = [
      "Generator",
      "ExistingGenerator",
      "GeneratorNew",
      "NGGenerator",
      "DieselGenerator",
    ];
    for (const k of keys) {
      if (outputs?.[k]) return outputs[k];
    }
    return {};
  })();
  const genToLoad = slice(gen.electric_to_load_series_kw);
  const genToStorage = slice(gen.electric_to_storage_series_kw);
  const genToGrid = slice(gen.electric_to_grid_series_kw);

  // CHP
  const chp = outputs?.CHP || {};
  const chpToLoad = slice(chp.electric_to_load_series_kw);
  const chpToStorage = slice(chp.electric_to_storage_series_kw);
  const chpToGrid = slice(chp.electric_to_grid_series_kw);

  const series = [];
  for (let i = 0; i < stepsPerDay; i++) {
    series.push({
      t: i / tph,
      load: load[i],
      "Utility \u2192 Load": utilToLoad[i],
      "Solar \u2192 Load": pvToLoad[i],
      "Storage \u2192 Load": esToLoad[i],
      "Generator \u2192 Load": genToLoad[i],
      "CHP \u2192 Load": chpToLoad[i],
      "Utility \u2192 Storage": utilToStorage[i],
      "Solar \u2192 Storage": pvToStorage[i],
      "Generator \u2192 Storage": genToStorage[i],
      "CHP \u2192 Storage": chpToStorage[i],
      "Solar \u2192 Grid": pvToGrid[i],
      "Storage \u2192 Grid": esToGrid[i],
      "Generator \u2192 Grid": genToGrid[i],
      "CHP \u2192 Grid": chpToGrid[i],
    });
  }

  return series;
}

export default reoptToDailySeries;
