# Skita glossary

## Source container

A Markdown file on disk that supplies one or more topics to `skita`. A source container is not assumed to have one topic type.

## Topic

An independently classifiable and potentially publishable unit within a source container. A topic has a type such as `concept`, `task`, or `reference`, its own title and source span, and relationships to other topics.

## Topic span

The source range that represents one topic inside a source container. It includes any immediately preceding ID or anchor declaration, the topic heading, and the topic content. A topic span can be analyzed and reported without creating a new source file.

## Topic envelope

The complete source identity boundary of a topic span: preceding ID/anchor declarations, the heading, the content range, and the relationship to the containing source container.

## Assembly

A composition unit that presents or orders multiple topics. An assembly may be represented by a source container, but assembly is a composition role rather than a replacement for the topic types of its members.

## Materialized topic

A derived output file or publication unit created from a topic span. Materialization is a downstream representation choice and does not change the source container's ownership or boundaries.

## Virtual topic span

A topic span retained as analysis and report data without creating a derived source file. Virtual spans are the canonical MVP representation; materialized topics are optional downstream projections.

## Sidecar

A tool that reads a source project without modifying it and writes its analysis artifacts, reports, and local findings in its own project space.

## Finding

A reviewable observation produced by analysis. A finding has a rule, severity, source location, explanation, and eventually a stable topic/source identity.

## Topic identity

The durable logical identity of a topic, independent of its current heading, source path, and line coordinates. An authored topic should expose an explicit anchor when it needs long-lived identity; an unanchored identity is provisional and may require review after substantive change. Generated Refdog topics use the identity of the upstream object they represent.

## Finding fingerprint

The normalized identity of the rule target and relevant evidence used to recognize the same finding across source moves and presentation edits. A finding fingerprint is not a line number or source path.

## Generated object identity

The identity supplied by the source model behind generated documentation, such as a command and option, or an API resource field with its version and complete property path. It is the primary identity for Refdog-derived topics and findings; rendered Markdown is a projection and provenance surface.

## Run directory

A sidecar-owned directory containing the artifacts from one analysis invocation. It is separate from every scanned source root and is treated as an immutable record of that run.

## Finding index

A generated, reviewable local projection of the current findings and their stable identities. It belongs to the sidecar's project space and is separate from the manually curated Wayfinder decision files.

## Source fact

An observed property preserved from the source or parser, such as a heading, marker, block type, position, anchor, or raw source slice. A source fact is distinct from an inferred classification or a review judgment.

## Section role

The structural purpose of a section within a topic, such as prerequisites, procedure, result, example, or related information. A section role does not determine the topic type.

## Container metadata

Metadata attached to a source container that describes its publication or ownership context. Container metadata may be inherited by member topics when they lack a local value, but it does not turn the container into a single topic.

## Topic default

A file-level fallback type used only as inference evidence for otherwise unmarked topic spans. A topic default never overrides a reviewed assignment or an explicit span marker.

## Finding severity

The action significance of an analysis result. Inventory records evidence, advisory findings request review of ambiguity, and blocking findings indicate that the analyzer cannot safely establish its model or outputs.

## Analysis workbench

The end-to-end `skita` surface that lets a user move from inventory through AST queries, topic modeling, structural validation, relationship analysis, publication preflight, and regression comparison. The workbench owns shared analysis evidence and interfaces while leaving source ownership, generated facts, navigation, publication, DITA writing, and editorial acceptance to their respective boundaries.

## AST query

A read-only query over the parsed Markdown syntax tree and preserved source positions. AST queries are an interactive and programmable way to understand existing content; they are not limited to a fixed warning catalog.

## Declared, inferred, and reviewed type

Three different states of topic classification. A declared type comes from an explicit source marker or metadata; an inferred type comes from analysis evidence; a reviewed type is a human-confirmed result. Inference must not overwrite declaration or source content.
