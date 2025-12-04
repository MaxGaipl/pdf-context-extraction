from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, create_model, constr

FieldType = Literal[
    "str",
    "bool",
    "int",
    "float",
    "decimal",
    "date",
    "datetime",
    "percent",
    "enum",
    "money",
]


@dataclass
class FieldSpec:
    """Normalized user field specification used to build the extraction model."""

    name: str
    description: str
    type: FieldType
    required: bool = True
    enum_values: Optional[List[str]] = None
    examples: List[str] = field(default_factory=list)
    currency_hint: Optional[str] = None  # Optional hint for money fields


class Percent(float):
    """Custom percent type that normalizes and bounds values."""

    scale: Literal["0-1", "0-100"] = "0-1"

    @classmethod
    def configure(cls, scale: Literal["0-1", "0-100"]) -> type["Percent"]:
        class _Percent(Percent):
            pass

        _Percent.scale = scale
        _Percent.__name__ = f"Percent_{scale.replace('-', '_')}"
        return _Percent

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value: Any) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Percent must be a number") from exc
        if cls.scale == "0-100":
            val = val / 100.0
        if val < 0 or val > 1:
            raise ValueError("Percent must be between 0 and 1 after normalization")
        return val


def _money_model() -> type[BaseModel]:
    """Return a small model representing a normalized monetary amount."""

    class Money(BaseModel):
        amount: Decimal = Field(..., description="Decimal amount")
        currency: constr(to_upper=True, min_length=3, max_length=3) = Field(
            ..., description="ISO 4217 currency code"
        )

        model_config = {"extra": "forbid"}

    return Money


def build_model(
    field_specs: List[FieldSpec],
    *,
    percent_scale: Literal["0-1", "0-100"] = "0-1",
) -> type[BaseModel]:
    """
    Build a Pydantic model dynamically from field specs.

    This model is intended for pydanticAI agent outputs. It enforces validation
    (strict enums, normalized percent, money split).
    """

    percent_type = Percent.configure(percent_scale)
    money_type = _money_model()

    model_fields: Dict[str, Tuple[Any, Any]] = {}

    for spec in field_specs:
        default = ... if spec.required else None
        t = spec.type
        if t == "str":
            model_fields[spec.name] = (str, Field(default=default, description=spec.description))
        elif t == "bool":
            model_fields[spec.name] = (bool, Field(default=default, description=spec.description))
        elif t == "int":
            model_fields[spec.name] = (int, Field(default=default, description=spec.description))
        elif t == "float":
            model_fields[spec.name] = (float, Field(default=default, description=spec.description))
        elif t == "decimal":
            model_fields[spec.name] = (Decimal, Field(default=default, description=spec.description))
        elif t == "date":
            model_fields[spec.name] = (date, Field(default=default, description=spec.description))
        elif t == "datetime":
            model_fields[spec.name] = (datetime, Field(default=default, description=spec.description))
        elif t == "percent":
            model_fields[spec.name] = (percent_type, Field(default=default, description=spec.description))
        elif t == "enum":
            if not spec.enum_values:
                raise ValueError(f"Field '{spec.name}' declared enum without values")
            literal_type = Literal.__getitem__(tuple(spec.enum_values))
            model_fields[spec.name] = (literal_type, Field(default=default, description=spec.description))
        elif t == "money":
            model_fields[spec.name] = (money_type, Field(default=default, description=spec.description))
        else:
            raise ValueError(f"Unsupported field type: {t}")

    class _BaseExtractionModel(BaseModel):
        model_config = {"extra": "forbid"}

    DynamicModel = create_model(  # type: ignore[call-arg, assignment]
        "ExtractionResult",
        __base__=_BaseExtractionModel,
        **model_fields,
    )
    return DynamicModel
