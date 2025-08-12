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

/**
 * Transform raw REopt `results.outputs` into structured objects used by the UI.
 * The REopt API field names can vary between versions so this helper attempts to
 * pick the most common keys while being tolerant of missing data. All values
 * come directly from live REopt API responses.
 */
export function transformReoptOutputs(results) {
  const out = results?.outputs || {};
  const rawScenarios = out.scenarios || out.Scenarios;
  const scenarioEntries = rawScenarios
    ? Object.entries(rawScenarios)
    : [["default", out]];

  const scenarios = {};

  for (const [name, o] of scenarioEntries) {
    // Debug: log raw scenario object and financial mapping
    console.log("[transformReoptOutputs] Scenario:", name, o);
    const fin = o.Financial || o;
    const financial = {
      upfront_cost:
        fin.capital_costs_after_non_discounted_incentives ??
        fin.capital_costs_after_non_discounted_incentives_without_macrs ??
        fin.initial_capital_cost ??
        fin.total_installed_cost ??
        null,
      net_savings:
        fin.developer_annual_free_cashflows?.[0] ??
        fin.net_capital_cost ??
        fin.net_savings_us_dollars ??
        null,
      npv:
        fin.npv_us_dollars ??
        fin.npv ??
        null,
      payback:
        fin.payback_years ??
        null,
      lcc:
        fin.lcc ??
        fin.lifecycle_cost_us_dollars ??
        null,
    };
    console.log("[transformReoptOutputs] Financial:", financial);

    const performance = (o.utility_bill_savings_by_year || []).map(
      (v, idx) => ({
        year: idx + 1,
        utility_savings: v,
        demand_savings: o.demand_charge_savings_by_year?.[idx] ?? null,
        capacity_savings: o.export_benefit_by_year?.[idx] ?? null,
      }),
    );

    const resilience = {
      outage_duration_hours: o.resilience_hours ?? o.outage_duration ?? null,
      percent_load_served:
        o.probability_ensuring_power_to_critical_load ??
        o.percent_load_served ??
        null,
    };

    const emissions = {
      baseline_co2e_tons:
        o.emissions_cone_co2_baseline_tons ??
        o.co2_emissions_baseline_tons ??
        null,
      post_co2e_tons:
        o.emissions_cone_co2_tons ??
        o.co2_emissions_tons ??
        null,
    };

    const payments = (o.developer_annual_cashflow || []).map((v, idx) => ({
      year: idx + 1,
      amount: v,
    }));

    scenarios[name] = { financial, performance, resilience, emissions, payments };
  }

  return { scenarios };
}


