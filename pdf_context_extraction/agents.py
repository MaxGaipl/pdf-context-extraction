from __future__ import annotations
import re
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from mimetypes import guess_type
from typing import Any, List, Optional, Sequence, Type

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.openai import OpenAIModel

from .schema import FieldSpec, FieldType, build_model


@dataclass
class DocumentContext:
    """Lightweight container for preprocessed document content."""

    file_path: Path
    text_blocks: Sequence[str]
    images: Sequence[Any]  # placeholders for rendered page images or thumbnails
    metadata: dict[str, Any]


class FieldSpecModel(BaseModel):
    """LLM-facing schema for a single field spec."""

    name: str = Field(..., description="Safe identifier, letters/numbers/underscore, starting with a letter")
    description: str
    type: FieldType
    required: bool = True
    enum_values: Optional[List[str]] = None
    examples: List[str] = Field(default_factory=list)
    currency_hint: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", value):
            raise ValueError("Field name must start with a letter and contain only letters, numbers, underscore")
        return value

    @model_validator(mode="after")
    def validate_enum_and_money(self) -> "FieldSpecModel":
        if self.type == "enum":
            if not self.enum_values:
                raise ValueError("enum_values must be provided for enum type")
            if any(not v for v in self.enum_values):
                raise ValueError("enum_values cannot contain empty strings")
        else:
            self.enum_values = None

        if self.type != "money":
            self.currency_hint = None
        return self


class SchemaAgentResponse(BaseModel):
    fields: List[FieldSpecModel]


class SchemaAgent:
    """
    LLM-driven agent that turns user instructions into normalized FieldSpecs.
    """

    def __init__(self, model_name: str = "gpt-4o"):
        self.model_name = model_name
        self._agent: Optional[Agent[SchemaAgentResponse]] = None

    @property
    def agent(self) -> Agent[SchemaAgentResponse]:
        if self._agent is None:
            model = OpenAIModel(self.model_name)
            self._agent = Agent[SchemaAgentResponse](
                model=model,
                system_prompt=self._system_prompt(),
                output_type=SchemaAgentResponse,
            )
        return self._agent

    def _system_prompt(self) -> str:
        return (
            "You map user-described fields to a strict JSON schema using only allowed types. "
            "Allowed types: str, bool, int, float, decimal, date (YYYY-MM-DD), datetime (ISO 8601), "
            "percent (as a number, may be 0-1 or 0-100 as specified), enum (with enum_values), "
            "money (amount + currency). "
            "If a user does not specify a type, infer the most likely type from the field name/description "
            "and choose it explicitly. "
            "Rules: "
            "1) Do not invent fields. "
            '2) Field names must start with a letter and contain only letters, numbers, underscore. '
            "3) For enum, provide enum_values explicitly. "
            "4) For money, you may include currency_hint if provided by the user (ISO 4217). "
            "5) Output only JSON matching the expected schema."
        )

    def run(self, user_input: str) -> List[FieldSpec]:
        """
        Convert user instructions to a list of FieldSpec instances.
        """
        # pydanticAI agents are async-first; run_sync blocks for CLI usage.
        result = self.agent.run_sync(user_input)
        # pydanticAI returns the parsed output as `result.output`
        response: SchemaAgentResponse = (
            result.output
            if isinstance(result.output, SchemaAgentResponse)
            else SchemaAgentResponse.model_validate(result.output)
        )
        specs: List[FieldSpec] = []
        for fs in response.fields:
            specs.append(
                FieldSpec(
                    name=fs.name,
                    description=fs.description,
                    type=fs.type,
                    required=fs.required,
                    enum_values=fs.enum_values,
                    examples=fs.examples,
                    currency_hint=fs.currency_hint,
                )
            )
        return specs

    def build_pydantic_model(
        self, field_specs: List[FieldSpec], *, percent_scale: str = "0-1"
    ) -> Type[BaseModel]:
        return build_model(field_specs, percent_scale=percent_scale)  # type: ignore[arg-type]


class ExtractionAgent:
    """
    Vision LLM agent that extracts field values for a single document.

    Uses pydanticAI to bind a Pydantic model for structured outputs.
    """

    def __init__(self, model_name: str = "gpt-4o"):
        self.model_name = model_name

    def run(
        self,
        model: Type[BaseModel],
        document: DocumentContext,
        *,
        instructions: str,
    ) -> BaseModel:
        """
        Given a Pydantic model and a document context, call the LLM to populate the model.

        Returns a Pydantic model instance or raises an error on validation failure.
        """
        system_prompt = (
            "You are a careful information extraction assistant. "
            "Fill the provided schema using only evidence from the document text and images. "
            "If a value is missing or unclear, leave it null. Do not invent data."
        )
        agent: Agent[Any] = Agent[Any](
            model=OpenAIModel(self.model_name),
            output_type=model,
            system_prompt=system_prompt,
        )

        user_prompt_parts: List[str] = [instructions]

        if document.metadata:
            user_prompt_parts.append(f"Metadata: {document.metadata}")

        if document.text_blocks:
            joined_text = "\n\n".join(document.text_blocks)
            user_prompt_parts.append(f"Document text:\n{joined_text}")

        if document.images:
            user_prompt_parts.append("Page images attached.")

        user_prompt = "\n\n".join(user_prompt_parts)

        # Combine text prompt with optional image inputs (BinaryContent)
        inputs: List[Any] = [user_prompt]
        inputs.extend(self._build_image_inputs(document.images))

        result = agent.run_sync(inputs)
        if isinstance(result.output, BaseModel):
            return result.output
        return model.model_validate(result.output)

    def _build_image_inputs(self, images: Sequence[Any]) -> List[Any]:
        """
        Normalize images to BinaryContent objects for vision models.

        Accepts:
        - bytes: treated as PNG bytes
        - str/Path: path to an image file
        - PIL.Image: will be converted to PNG bytes
        """
        inputs: List[Any] = []
        for img in images:
            data: Optional[bytes] = None
            media_type = "image/png"

            if isinstance(img, bytes):
                data = img
            elif isinstance(img, (str, Path)):
                path = Path(img)
                if path.exists():
                    data = path.read_bytes()
                    media_type = guess_type(path.name)[0] or media_type
            else:
                # Attempt PIL-like interface
                if hasattr(img, "save"):
                    buffer = BytesIO()
                    img.save(buffer, format="PNG")
                    data = buffer.getvalue()

            if not data:
                continue

            inputs.append(BinaryContent(data=data, media_type=media_type))

        return inputs
