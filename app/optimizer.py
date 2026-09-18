
from __future__ import annotations

from dataclasses import dataclass

import pulp

from .schemas import (
    DirectiveInterpretation,
    HourlyPlanEntry,
    OptimizeRequest,
    OptimizeResponse,
)


@dataclass
class DerivedConstraints:
    effective_solar: list[float]
    minimum_reserve: list[float]
    no_charge: set[int]
    no_discharge: set[int]
    max_grid: dict[int, float]


def derive_constraints(
    req: OptimizeRequest, directives: list[DirectiveInterpretation]
) -> DerivedConstraints:
    effective_solar = [h.solar_kwh for h in req.hours]
    minimum_reserve = [req.battery.minimum_energy_kwh] * 24
    no_charge: set[int] = set()
    no_discharge: set[int] = set()
    max_grid: dict[int, float] = {}

    for d in directives:
        if not d.applies:
            continue
        a = d.structured_adjustment or {}

        if d.directive_type == "solar_reduction":
            factor = float(a["factor"])
            for h in a["hours"]:
                # If multiple reductions overlap, compose them multiplicatively.
                # The official documents do not give a separate overlap rule.
                effective_solar[h] *= factor

        elif d.directive_type == "minimum_battery_reserve":
            reserve = float(a["minimum_energy_kwh"])
            for h in a["hours"]:
                minimum_reserve[h] = max(minimum_reserve[h], reserve)

        elif d.directive_type == "no_charge_window":
            no_charge.update(a["hours"])

        elif d.directive_type == "no_discharge_window":
            no_discharge.update(a["hours"])

        elif d.directive_type == "max_grid_window":
            cap = float(a["max_grid_kwh"])
            for h in a["hours"]:
                max_grid[h] = min(max_grid.get(h, cap), cap)

    return DerivedConstraints(
        effective_solar=effective_solar,
        minimum_reserve=minimum_reserve,
        no_charge=no_charge,
        no_discharge=no_discharge,
        max_grid=max_grid,
    )


def optimize_schedule(
    req: OptimizeRequest,
    directives: list[DirectiveInterpretation],
) -> OptimizeResponse:
    c = derive_constraints(req, directives)
    b = req.battery
    H = range(24)

    problem = pulp.LpProblem("GridWise", pulp.LpMinimize)

    grid = {h: pulp.LpVariable(f"grid_{h}", lowBound=0) for h in H}
    solar = {h: pulp.LpVariable(f"solar_{h}", lowBound=0) for h in H}
    charge = {h: pulp.LpVariable(f"charge_{h}", lowBound=0) for h in H}
    discharge = {h: pulp.LpVariable(f"discharge_{h}", lowBound=0) for h in H}
    energy = {h: pulp.LpVariable(f"energy_{h}", lowBound=0) for h in H}

    charge_on = {
        h: pulp.LpVariable(f"charge_on_{h}", cat="Binary") for h in H
    }
    discharge_on = {
        h: pulp.LpVariable(f"discharge_on_{h}", cat="Binary") for h in H
    }

    problem += pulp.lpSum(
        grid[h] * req.hours[h].tariff_bdt_per_kwh for h in H
    )

    for h in H:
        problem += solar[h] <= c.effective_solar[h]

        problem += charge[h] <= b.max_charge_kwh_per_hour * charge_on[h]
        problem += (
            discharge[h] <= b.max_discharge_kwh_per_hour * discharge_on[h]
        )
        problem += charge_on[h] + discharge_on[h] <= 1

        if h in c.no_charge:
            problem += charge[h] == 0
        if h in c.no_discharge:
            problem += discharge[h] == 0
        if h in c.max_grid:
            problem += grid[h] <= c.max_grid[h]

        problem += energy[h] >= c.minimum_reserve[h]
        problem += energy[h] <= b.capacity_kwh

        if h == 0:
            problem += (
                energy[h]
                == b.initial_energy_kwh + charge[h] - discharge[h]
            )
        else:
            problem += (
                energy[h] == energy[h - 1] + charge[h] - discharge[h]
            )

        problem += (
            grid[h] + solar[h] + discharge[h]
            == req.hours[h].demand_kwh + charge[h]
        )

    problem += energy[23] == b.initial_energy_kwh

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=15)
    status = problem.solve(solver)

    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(
            f"Optimizer did not find an optimal solution: {pulp.LpStatus[status]}"
        )

    plan: list[HourlyPlanEntry] = []
    tol = 1e-6

    for h in H:
        g = max(0.0, float(pulp.value(grid[h]) or 0.0))
        s = max(0.0, float(pulp.value(solar[h]) or 0.0))
        ch = max(0.0, float(pulp.value(charge[h]) or 0.0))
        dis = max(0.0, float(pulp.value(discharge[h]) or 0.0))
        e = float(pulp.value(energy[h]) or 0.0)

        if ch > tol:
            action = "charge"
            battery_kwh = ch
        elif dis > tol:
            action = "discharge"
            battery_kwh = dis
        else:
            action = "idle"
            battery_kwh = 0.0

        plan.append(
            HourlyPlanEntry(
                hour=h,
                grid_kwh=round(g, 6),
                solar_used_kwh=round(s, 6),
                battery_action=action,
                battery_kwh=round(battery_kwh, 6),
                battery_energy_after_kwh=round(e, 6),
            )
        )

    total_grid = sum(p.grid_kwh for p in plan)
    total_cost = sum(
        plan[h].grid_kwh * req.hours[h].tariff_bdt_per_kwh for h in H
    )
    peak_grid = max(p.grid_kwh for p in plan)

    applied_count = sum(1 for d in directives if d.applies)
    summary = (
        f"Applied {applied_count} operator directive(s), satisfied the GridWise "
        "energy and battery constraints, and minimized 24-hour grid electricity cost."
    )

    return OptimizeResponse(
        scenario_id=req.scenario_id,
        directive_interpretation=directives,
        hourly_plan=plan,
        total_grid_kwh=round(total_grid, 6),
        total_cost_bdt=round(total_cost, 6),
        peak_grid_kwh=round(peak_grid, 6),
        plan_summary=summary,
    )
