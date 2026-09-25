# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2"]
# ///
"""Draft citable use record, for discussion. Not wired to anything.

One record is one registered use as a label states it: a crop, a weed, a state set, a rate and its
conditions, with the page and section it came from. It is what the agent quotes when it cites
label content, so every field an agent might repeat carries the label's own wording beside any
parsed value. It follows the plan's `RegisteredUse` (AGENTIC_WEED_MANAGEMENT_DEVELOPMENT_PLAN.md
§2.5) but drops the eligibility and optimisation fields the proposed scope defers.

Open questions for review are marked `# REVIEW:`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    """Where on the label a fact came from. Every record needs at least one."""

    model_config = ConfigDict(extra="forbid")

    apvma_product_number: str = Field(
        description="e.g. '31209', from the label file name"
    )
    label_file: str = Field(description="e.g. 'data/labels/31209ELBL.pdf'")
    page: int = Field(ge=1, description="1-indexed PDF page")
    section: str = Field(description="Label heading, e.g. 'Directions for Use'")
    table_row: int | None = Field(
        default=None, ge=1, description="Row within the section's table, if tabular"
    )
    quote: str = Field(description="The exact label text the record was read from")


class Rate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="Rate exactly as printed, e.g. '1.0 to 1.5 L/ha'")
    min_value: float | None = None
    max_value: float | None = None
    unit: str | None = Field(
        default=None, description="e.g. 'L/ha', 'g/ha', 'mL/100 L'"
    )
    # REVIEW: water volume and adjuvant requirements, here or in `conditions`?


class Restriction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["withholding_harvest", "withholding_grazing", "plant_back", "other"]
    text: str = Field(description="As printed")
    days: int | None = Field(
        default=None, ge=0, description="Parsed, when the label gives a number of days"
    )
    applies_to: str | None = Field(
        default=None, description="e.g. the following crop, for plant-back"
    )
    citation: Citation


class UseRecord(BaseModel):
    """One registered use, as printed on one label."""

    model_config = ConfigDict(extra="forbid")

    product_name: str
    crop: str = Field(description="As printed, e.g. 'Wheat (not durum)'")
    weed: str = Field(description="As printed, e.g. 'Annual ryegrass'")
    states: list[str] = Field(description="As printed, e.g. ['WA'] or ['All States']")
    rate: Rate
    crop_stage: str | None = Field(
        default=None, description="As printed; None if the label gives none"
    )
    weed_stage: str | None = Field(
        default=None, description="As printed; None if the label gives none"
    )
    conditions: str | None = Field(
        default=None, description="Critical comments for this use, as printed"
    )
    restrictions: list[Restriction] = Field(default_factory=list)
    citations: list[Citation] = Field(min_length=1)
    extraction: Literal["manual", "rule", "llm"] = Field(
        description="How the record was produced"
    )
    # REVIEW: normalised crop and weed ids (for joins and WSW species names) in this record or a
    # separate lookup? Keeping the printed text here and mapping elsewhere keeps citations exact.


if __name__ == "__main__":
    import json

    print(json.dumps(UseRecord.model_json_schema(), indent=2))
