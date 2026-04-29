<div align="center">
  <img src="assets/satr_edu_clean.png" width="100"/>
  <h1>Satr Edu</h1>
</div>

<p align="center">
  <a href="https://github.com/ahmedmosalam2/Satr_Edu_Ai">Document</a> | 
  <a href="#">Roadmap</a> | 
  <a href="#">Twitter</a> | 
  <a href="#">Discord</a> | 
  <a href="#">Demo</a>
</p>

# README in English | [العربية](#)

## Table of Contents
- [What is Satr Edu?](#what-is-satr-edu-ai)
- [Demo](#demo)
- [Latest Updates](#latest-updates)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Get Started](#get-started)
- [Configurations](#configurations)
- [Build a Docker image](#build-a-docker-image)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Community](#community)
- [Contributing](#contributing)

## What is Satr Edu?
Satr Edu is a leading open-source Retrieval-Augmented Generation (RAG) engine that fuses cutting-edge RAG with Agent capabilities to create a superior context layer for educational LLMs. It offers a streamlined RAG workflow adaptable to educational institutions of any scale. Powered by a converged context engine and pre-built educational agent templates, Satr Edu enables developers to transform complex learning materials into high-fidelity, production-ready AI tutors with exceptional efficiency and precision.

## Demo
Try our demo at http://localhost:8000/docs.

## Latest Updates
* 2026-04-28 Supports Gemini 1.5 Flash for advanced Arabic generation.
* 2026-04-27 Integrates Surya OCR for GPU-accelerated document and image parsing.
* 2026-04-25 Supports 'Memory' and ReAct logic for AI agent.
* 2026-04-23 Supports multi-modal file processing (PDF, DOCX, PPTX, Images).
* 2026-04-20 Supports orchestrable ingestion pipeline for educational content.

## Key Features
* **"Quality in, quality out"**
  Deep document understanding-based knowledge extraction from unstructured educational data.
  Finds "needle in a data haystack" of literally unlimited tokens.

* **Template-based chunking**
  Intelligent and explainable.
  Plenty of template options to choose from (Recursive, Semantic, Structure).

* **Grounded citations with reduced hallucinations**
  Visualization of text chunking to allow human intervention.
  Quick view of the key references and traceable citations to support grounded answers for students.

* **Compatibility with heterogeneous data sources**
  Supports Word, slides, excel, txt, images, scanned copies, structured data, web pages, and more.

* **Automated and effortless RAG workflow**
  Streamlined RAG orchestration catered to students and educational businesses.
  Configurable LLMs (Ollama, Gemini) as well as embedding models.
  Multiple recall paired with fused re-ranking via Qdrant.
  Intuitive APIs for seamless integration with business.

## System Architecture

Satr Edu follows a modular architecture designed for high-fidelity document processing and intelligent retrieval. The system is divided into several specialized layers to ensure scalability and precision.

<div align="center">
  <img src="image.png" alt="Satr Edu System Architecture" width="900"/>
</div>

### Technical Infrastructure

- **Ingestion Layer**: Orchestrates multi-format file processing using a factory pattern. It utilizes specialized parsers for PDF, DOCX, and HTML, with a dedicated GPU-accelerated OCR pipeline for scanned content.
- **Processing Layer**: Implements advanced chunking strategies including recursive character splitting and structural awareness to maintain document hierarchy and context.
- **Storage Layer**: A hybrid database approach using Qdrant for high-dimensional vector search and MongoDB for relational metadata and project management.
- **Agentic Reasoning**: A multi-agent system built on the ReAct (Reasoning + Acting) pattern, capable of tool-use and autonomous context retrieval to provide grounded educational answers.
- **Task Management**: Utilizes Celery and Redis for asynchronous background processing, ensuring that heavy computational tasks like OCR do not block the main application flow.

## Get Started

**Prerequisites**
* CPU >= 4 cores
* RAM >= 16 GB
* Disk >= 50 GB
* Docker >= 24.0.0 & Docker Compose >= v2.26.1

**Start up the server**

Clone the repo:
```bash
$ git clone https://github.com/ahmedmosalam2/Satr_Edu_Ai.git
```

Start up the server using the pre-built Docker Compose:
```bash
$ cd Satr_Edu_Ai
$ docker compose -f docker/docker-compose.yml up -d
```

Check the server status after having the server up and running:
```bash
$ docker logs -f satr_edu_app
```

The following output confirms a successful launch of the system:
```text
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

In your web browser, enter the IP address of your server and log in to Satr Edu.
With the default settings, you only need to enter `http://localhost:8000/docs` to see the API interface.

## Configurations
When it comes to system configurations, you will need to manage the following files:

* `.env`: Keeps the fundamental setups for the system, such as API keys, Database passwords, and LLM configurations.
* `docker/docker-compose.yml`: The system relies on docker-compose.yml to start up. The environment variables in this file will be automatically populated when the Docker container starts.

To update the default HTTP serving port (8000), go to docker-compose.yml and change `8000:8000` to `<YOUR_SERVING_PORT>:8000`.

Updates to the above configurations require a reboot of all containers to take effect:
```bash
$ docker compose -f docker/docker-compose.yml restart app
```

## Build a Docker image
This image is approximately 2 GB in size and relies on external LLM and embedding services.

```bash
$ git clone https://github.com/ahmedmosalam2/Satr_Edu_Ai.git
$ cd Satr_Edu_Ai/
$ docker build --platform linux/amd64 -f Dockerfile -t satr_edu_ai:latest .
```

## Documentation
* Quickstart
* Configuration
* Release notes
* User guides
* Developer guides

## Roadmap
See the Satr Edu Roadmap 2026

## Community
* Discord
* Twitter
* GitHub Discussions

## Contributing
Satr Edu flourishes via open-source collaboration. In this spirit, we embrace diverse contributions from the community. If you would like to be a part, review our Contribution Guidelines first.
