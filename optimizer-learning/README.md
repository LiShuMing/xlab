# Optimizer Learning Tool — Volcano vs Cascades

A Python project for comparing two classic query optimizer algorithms side-by-side:
- **Volcano** (bottom-up, Calcite-style)
- **Cascades** (top-down, Graefe 1995-style)

Both optimizers work on the same relational algebra model and rule set, making
it easy to see how their different approaches lead to the same (or different)
optimal plans.

## Quick Start

```bash
cd optimizer-learning

# List available examples
python cli.py list

# Run a single optimizer
python cli.py run volcano two-table-join
python cli.py run cascades two-table-join

# Compare both optimizers on one example
python cli.py compare two-table-join

# Compare all examples
python cli.py compare --all

# See internal state (RelSets/Groups, rule firing order, etc.)
python cli.py explain volcano two-table-join
python cli.py explain cascades two-table-join
```

## Project Structure

```
optimizer-learning/
├── cli.py                    # Command-line entry point
├── optimizer/                 # Shared model & rules
│   ├── model.py              # RelNode, Cost, TraitSet, Convention
│   ├── rules.py              # Transformation rules (RelOptRule equivalents)
│   └── cost.py               # Cost computation utilities
├── volcano/                   # Volcano optimizer (Calcite-style)
│   └── planner.py            # VolcanoPlanner: RelSet/RelSubset, FIFO queue
├── cascades/                  # Cascades optimizer (Graefe 1995-style)
│   └── planner.py            # CascadesPlanner: Memo, Group/GroupExpression, tasks
├── compare/                   # Comparison engine
│   └── engine.py             # Side-by-side analysis
├── examples/                  # Example query trees
│   └── queries.py            # SQL→RelNode examples
└── tests/                     # Tests
```

## Architecture Comparison

### Volcano (Calcite-style)

```
Phase 1: BUILDING_EQUIVALENCE_CLASSES (bottom-up)
  ┌─────────────────────────────────────────────────┐
  │ register(root)                                  │
  │   → register children first (bottom-up)          │
  │   → create/find RelSet for each RelNode          │
  │   → RelSet.add(rel) → RelSubset by trait         │
  │   → fire rules → enqueue RuleMatches            │
  │   → parent input update when physical arrives    │
  └─────────────────────────────────────────────────┘
                        ↓
Phase 2: Process Rule Queue (FIFO, exhaustive)
  ┌─────────────────────────────────────────────────┐
  │ while queue not empty:                          │
  │   match = queue.poll()                           │
  │   new_rels = match.rule.transform()              │
  │   for new_rel in new_rels: register(new_rel)     │
  └─────────────────────────────────────────────────┘
                        ↓
Phase 3: OPTIMIZING — findBestExp from root RelSubset
```

**Key data structures**:
| Calcite Class | This Project |
|---|---|
| `RelSet` | `RelSet` — equivalence class |
| `RelSubset` | `RelSubset` — trait-constrained group |
| `VolcanoRuleCall` | `RuleMatch` |
| `IterativeRuleQueue` | `IterativeRuleQueue` |
| `mapDigestToRel` | `_digest_map` (structural canonicalization) |
| `VolcanoPlanner.findBestExp()` | `VolcanoPlanner._find_best_exp()` |

### Cascades (Graefe 1995-style)

```
Phase 1: Build Memo (top-down traversal)
  ┌─────────────────────────────────────────────────┐
  │ build_memo(root)                                │
  │   → create Group for root                        │
  │   → recursively build child Groups               │
  │   → GroupExpression with Group references        │
  └─────────────────────────────────────────────────┘
                        ↓
Phase 2: Optimize (recursive descent)
  ┌─────────────────────────────────────────────────┐
  │ OptimizeGroup(root_group):                       │
  │   1. recurse on children (bottom-up cost)        │
  │   2. update RelNode inputs → physical children   │
  │   3. fire exploration rules → new GroupExprs     │
  │   4. compute total costs → update best           │
  └─────────────────────────────────────────────────┘
```

**Key data structures**:
| Cascades Concept | This Project |
|---|---|
| Memo | `Memo` — explicit Group tree |
| Group | `Group` — equivalence class |
| GroupExpression | `GroupExpression` — RelNode in a Group |
| OptimizeGroup task | `OptimizeGroup` (recursive) |
| Upper/Lower bound pruning | `upper_bound` / `lower_bound` |
| Enforcer task | `EnforceProperties` |

## Key Differences Demonstrated

### 1. Equivalence Class Structure

| Aspect | Volcano | Cascades |
|---|---|---|
| Container | `RelSet` + `RelSubset` | `Memo` with `Group` |
| Physical grouping | Same RelSet (semantic equivalence) | Same Group (explicit) |
| Trait handling | RelSubset per trait combination | is_logical flag on GroupExpression |

### 2. Rule Execution

| Aspect | Volcano | Cascades |
|---|---|---|
| Order | FIFO queue (all matches equal) | Recursive task descent |
| Trigger | RelNode registration event | OptimizeGroup execution |
| Parent-child sync | Input replacement when physical arrives | `_update_rel_children` before rule fire |

### 3. Search Space

| Metric | two-table-join | star-schema |
|---|---|---|
| Volcano rule firings | 4 | 27 |
| Cascades rule firings | 4 | 13 |
| Volcano equivalence classes | 3 | 11 |
| Cascades groups | 3 | 10 |

### 4. Cost Pruning

- **Volcano**: Exhaustive — all rules fire, no cost-based pruning during search
- **Cascades**: Upper/lower bound pruning — branches cut when `lower_bound >= upper_bound`

In this simplified implementation, both produce identical plans for basic queries.
The Cascades pruning advantage becomes more pronounced with larger queries and
more diverse cost distributions.

## How to Extend

### Adding New Rules

Add a new `Rule` subclass in `optimizer/rules.py`:

```python
class MyNewRule(Rule):
    def __init__(self):
        super().__init__("MyRule", priority=5)

    def matches(self, rel: RelNode) -> bool:
        return isinstance(rel, MyNodeType)

    def transform(self, match: RuleMatch) -> list[RelNode]:
        # Produce equivalent expressions
        return [new_rel]
```

Then add it to `default_rules()`.

### Adding New Query Examples

Add a function in `examples/queries.py` that returns a RelNode tree:

```python
def my_query() -> RelNode:
    RelNode.reset_id_counter()
    scan = TableScan("my_table", row_count=1000.0)
    return LogicalFilter(input=scan, condition="x > 0")
```

Register it in the `EXAMPLES` dict.

## Mapping to Calcite Source Code

| This Project | Calcite Equivalent |
|---|---|
| `optimizer/model.py` | `core/src/main/java/org/apache/calcite/plan/RelNode.java` |
| `optimizer/rules.py` | `core/src/main/java/org/apache/calcite/plan/RelOptRule.java` |
| `volcano/planner.py` | `core/src/main/java/org/apache/calcite/plan/volcano/VolcanoPlanner.java` |
| `RelSet` | `core/src/main/java/org/apache/calcite/plan/volcano/RelSet.java` |
| `RelSubset` | `core/src/main/java/org/apache/calcite/plan/volcano/RelSubset.java` |
| `_digest_map` | `VolcanoPlanner.mapDigestToRel` |
| `cascades/planner.py` | Cascades algorithm (not in Calcite — Graefe 1995 paper) |
| `Memo` / `Group` | Implicit in Cascades, explicit here |
| `OptimizeGroup` | Cascades OptimizeGroup task |
