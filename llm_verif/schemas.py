"""
Pydantic schemas for structured output from OpenAI API.

These schemas define the expected format for LLM responses when generating
testplans and testbenches. They are used with OpenAI's structured output
feature to ensure consistent, parseable responses.
"""

from pydantic import BaseModel, Field


class TestbenchResponse(BaseModel):
    """
    Schema for testbench generation responses.
    
    This schema matches the JSON format used in prompt_templates.py.
    The testbench code is expected to be a complete Verilog/SystemVerilog
    testbench module named 'tb_llm'.
    """
    test_bench: str = Field(
        ...,
        description="Complete Verilog or SystemVerilog testbench code. "
                    "Must be a valid module named 'tb_llm' with appropriate "
                    "clock generation, DUT instantiation, and test stimuli."
    )
    comments: str = Field(
        default="",
        description="Additional comments or explanations about the generated "
                    "testbench, including design decisions or coverage strategy."
    )


class Testpoint(BaseModel):
    """
    Single testpoint for a feature.
    """
    name: str = Field(..., description="Short name for the testpoint.")
    description: str = Field(..., description="Detailed description of the stimulus and checks.")
    expected: str = Field(..., description="Expected outcome or assertion for this testpoint.")


class FeatureSpec(BaseModel):
    """
    Feature entry containing the feature name and its testpoints.
    """
    feature: str = Field(..., description="Name of the feature or functionality.")
    testpoints: list[Testpoint] = Field(
        ...,
        description="List of testpoints (stimulus/check pairs) for this feature."
    )


class FeatureTestplanResponse(BaseModel):
    """
    Schema for feature-specific testplan generation responses with nested testpoints.
    """
    features: list[FeatureSpec] = Field(
        ...,
        description="List of features, each with a list of testpoints."
    )
    summary: str = Field(
        default="",
        description="Brief summary of the verification strategy and key testing areas."
    )

class TestplanResponse(BaseModel):
    """
    Schema for verification/test plan generation responses.
    
    This schema is for the verification planning stage where the LLM
    generates a structured plan describing test scenarios, coverage goals,
    and verification strategy before writing actual testbench code.
    """
    plan: str = Field(
        ...,
        description="Comprehensive verification plan including test objectives, "
                    "test scenarios, stimulus descriptions, expected outcomes, "
                    "coverage goals, and any special conditions or assertions needed."
    )
    summary: str = Field(
        default="",
        description="Brief summary of the verification strategy and key testing areas."
    )
