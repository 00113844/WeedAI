# NeMo Guardrails Package

This package implements domain-specific guardrails using NVIDIA NeMo Guardrails, ensuring the WeedAI system operates safely, compliantly, and within agronomic scope.

## Table of Contents
1. [Quick Start](#quick-start)
2. [Structure](#structure)
3. [Configuration](#configuration)
4. [Custom Actions](#custom-actions)
5. [Testing](#testing)
6. [Integration](#integration)

## Quick Start

### Installation

```bash
# Install guardrails package (isolated dependencies)
uv pip install -e packages/guardrails

# Or via workspace
uv add nemo-guardrails[langchain] --package packages/guardrails
```

### Basic Usage

```python
from guardrails.guardrail import GuardrailRunner

# Initialize with config
guardrail = GuardrailRunner(
    config_path="packages/guardrails/src/guardrails/config/config.yml"
)

# Check user input
response = await guardrail.check_input(
    user_message="How do I control Ryegrass in wheat?",
    context={}
)

if response.guardrail_passed:
    # Safe to process
    proceed_with_request(response.modified_message)
else:
    # Rejected by guardrail
    return response.bot_message  # Pre-defined guardrail response
```

## Structure

```
packages/guardrails/
├── pyproject.toml                              # Isolated dependencies
├── src/guardrails/
│   ├── __init__.py
│   ├── guardrail.py                           # Main GuardrailRunner class
│   ├── config/
│   │   ├── __init__.py
│   │   ├── config.yml                         # NeMo Guardrails configuration
│   │   └── rails.co                           # Colang rule definitions
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── custom_actions.py                  # Domain-specific action handlers
│   │   ├── pii_detector.py                    # PII detection logic
│   │   └── topic_classifier.py                # Topic classification
│   └── utils/
│       ├── __init__.py
│       └── validators.py                      # Validation helpers
├── tests/
│   ├── __init__.py
│   ├── conftest.py                            # Pytest fixtures
│   ├── test_pii_detection.py                  # PII tests
│   ├── test_topical_rails.py                  # Topic classification tests
│   └── test_liability.py                      # Liability disclaimer tests
└── README.md                                  # This file
```

## Configuration

### config.yml

Main NeMo Guardrails configuration file. Defines model, action path, and core settings.

**Key Fields:**
```yaml
models:
  - type: main
    engine: openai | gemini | anthropic | custom
    model: gemini-2.5-flash
    temperature: 0.7

rails:
  config:
    colang_version: "0.1a"
    
execution:
  rails:
    - type: input_guardrail
    - type: output_guardrail
```

**For WeedAI:**
- Engine: `gemini` (matches existing ingestion stack)
- Model: `gemini-2.5-flash` (fast, cost-effective)
- Rails: Input + Output guards (PII, off-topic, liability)

### rails.co

Colang rule definitions for guardrail flows.

**Example Flows:**
```colang
# Define guardrail messages
define user message
  "user asks about agriculture" as agriculture
  "user asks about medical topics" as medical_advice
  "user provides PII" as provides_pii

define bot message
  "bot provides agronomic guidance" as agronomic_guidance
  "bot declines off-topic query" as off_topic_decline
  "bot warns about PII" as pii_warning

# Define guardrail flows
define flow check agriculture topic
  user intent is agriculture
  # Continue processing
  bot provide agronomic_guidance

define flow prevent medical advice
  user intent is medical_advice
  bot send off_topic_decline

define flow prevent pii disclosure
  $pii_detected = check_pii(${user.message})
  if $pii_detected
    bot send pii_warning
    stop
```

## Custom Actions

Custom actions extend guardrails with domain-specific logic. All actions are async functions.

### PII Detection

**File:** `src/guardrails/actions/pii_detector.py`

```python
async def check_pii(text: str) -> bool:
    """Detect PII in user input."""
    # Checks for emails, phone numbers, SSN, addresses, etc.
    # Returns True if PII detected

async def redact_pii(text: str) -> str:
    """Redact PII from text."""
    # Returns text with PII replaced with [REDACTED]
```

### Topic Classification

**File:** `src/guardrails/actions/topic_classifier.py`

```python
async def classify_topic(text: str) -> str:
    """
    Classify user message topic.
    Returns: 'agriculture' | 'off_topic' | 'neutral'
    """
    # Keyword-based classification with fallback to LLM
```

### Monitoring & Logging

**File:** `src/guardrails/actions/custom_actions.py`

```python
async def log_guardrail_violation(
    violation_type: str,
    user_message: str,
    action_taken: str,
    metadata: dict
) -> None:
    """Log guardrail violations for monitoring."""
    # Log to LangSmith / Prometheus / MongoDB audit trail
```

## Testing

### Run Tests

```bash
# All tests
cd packages/guardrails
pytest tests/ -v

# Specific test suite
pytest tests/test_pii_detection.py -v

# With coverage
pytest tests/ --cov=src/guardrails --cov-report=html
```

### Test Files

| Test | Purpose | Coverage |
|------|---------|----------|
| `test_pii_detection.py` | Email, phone, SSN patterns | Regex accuracy |
| `test_topical_rails.py` | Agriculture vs. off-topic classification | Intent detection |
| `test_liability.py` | Disclaimer inclusion in responses | All response paths |

### Example Test

```python
# tests/test_pii_detection.py
import pytest
from guardrails.actions.pii_detector import check_pii

@pytest.mark.asyncio
async def test_email_detection():
    result = await check_pii("Email me at john@example.com")
    assert result is True

@pytest.mark.asyncio
async def test_clean_input():
    result = await check_pii("How do I control Ryegrass?")
    assert result is False
```

## Integration

### Integrate with LangGraph Workflow

In `packages/graph/src/graph/workflow.py`:

```python
from guardrails.guardrail import GuardrailRunner

# Initialize guardrails
guardrail = GuardrailRunner(
    config_path="packages/guardrails/src/guardrails/config/config.yml"
)

# Define graph node
async def guardrail_node(state: GraphState) -> dict:
    """Guardrail check before RAG retrieval."""
    user_message = state.messages[-1].content
    
    response = await guardrail.check_input(user_message, context=state)
    
    if not response.guardrail_passed:
        # Rejected by guardrail
        return {
            "messages": [AIMessage(content=response.bot_message)],
            "guardrail_rejection": True
        }
    
    return {
        "user_message_checked": response.modified_message,
        "guardrail_rejection": False
    }

# Add to graph
graph.add_node("guardrail", guardrail_node)
graph.add_edge("input", "guardrail")
graph.add_edge("guardrail", "rag_retrieval")
```

### Environment Variables

**`.env.example`:**
```env
# Guardrails Configuration
GUARDRAILS_CONFIG_PATH=packages/guardrails/src/guardrails/config/config.yml
GUARDRAILS_LOG_LEVEL=INFO
GUARDRAILS_STRICT_MODE=true  # Reject any guardrail violation

# LangSmith (Optional)
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=WeedAI-Guardrails
```

## Escalation & Support

**Escalation Email:** [TBD - DEFINE]

**Common Issues:**

1. **PII detector too strict?**
   - Adjust regex patterns in `pii_detector.py`
   - Consider false positive rate vs. security

2. **Off-topic classifier rejecting valid queries?**
   - Add agronomic keywords to `topic_classifier.py`
   - Test with real user queries

3. **Guardrails slow down inference?**
   - Profile with `cProfile`
   - Use lightweight LLM (flash model)
   - Cache classification results

---

**Package Version:** 0.1.0  
**Last Updated:** 2026-01-07  
**Maintainer:** Backend Team
