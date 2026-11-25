# Skita Example: Batch Scan Output

This shows what a typical Skita scan run looks like — structure, output files, and how to read the results.

## Running a Scan

```
skita scan /path/to/docs/input
```

Skita walks the source directory, skips files matched by `.skignore`, parses each Markdown file for topic span annotations, applies rules, and writes results to `build/runs/<run-id>/`.

## Output Structure

```
build/runs/<run-id>/
├── summary.md         # Human-readable batch report
├── index.json         # Machine-readable version of the same
└── files/
    └── <section>/<file>.md/
        ├── manifest.json   # Brief per-file metadata (hash, counts)
        ├── model.json      # Full parsed document model
        ├── findings.json   # Structured list of findings
        └── report.md       # Human-readable per-file report
```

## Reading the Batch Summary

`summary.md` and `index.json` report aggregate counts:

| Metric | Meaning |
|---|---|
| `.md files found` | All Markdown files discovered in the source tree |
| `Ignored (.skignore)` | Files excluded by `.skignore` rules |
| `Processed` | Files actually analyzed |
| `Errors` | Files that failed to parse |
| `Total spans` | Annotated topic sections across all processed files |
| `Total findings` | Issues found (blocking + advisory + inventory) |
| `Blocking` | Findings that would prevent publication |
| `Advisory` | Warnings that need human review |

A file with status `ok` has zero blocking findings. It may still have advisory findings.

## Per-File Output

Each processed file gets a subdirectory under `files/`. The four artifacts:

### `manifest.json`

Lightweight header: source path, content hash, run ID, and counts. Used for caching — if the hash hasn't changed, the file can be skipped on the next run.

### `model.json`

The full parsed document model. Key fields:

- **`spans`** — topic sections that have been annotated with an anchor and type. Each span records:
  - `topic_id` — the anchor value (e.g. `console-quickstart`)
  - `topic_type` — `concept`, `task`, `reference`, or `assembly`
  - `role` — `topic` or `assembly`
  - `confidence` — `declared` (explicit anchor) or `heuristic`
  - `start_line` / `end_line` — location in the source file
  - `intro_lines` — prose before the first child member (assembly only)
  - `members` — child spans (assembly only)
  - `content_lines` — the topic body

- **`candidates`** — headings that look like topic spans but have no anchor annotation. These are heuristic suggestions, not confirmed spans.

### `findings.json`

A list of findings. Each finding has:

```json
{
  "finding_id": "4b1abff51907009b",
  "rule": "ASSEMBLY_INTRO_CANDIDATE",
  "severity": "advisory",
  "topic_id": "console",
  "message": "Assembly has 2 line(s) of intro prose ...",
  "evidence": "The Network console provides ...",
  "source_path": "/path/to/console/index.md",
  "start_line": 5
}
```

Severities:

| Severity | Meaning |
|---|---|
| `blocking` | Must be resolved; file cannot be published |
| `advisory` | Needs human review; does not block |
| `inventory` | Informational count (e.g. topic count, unmarked headings) |

### `report.md`

A human-readable rendering of the model and findings. Contains:

1. **Topic Spans** — the declared topic hierarchy with IDs, types, and line numbers
2. **Unmarked Headings** — heuristic candidates (not confirmed spans)
3. **Advisory Findings** — each finding with its evidence quoted
4. **Inventory** — summary counts

## Common Advisory Rules

| Rule | What It Means |
|---|---|
| `ASSEMBLY_INTRO_CANDIDATE` | An assembly has intro prose before its first member. Consider promoting it to a concept topic. |
| `NO_ORDERED_STEPS` | A task topic has no numbered list. May be an intentional informal procedure. |
| `UNMARKED_HEADINGS` | Headings in the file that are not annotated as topic spans — heuristic candidates only. |

## Example: Annotated Markdown Source

Skita reads topic annotations from HTML anchor tags or heading attributes embedded in Markdown:

```markdown
<!-- {#console type=assembly} -->
# Maintain network health and service reachability

Intro prose about the assembly.

<!-- {#console-quickstart type=concept} -->
## Get started with Skupper network console

1. Install the Network Observer on a Kubernetes cluster.
2. Change context to a site namespace.
3. Install with defaults:
   ```bash
   helm install skupper-network-observer ...
   ```

<!-- {#console-advanced type=concept} -->
## Advanced Configuration

The Network Observer Helm chart includes advanced configuration options...
```

## Filtering with .skignore

`.skignore` follows `.gitignore` syntax. Files and directories matched are recorded in `index.json` with `"skipped": true` and produce no model, findings, or report artifacts.

Example: in the scan above, the entire `refdog/` subtree (88 files) was ignored, leaving 32 files for analysis.
