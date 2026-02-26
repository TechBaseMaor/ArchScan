"""Planning terminology ontology v1 — versioned lexicon for Israeli permit vocabulary.

Provides canonical terms, Hebrew aliases, units, categories, rule linkages,
and external reference grounding for the domain of architectural permits.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ONTOLOGY_VERSION = "1.0.0"


class ExternalReference(BaseModel):
    source: str
    url: str = ""
    section: str = ""
    description: str = ""


class OntologyTerm(BaseModel):
    term_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    hebrew_name: str = ""
    category: str = ""
    unit: str = ""
    value_type: str = "numeric"
    rule_links: list[str] = Field(default_factory=list)
    confidence_boost: float = 0.0
    external_refs: list[ExternalReference] = Field(default_factory=list)
    notes: str = ""


class PlanningOntology(BaseModel):
    version: str = ONTOLOGY_VERSION
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    terms: list[OntologyTerm] = Field(default_factory=list)
    category_index: dict[str, list[str]] = Field(default_factory=dict)

    def get_term(self, term_id: str) -> OntologyTerm | None:
        for t in self.terms:
            if t.term_id == term_id:
                return t
        return None

    def find_by_alias(self, text: str) -> list[OntologyTerm]:
        text_lower = text.lower().strip()
        matches = []
        for t in self.terms:
            all_names = [t.canonical_name.lower(), t.hebrew_name.lower()] + [a.lower() for a in t.aliases]
            if text_lower in all_names:
                matches.append(t)
        return matches

    def rebuild_index(self) -> None:
        self.category_index = {}
        for t in self.terms:
            self.category_index.setdefault(t.category, []).append(t.term_id)


def build_seed_ontology() -> PlanningOntology:
    """Create the v1 ontology seeded with terms discovered in the Alon pilot."""
    terms = [
        OntologyTerm(
            term_id="total_building_area",
            canonical_name="Total Building Area",
            aliases=["gross area", "total area", "שטח כולל", "סה\"כ שטחי בניה"],
            hebrew_name="שטח בנייה כולל",
            category="area",
            unit="m²",
            rule_links=["area_check"],
            confidence_boost=0.1,
            external_refs=[
                ExternalReference(
                    source="Israeli Planning and Building Law",
                    section="תקנות התכנון והבניה (חישוב שטחים)",
                    description="Defines how gross building area is calculated for permit purposes",
                ),
            ],
        ),
        OntologyTerm(
            term_id="net_area",
            canonical_name="Net Area",
            aliases=["net floor area", "שטח נטו", "שטח עיקרי"],
            hebrew_name="שטח נטו",
            category="area",
            unit="m²",
            rule_links=["area_check"],
            external_refs=[
                ExternalReference(
                    source="Israeli Planning and Building Law",
                    section="תקנות חישוב שטחים, סעיף 4",
                    description="Net area excluding service areas, stairwells, and common spaces",
                ),
            ],
        ),
        OntologyTerm(
            term_id="service_area",
            canonical_name="Service Area",
            aliases=["שטח שירות", "שטחי שירות", "service floor area"],
            hebrew_name="שטח שירות",
            category="area",
            unit="m²",
            rule_links=["area_check"],
        ),
        OntologyTerm(
            term_id="building_height",
            canonical_name="Building Height",
            aliases=["max height", "גובה בניין", "גובה מקסימלי", "גובה מותר"],
            hebrew_name="גובה בניין",
            category="height",
            unit="m",
            rule_links=["height_check"],
            confidence_boost=0.1,
            external_refs=[
                ExternalReference(
                    source="Taba Plan",
                    description="Maximum permitted building height above ground level",
                ),
            ],
        ),
        OntologyTerm(
            term_id="floor_height",
            canonical_name="Floor Height",
            aliases=["story height", "גובה קומה", "גובה קומה טיפוסית"],
            hebrew_name="גובה קומה",
            category="height",
            unit="m",
            rule_links=["height_check"],
        ),
        OntologyTerm(
            term_id="num_floors",
            canonical_name="Number of Floors",
            aliases=["floor count", "stories", "מספר קומות", "קומות"],
            hebrew_name="מספר קומות",
            category="level",
            unit="floors",
            value_type="integer",
            rule_links=["floor_count_check"],
        ),
        OntologyTerm(
            term_id="front_setback",
            canonical_name="Front Setback",
            aliases=["front yard", "קו בניין קדמי", "נסיגה קדמית"],
            hebrew_name="קו בניין קדמי",
            category="setback",
            unit="m",
            rule_links=["setback_check"],
            confidence_boost=0.05,
            external_refs=[
                ExternalReference(
                    source="Local Building Plan (Taba)",
                    description="Minimum distance from front lot boundary to building face",
                ),
            ],
        ),
        OntologyTerm(
            term_id="side_setback",
            canonical_name="Side Setback",
            aliases=["side yard", "קו בניין צידי", "נסיגה צידית"],
            hebrew_name="קו בניין צידי",
            category="setback",
            unit="m",
            rule_links=["setback_check"],
        ),
        OntologyTerm(
            term_id="rear_setback",
            canonical_name="Rear Setback",
            aliases=["rear yard", "קו בניין אחורי", "נסיגה אחורית"],
            hebrew_name="קו בניין אחורי",
            category="setback",
            unit="m",
            rule_links=["setback_check"],
        ),
        OntologyTerm(
            term_id="parking_spaces",
            canonical_name="Parking Spaces",
            aliases=["parking count", "חניות", "מספר חניות", "מקומות חניה"],
            hebrew_name="מקומות חניה",
            category="parking",
            unit="spaces",
            value_type="integer",
            rule_links=["parking_check"],
            external_refs=[
                ExternalReference(
                    source="Municipal Parking Standards",
                    description="Required number of parking spaces per dwelling unit or area",
                ),
                ExternalReference(
                    source="Spatial Guidelines - Parking and Site Development",
                    section="הנחיות מרחביות לפיתוח המגרש והסדרי חניה",
                    description="Alon pilot spatial guidelines for lot development and parking arrangements",
                ),
            ],
        ),
        OntologyTerm(
            term_id="dwelling_units",
            canonical_name="Dwelling Units",
            aliases=["apartments", "units", "יחידות דיור", "דירות", "מספר דירות"],
            hebrew_name="יחידות דיור",
            category="dwelling_units",
            unit="units",
            value_type="integer",
            rule_links=["dwelling_unit_check"],
        ),
        OntologyTerm(
            term_id="building_coverage",
            canonical_name="Building Coverage Ratio",
            aliases=["coverage", "lot coverage", "אחוזי כיסוי", "כיסוי קרקע", "תכסית"],
            hebrew_name="אחוזי כיסוי",
            category="coverage",
            unit="%",
            rule_links=["coverage_check"],
            external_refs=[
                ExternalReference(
                    source="Local Building Plan",
                    description="Maximum percentage of lot area that may be covered by building footprint",
                ),
            ],
        ),
        OntologyTerm(
            term_id="building_rights",
            canonical_name="Building Rights (FAR)",
            aliases=["floor area ratio", "זכויות בנייה", "אחוזי בנייה", "מקדם ניצול"],
            hebrew_name="זכויות בנייה",
            category="regulatory_threshold",
            unit="%",
            external_refs=[
                ExternalReference(
                    source="Israeli Planning Law",
                    description="Floor Area Ratio — total permitted building area relative to lot area",
                ),
            ],
        ),
        OntologyTerm(
            term_id="waste_collection",
            canonical_name="Waste Collection Area",
            aliases=["garbage room", "אצירת אשפה", "חדר אשפה", "מתחם אשפה"],
            hebrew_name="אצירת אשפה",
            category="environment",
            unit="m²",
            external_refs=[
                ExternalReference(
                    source="Municipal Waste Policy",
                    section="מדיניות להיתרי בניה בנושא אצירת אשפה",
                    description="Requirements for waste collection rooms/areas in new buildings",
                ),
            ],
        ),
        OntologyTerm(
            term_id="green_building",
            canonical_name="Green Building Standard",
            aliases=["sustainable building", "בנייה ירוקה", "תקן ירוק", "Israeli Green Standard 5281"],
            hebrew_name="בנייה ירוקה",
            category="environment",
            unit="points",
            value_type="score",
            external_refs=[
                ExternalReference(
                    source="Israeli Standard 5281",
                    url="https://www.sii.org.il",
                    description="Israeli Green Building Standard for sustainable construction rating",
                ),
                ExternalReference(
                    source="Municipal Green Building Policy",
                    section="תמצית מדיניות בניה ירוקה להיתרי בניה",
                    description="Summary of green building policy for building permits",
                ),
            ],
        ),
        OntologyTerm(
            term_id="lot_area",
            canonical_name="Lot Area",
            aliases=["plot area", "site area", "שטח מגרש", "שטח חלקה"],
            hebrew_name="שטח מגרש",
            category="area",
            unit="m²",
            rule_links=["area_check"],
        ),
        OntologyTerm(
            term_id="basement_area",
            canonical_name="Basement Area",
            aliases=["underground area", "שטח מרתף", "קומת מרתף"],
            hebrew_name="שטח מרתף",
            category="area",
            unit="m²",
        ),
        OntologyTerm(
            term_id="roof_area",
            canonical_name="Roof Floor Area",
            aliases=["penthouse area", "שטח גג", "קומת גג"],
            hebrew_name="שטח קומת גג",
            category="area",
            unit="m²",
        ),
        OntologyTerm(
            term_id="fence_height",
            canonical_name="Fence Height",
            aliases=["wall height", "גובה גדר", "גובה חומה"],
            hebrew_name="גובה גדר",
            category="setback",
            unit="m",
        ),
        OntologyTerm(
            term_id="environmental_quality",
            canonical_name="Environmental Quality Requirements",
            aliases=["איכות הסביבה", "דרישות סביבתיות"],
            hebrew_name="איכות הסביבה",
            category="environment",
            unit="",
            value_type="text",
            external_refs=[
                ExternalReference(
                    source="Municipal Environmental Policy",
                    section="מדיניות להיתרי בניה בנושא איכות הסביבה",
                    description="Environmental quality requirements for building permits",
                ),
            ],
        ),
        OntologyTerm(
            term_id="survey_point",
            canonical_name="Survey Control Point",
            aliases=["benchmark", "נקודת מדידה", "נ.מ.", "נקודת גובה"],
            hebrew_name="נקודת מדידה",
            category="survey",
            unit="m",
            notes="Elevation reference points from site survey maps",
        ),
        OntologyTerm(
            term_id="spatial_guidelines",
            canonical_name="Spatial Guidelines",
            aliases=["הנחיות מרחביות", "הנחיות עיצוב", "design guidelines"],
            hebrew_name="הנחיות מרחביות",
            category="regulatory_threshold",
            unit="",
            value_type="text",
            external_refs=[
                ExternalReference(
                    source="Municipal Spatial Guidelines",
                    section="הנחיות מרחביות לתכנון ועיצוב הבניין",
                    description="Spatial design guidelines for building design and planning",
                ),
            ],
        ),
    ]

    ontology = PlanningOntology(terms=terms)
    ontology.rebuild_index()
    return ontology


def save_ontology(ontology: PlanningOntology, output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(ontology.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Ontology v%s saved to %s (%d terms)", ontology.version, out, len(ontology.terms))
    return out


def load_ontology(path: str | Path) -> PlanningOntology:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return PlanningOntology.model_validate(raw)
