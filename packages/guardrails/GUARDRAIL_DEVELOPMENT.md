# NeMo Guardrails Development Guide

## Overview
This document outlines the development phases, implementation details, and best practices for integrating NeMo Guardrails into the WeedAI system. Guardrails ensure safe, domain-specific, and compliant AI agent behavior.

## Table of Contents
1. [Phase Overview](#phase-overview)
2. [Question 1: Dependency Management](#question-1-dependency-management)
3. [Question 2: PII Protection & Domain Restrictions](#question-2-pii-protection--domain-restrictions)
4. [Question 3: Implementation Timeline](#question-3-implementation-timeline)
5. [Question 4: Monitoring & Observability](#question-4-monitoring--observability)
6. [Implementation Checklist](#implementation-checklist)

---

## Phase Overview

### When Guardrails Are Developed
Guardrails should be designed and implemented at **multiple phases** of the development lifecycle:

| Phase | When | Why | Artifacts |
|-------|------|-----|-----------|
| **Phase 0: Discovery** | Pre-implementation | Define safety requirements, domain boundaries, and compliance needs | Guardrail requirements doc (this file) |
| **Phase 1: Architecture** | Early design | Establish guardrail patterns and integration points in LangGraph | Rails structure, config design |
| **Phase 2: Core Development** | Parallel with backend | Build basic guardrails (topical, PII, liability) | `config.yml`, `rails.co`, custom actions |
| **Phase 3: RAG Integration** | After knowledge graph setup | Ensure guardrails work with retrieval results | RAG guardrails, source validation |
| **Phase 4: Testing & Validation** | Pre-deployment | Unit, integration, and adversarial tests | Test suite in `packages/guardrails/tests/` |
| **Phase 5: Monitoring & Observability** | Deployment & beyond | Track guardrail violations and effectiveness | Metrics, logging, alerting |

---

## Question 1: Dependency Management

### Recommendation: Separate, Composable Dependencies

**Rationale:** NeMo Guardrails has specific dependencies (LLM integrations, Colang runtime) that may conflict with other components. Using separate dependency management allows:
- Isolated updates (NeMo updates don't break the core LangGraph workflow)
- Lighter-weight installations (users can install only what they need)
- Clear dependency boundaries

### Directory Structure

```
packages/guardrails/
├── pyproject.toml              # Isolated guardrails dependencies
│   ├── nemo-guardrails[langchain]
│   ├── pydantic
│   └── python-dotenv
├── src/guardrails/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── config.yml          # NeMo config
│   │   └── rails.co            # Colang definitions
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── custom_actions.py   # Domain-specific handlers
│   │   └── pii_detector.py     # PII detection logic
│   ├── guardrail.py            # Main GuardrailRunner wrapper
│   └── utils/
│       ├── __init__.py
│       └── validators.py       # Validation utilities
├── tests/
│   ├── test_pii_detection.py
│   ├── test_topical_rails.py
│   ├── test_liability.py
│   └── conftest.py
└── README.md                   # Component-specific setup
```

### Dependency Isolation Strategy

**Root `pyproject.toml`** (workspace mode):
```toml
[tool.uv.workspace]
members = [
    "apps/api",
    "apps/web",
    "apps/simulation-sidecar",
    "packages/core",
    "packages/graph",
    "packages/guardrails",  # Isolated member
]
```

**`packages/guardrails/pyproject.toml`**:
```toml
[project]
name = "guardrails"
version = "0.1.0"
dependencies = [
    "nemo-guardrails[langchain]==0.10.0",  # Pinned version
    "pydantic>=2.0",
    "python-dotenv",
]
```

**Installation:**
```bash
# Install only guardrails dependencies
uv pip install -e packages/guardrails

# Or install specific guardrails version
uv add nemo-guardrails[langchain] --package packages/guardrails
```

---

## Question 2: PII Protection & Domain Restrictions

### Guardrail Categories & Implementation

#### A. PII Detection & Prevention

**Objective:** Prevent the system from disclosing or processing Personally Identifiable Information.

**PII Types to Restrict:**
- Names (persons, companies)
- Email addresses
- Phone numbers
- Social Security Numbers (SSN)
- Addresses (home, IP)
- Financial account numbers
- Government IDs

**Implementation in `rails.co`:**
```colang
define user message
  "user wants to know PII" as pii_request

define bot message
  "bot discloses PII" as pii_disclosure

define flow handle pii request
  user intent is pii_request
  bot respond with "I cannot provide personally identifiable information. Please consult with the relevant department for sensitive data."

define flow prevent pii in context
  $pii_detected = check_pii(${user.message})
  if $pii_detected
    bot send message "PII detected in your query. Please rephrase without personal details."
```

**Custom Action in `custom_actions.py`:**
```python
from typing import Optional
import re

async def check_pii(text: str) -> bool:
    """Detect common PII patterns."""
    pii_patterns = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b(?:\+61|0)[0-9 ]{8,}\b',  # Australian format
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    }
    
    for pii_type, pattern in pii_patterns.items():
        if re.search(pattern, text):
            return True
    return False
```

#### B. Domain Restriction (Agronomic Topics Only)

**Objective:** Keep agents focused on agronomic and herbicide-related queries only.

**Off-Limits Topics:**
- Medical/health advice
- Financial advice
- Political/controversial topics
- Unrelated technical support

**Implementation in `rails.co`:**
```colang
define user message
  "user asks about agriculture/herbicides" as agriculture_query
  "user asks about off-topic subjects" as off_topic_query

define bot message
  "bot provides agronomic advice" as agronomic_response
  "bot declines off-topic query" as off_topic_decline

define flow handle agriculture question
  user intent is agriculture_query
  # Proceed with normal processing

define flow decline off-topic
  user intent is off_topic_query
  bot respond with "I specialize in agronomic advice and herbicide management. Please ask questions related to weed control, crop protection, or integrated pest management."
```

**Custom Intent Classifier in `custom_actions.py`:**
```python
from typing import Optional

async def classify_topic(text: str) -> str:
    """
    Classify user message intent.
    Returns: 'agriculture', 'off_topic', or 'neutral'
    """
    agriculture_keywords = [
        'herbicide', 'weed', 'crop', 'pesticide',
        'pest', 'fungicide', 'insecticide', 'yield',
        'rotation', 'infestation', 'control'
    ]
    
    off_topic_keywords = [
        'doctor', 'medical', 'legal', 'financial',
        'political', 'religious', 'investment', 'mortgage'
    ]
    
    text_lower = text.lower()
    
    if any(kw in text_lower for kw in agriculture_keywords):
        return 'agriculture'
    if any(kw in text_lower for kw in off_topic_keywords):
        return 'off_topic'
    return 'neutral'
```

#### C. Liability Disclosure

**Objective:** Include appropriate disclaimers and limit liability exposure.

**Implementation in `rails.co`:**
```colang
define bot message
  "bot includes liability disclaimer" as liability_notice

define flow add liability disclaimer
  # Appended to agronomic responses
  bot respond with "⚠️ DISCLAIMER: This advice is general in nature. Always follow product label instructions and consult local agronomists for field-specific recommendations."
```

---

## Question 3: Implementation Timeline

### Recommended Phases

| Timeline | Phase | Key Deliverables | Owner | Notes |
|----------|-------|------------------|-------|-------|
| **Week 1-2** | Setup & Config | `config.yml`, basic rails structure, PII detector | Backend Lead | Parallel with Phase 2 backend work |
| **Week 3-4** | Core Rails | Domain classification, topical guards, liability notice | Backend Lead | Test with mock LangGraph states |
| **Week 5-6** | Integration | Integrate with LangGraph workflow, test end-to-end | Backend + Graph Lead | Requires functional graph nodes |
| **Week 7-8** | Testing & Refinement | Unit tests, integration tests, adversarial tests | QA + Backend | 85%+ test coverage |
| **Week 9-10** | Monitoring Setup | Logging, metrics, alerting (see Q4) | DevOps + Backend | Optional: upgrade to paid monitoring |
| **Week 11-12** | Deployment Prep | Docker integration, staging tests, documentation | DevOps | Production readiness review |

### Blockers & Dependencies

- **Blocker 1:** LangGraph workflow must be functional (Phase 2)
- **Blocker 2:** Neo4j knowledge graph must be queryable (Phase 3)
- **Blocker 3:** LLM integration (Gemini/Claude) tested with guardrails

### Escalation Process

**For guardrail violations (TBD - No current escalation email):**
- Log to monitoring system (Grafana/DataDog)
- Alert DevOps/Backend lead via Slack #incidents
- Store violation details in audit log (MongoDB)

**Current Escalation Contacts:**
- **Backend Lead:** [TBD]
- **Product Manager:** [TBD]
- **Escalation Email:** [TBD - DEFINE]

---

## Question 4: Monitoring & Observability

### Strategy: LangChain Ecosystem Focus

**Recommended Approach:** Use **LangChain's built-in observability** (LangSmith) paired with **open-source logging** (Loki/Prometheus) to avoid vendor lock-in while maintaining single-ecosystem consistency.

### Monitoring Components

#### A. Guardrail Violations

**Metrics to Track:**
- PII detection triggers (count, patterns)
- Off-topic query rejections (count, user feedback)
- Liability disclaimer inclusion rate
- False positive rate (guardrail blocked valid requests)

**Implementation in `custom_actions.py`:**
```python
from typing import Optional
import json
from datetime import datetime

async def log_guardrail_violation(
    violation_type: str,
    user_message: str,
    action_taken: str,
    metadata: Optional[dict] = None
) -> None:
    """Log guardrail violations for monitoring."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "violation_type": violation_type,  # 'pii', 'off_topic', 'liability'
        "action_taken": action_taken,      # 'rejected', 'flagged', 'modified'
        "metadata": metadata or {}
    }
    
    # Send to LangSmith (via LangChain callback)
    # Also log to stderr for Docker/Kubernetes collection
    print(json.dumps(log_entry), file=sys.stderr)
    
    # Optional: Store in MongoDB for audit trail
    # await audit_collection.insert_one(log_entry)
```

#### B. Integration with LangChain Callbacks

**Use LangChain's callback system** to automatically capture guardrail metrics:

```python
from langchain.callbacks import LangChainTracer

# In main API setup
tracer = LangChainTracer(project_name="WeedAI-Guardrails")

# Guardrails automatically logged
guardrail_runner = GuardrailRunner(
    callbacks=[tracer],
    config_path="packages/guardrails/config/config.yml"
)
```

#### C. Dashboard Queries (Optional: Grafana/Prometheus)

**If scaling to production:**

```promql
# PII violations per hour
rate(guardrail_pii_violations_total[1h])

# Off-topic rejection rate
rate(guardrail_offTopic_rejections_total[1h]) / rate(requests_total[1h])

# Average response latency (with guardrails)
histogram_quantile(0.95, rate(guardrail_latency_seconds_bucket[5m]))
```

### Monitoring Setup (No External Vendor Required)

**Option 1: LangSmith (LangChain Native)**
- Pros: Zero setup, built into LangChain ecosystem
- Cons: Proprietary cloud (but free tier available)
- Recommendation: Use for MVP, optional upgrade later

**Option 2: Open-Source Stack (Prometheus + Loki)**
- Pros: Self-hosted, no vendor lock-in
- Cons: More operational overhead
- Components:
  - **Prometheus:** Metrics collection (guardrail violations, latency)
  - **Loki:** Log aggregation (guardrail reasons, PII patterns)
  - **Grafana:** Visualization
- Kubernetes-ready (if deployed to GCP)

**Decision:** Start with **LangSmith** for MVP, migrate to Prometheus+Loki if self-hosting becomes requirement.

### Alerting Rules

**Critical Alerts:**
```yaml
# Alert on PII detection spike
- alert: PIIDetectionSpike
  expr: rate(guardrail_pii_violations_total[5m]) > 5
  for: 5m
  annotations:
    summary: "High PII detection rate"
    action: "Review flagged queries in audit log"

# Alert on high rejection rate
- alert: HighGuardrailRejectionRate
  expr: rate(guardrail_rejections_total[5m]) / rate(requests_total[5m]) > 0.1
  for: 10m
  annotations:
    summary: "Guardrails rejecting >10% of requests"
    action: "Check guardrail config, may need refinement"
```

---

## Implementation Checklist

### Pre-Implementation
- [ ] Define escalation email address (currently TBD)
- [ ] Finalize monitoring approach (LangSmith vs. Prometheus)
- [ ] Assign owners for each phase
- [ ] Set up `packages/guardrails` directory structure

### Phase 1: Setup & Config (Week 1-2)
- [ ] Create `packages/guardrails/pyproject.toml` with isolated dependencies
- [ ] Create `packages/guardrails/src/guardrails/config/config.yml`
- [ ] Create `packages/guardrails/src/guardrails/config/rails.co`
- [ ] Create `packages/guardrails/src/guardrails/actions/custom_actions.py`
- [ ] Create `packages/guardrails/src/guardrails/actions/pii_detector.py`
- [ ] Test PII detection with unit tests
- [ ] Document setup in `packages/guardrails/README.md`

### Phase 2: Core Rails (Week 3-4)
- [ ] Implement domain classification action
- [ ] Implement off-topic detection flow
- [ ] Implement liability disclaimer flow
- [ ] Add logging for all guardrail violations
- [ ] Test with mock LangGraph states

### Phase 3: Integration (Week 5-6)
- [ ] Wire guardrails into `packages/graph/workflow.py`
- [ ] Test with real knowledge graph queries
- [ ] Validate PII is not leaked from RAG retrieval
- [ ] Document integration points in Graph README

### Phase 4: Testing & Refinement (Week 7-8)
- [ ] Add unit tests: `tests/test_pii_detection.py`
- [ ] Add unit tests: `tests/test_topical_rails.py`
- [ ] Add unit tests: `tests/test_liability.py`
- [ ] Add integration tests with mock LangGraph
- [ ] Reach 85%+ test coverage
- [ ] Adversarial test: attempt PII injection, jailbreaks

### Phase 5: Monitoring (Week 9-10)
- [ ] Set up LangSmith project (or Prometheus)
- [ ] Implement `log_guardrail_violation()` across all guards
- [ ] Create Grafana dashboard (optional)
- [ ] Define alerting rules

### Phase 6: Deployment (Week 11-12)
- [ ] Integrate guardrails Docker image into `docker-compose.yml`
- [ ] Document environment variables (`.env.example`)
- [ ] Perform staging tests
- [ ] Create runbook for escalation

---

## References & Resources

- [NeMo Guardrails Documentation](https://docs.nvidia.com/nemo/guardrails/)
- [Colang Language Spec](https://docs.nvidia.com/nemo/guardrails/colang/)
- [LangChain + NeMo Integration](https://python.langchain.com/docs/integrations/providers/nemo_guardrails)
- [LangSmith Monitoring](https://smith.langchain.com/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-07  
**Next Review:** 2026-01-14
