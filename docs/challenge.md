# The challenge: Make Blueprints Talk

Junction hackathon challenge set by **Stoa**. This page restates the brief as Stoa gave it, then lists what follows from it for us. Where the brief is silent, we say so rather than guess.

## The brief

> Build a program that answers natural language questions about construction drawings and building information models accurately and verifiably.

- **The problem.** Construction site engineers spend hours every day looking for information in drawings. General-purpose AI models often fail when they analyze complex technical drawings. Stoa calls this one of the hardest unsolved problems in construction tech.
- **The task.** Build a program that answers natural language questions about construction drawings.
- **The data.** Stoa provides a dataset of real technical drawings in many formats and languages, together with example questions.
- **What a great answer is.** It is **correct**, and it **shows where in the drawing it came from**, so a person can verify it in seconds.
- **What they want to see.** Solutions that next year's frontier models won't make obsolete. For example, hybrid solutions that combine frontier models with computer vision, 3D, geometry, or small fine-tuned models.

## About Stoa

Stoa is building an AI-native operating system for construction, an industry worth about $15 trillion (roughly 13% of world GDP). The team is based in Helsinki and already works with several of the largest construction companies in the Nordics.

The brief lists Stoa's founding tech team as the source of insight for teams: engineers who work on construction AI daily, together with a construction engineer with years of experience on large building projects.

## What we know about the dataset

From the brief, plus what we have seen in the files so far:

- **Formats:** "many formats". So far we have seen raster images (PNG), vector PDFs and IFC building models.
- **Languages:** "many languages". The floor plan we have looked at is Finnish, e.g. `MH` (bedroom), `OH` (living room), door tags like `09` (900 mm leaf) and dimensions in millimetres such as `10 800`.
- **Example questions:** included with the dataset. Treat them as the core of our evaluation set (see `backend/eval/`).

Not stated in the brief, so check before relying on it: how the challenge is judged and how answers are scored, whether there is a held-out question set, and whether drawings and IFC files describe the same buildings. If they do, the IFC can serve as ground truth for what we extract from the drawings.

## What this means for our build

| The brief asks for | How we answer it |
| --- | --- |
| Accurate answers | Facts come from a structured building model (rooms, walls, doors, dimensions) extracted by deterministic readers, not from a model reading pixels at answer time. |
| Verifiable answers | Every fact keeps its source: document, page and bounding box, or IFC GlobalId. Answers must cite that evidence. The server checks each citation, and the UI highlights it on the drawing or in the 3D model. |
| Many formats and languages | One reader per format (IFC, vector PDF, raster/OCR) writes into the same model. The drawing vocabulary is a table we extend as we see new codes. |
| Not obsolete next year | Hybrid design: geometry, OCR and IFC parsing do the measuring, and the language model plans and explains. A better model improves the system without replacing it. |

Architecture and setup are in the [README](../README.md); decisions are logged in [decisions.md](decisions.md).
