# Demo video pipeline. Run from demo-video/: `make help`. Not part of the app's `make check` or CI.

RUN = uv run python -m pipeline.cli

.PHONY: help keys plan voices voice-test voice record captions assemble review check all clean

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

keys: ## Check the Gemini and ElevenLabs keys can be found (never prints them)
	$(RUN) keys

plan: ## Word budget per segment; fails if the script can't fit
	$(RUN) plan

voices: ## List ElevenLabs voices (optional: SEARCH=narration)
	$(RUN) voices $(if $(SEARCH),--search "$(SEARCH)")

voice-test: plan ## One test clip for the first segment (optional: VOICE=<voice_id>)
	$(RUN) voice-test $(if $(VOICE),--voice $(VOICE))

voice: plan ## All clips -> out/audio/; needs voice.approved: true in video.yaml
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
