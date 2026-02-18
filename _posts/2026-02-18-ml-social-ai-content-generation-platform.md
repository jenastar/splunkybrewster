---
share: true
layout: post
title: "ML Social: An AI-Powered Content Generation Platform"
date: 2026-02-18T14:17:52-08:00
slug: 2026-02-18-ml-social-ai-content-generation-platform
tags:
  - ai
  - python
  - aws-bedrock
  - openai
  - video-generation
  - podcasts
  - streamlit
permalink: /2026/02/ml-social-ai-content-generation-platform.html
---

<div class="video-embed">
<iframe width="100%" height="400" src="https://www.youtube.com/embed/L7kCpLQ6KCc?list=PLf3piQ-M6S6TIuKHPkbp-_bmYoAu_62xY" frameborder="0" allowfullscreen></iframe>
</div>

ML Social is an AI content generation platform I built that handles the full pipeline from concept to published content. It generates educational videos, podcast episodes, and social media posts, then distributes them to YouTube, Spotify, TikTok, and Instagram. The whole thing runs through a Streamlit UI or CLI, and the core idea is simple: automate the boring parts of content creation so you can focus on what matters.

<!--more-->

## What It Does

The platform has a 10-step pipeline:

1. **Concept Selection** -- picks a topic from a curriculum or generates one with GPT-4
2. **Script Generation** -- writes an educational script using GPT-4, optimized for the target format
3. **Script Optimization** -- analyzes past content performance and refines the script
4. **Visual Prompt Engineering** -- creates detailed visual descriptions for each scene
5. **Video Generation** -- generates actual video clips using AWS Bedrock Nova Reel or Kling AI
6. **Audio Generation** -- converts the script to speech with OpenAI TTS (6 voice options) or AWS Polly as fallback
7. **Video Editing** -- combines clips with audio, burns subtitles, adds intros/outros
8. **Avatar Overlay** -- composites HeyGen avatar videos onto backgrounds with green screen removal
9. **Distribution** -- uploads to YouTube, TikTok, Instagram, and Spotify
10. **Analytics** -- tracks performance metrics for the optimization feedback loop

Each step is modular. You can run the full pipeline end-to-end, or use individual components. Want to just generate audio from a script? That works. Just need video clips from prompts? Also works.

## What's Next

The idea is to replace the linear pipeline with autonomous agents that can make decisions about content strategy, select the best generation approach for each piece of content, and learn from performance data. It's early, but the agent-based architecture is more flexible than the current step-by-step pipeline.


## The Podcast Network

One of the more interesting pieces is the 5-series podcast network, all branded under "Need-to-Nerd Basis":

- **AI** -- daily briefings on AI breakthroughs, model releases, tools, and policy
- **Cyber Threat Brief** -- daily threat intel covering campaigns, actors, breaches, and TTPs
- **Vuln Watch** -- critical CVEs, zero-days, and patch intelligence as they drop
- **GeoRisk Intel** -- weekly analysis of terrorist groups, paramilitary orgs, and nation-state ops
- **CISO Briefing** -- executive-level cybersecurity intelligence for security leadership

Each series has its own character, tone, segments, and visual style. The AI series uses a "Tech Sage" character with holographic displays and floating data visualizations. The Cyber Threat Brief uses a "Code Ninja" in a dark command center with matrix-style code streams. The content prompts, tone guidelines, and segment structures are all defined in YAML configs, so adding a new series is just adding a new config block.

The podcast pipeline generates the script, converts it to audio, creates an RSS feed, and pushes everything to S3 with CloudFront distribution. For Spotify specifically, it generates upload instructions and metadata alongside the audio file.

## Video Generation Architecture

The platform supports multiple backends through a unified interface:

**Primary: AWS Bedrock Nova Reel** -- actual AI video generation. Supports 6-120 second clips in multi-shot mode at 1280x720, 24fps. You give it a text prompt, it generates real video. This is the default and it works well for educational content.

**Secondary: Kling AI** -- another true video generation API. Good for character-focused content. Uses JWT auth against `api.klingai.com`.

**Fallback: Image-to-Video** -- generates images with Bedrock Titan Image Generator v2 or DALL-E 3, then stitches them into video with MoviePy. Not as good as native video generation, but works when the video APIs are unavailable.

The unified generator auto-selects the best available provider and falls back gracefully. The routing is based on a config field:

```yaml
video_generation:
    model: aws_bedrock_video   # Routes to Nova Reel
    resolution: 1280x720
    fps: 24
    nova_reel_duration: 12     # 2 shots, 12 seconds per clip
```

## Character System

The platform has a character system for visual consistency. Each character is defined with detailed visual descriptions that get injected into every prompt:

- **Cypher-sensei** -- cyberpunk anime ML educator with electric blue eyes, twin spacebuns, and a high-tech armored suit. Holographic cityscapes in magenta and violet.
- **Dr. Neural** -- professional AI researcher in a university lab with whiteboards full of equations
- **Tech Sage** -- mystical technology mentor in a futuristic library with floating holographic books
- **Code Ninja** -- energetic programming instructor in a high-tech coding dojo
- **News Presenter** -- professional tech news anchor in a modern newsroom

These characters maintain visual consistency across episodes. The character description gets prepended to every visual prompt, so Nova Reel generates scenes with the same character style throughout.

## The Frontend

The Streamlit UI has 8 tabs:

- **Automated Pipeline** -- one-click full pipeline or custom settings with avatar selection, background video, subtitle profiles
- **Hybrid Video Generator** -- manually composite avatar videos onto backgrounds
- **Prompt Engineering** -- interactive tool for designing and testing visual prompts
- **Subtitle Engineering** -- real-time subtitle style preview with MoviePy and FFmpeg, profile save/load
- **AI News Generator** -- generate episodes for any of the 5 podcast series
- **YouTube Upload** -- direct upload with OAuth
- **Curriculum** -- manage the educational content curriculum and track progress
- **Spotify News Generator** -- Spotify-optimized podcast generation with one-click publish

The subtitle engineering tab is particularly useful. You pick a video clip, configure font, stroke, shadow, alignment, and margin settings, then preview the result in real-time. Once you like a style, save it as a profile and apply it to any future pipeline run.

![Pasted image 20260218142432](/assets/media/pasted-image-20260218142432.png)

## Tech Stack

The platform ties together a lot of services:

- **AI/ML**: OpenAI GPT-4 (scripts, optimization), DALL-E 3 (images), TTS-1 (audio), AWS Bedrock (video, images), HeyGen (avatar videos), Kling AI (video)
- **Audio**: OpenAI TTS with 6 voices, AWS Polly fallback, pydub for processing
- **Video**: MoviePy 2.x, FFmpeg, OpenCV for editing and compositing
- **Distribution**: YouTube Data API v3 (OAuth), Spotify (RSS/S3), TikTok and Instagram APIs
- **Infrastructure**: AWS S3, CloudFront, Terraform IaC, Google Cloud Storage
- **Frontend**: Streamlit with 8-tab interface

