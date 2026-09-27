# Japanese Comments Coding Skill

## Purpose

This skill defines a **coding‑only** workflow that enforces all source‑code
comments to be written in Japanese. It is intended for projects where the
team communicates primarily in Japanese and wants the codebase to be
readable without language barriers.

## Scope

* Applies to any **.py**, **.js**, **.ts**, **.sh**, **.dockerfile** and other
  script files in the repository.
* Only comment lines (starting with `#`, `//`, `/* … */`, `<!-- … -->`, etc.)
  are targeted.  Code statements are never altered.
* The skill does **not** modify documentation files such as `README.md`
  unless they are explicitly included in a separate documentation‑style
  skill.

## Step‑by‑Step Process

1. **Detect Comment Tokens** – Scan each file for language‑specific comment
   markers.   For Python/Shell: `#`.  For JavaScript/TypeScript: `//` and
   `/* … */`.  For Dockerfile: `#`.  For HTML templates: `<!-- … -->`.
2. **Extract Text** – Strip the comment marker and any leading whitespace to get the
   raw comment text.
3. **Translate to Japanese** – Use a reliable translation method (e.g. a
   bilingual teammate, trusted translation API, or manual rewrite).  Preserve
   any code snippets, URLs, or special tokens inside the comment.
4. **Preserve Formatting** – Re‑attach the original comment marker and leading
   indentation so the file’s layout is unchanged.
5. **Validate** – Run a quick lint step that checks for non‑Japanese characters
   in comment bodies (e.g. using a regex that matches Unicode Hiragana/Katakana
   ranges).  Fail the lint if any comment contains English alphabetic text.
6. **Commit** – Ensure the change passes the repository’s existing CI/lint
   pipelines before merging.

## Decision Points & Branching

* **Existing Japanese Comment?** – If the comment already contains Japanese,
  leave it unchanged.
* **Mixed Language Comment?** – Split the comment into separate lines: keep the
  Japanese part and translate the English part, preserving any code literals.
* **Untranslatable Content** – For URLs, file paths, or code examples, keep the
  original text unchanged and add a Japanese explanatory prefix.

## Quality Criteria

* **Correctness** – The translated comment must convey the same meaning as the
  original.
* **Readability** – Use natural Japanese phrasing, respecting the project's
  style guide (e.g. line length ≤ 79 characters for Python).
* **Idempotence** – Running the skill a second time should result in no further
  modifications.
* **No Syntax Breakage** – The file must still pass its language’s parser after
  comment translation.

## Example Prompt

```
Translate all comments in the workspace to Japanese, keeping code unchanged.
```

## Related Customizations

* `agent-customization` – Use this skill in combination with a generic
  *code‑review* skill to automatically enforce comment language standards.
* `project-setup-info-local` – Add a pre‑commit hook that runs this skill’s lint
  check before commits.

---

*Created by GitHub Copilot based on user request to define a coding skill that
emphasizes Japanese comments.*
