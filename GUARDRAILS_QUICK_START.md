# Guardrails Quick Start Reference

## 📚 Documentation Files Created

### Root Level (3 files)
| File | Purpose | Audience |
|------|---------|----------|
| `GUARDRAILS_IMPLEMENTATION_SUMMARY.md` | Executive summary of all deliverables | Project Leads, Backend Team |
| `DEPENDENCY_MANAGEMENT.md` | Strategy for non-monolithic dependencies | DevOps, Python Developers |
| (This file) | Quick reference guide | All Developers |

### `packages/guardrails/` (4 files)
| File | Purpose | Audience |
|------|---------|----------|
| `README.md` | Quick start & integration guide | Developers |
| `GUARDRAIL_DEVELOPMENT.md` | Comprehensive development guide (Q1-Q4) | Technical Leads |
| `IMPLEMENTATION_INSTRUCTIONS.md` | Step-by-step with code templates | Developers |
| `pyproject.toml` | Package configuration | DevOps |

---

## 🎯 Key Answers to Your Questions

### Q1: Non-Monolithic Dependencies ✅
**Answer:** YES - Guardrails in `packages/guardrails/` with separate `pyproject.toml`

**Why:** NeMo has specific LLM dependencies that may conflict with API/web layers
- Isolated = smaller install footprint
- Can upgrade NeMo without affecting other packages
- Users can install only what they need

**See:** `DEPENDENCY_MANAGEMENT.md`

---

### Q2: PII & Domain Protection ✅
**Answer:** Three-layer guardrails implemented

1. **PII Detection**
   - Email, phone, SSN, address, ABN, ACN patterns
   - Redaction capability
   - Implementation: `pii_detector.py`

2. **Domain Restriction**
   - Agriculture keywords ✓ → allow
   - Off-topic keywords ✗ → reject
   - Neutral → classify with LLM fallback
   - Implementation: `topic_classifier.py`

3. **Liability Disclaimer**
   - Auto-appended to agronomic responses
   - Defines limitations of advice
   - Implementation: `rails.co` flow

**See:** `GUARDRAIL_DEVELOPMENT.md` (Q2 Section) & `IMPLEMENTATION_INSTRUCTIONS.md`

---

### Q3: Implementation Timeline ✅
**Answer:** 12-week phased approach

```
Phase 1 (Weeks 1-2):   Setup, PII detection
Phase 2 (Weeks 3-4):   Core guardrails, domain classification
Phase 3 (Weeks 5-6):   Integration with LangGraph
Phase 4 (Weeks 7-8):   Testing (85%+ coverage)
Phase 5 (Weeks 9-10):  Monitoring setup
Phase 6 (Weeks 11-12): Deployment
```

**Blockers:**
- LangGraph workflow must be functional
- Neo4j knowledge graph must be queryable
- LLM integration tested

**See:** `GUARDRAIL_DEVELOPMENT.md` (Q3 Timeline)

---

### Q4: Monitoring & Observability ✅
**Answer:** LangChain Ecosystem (NOT Grafana/DataDog)

**Primary:** LangSmith (free tier, built-in to LangChain)
- Zero setup required
- Optional upgrade later
- Tracks guardrail violations

**Alternative:** Prometheus + Loki (self-hosted)
- Prometheus: metrics
- Loki: log aggregation
- Grafana: visualization
- For production deployment

**Metrics Tracked:**
- PII detection triggers
- Off-topic rejections
- Liability disclaimer inclusion
- False positive rate

**See:** `GUARDRAIL_DEVELOPMENT.md` (Q4 Monitoring)

---

## 🚨 Critical: No Escalation Email

**Status:** ⚠️ TBD - MUST DEFINE

**Fields to Fill:**
- Backend Lead email/Slack
- Product Manager email
- Escalation email address

**Location:** `GUARDRAIL_DEVELOPMENT.md` (Phase 3 section)

**Temporary Process:**
1. Log to LangSmith
2. Alert via Slack #incidents
3. Store in audit log (MongoDB)

---

## 📋 Implementation Checklist

### Pre-Phase 1
- [ ] Read `GUARDRAILS_IMPLEMENTATION_SUMMARY.md`
- [ ] Read `GARDRAIL_DEVELOPMENT.md` (full guide)
- [ ] **Define escalation email address**
- [ ] Add guardrails to root `pyproject.toml` workspace.members

### Phase 1 (Weeks 1-2)
- [ ] Create src/guardrails modules (from IMPLEMENTATION_INSTRUCTIONS.md)
- [ ] Implement GuardrailRunner, pii_detector, topic_classifier
- [ ] Create config.yml and rails.co

### Phase 2 (Weeks 3-4)
- [ ] Write unit tests (test_pii_detection.py, test_topical_rails.py)
- [ ] Achieve 85%+ coverage
- [ ] Test with real-world PII examples

### Phase 3+ (Weeks 5+)
- [ ] Integrate with LangGraph workflow
- [ ] Set up LangSmith monitoring
- [ ] Deploy to staging

---

## 🔧 Quick Commands

### Install Guardrails
```bash
# Install isolated guardrails package
uv pip install -e packages/guardrails

# Or via workspace
uv add nemo-guardrails[langchain] --package packages/guardrails
```

### Run Tests
```bash
cd packages/guardrails
pytest tests/ -v --cov=src/guardrails
```

### Add Dependencies to Guardrails
```bash
# Add to guardrails (not root!)
uv add some-package --package packages/guardrails
```

### Integrate with LangGraph
```python
from guardrails.guardrail import GuardrailRunner

guardrail = GuardrailRunner(
    config_path="packages/guardrails/src/guardrails/config/config.yml"
)

# Check user input before processing
response = await guardrail.check_input(user_message)

if response.guardrail_passed:
    proceed_with_request(response.modified_message)
else:
    return response.bot_message  # Guardrail rejection message
```

---

## 📖 Reading Guide

### For Project Leads
1. Read: `GUARDRAILS_IMPLEMENTATION_SUMMARY.md` (5 min)
2. Scan: `GUARDRAIL_DEVELOPMENT.md` overview (10 min)
3. Action: Define escalation contacts (5 min)

### For Developers (Phase 1)
1. Read: `README.md` in packages/guardrails (5 min)
2. Follow: `IMPLEMENTATION_INSTRUCTIONS.md` Phase 1 (2-3 hours)
3. Implement: Directory structure, core modules

### For Developers (Phase 2)
1. Read: Test examples in `IMPLEMENTATION_INSTRUCTIONS.md` (10 min)
2. Write: Unit tests (pii, topical, liability)
3. Run: `pytest tests/ --cov=src/guardrails`

### For DevOps/Architects
1. Read: `DEPENDENCY_MANAGEMENT.md` (15 min)
2. Read: `GUARDRAIL_DEVELOPMENT.md` Q4 section (10 min)
3. Plan: LangSmith vs. Prometheus setup

---

## 🎓 Key Concepts

### Colang Rails
Declarative rules engine for guardrails. Define user messages, bot messages, and flows.

```colang
define user message
  "user provides PII" as pii_input

define flow prevent pii
  $pii_detected = check_pii(${user.message})
  if $pii_detected
    bot send "PII warning message"
    stop
```

### NeMo Guardrails Architecture
```
User Input → Guardrails Check → LLM → Output Guardrails → Response
```

### LangChain Integration
NeMo works with LangChain via `nemo-guardrails[langchain]` extra.

### Isolation Strategy
- `packages/guardrails/` has own `pyproject.toml`
- Can upgrade NeMo without affecting `apps/api`
- Can install just guardrails for testing

---

## ❓ FAQ

**Q: Can users avoid guardrails?**
A: No. Guardrails run at API layer before LLM. Cannot be bypassed.

**Q: Will guardrails slow down responses?**
A: Minimal impact. PII check is regex (~1ms), topic class is keyword-based (~5ms).

**Q: Can guardrails reject valid agronomic queries?**
A: Possible false positives in early versions. Test with real user queries and refine keyword lists.

**Q: What if escalation email is not defined?**
A: Violations log to monitoring but won't send email. Define email ASAP.

---

## 🔗 References

- [NeMo Guardrails Docs](https://docs.nvidia.com/nemo/guardrails/)
- [Colang Language](https://docs.nvidia.com/nemo/guardrails/colang/)
- [LangChain Integration](https://python.langchain.com/docs/integrations/providers/nemo_guardrails)
- [LangSmith](https://smith.langchain.com/)
- [uv Package Manager](https://astral.sh/blog/uv)

---

**Version:** 1.0  
**Created:** 2026-01-07  
**Status:** Ready for Implementation  
**Next Review:** 2026-01-14
