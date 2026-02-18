"""Tests for LLMPatternAnalyzer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from argus.domain.llm.value_objects import ModelConfig
from argus.domain.memory.value_objects import PatternCategory
from argus.infrastructure.memory.llm_analyzer import LLMPatternAnalyzer, _PatternOutput
from argus.shared.exceptions import ProfileAnalysisError
from argus.shared.types import TokenCount


@pytest.fixture
def model_config() -> ModelConfig:
    return ModelConfig(
        model="google-gla:gemini-2.5-flash",
        max_tokens=TokenCount(4096),
        temperature=0.0,
    )


class TestLLMPatternAnalyzer:
    @patch("argus.infrastructure.memory.llm_analyzer.create_agent")
    def test_analyze_returns_patterns(
        self,
        mock_create_agent: MagicMock,
        model_config: ModelConfig,
    ) -> None:
        output = _PatternOutput(
            patterns=[
                _PatternOutput.Pattern(
                    category="architecture",
                    description="Layer dependency rules",
                    confidence=0.9,
                    examples=["domain never imports infrastructure"],
                ),
                _PatternOutput.Pattern(
                    category="naming",
                    description="Snake case functions",
                    confidence=0.8,
                    examples=[],
                ),
            ]
        )
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        analyzer = LLMPatternAnalyzer(config=model_config)
        patterns = analyzer.analyze("outline text")

        assert len(patterns) == 2
        assert patterns[0].category == PatternCategory.ARCHITECTURE
        assert patterns[0].confidence == 0.9
        assert patterns[1].category == PatternCategory.NAMING

    @patch("argus.infrastructure.memory.llm_analyzer.create_agent")
    def test_analyze_clamps_confidence(
        self,
        mock_create_agent: MagicMock,
        model_config: ModelConfig,
    ) -> None:
        output = _PatternOutput(
            patterns=[
                _PatternOutput.Pattern(
                    category="style",
                    description="test",
                    confidence=1.5,
                ),
            ]
        )
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        analyzer = LLMPatternAnalyzer(config=model_config)
        patterns = analyzer.analyze("text")

        assert patterns[0].confidence == 1.0

    @patch("argus.infrastructure.memory.llm_analyzer.create_agent")
    def test_analyze_maps_unknown_category_to_style(
        self,
        mock_create_agent: MagicMock,
        model_config: ModelConfig,
    ) -> None:
        output = _PatternOutput(
            patterns=[
                _PatternOutput.Pattern(
                    category="unknown_thing",
                    description="test",
                    confidence=0.7,
                ),
            ]
        )
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        analyzer = LLMPatternAnalyzer(config=model_config)
        patterns = analyzer.analyze("text")

        assert patterns[0].category == PatternCategory.STYLE

    @patch("argus.infrastructure.memory.llm_analyzer.create_agent")
    def test_analyze_wraps_errors(
        self,
        mock_create_agent: MagicMock,
        model_config: ModelConfig,
    ) -> None:
        mock_create_agent.side_effect = RuntimeError("LLM down")

        analyzer = LLMPatternAnalyzer(config=model_config)

        with pytest.raises(ProfileAnalysisError, match="Pattern analysis failed"):
            analyzer.analyze("text")
