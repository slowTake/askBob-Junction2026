# Demo video pipeline. Run from demo-video/: `make help`. Not part of the app's `make check` or CI.

RUN = uv run python -m pipeline.cli

.PHONY: help plan voice record captions assemble review check all clean

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

plan: ## Word budget per segment; fails if the script can't fit
	$(RUN) plan

voice: plan ## (stub) ElevenLabs clip per segment -> out/audio/
	$(RUN) voice

record: ## (stub) Playwright take per segment -> out/recordings/
	$(RUN) record

captions: ## out/captions.srt from the voiceover text and clip lengths
	$(RUN) captions

assemble: captions ## (stub) ffmpeg -> out/final.mp4
	$(RUN) assemble

review: ## (stub) Gemini critique of out/final.mp4 against checklist.md
	$(RUN) review

check: ## ffprobe out/final.mp4; fails above max_final_s (115 s)
	$(RUN) check

all: plan voice record assemble check ## Whole pipeline, stops at the first failure

clean: ## Delete generated media in out/
	rm -rf out
