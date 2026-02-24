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
        storey_name = _containing_storey_name(space)

        net_area = _get_quantity(space, "NetFloorArea")
        gross_area = _get_quantity(space, "GrossFloorArea")
        area = net_area or gross_area
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
                    metadata={
                        "subtype": "net" if net_area is not None else "gross",
                        "space_name": name,
                        "storey": storey_name,
                    },
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
                    metadata={"space_name": name, "storey": storey_name},
                )
            )

    # ── Building storeys (levels + floor summaries) ────────────────────
    for storey in model.by_type("IfcBuildingStorey"):
        s_name = storey.Name or storey.GlobalId
        elev = getattr(storey, "Elevation", None)
        if elev is not None:
            facts.append(
                ExtractedFact(
                    revision_id=revision_id,
                    source_hash=source_hash,
                    fact_type=FactType.GEOMETRIC,
                    category="level",
                    label=f"Elevation of {s_name}",
                    value=round(float(elev), 4),
                    unit="m",
                    raw_source_ref=f"IfcBuildingStorey#{storey.id()}",
                    metadata={"storey_name": s_name},
                )
            )

        space_count, total_area = _storey_space_summary(storey)
        if space_count > 0:
            facts.append(
                ExtractedFact(
                    revision_id=revision_id,
                    source_hash=source_hash,
                    fact_type=FactType.GEOMETRIC,
                    category="floor_summary",
                    label=f"Floor summary: {s_name}",
                    value=space_count,
                    unit="spaces",
                    raw_source_ref=f"IfcBuildingStorey#{storey.id()}",
                    metadata={
                        "storey_name": s_name,
                        "space_count": space_count,
                        "total_area_m2": round(total_area, 4) if total_area else None,
                        "elevation_m": round(float(elev), 4) if elev is not None else None,
                    },
                )
            )

    # ── Openings (windows and doors) ───────────────────────────────────
    _extract_opening_facts(model, revision_id, source_hash, facts)

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


def _containing_storey_name(element) -> str:
    """Walk the spatial hierarchy upward to find the containing IfcBuildingStorey name."""
    try:
        for rel in getattr(element, "Decomposes", []):
            parent = rel.RelatingObject
            if parent.is_a("IfcBuildingStorey"):
                return parent.Name or parent.GlobalId
        for rel in getattr(element, "ContainedInStructure", []):
            parent = rel.RelatingStructure
            if parent.is_a("IfcBuildingStorey"):
                return parent.Name or parent.GlobalId
    except Exception:
        pass
    return ""


def _storey_space_summary(storey) -> tuple[int, float]:
    """Return (space_count, total_area) for spaces belonging to a storey."""
    space_count = 0
    total_area = 0.0
    try:
        for rel in getattr(storey, "ContainsElements", []):
            for elem in rel.RelatedElements:
                if elem.is_a("IfcSpace"):
                    space_count += 1
                    a = _get_quantity(elem, "NetFloorArea") or _get_quantity(elem, "GrossFloorArea")
                    if a is not None:
                        total_area += a
        for rel in getattr(storey, "IsDecomposedBy", []):
            for child in rel.RelatedObjects:
                if child.is_a("IfcSpace"):
                    space_count += 1
                    a = _get_quantity(child, "NetFloorArea") or _get_quantity(child, "GrossFloorArea")
                    if a is not None:
                        total_area += a
    except Exception:
        pass
    return space_count, total_area


def _extract_opening_facts(model, revision_id: str, source_hash: str, facts: list[ExtractedFact]) -> None:
    """Extract window and door facts with dimensions from property sets."""
    for ifc_type, category in [("IfcWindow", "opening_window"), ("IfcDoor", "opening_door")]:
        try:
            elements = model.by_type(ifc_type)
        except Exception:
            continue
        for elem in elements:
            name = getattr(elem, "Name", None) or elem.GlobalId
            storey_name = _containing_storey_name(elem)

            width = (
                getattr(elem, "OverallWidth", None)
                or _get_quantity(elem, "Width")
            )
            height = (
                getattr(elem, "OverallHeight", None)
                or _get_quantity(elem, "Height")
            )

            meta: dict = {"storey": storey_name, "element_name": name}
            if width is not None:
                meta["width_m"] = round(float(width), 4)
            if height is not None:
                meta["height_m"] = round(float(height), 4)

            dim_label = ""
            if width is not None and height is not None:
                dim_label = f" ({round(float(width), 2)}x{round(float(height), 2)}m)"
            type_label = "Window" if category == "opening_window" else "Door"

            facts.append(
                ExtractedFact(
                    revision_id=revision_id,
                    source_hash=source_hash,
                    fact_type=FactType.GEOMETRIC,
                    category=category,
                    label=f"{type_label}: {name}{dim_label}",
                    value=1,
                    unit="count",
                    raw_source_ref=f"{ifc_type}#{elem.id()}",
                    metadata=meta,
                )
            )

    logger.debug(
        "Openings extracted: %d windows, %d doors",
        sum(1 for f in facts if f.category == "opening_window"),
        sum(1 for f in facts if f.category == "opening_door"),
    )


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
