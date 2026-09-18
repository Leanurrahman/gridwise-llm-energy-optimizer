
from __future__ import annotations

from .optimizer import derive_constraints
from .schemas import OptimizeRequest, OptimizeResponse


TOL = 0.01


def replay_and_validate(req: OptimizeRequest, resp: OptimizeResponse) -> None:
    if len(resp.hourly_plan) != 24:
        raise ValueError("hourly_plan must contain 24 entries")

    plan = sorted(resp.hourly_plan, key=lambda x: x.hour)
    if [x.hour for x in plan] != list(range(24)):
        raise ValueError("hourly_plan must contain hours 0..23 exactly once")

    c = derive_constraints(req, resp.directive_interpretation)
    b = req.battery
    previous_energy = b.initial_energy_kwh

    recalculated_grid = 0.0
    recalculated_cost = 0.0
    recalculated_peak = 0.0

    for h in range(24):
        p = plan[h]

        if min(
            p.grid_kwh,
            p.solar_used_kwh,
            p.battery_kwh,
            p.battery_energy_after_kwh,
        ) < -TOL:
            raise ValueError("Negative energy value in hourly_plan")

        if p.solar_used_kwh > c.effective_solar[h] + TOL:
            raise ValueError("Solar usage exceeds effective solar")

        if p.battery_action == "charge":
            charge = p.battery_kwh
            discharge = 0.0
        elif p.battery_action == "discharge":
            charge = 0.0
            discharge = p.battery_kwh
        else:
            charge = 0.0
            discharge = 0.0
            if abs(p.battery_kwh) > TOL:
                raise ValueError("idle requires battery_kwh=0")

        if charge > b.max_charge_kwh_per_hour + TOL:
            raise ValueError("Battery charge-rate violation")
        if discharge > b.max_discharge_kwh_per_hour + TOL:
            raise ValueError("Battery discharge-rate violation")

        if h in c.no_charge and charge > TOL:
            raise ValueError("no_charge_window violation")
        if h in c.no_discharge and discharge > TOL:
            raise ValueError("no_discharge_window violation")
        if h in c.max_grid and p.grid_kwh > c.max_grid[h] + TOL:
            raise ValueError("max_grid_window violation")

        expected_energy = previous_energy + charge - discharge
        if abs(expected_energy - p.battery_energy_after_kwh) > TOL:
            raise ValueError("Battery state-transition violation")

        if p.battery_energy_after_kwh < c.minimum_reserve[h] - TOL:
            raise ValueError("Minimum battery reserve violation")
        if p.battery_energy_after_kwh > b.capacity_kwh + TOL:
            raise ValueError("Battery capacity violation")

        lhs = p.grid_kwh + p.solar_used_kwh + discharge
        rhs = req.hours[h].demand_kwh + charge
        if abs(lhs - rhs) > TOL:
            raise ValueError("Hourly energy-balance violation")

        previous_energy = p.battery_energy_after_kwh
        recalculated_grid += p.grid_kwh
        recalculated_cost += (
            p.grid_kwh * req.hours[h].tariff_bdt_per_kwh
        )
        recalculated_peak = max(recalculated_peak, p.grid_kwh)

    if abs(previous_energy - b.initial_energy_kwh) > TOL:
        raise ValueError("End-of-day battery neutrality violation")

    if abs(recalculated_grid - resp.total_grid_kwh) > TOL:
        raise ValueError("total_grid_kwh does not match hourly_plan")
    if abs(recalculated_cost - resp.total_cost_bdt) > TOL:
        raise ValueError("total_cost_bdt does not match hourly_plan")
    if abs(recalculated_peak - resp.peak_grid_kwh) > TOL:
        raise ValueError("peak_grid_kwh does not match hourly_plan")
