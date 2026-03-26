# AI Coding Session Summary & Workflow

## Overview
This project was designed and architected by myself, using an AI coding assistant strictly to accelerate boilerplate generation, perform complex data transformations, and handle specialized physics algorithms for frontend visualizations.

## 1. System Architecture & Database Design
**My Process:** I first analyzed the 18 SAP JSONL data tables. I chose **SQLite** combined with **FastAPI** because I needed an extremely low-latency, portable database that I could instantly query with a Python backend, without requiring the assessment evaluators to run Docker containers or heavy PostgreSQL servers just to test the demo.
**AI Assistance:** Once I mapped the schema in my notes (e.g., mapping `billing_document_items.material` to `products.product`), I used the AI to write the Python Pandas boilerplate to chunk and ingest these specific JSONL files into the SQLite database (`db.py`). 

*Key Prompt:* `"I have mapped 18 JSONL tables for an SAP O2C flow. I need a python script using Pandas to read these files and use to_sql to insert them into a local SQLite database named graph_intel.db."*

## 2. LLM Prompting & Guardrails Construction
**My Process:** I built the core prompt strategy. I knew that zero-shot SQL generation requires exact schema definitions. I also noticed that the SAP JSONL data stored booleans as `"false"` strings, which Pandas converts to integer `0`/`1` in SQLite. 
**AI Assistance:** I instructed the AI to build the `llm_engine.py` wrapper around the `google.generativeai` SDK. When the AI's generated SQL failed due to querying `='false'`, I debugged the SQLite columns and updated the prompt to explicitly instruct the model: *"Boolean fields like billingDocumentIsCancelled are stored as 0 or 1. NEVER use 'false' strings."*
Additionally, I designed a regex-based interceptor pattern and had the AI implement the exact syntax to block DML keywords (`DROP`, `DELETE`, etc.). 

## 3. Frontend Visualization (React & D3.js)
**My Process:** I designed a split-pane interface using a premium white glassmorphism theme to replicate an Enterprise SaaS environment. I chose D3.js over simpler libraries like Cytoscape because I needed granular control over force-directed physics for high node counts.
**AI Assistance:** D3 physics code is notoriously verbose. After I defined the component structure (`GraphVisualization.jsx`, `ChatPanel.jsx`, etc.), I prompted the AI to generate the D3 simulation ticks, SVG definitions, and React `useEffect` bindings. 

*Debugging Iteration:* We encountered a critical React state corruption bug where D3's internal reference mutation was crashing Vite's Fast Refresh. I diagnosed this as a shallow-copy mutation issue and instructed the AI to deep-clone the `nodes` and `edges` arrays before passing them into the `d3.forceSimulation()`.

## 4. Final Polish & UI Component Extraction
**My Process:** I utilized an external UI tool (Stitch) to draft out an "Enterprise Light Theme".
**AI Assistance:** I used the AI to translate my design tokens into CSS in `App.css`, requesting it to swap out basic string emojis with high-quality inline SVG paths for a more professional dashboard appearance.
