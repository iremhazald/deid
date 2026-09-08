"""Transformation strategies: detection remains separate from how text is changed."""

from app.transforms.catalog import build_catalog
from app.transforms.planner import (
    apply_operations,
    apply_transforms,
    build_operations,
    requires_text_rebuild,
    resolve_strategy_for_entity,
    seed_category_defaults,
)
from app.transforms.resolution import assign_resolved_entities
from app.transforms.validate import build_transformation_audit, validate_operations

__all__ = [
    "apply_operations",
    "apply_transforms",
    "assign_resolved_entities",
    "build_catalog",
    "build_operations",
    "build_transformation_audit",
    "requires_text_rebuild",
    "resolve_strategy_for_entity",
    "seed_category_defaults",
    "validate_operations",
]
