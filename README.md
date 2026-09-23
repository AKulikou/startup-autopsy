# Startup Autopsy

**Honest AI-powered business idea validation** — Multiple analytical perspectives, no marketing speak.

An MCP server that evaluates business ideas using 8 strategic prompts, providing brutally honest feedback on viability, risks, and hidden assumptions.

---

## 📌 Overview

Instead of encouragement, Startup Autopsy gives you:
- **Multiple perspectives**: Evaluate from 3+ analytical angles (Profit Designer, No-Code Stack, Reality Auditor)
- **Honest assessment**: Separate what's possible from what's probable
- **Assumption validation**: Identify which beliefs underpin your numbers
- **Risk identification**: Find the single biggest threat to your project
- **Actionable next steps**: "Do this first" vs. "Don't pursue this"

### Current Status
**Phase 2 (MVP)** — Working with 3 evaluators, Markdown report generation, local CLI interface.

**Next phases:** FastAPI web interface, async execution, 8-evaluator full framework.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Anthropic API key (Claude access)

### Installation

```bash
# Clone or navigate to project
cd startup-autopsy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Run Analysis

```bash
python main.py
```

The CLI will:
1. Show available business ideas
2. Run 3 evaluators on your choice
3. Generate individual reports + synthesis
4. Save to `results/` directory

---

## 📁 Project Structure

```
startup-autopsy/
├── logs/                          # Application logs (auto-created)
│   └── startup_autopsy_*.log
├── results/                       # Generated reports (Markdown)
│   ├── idea_name_💰_*.md         # Individual evaluator reports
│   └── idea_name_SYNTHESIS_*.md  # Aggregated analysis
├── ideas/                         # Business ideas (text files)
│   └── [idea_name].txt
├── evaluators/                    # Evaluation modules
│   ├── base.py                   # BaseEvaluator abstract class
│   ├── profitable_designer.py    # Revenue & product viability
│   ├── no_code_stack.py          # Technical feasibility (7-day MVP)
│   └── reality_auditor.py        # Critical risk assessment
├── core/                          # Core functionality
│   ├── idea_processor.py         # Load/save ideas
│   ├── result_writer.py          # Write reports to disk
│   └── report_aggregator.py      # Synthesize results
├── config.py                      # Configuration (model, tokens)
├── main.py                        # Entry point
├── requirements.txt               # Python dependencies
├── .env                           # Environment variables (git-ignored)
├── .gitignore                     # Git ignore rules
└── README.md                      # This file
```

---

## 🔧 Configuration

### `config.py`
```python
MODEL = "claude-opus-4-1-20250805"  # Claude model to use
MAX_TOKENS = 2000                   # Max tokens per evaluation
```

### `.env`
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 📊 How It Works

### Evaluators (Current)

| Evaluator | Focus | Questions |
|-----------|-------|-----------|
| **💰 Profitable App Designer** | Revenue Model | Can people pay monthly? What's realistic pricing? Unit economics? |
| **🔧 No-Code Stack Master** | Technical Feasibility | Build MVP in 7 days with no-code? What stack? What ships on day 7? |
| **🎯 Reality Auditor** | Risk Assessment | What kills this in 30 days? Hidden assumptions? Blindspots? |

### Analysis Flow

```
1. Load business idea
   ↓
2. Run 3 evaluators in parallel (Phase 3: async)
   ├── Evaluator 1: Claude API call → Parse result
   ├── Evaluator 2: Claude API call → Parse result
   └── Evaluator 3: Claude API call → Parse result
   ↓
3. Save individual reports (Markdown)
   ├── Report 1: results/idea_EVALUATOR1_timestamp.md
   ├── Report 2: results/idea_EVALUATOR2_timestamp.md
   └── Report 3: results/idea_EVALUATOR3_timestamp.md
   ↓
4. Aggregate & synthesize
   └── Consensus, differences, comparison table
   ↓
5. Save synthesis report
   └── results/idea_SYNTHESIS_timestamp.md
```

### Verdict Categories

- **VIABLE** — High confidence, ready to build
- **VIABLE_IF** — Conditional on proving X
- **NEEDS_VALIDATION** — Too early, needs user research first
- **RISKY** — Major risks identified, needs mitigation
- **NOT_VIABLE** — Fundamental flaw found

---

## 📝 Adding a Business Idea

1. Create a text file in `ideas/` folder:
   ```bash
   ideas/your_idea_name.txt
   ```

2. Write your idea (1-3 paragraphs):
   ```
   Problem you're solving:
   How you'll solve it:
   Target customers:
   Revenue model:
   ```

3. Run analysis:
   ```bash
   python main.py
   # Select your idea by number or name
   ```

---

## 📈 Reading Results

### Individual Reports
Each evaluator produces a full analysis in Markdown:
- Assessment of the idea from their perspective
- Specific assumptions and reasoning
- Verdict + confidence level
- Token usage (for cost tracking)

### Synthesis Report
Aggregated view showing:
- **CONSENSUS** — What all evaluators agree on
- **KEY DIFFERENCES** — Where opinions diverge
- **EVALUATORS COMPARISON** — Side-by-side table (verdict, confidence, tokens)
- **RECOMMENDED NEXT STEPS** — Actionable guidance

---

## 🔄 Roadmap

### Phase 2 (Current)
- ✅ 3 evaluators (Profitable Designer, No-Code Stack, Reality Auditor)
- ✅ Local CLI interface
- ✅ Markdown report generation
- ✅ Synthesis aggregation
- ⏳ Verdict parsing (in progress)

### Phase 3
- Async execution (evaluate 3 evaluators in parallel, ~40s instead of ~120s)
- Add remaining evaluators (AI Tool Creator, SaaS Revenue Builder, Viral Designer, Launch Expert, Churn Eliminator)
- Better error handling

### Phase 4
- FastAPI web interface
- Database for results
- User authentication (if multi-user)
- Export to PDF/JSON

---

## 🛠 Development

### Running Tests
```bash
# Check a specific idea
python main.py
# Select: 6 (fitness_tracker) or 8 (meeting_schedule)
```

### Debugging
Logs are stored in `logs/` directory:
```bash
tail -f logs/startup_autopsy_*.log
```

### Adding a New Evaluator

1. Create `evaluators/your_evaluator.py`:
```python
from .base import BaseEvaluator

class YourEvaluator(BaseEvaluator):
    def get_evaluator_name(self) -> str:
        return "📊 Your Evaluator Name"
    
    def get_system_prompt(self) -> str:
        # Your role/instructions
        pass
    
    def get_evaluation_prompt(self) -> str:
        # Your questions
        pass
```

2. Add to `main.py`:
```python
evaluators = [
    ProfitableAppDesigner(idea_content),
    NoCodeStackMaster(idea_content),
    RealityAuditor(idea_content),
    YourEvaluator(idea_content),  # ← Add this
]
```

---

## 📋 Requirements

See `requirements.txt`:
```
anthropic>=0.30.0
python-dotenv>=1.0.0
```

---

## 🤔 FAQ

**Q: Why 3 evaluators and not 8?**
A: MVP phase. Full framework has 8 strategic perspectives. Start with the 3 highest-leverage.

**Q: Can I modify the prompts?**
A: Yes. Edit `evaluators/*.py` → `get_evaluation_prompt()`. Tweak questions, output format, requirements.

**Q: How much does this cost?**
A: ~$0.10-0.20 per idea (3 evaluators × 2000 tokens @ Claude pricing). Log tokens in results.

**Q: Why Markdown reports?**
A: Version control friendly, readable in any editor, easy to diff, publish to web.

---

## 📧 Contact

Built as a learning project to understand MCP, Claude API, and business analysis framework.

Questions? Feedback? Open an issue or check the transcript in `/mnt/transcripts/`.

---

## 📜 License

Personal project. Use at your own discretion.

---

**Last Updated:** 2026-09-22  
**Status:** Phase 2 (MVP with 3 evaluators)  
**Next Milestone:** Async evaluation + Phase 3 evaluators
