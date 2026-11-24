# skita — Markdown Documentation Analysis Sidecar

## Overview

skita is a read-only command-line tool that analyses Markdown documentation source files and produces structured findings without modifying the source tree. Its primary purpose is to model topic structure — identifying topic spans, their types and confidence levels, assembly composition, and structural issues — ahead of a downstream DITA publication path.

The tool operates as a sidecar: it reads source files from an existing documentation repository and writes all outputs to a separate sidecar directory. No source file is ever written to or modified.

## Problem and Context

Documentation repositories written in Markdown frequently contain multiple logical topics per file. A single file may hold an assembly container, two task topics, and a reference topic. Without explicit analysis, it is not possible to determine where topic boundaries fall, what type each topic is, or whether structural assumptions made during authoring are consistent with the downstream publication model.

skita addresses this gap by analysing source files against an explicit topic boundary contract and reporting findings at three severity levels: inventory (factual counts), advisory (reviewable structure), and blocking (integrity failures). The findings are deterministic: identical input always produces identical output.

## Source Format

skita analyses files that follow the skupper-docs authoring convention. Each topic span is introduced by three consecutive elements: an anchor tag, a heading, and a marker comment.

```markdown
<a id="topic-id"></a>
## Heading text
<!--PROCEDURE-->

Topic content...
```

The anchor provides a stable, author-assigned identity for the topic. The heading provides the display title and establishes nesting depth. The marker declares the topic type.

### Marker vocabulary

| Marker | Meaning |
|---|---|
| `<!--CONCEPT-->` | Conceptual topic (`concept`) |
| `<!--PROCEDURE-->` | Task topic (`task`) |
| `<!--REFERENCE-->` | Reference topic (`reference`) |
| `<!--ASSEMBLY-->` | Composition container — not a topic type |

`ASSEMBLY` is a container role, not a topic type. An assembly groups member topics and may contain introductory prose before its first member. The assembly's topic type is always `null` in the model.

Headings that carry no marker are recorded as heuristic candidates in inventory findings. They are not promoted to confirmed topic spans without an explicit marker.

### File frontmatter

A source file may have YAML frontmatter between `---` delimiters. Frontmatter is treated as container-level metadata (`skip`, `navtitle`, and similar fields). A `topic_default` field may supply a fallback type for otherwise unmarked spans. A `topic_type` field at file level is not permitted and triggers an advisory finding, since type is always determined at the span level.

## Topic Identity

Each topic span receives a stable `topic_id`. When the span has an anchor tag immediately preceding its heading, the anchor value is the `topic_id`. When no anchor is present, skita assigns a deterministic provisional ID derived from a SHA-256 hash of the source path, heading text, and line number. Provisional IDs are prefixed with `~` to distinguish them from author-assigned identities.

Finding identity is computed separately: a SHA-256 hash of the rule name, `topic_id`, and evidence string. Finding IDs are stable across runs for unchanged input, allowing findings to be tracked and reviewed over time.

## Assembly Model

An assembly span contains two parts: introductory prose and member spans.

**Introductory prose** is content that appears between the `<!--ASSEMBLY-->` marker and the first child topic or sub-assembly heading. It is recorded in the model and always triggers an `ASSEMBLY_INTRO_CANDIDATE` advisory finding, since the prose may warrant promotion to a standalone concept topic.

**Member spans** are topic or assembly spans at a greater heading depth than the assembly itself. Assembly composition is within-file only. Cross-file assembly composition — where a ditamap groups topics from multiple source files — is a navigation and publication concern handled downstream. skita models what is structurally present in a single source container.

One level of assembly nesting is supported in the MVP: an assembly may contain sub-assemblies, and sub-assemblies may contain leaf topic spans.

## Confidence Levels

Each topic span carries a confidence value that records how its type was determined.

| Confidence | Meaning |
|---|---|
| `declared` | An explicit marker comment was present |
| `inferred/high` | Strong structural evidence, no explicit marker |
| `inferred/medium` | Moderate structural evidence |
| `inferred/low` | Weak evidence; type is speculative |
| `reviewed` | A human-confirmed assignment overrides inference |

The current MVP produces only `declared` confidence for marked spans. Heuristic inference for unmarked headings is recorded as candidates in inventory findings rather than as confirmed spans with inferred confidence.

## Reviewed Assignments

A reviewer may override or confirm a span's type by writing a reviewed assignment to `reviews.json` in the sidecar root. This file persists across runs and is never written to the source repository.

Each entry records:

```json
{
  "topic_id": "kube-token-cli",
  "reviewed_type": "task",
  "evidence_ref": "finding-id-of-the-advisory-that-prompted-review",
  "timestamp": "2026-11-24T15:00:00Z"
}
```

At analysis time, skita reads `reviews.json` and applies reviewed assignments before producing findings. A reviewed assignment takes precedence over all other confidence levels. The original declared or inferred values remain in the model alongside the reviewed assignment; the evidence chain is preserved, not replaced.

## Artifact Contract

Each `skita scan` invocation creates a named run directory under `<sidecar>/runs/`. The run name defaults to `<timestamp>-<source-hash-prefix>` and may be overridden with `--run-name`.

| File | Contents |
|---|---|
| `model.json` | Full span tree: topic IDs, types, confidence, hierarchy, content |
| `findings.json` | All findings with rule, severity, topic ID, message, evidence |
| `manifest.json` | Run metadata: skita version, source path, hash, timestamp, counts |
| `report.md` | Human-readable summary: span tree, findings by severity, inventory |

Runs with identical source input and identical `reviews.json` produce byte-identical output. Source files are never modified.

## Findings

Findings are classified by severity.

**Inventory** findings record structural facts without implying a defect. `TOPIC_COUNT` reports the number of declared spans. `UNMARKED_HEADINGS` reports the count of headings without markers.

**Advisory** findings identify structure that is reviewable but not necessarily wrong. The principal advisory rules are:

- `ASSEMBLY_INTRO_CANDIDATE` — assembly contains prose before its first member. The prose may have independent reader purpose and may warrant promotion to a concept topic. Promotion always requires a reviewed assignment; skita does not promote automatically.
- `NO_ORDERED_STEPS` — a task span contains no ordered list. This may indicate an approved informal procedure or a structural omission.
- `FILE_TOPIC_TYPE_NOT_ALLOWED` — file frontmatter contains a `topic_type` field, which is not permitted at file level.
- `ASSEMBLY_NO_MEMBERS` — an assembly span has no declared member spans.

**Blocking** findings indicate analyzer-integrity failures. `DUPLICATE_TOPIC_ID` fires when two spans share the same topic ID, which would make findings and model references ambiguous. A run with blocking findings should not be used for downstream decisions.

## Limitations

skita's scope is deliberately constrained for the MVP.

- **Within-file composition only.** Assembly membership is determined from the structure of a single source file. skita does not resolve cross-file navigation structures or ditamap references.
- **No link validation.** Links within topic content are recorded as source facts but not resolved or verified.
- **No macro expansion.** Source macros and includes are preserved as literal content in the model.
- **No DITA validation.** skita does not validate DITA XML or verify that its output would satisfy a DITA processor.
- **No editorial decisions.** skita identifies structure and emits advisory findings. Decisions about whether to promote intro prose, re-type a topic, or restructure an assembly are made by reviewers, not by the tool.
- **Markdown source only.** Refdog-generated reference content and AsciiDoc files are outside the MVP scope.

## Usage

```bash
# Run directly (no installation required)
./skita scan <source-file> --sidecar <sidecar-dir>

# Override the run name
./skita scan <source-file> --sidecar <sidecar-dir> --run-name my-review

# Install via pip, then use from PATH
pip install -e .
skita scan <source-file> --sidecar <sidecar-dir>
```

Exit code is 0 when no blocking findings are present, 1 when blocking findings exist or the source file cannot be read.

## Reference Corpus

The authoritative reference corpus is the aligned pair of source files and expected DITA output:

- **Source:** `~/repos/sk/skupper-docs/input/`
- **Expected output:** `~/repos/sk/aem-dita/`

The DITA output provides ground truth for expected topic counts and type assignments. Pilot validation files are `kube-cli/site-linking.md` (assembly with five member topics), `install/cli.md` (single task topic), and `troubleshooting/index.md` (assembly with four task members). All pilot files produce zero blocking findings and span counts consistent with the DITA output.

## Architecture Decisions

Thirteen architecture decisions govern the design. All are recorded as local Markdown in `issues/`, with the decision map at `issues/000-map.md`. Key decisions that most directly affect observable behaviour:

- **0001** — skita is read-only; source files are never written to.
- **0003** — Explicit markers delimit topic spans; unmarked headings are heuristic candidates only.
- **0004** — Anchor tag value is the authoritative topic ID; deterministic provisional IDs are assigned when no anchor is present.
- **0008** — Topic spans are virtual in the MVP; physical file splitting is a downstream export concern.
- **0012** — Reviewed assignments are sidecar-only, stored in `reviews.json`; they are never written back to source.
- **0013** — Assembly composition is within-file only; cross-file composition is a navigation concern outside skita's scope.
