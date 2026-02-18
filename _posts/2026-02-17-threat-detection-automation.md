---
share: true
layout: post
title: Threat Detection Automation
date: 2026-02-17T17:25:25-08:00
slug: 2026-02-17-threat-detection-automation
tags:
  - 
permalink: /2026/02/threat-detection-automation.html
---
![[AS_Short (1) 1.mp4|AS_Short (1) 1.mp4]]


This project automates threat detection instantiation or overhaul by first learning the unique data lake schema (all client environments are unique) and correlating that schema against a TTP framework (think MITRE). The schema discovery feeds a relational memory store that maps available telemetry to framework techniques. Once the schema is known we're also able to audit existing detections and event sources to:
<% tp.file.cursor(1) %>

<!--more-->

<% tp.file.cursor(2) %>


- Reveal any gap in coverage
- Identify potential detections given the available data set
- Curate detections for entire MITRE domains in bulk

Query generation uses Knowledge Graph-Augmented Generation (KGAG), a structured alternative to RAG that grounds every query against the discovered schema instead of relying on vector similarity and LLM inference. Benchmarked against 6 architectures including a 3B parameter LLM with full catalog context. The deterministic KGAG engine outperformed all of them.
  

The solution then is able to produce:

- NL-to-structured-query searching with .976 accuracy, a marked improvement from the vendor's .36 accuracy
- Detection automation aligning with the chosen framework domain
- Detection automation given the available data sources
- Coverage assessment and gap analysis per framework tactic
- Knowledge object management (clean up my env!)
- Data modeling suggestions and implementation