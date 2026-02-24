"""IFC ingestion adapter — extracts geometric facts from IFC2x3/IFC4 files."""
from __future__ import annotations

import logging
from pathlib import Path

from src.app.domain.models import ExtractedFact, FactType

logger = logging.getLogger(__name__)


def extract_facts_from_ifc(file_path: str, revision_id: str, source_hash: str) -> list[ExtractedFact]:
    try:
        import ifcopenshell
        import ifcopenshell.util.element as eu
    except ImportError:
        logger.warning("ifcopenshell not installed — returning empty facts for IFC file")
        return []

    facts: list[ExtractedFact] = []
    model = ifcopenshell.open(file_path)

    # ── Spaces (areas, heights) ────────────────────────────────────────
    for space in model.by_type("IfcSpace"):
        name = getattr(space, "LongName", None) or getattr(space, "Name", None) or space.GlobalId

        area = _get_quantity(space, "NetFloorArea") or _get_quantity(space, "GrossFloorArea")
        if area is not None:
            facts.append(
                ExtractedFact(
                    revision_id=revision_id,
                    source_hash=source_hash,
                    fact_type=FactType.GEOMETRIC,
                    category="area",
                    label=f"Area of {name}",
                    value=round(area, 4),
                    unit="m2",
                    raw_source_ref=f"IfcSpace#{space.id()}",
                )
            )

        height = _get_quantity(space, "Height")
        if height is not None:
            facts.append(
                ExtractedFact(
                    revision_id=revision_id,
                    source_hash=source_hash,
                    fact_type=FactType.GEOMETRIC,
                    category="height",
                    label=f"Height of {name}",
                    value=round(height, 4),
                    unit="m",
                    raw_source_ref=f"IfcSpace#{space.id()}",
                )
            )

    # ── Building storeys (levels) ──────────────────────────────────────
    for storey in model.by_type("IfcBuildingStorey"):
        elev = getattr(storey, "Elevation", None)
        if elev is not None:
            facts.append(
                ExtractedFact(
                    revision_id=revision_id,
                    source_hash=source_hash,
                    fact_type=FactType.GEOMETRIC,
                    category="level",
                    label=f"Elevation of {storey.Name or storey.GlobalId}",
                    value=round(float(elev), 4),
                    unit="m",
                    raw_source_ref=f"IfcBuildingStorey#{storey.id()}",
                )
            )

    # ── Site setback (simplified: bounding box of IfcSite vs IfcBuilding) ──
    _extract_setback_facts(model, revision_id, source_hash, facts)

    # ── Wall / slab intersections (basic bounding-box overlap) ─────────
    _extract_intersection_facts(model, revision_id, source_hash, facts)

    logger.info("IFC adapter extracted %d facts from %s", len(facts), file_path)
    return facts


def _get_quantity(element, qty_name: str) -> float | None:
    """Try to read a quantity from property sets attached to an IFC element."""
    try:
        import ifcopenshell.util.element as eu
        psets = eu.get_psets(element)
        for pset_data in psets.values():
            if qty_name in pset_data:
                val = pset_data[qty_name]
                if val is not None:
                    return float(val)
    except Exception:
        pass
    return None


def _extract_setback_facts(model, revision_id: str, source_hash: str, facts: list[ExtractedFact]) -> None:
    """Simplified setback: distance between IfcSite placement and IfcBuilding placement origins."""
    try:
        sites = model.by_type("IfcSite")
        buildings = model.by_type("IfcBuilding")
        if not sites or not buildings:
            return

        site = sites[0]
        building = buildings[0]

        site_origin = _placement_origin(site)
        bldg_origin = _placement_origin(building)

        if site_origin and bldg_origin:
            dx = bldg_origin[0] - site_origin[0]
            dy = bldg_origin[1] - site_origin[1]
            distance = (dx**2 + dy**2) ** 0.5
            facts.append(
                ExtractedFact(
                    revision_id=revision_id,
                    source_hash=source_hash,
                    fact_type=FactType.GEOMETRIC,
                    category="setback",
                    label="Building-to-site origin distance (simplified setback)",
                    value=round(distance, 4),
                    unit="m",
                    raw_source_ref=f"IfcSite#{site.id()}/IfcBuilding#{building.id()}",
                )
            )
    except Exception as exc:
        logger.debug("Setback extraction failed: %s", exc)


def _placement_origin(element) -> tuple[float, float, float] | None:
    try:
        placement = element.ObjectPlacement
        if placement and hasattr(placement, "RelativePlacement"):
            rp = placement.RelativePlacement
            if hasattr(rp, "Location"):
                coords = rp.Location.Coordinates
                return tuple(float(c) for c in coords)
    except Exception:
        pass
    return None


def _extract_intersection_facts(model, revision_id: str, source_hash: str, facts: list[ExtractedFact]) -> None:
    """Very basic bounding-box overlap detection between walls."""
    try:
        walls = model.by_type("IfcWall")
        if len(walls) < 2:
            return

        bbs = []
        for w in walls[:50]:  # cap for performance
            bb = _get_bounding_box(w)
            if bb:
                bbs.append((w, bb))

        intersections_found = 0
        for i in range(len(bbs)):
            for j in range(i + 1, len(bbs)):
                w1, bb1 = bbs[i]
                w2, bb2 = bbs[j]
                if _boxes_overlap(bb1, bb2):
                    intersections_found += 1

        if intersections_found > 0:
            facts.append(
                ExtractedFact(
                    revision_id=revision_id,
                    source_hash=source_hash,
                    fact_type=FactType.GEOMETRIC,
                    category="intersection",
                    label=f"Wall bounding-box overlaps detected",
                    value=intersections_found,
                    unit="count",
                    raw_source_ref="IfcWall bbox analysis",
                )
            )
    except Exception as exc:
        logger.debug("Intersection extraction failed: %s", exc)


def _get_bounding_box(element) -> tuple[tuple[float, ...], tuple[float, ...]] | None:
    try:
        import ifcopenshell.util.placement as up
        matrix = up.get_local_placement(element.ObjectPlacement)
        origin = (matrix[0][3], matrix[1][3], matrix[2][3])
        return (origin, (origin[0] + 0.3, origin[1] + 0.3, origin[2] + 3.0))
    except Exception:
        return None


def _boxes_overlap(a, b) -> bool:
    (a_min, a_max) = a
    (b_min, b_max) = b
    for i in range(3):
        if a_max[i] < b_min[i] or b_max[i] < a_min[i]:
            return False
    return True
