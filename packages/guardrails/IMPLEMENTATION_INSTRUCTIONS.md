# Guardrails Implementation Instructions

## Overview
This document provides step-by-step instructions for implementing the guardrails package. Follow this guide sequentially to build out the NeMo Guardrails integration.

## Prerequisites

- Python 3.11+
- `uv` package manager installed
- Access to WeedAI repository
- Gemini API key (for LLM-backed classification)

## Phase 1: Setup & Initialization (Week 1-2)

### Step 1.1: Create Directory Structure

```bash
# Already created
mkdir -p packages/guardrails/src/guardrails/{config,actions,utils}
mkdir -p packages/guardrails/tests
```

### Step 1.2: Initialize Python Package

Create `packages/guardrails/src/guardrails/__init__.py`:

```python
"""NeMo Guardrails package for WeedAI."""

__version__ = "0.1.0"
```

Create `packages/guardrails/src/guardrails/config/__init__.py`:

```python
"""Configuration module for guardrails."""
```

Create `packages/guardrails/src/guardrails/actions/__init__.py`:

```python
"""Custom actions for guardrails."""
```

Create `packages/guardrails/src/guardrails/utils/__init__.py`:

```python
"""Utility functions for guardrails."""
```

### Step 1.3: Create Base GuardrailRunner Class

Create `packages/guardrails/src/guardrails/guardrail.py`:

```python
"""Main GuardrailRunner class for WeedAI."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

import yaml
from nemo_guardrails import RailsConfig, create_llm_rails

logger = logging.getLogger(__name__)

@dataclass
class GuardrailCheckResult:
    """Result of guardrail check."""
    guardrail_passed: bool
    modified_message: str
    bot_message: Optional[str]
    violation_type: Optional[str]
    metadata: dict

class GuardrailRunner:
    """Main guardrail runner for WeedAI."""
    
    def __init__(self, config_path: str, llm_config: Optional[dict] = None):
        """
        Initialize GuardrailRunner.
        
        Args:
            config_path: Path to config.yml
            llm_config: Optional LLM configuration overrides
        """
        self.config_path = Path(config_path)
        self.llm_config = llm_config or {}
        
        # Load NeMo configuration
        with open(self.config_path) as f:
            config_dict = yaml.safe_load(f)
        
        self.rails_config = RailsConfig.from_dict(config_dict)
        self.rails = create_llm_rails(self.rails_config)
        
        logger.info(f"GuardrailRunner initialized from {self.config_path}")
    
    async def check_input(
        self,
        user_message: str,
        context: Optional[dict] = None,
    ) -> GuardrailCheckResult:
        """
        Check user input against guardrails.
        
        Args:
            user_message: User query
            context: Optional context (state, history, etc.)
        
        Returns:
            GuardrailCheckResult with pass/fail and details
        """
        context = context or {}
        
        try:
            # Execute guardrails
            response = await self.rails.generate(
                messages=[{"role": "user", "content": user_message}],
                **context
            )
            
            return GuardrailCheckResult(
                guardrail_passed=True,
                modified_message=user_message,
                bot_message=None,
                violation_type=None,
                metadata={"response": response}
            )
        except Exception as e:
            logger.warning(f"Guardrail check failed: {e}")
            
            # Return failure result
            return GuardrailCheckResult(
                guardrail_passed=False,
                modified_message=user_message,
                bot_message="I encountered a safety check issue. Please rephrase your query.",
                violation_type="unknown",
                metadata={"error": str(e)}
            )
    
    async def check_output(
        self,
        bot_message: str,
        user_context: Optional[dict] = None,
    ) -> GuardrailCheckResult:
        """Check bot output against guardrails."""
        # Similar to check_input but for output validation
        return GuardrailCheckResult(
            guardrail_passed=True,
            modified_message=bot_message,
            bot_message=None,
            violation_type=None,
            metadata={}
        )
```

### Step 1.4: Create PII Detector

Create `packages/guardrails/src/guardrails/actions/pii_detector.py`:

```python
"""PII detection logic."""

import re
from typing import Optional, List

# Common PII patterns
PII_PATTERNS = {
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'phone_au': r'\b(?:\+61|0)[0-9 ]{8,}\b',  # Australian
    'phone_us': r'\b(?:\+1|\()?[0-9]{3}[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
    'abn': r'\b\d{11}\b',  # Australian Business Number
    'acn': r'\b\d{9}\b',   # Australian Company Number
}

async def check_pii(text: str) -> bool:
    """
    Detect PII in text.
    
    Args:
        text: Text to check
    
    Returns:
        True if PII detected, False otherwise
    """
    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, text):
            return True
    return False

async def detect_pii_types(text: str) -> List[str]:
    """
    Detect which PII types are present.
    
    Args:
        text: Text to check
    
    Returns:
        List of detected PII types
    """
    detected = []
    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, text):
            detected.append(pii_type)
    return detected

async def redact_pii(text: str, replacement: str = "[REDACTED]") -> str:
    """
    Redact PII from text.
    
    Args:
        text: Text to redact
        replacement: Replacement string
    
    Returns:
        Text with PII redacted
    """
    result = text
    for pii_type, pattern in PII_PATTERNS.items():
        result = re.sub(pattern, replacement, result)
    return result
```

### Step 1.5: Create Topic Classifier

Create `packages/guardrails/src/guardrails/actions/topic_classifier.py`:

```python
"""Topic classification for domain restriction."""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# Agriculture keywords
AGRICULTURE_KEYWORDS = {
    'herbicide', 'weed', 'crop', 'pesticide', 'fungicide',
    'insecticide', 'yield', 'rotation', 'infestation', 'control',
    'spray', 'mode of action', 'moa', 'resistance', 'application',
    'dosage', 'rate', 'timing', 'weather', 'soil', 'plant-back'
}

# Off-topic keywords
OFF_TOPIC_KEYWORDS = {
    'doctor', 'medical', 'legal', 'financial', 'investment',
    'political', 'religious', 'mortgage', 'stock', 'bitcoin',
    'health', 'diagnosis', 'treatment', 'medication', 'surgery'
}

async def classify_topic(text: str) -> Literal['agriculture', 'off_topic', 'neutral']:
    """
    Classify message topic.
    
    Args:
        text: User message
    
    Returns:
        'agriculture' | 'off_topic' | 'neutral'
    """
    text_lower = text.lower()
    
    # Check for off-topic first (higher priority)
    off_topic_matches = sum(1 for kw in OFF_TOPIC_KEYWORDS if kw in text_lower)
    agriculture_matches = sum(1 for kw in AGRICULTURE_KEYWORDS if kw in text_lower)
    
    if off_topic_matches > 0:
        return 'off_topic'
    
    if agriculture_matches > 0:
        return 'agriculture'
    
    return 'neutral'
```

### Step 1.6: Create Config Files

Create `packages/guardrails/src/guardrails/config/config.yml`:

```yaml
models:
  - type: main
    engine: gemini
    model: gemini-2.5-flash
    temperature: 0.7

rails:
  config:
    colang_version: "0.1a"
    
  execution:
    rails:
      - type: input_guardrail
      - type: output_guardrail

actions:
  - name: check_pii
    module: guardrails.actions.pii_detector
    method: check_pii
  - name: detect_pii_types
    module: guardrails.actions.pii_detector
    method: detect_pii_types
  - name: redact_pii
    module: guardrails.actions.pii_detector
    method: redact_pii
  - name: classify_topic
    module: guardrails.actions.topic_classifier
    method: classify_topic

settings:
  pii_strict_mode: true  # Reject any PII
  off_topic_strict_mode: false  # Warn but allow (for now)
```

Create `packages/guardrails/src/guardrails/config/rails.co`:

```colang
define user message
  "user asks about agriculture" as agriculture_query
  "user asks about off-topic subjects" as off_topic_query
  "user provides personally identifiable information" as provides_pii

define bot message
  "bot provides agronomic guidance" as agronomic_response
  "bot declines off-topic query" as off_topic_decline
  "bot warns about PII" as pii_warning

define flow check agriculture topic
  user intent is agriculture_query
  # Continue processing (no rejection)

define flow decline off-topic
  user intent is off_topic_query
  bot send off_topic_decline
  stop

define flow prevent pii in input
  $pii_detected = check_pii(${user.message})
  if $pii_detected
    bot send pii_warning
    stop

define flow add liability disclaimer
  # Append to agronomic responses
  bot send "⚠️ DISCLAIMER: This advice is general in nature. Always follow product label instructions and consult local agronomists for field-specific recommendations."
```

### Step 1.7: Create Test Fixtures

Create `packages/guardrails/tests/conftest.py`:

```python
"""Pytest configuration and fixtures."""

import pytest
import asyncio

@pytest.fixture
def event_loop():
    """Provide event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def guardrail_runner():
    """Provide initialized GuardrailRunner."""
    from guardrails.guardrail import GuardrailRunner
    
    config_path = "packages/guardrails/src/guardrails/config/config.yml"
    runner = GuardrailRunner(config_path)
    yield runner
```

## Phase 2: Unit Tests (Week 2)

### Step 2.1: PII Detection Tests

Create `packages/guardrails/tests/test_pii_detection.py`:

```python
"""Tests for PII detection."""

import pytest
from guardrails.actions.pii_detector import (
    check_pii,
    detect_pii_types,
    redact_pii
)

class TestPIIDetection:
    """PII detection tests."""
    
    @pytest.mark.asyncio
    async def test_email_detection(self):
        """Test email detection."""
        assert await check_pii("Contact me at john.doe@example.com")
        assert not await check_pii("How do I control weeds?")
    
    @pytest.mark.asyncio
    async def test_phone_detection(self):
        """Test phone number detection."""
        assert await check_pii("Call me at 0412 345 678")
        assert await check_pii("+61 2 1234 5678")
    
    @pytest.mark.asyncio
    async def test_pii_types(self):
        """Test PII type detection."""
        result = await detect_pii_types("Email: test@example.com")
        assert 'email' in result
    
    @pytest.mark.asyncio
    async def test_redaction(self):
        """Test PII redaction."""
        text = "Contact john@example.com or 0412 345 678"
        result = await redact_pii(text)
        assert "@example.com" not in result
        assert "[REDACTED]" in result
```

### Step 2.2: Topic Classification Tests

Create `packages/guardrails/tests/test_topical_rails.py`:

```python
"""Tests for topic classification."""

import pytest
from guardrails.actions.topic_classifier import classify_topic

class TestTopicClassification:
    """Topic classification tests."""
    
    @pytest.mark.asyncio
    async def test_agriculture_classification(self):
        """Test agriculture topic detection."""
        result = await classify_topic("How do I control Ryegrass in wheat?")
        assert result == 'agriculture'
    
    @pytest.mark.asyncio
    async def test_off_topic_classification(self):
        """Test off-topic detection."""
        result = await classify_topic("What's the best stock to buy?")
        assert result == 'off_topic'
    
    @pytest.mark.asyncio
    async def test_neutral_classification(self):
        """Test neutral topic detection."""
        result = await classify_topic("What time is it?")
        assert result == 'neutral'
```

### Step 2.3: Run Tests

```bash
cd packages/guardrails
pytest tests/ -v --cov=src/guardrails --cov-report=html
```

## Phase 3: Integration (Week 5-6)

### Step 3.1: Integrate with LangGraph

Update `packages/graph/src/graph/workflow.py`:

```python
from guardrails.guardrail import GuardrailRunner
from langchain_core.messages import AIMessage

# Initialize guardrails
guardrail = GuardrailRunner(
    config_path="packages/guardrails/src/guardrails/config/config.yml"
)

async def guardrail_node(state: GraphState) -> dict:
    """Guardrail check before RAG retrieval."""
    user_message = state.messages[-1].content
    
    response = await guardrail.check_input(user_message, context=state)
    
    if not response.guardrail_passed:
        return {
            "messages": [AIMessage(content=response.bot_message)],
            "guardrail_violation": response.violation_type
        }
    
    return {
        "messages": state.messages,
        "guardrail_violation": None
    }

# Add to graph
graph.add_node("guardrail_check", guardrail_node)
graph.add_edge("input", "guardrail_check")
graph.add_edge("guardrail_check", "rag_retrieval")
```

## Deliverables Checklist

- [x] Directory structure created
- [x] pyproject.toml with isolated dependencies
- [x] GuardrailRunner base class
- [x] PII detector module
- [x] Topic classifier module
- [x] config.yml and rails.co
- [ ] Unit tests passing (85%+ coverage)
- [ ] Integration with LangGraph
- [ ] Monitoring setup
- [ ] Documentation complete

---

**Next Steps:** Proceed to Phase 2 testing, then integration with LangGraph workflow.
