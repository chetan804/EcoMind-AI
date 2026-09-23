"""Sustainability engine.

Design principles (docs/adr/0008-sustainability-methodology.md):
- Every metric is labelled measured / estimated / modeled.
- Every computed value retains its factor code+version, methodology text and
  assumptions — surfaced in the UI, never hidden in code.
- Emissions classification follows the organisational boundary: fleet fuel
  combustion for owned vehicles is Scope 1; treatment/disposal of collected
  waste is Scope 3 (category 5, waste generated in operations) from the
  operator's reporting perspective; avoided emissions are presented as a
  modelled comparative (landfill baseline), NOT as offsets.
- Factor values are seeded from published sources with provenance; they are
  configurable per deployment.

Scope framing note: for a municipal operator that owns its fleet, diesel/petrol
combustion is Scope 1. Waste-treatment emissions are reported here as
"treatment" lines with their own scope tag; deployments can remap categories
to their reporting boundary via the factor library.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import delete, func, select

from app.core.db import AsyncSession, utcnow
from app.core.logging import get_logger
from app.sustainability.models import (
    CarbonRecord,
    DataQuality,
    EmissionFactor,
    EmissionScope,
    WasteTreatment,
)

log = get_logger("sustainability")

# Fuel densities used to convert route distance (km) into litres when direct
# fuel records are absent. These are engineering estimates, labelled as such.
FUEL_L_PER_KM = {
    "diesel": 0.35,   # typical 10–14 m³ compactor truck
    "petrol": 0.12,
    "cng": 0.40,      # kg-equivalent handled via factor unit; approximated
    "hybrid": 0.22,
    "electric": 0.0,  # handled via grid factor if charging data exists
}


async def seed_emission_factors(session: AsyncSession) -> int:
    """Idempotent seed of the platform factor library with real published values.

    Sources:
    - EPA GHG Emission Factors Hub (2024) — mobile combustion, kg CO2e per
      litre (converted from per-gallon values: gasoline 8.78 kg/gal,
      diesel 10.21 kg/gal, incl. CH4/N2O for typical vehicles).
    - EPA WARM v15 — net emission factors for mixed MSW management pathways
      (per short ton, converted to per metric tonne).
    Values are approximations for planning, not audited inventories; each
    factor carries source + methodology for transparency.
    """
    factors = [
        ("fuel_diesel_l", "Diesel combustion (fleet)", "fuel", "EPA GHG Emission Factors Hub 2024",
         "global", 2024, "kg_co2e_per_litre", 2.689,
         "Diesel consumption converted from EPA per-gallon factor (10.21 kg CO2e/gal incl. CH4 and N2O for heavy-duty vehicles).", "1", 5.0),
        ("fuel_petrol_l", "Petrol combustion (fleet)", "fuel", "EPA GHG Emission Factors Hub 2024",
         "global", 2024, "kg_co2e_per_litre", 2.322,
         "Gasoline converted from EPA per-gallon factor (8.78 kg CO2e/gal incl. CH4 and N2O).", "1", 5.0),
        ("fuel_cng_kg", "CNG combustion (fleet)", "fuel", "EPA GHG Emission Factors Hub 2024",
         "global", 2024, "kg_co2e_per_kg", 2.21,
         "CNG stationary/mobile combustion factor incl. CH4 and N2O (per kg).", "1", 8.0),
        ("waste_landfill_t", "Mixed MSW to landfill", "waste_treatment", "EPA WARM v15",
         "global", 2024, "kg_co2e_per_tonne", 580.0,
         "Net life-cycle GHG factor for mixed MSW landfilled (WARM, converted from short tons; excludes biogenic CO2, includes CH4 collection assumptions).", "1", 25.0),
        ("waste_recycling_t", "Mixed recyclables to recycling", "waste_treatment", "EPA WARM v15",
         "global", 2024, "kg_co2e_per_tonne", 80.0,
         "Net life-cycle factor for mixed recyclables processing (transport + processing, credit for material substitution excluded to stay conservative).", "1", 30.0),
        ("waste_composting_t", "Organics to composting", "waste_treatment", "EPA WARM v15",
         "global", 2024, "kg_co2e_per_tonne", 100.0,
         "Net life-cycle factor for windrow composting of organics.", "1", 30.0),
        ("waste_incineration_t", "Mixed MSW to incineration", "waste_treatment", "EPA WARM v15",
         "global", 2024, "kg_co2e_per_tonne", 40.0,
         "Net factor for waste-to-energy incl. energy recovery credit (non-biogenic CO2 only).", "1", 35.0),
    ]
    created = 0
    for code, name, category, source, region, year, unit, value, methodology, version, unc in factors:
        exists = (
            await session.execute(
                select(EmissionFactor).where(EmissionFactor.code == code, EmissionFactor.version == version)
            )
        ).scalar_one_or_none()
        if exists:
            continue
        from app.sustainability.models import FactorCategory

        session.add(
            EmissionFactor(
                code=code,
                name=name,
                category=FactorCategory(category),
                source=source,
                source_url="https://www.epa.gov/climateleadership/ghg-emission-factors-hub",
                region=region,
                year=year,
                unit=unit,
                value=value,
                methodology=methodology,
                version=version,
                uncertainty_pct=unc,
            )
        )
        created += 1
    return created


async def recompute_period(
    session: AsyncSession, *, organization_id: uuid.UUID, period_start: date, period_end: date
) -> dict:
    """Recompute carbon records for one org and period from activity data."""
    # Replace previous computation for this period.
    await session.execute(
        delete(CarbonRecord).where(
            CarbonRecord.organization_id == organization_id,
            CarbonRecord.period_start == period_start,
            CarbonRecord.period_end == period_end,
        )
    )

    factor_cache: dict[str, EmissionFactor] = {}
    factors = (await session.execute(select(EmissionFactor).where(EmissionFactor.is_active.is_(True)))).scalars().all()
    for f in factors:
        factor_cache[f.code] = f

    # --- Activity data: waste treatments (measured/estimated) ---
    treatments = (
        await session.execute(
            select(WasteTreatment).where(
                WasteTreatment.organization_id == organization_id,
                WasteTreatment.treatment_date >= period_start,
                WasteTreatment.treatment_date <= period_end,
            )
        )
    ).scalars().all()

    by_destination: dict[str, float] = {}
    for t in treatments:
        by_destination[t.destination] = by_destination.get(t.destination, 0.0) + float(t.weight_kg)

    dest_factor = {
        "landfill": "waste_landfill_t",
        "recycling": "waste_recycling_t",
        "composting": "waste_composting_t",
        "incineration": "waste_incineration_t",
    }

    records: list[CarbonRecord] = []
    total_collected_kg = sum(by_destination.values())

    for destination, kg in by_destination.items():
        code = dest_factor.get(destination)
        if code is None or code not in factor_cache:
            continue
        f = factor_cache[code]
        tonnes = kg / 1000.0
        records.append(
            CarbonRecord(
                organization_id=organization_id,
                period_start=period_start,
                period_end=period_end,
                scope=EmissionScope.scope3,
                category=f"treatment_{destination}",
                activity_value=round(kg, 1),
                activity_unit="kg",
                factor_code=f.code,
                factor_version=f.version,
                co2e_kg=round(tonnes * float(f.value), 1),
                quality=DataQuality.modeled,
                methodology=(
                    f"Treatment emissions for {kg/1000:.2f} t to {destination}. "
                    f"{f.source}: {f.methodology} Factor {f.code} v{f.version} = {f.value} {f.unit}."
                ),
                assumptions={
                    "factor_source": f.source,
                    "factor_uncertainty_pct": f.uncertainty_pct,
                    "includes_ch4_n2o": True,
                },
                computed_at=utcnow(),
            )
        )

    # --- Fleet: distance-based estimate from completed routes ---
    from app.fleet.models import FuelType, Vehicle
    from app.routing.models import Route, RouteStatus

    vehicles = {
        v.id: v
        for v in (
            await session.execute(select(Vehicle).where(Vehicle.organization_id == organization_id))
        ).scalars().all()
    }
    fleet_km_by_fuel: dict[str, float] = {}
    routes = (
        await session.execute(
            select(Route).where(
                Route.organization_id == organization_id,
                Route.status.in_([RouteStatus.completed, RouteStatus.in_progress]),
                Route.service_date >= period_start,
                Route.service_date <= period_end,
            )
        )
    ).scalars().all()
    for r in routes:
        if r.total_distance_km is None:
            continue
        v = vehicles.get(r.vehicle_id)
        fuel = (v.fuel_type.value if v else FuelType.diesel) if v else "diesel"
        if isinstance(fuel, FuelType):
            fuel = fuel.value
        fleet_km_by_fuel[fuel] = fleet_km_by_fuel.get(fuel, 0.0) + float(r.total_distance_km)

    for fuel, km in fleet_km_by_fuel.items():
        if fuel == "electric":
            # No charging records in V1: report activity without emissions and
            # label the gap explicitly rather than inventing grid assumptions.
            records.append(
                CarbonRecord(
                    organization_id=organization_id,
                    period_start=period_start,
                    period_end=period_end,
                    scope=EmissionScope.scope1,
                    category="fleet_electric_km",
                    activity_value=round(km, 1),
                    activity_unit="km",
                    factor_code=None,
                    factor_version=None,
                    co2e_kg=0.0,
                    quality=DataQuality.estimated,
                    methodology=(
                        "EV distance recorded; charging/grid factor not yet configured — "
                        "emissions reported as 0 with an explicit data gap. Configure a regional "
                        "grid factor to enable Scope 2 estimates."
                    ),
                    assumptions={"data_gap": "no_charging_records"},
                    computed_at=utcnow(),
                )
            )
            continue
        l_per_km = FUEL_L_PER_KM.get(fuel, 0.3)
        code = {"diesel": "fuel_diesel_l", "petrol": "fuel_petrol_l", "cng": "fuel_cng_kg", "hybrid": "fuel_petrol_l"}[fuel]
        f = factor_cache.get(code)
        if f is None:
            continue
        litres = km * l_per_km
        records.append(
            CarbonRecord(
                organization_id=organization_id,
                period_start=period_start,
                period_end=period_end,
                scope=EmissionScope.scope1,
                category=f"fleet_{fuel}",
                activity_value=round(litres, 1),
                activity_unit="litre" if fuel != "cng" else "kg",
                factor_code=f.code,
                factor_version=f.version,
                co2e_kg=round(litres * float(f.value), 1),
                quality=DataQuality.estimated,
                methodology=(
                    f"Distance-based estimate: {km:.0f} km driven × {l_per_km} L/100km/100 assumed "
                    f"consumption for {fuel} fleet = {litres:.0f} L; × {f.value} kg CO2e/L "
                    f"({f.source}). Replace with fuel-card records for measured Scope 1."
                ),
                assumptions={
                    "assumed_consumption_l_per_km": l_per_km,
                    "basis": "route_distance",
                    "factor_source": f.source,
                },
                computed_at=utcnow(),
            )
        )

    for rec in records:
        session.add(rec)

    # --- Derived summary ---
    total_co2e = sum(float(r.co2e_kg) for r in records if r.scope != EmissionScope.avoided)
    diverted_kg = by_destination.get("recycling", 0.0) + by_destination.get("composting", 0.0)
    diversion_rate = (diverted_kg / total_collected_kg) if total_collected_kg > 0 else 0.0

    # Modelled avoided emissions vs all-landfill baseline (comparative, NOT an offset).
    avoided = 0.0
    for destination in ("recycling", "composting", "incineration"):
        kg = by_destination.get(destination, 0.0)
        if kg <= 0:
            continue
        f_actual = factor_cache.get(dest_factor[destination])
        f_base = factor_cache.get("waste_landfill_t")
        if f_actual and f_base:
            avoided += (float(f_base.value) - float(f_actual.value)) * (kg / 1000.0)
    if avoided > 0:
        session.add(
            CarbonRecord(
                organization_id=organization_id,
                period_start=period_start,
                period_end=period_end,
                scope=EmissionScope.avoided,
                category="avoided_vs_landfill",
                activity_value=round(diverted_kg, 1),
                activity_unit="kg",
                factor_code="waste_landfill_t",
                factor_version=factor_cache["waste_landfill_t"].version if "waste_landfill_t" in factor_cache else "1",
                co2e_kg=round(avoided, 1),
                quality=DataQuality.modeled,
                methodology=(
                    "Comparative scenario (MODELLED, not an offset credit): emissions if all "
                    "diverted waste had gone to landfill minus actual treatment emissions, using "
                    "EPA WARM net factors. Reported for decision support only."
                ),
                assumptions={
                    "baseline": "all_diverted_waste_to_landfill",
                    "is_offset_credit": False,
                },
                computed_at=utcnow(),
            )
        )

    await session.flush()
    return {
        "records": len(records) + (1 if avoided > 0 else 0),
        "total_co2e_kg": round(total_co2e, 1),
        "total_collected_kg": round(total_collected_kg, 1),
        "diverted_kg": round(diverted_kg, 1),
        "diversion_rate": round(diversion_rate, 4),
        "avoided_kg_modeled": round(avoided, 1),
    }


async def period_summary(
    session: AsyncSession, *, organization_id: uuid.UUID, period_start: date, period_end: date
) -> dict:
    records = (
        await session.execute(
            select(CarbonRecord).where(
                CarbonRecord.organization_id == organization_id,
                CarbonRecord.period_start == period_start,
                CarbonRecord.period_end == period_end,
            )
        )
    ).scalars().all()
    treatments = (
        await session.execute(
            select(WasteTreatment.destination, func.sum(WasteTreatment.weight_kg)).where(
                WasteTreatment.organization_id == organization_id,
                WasteTreatment.treatment_date >= period_start,
                WasteTreatment.treatment_date <= period_end,
            ).group_by(WasteTreatment.destination)
        )
    ).all()

    total_collected = sum(float(w or 0) for _, w in treatments)
    diverted = sum(float(w or 0) for d, w in treatments if d in ("recycling", "composting"))

    return {
        "period": {"start": period_start, "end": period_end},
        "waste": {
            "total_collected_kg": round(total_collected, 1),
            "by_destination": {d: round(float(w or 0), 1) for d, w in treatments},
            "diverted_kg": round(diverted, 1),
            "diversion_rate": round(diverted / total_collected, 4) if total_collected else 0.0,
        },
        "emissions": {
            "total_co2e_kg": round(sum(float(r.co2e_kg) for r in records if r.scope != EmissionScope.avoided), 1),
            "scope1_kg": round(sum(float(r.co2e_kg) for r in records if r.scope == EmissionScope.scope1), 1),
            "scope3_kg": round(sum(float(r.co2e_kg) for r in records if r.scope == EmissionScope.scope3), 1),
            "avoided_kg_modeled": round(sum(float(r.co2e_kg) for r in records if r.scope == EmissionScope.avoided), 1),
        },
        "records": [
            {
                "id": r.id,
                "scope": r.scope.value,
                "category": r.category,
                "activity_value": float(r.activity_value),
                "activity_unit": r.activity_unit,
                "co2e_kg": float(r.co2e_kg),
                "quality": r.quality.value,
                "factor_code": r.factor_code,
                "factor_version": r.factor_version,
                "methodology": r.methodology,
                "assumptions": r.assumptions,
            }
            for r in records
        ],
    }
