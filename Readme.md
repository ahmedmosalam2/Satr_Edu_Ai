<div align="center">

# ✨ Satr Edu AI

### AI-Powered Document Intelligence Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=flat-square&logo=mongodb&logoColor=white)](https://mongodb.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

<br/>

*Transform your documents into intelligent, searchable knowledge using cutting-edge AI*

<br/>

[Getting Started](#-getting-started) •
[Features](#-features) •
[API Docs](#-api-reference) •
[Architecture](#-architecture)

---

</div>

## 📋 What is Satr Edu AI?

**Satr Edu AI** is an enterprise-grade platform that converts unstructured educational content into structured, AI-ready data. Whether you're building a RAG system, a document search engine, or an intelligent tutoring system — this platform handles the heavy lifting.

<br/>

## 🎯 Features

<table>
<tr>
<td width="50%">

### 📄 Document Processing
- PDF, Word, PowerPoint, Excel
- HTML, Markdown, JSON, CSV
- Plain text files
- Automatic format detection

</td>
<td width="50%">

### 🤖 AI-Powered OCR
- Transformer-based vision models
- GPU acceleration support
- Handwritten text recognition
- Multi-language support

</td>
</tr>
<tr>
<td width="50%">

### ✂️ Smart Chunking
- Recursive text splitting
- Configurable chunk size & overlap
- Metadata preservation
- RAG-optimized output

</td>
<td width="50%">

### 🗄️ Data Management
- Async MongoDB operations
- Project-based organization
- Asset tracking & versioning
- Automatic indexing

</td>
</tr>
</table>

<br/>

## 🚀 Getting Started

### Prerequisites

```
Python 3.10+
MongoDB 4.4+
CUDA GPU (optional)
```

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/Satr_Edu_Ai.git
cd Satr_Edu_Ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
```

### Configuration

```env
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=satr_edu_ai
OCR_MODEL=microsoft/trocr-base-handwritten
APP_FILES_PATH=./src/assets/files
```

### Run

```bash
# Development
uvicorn main:app --reload --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

<br/>

## 📡 API Reference

### Upload Document

```http
POST /api/v1/upload/{project_id}
Content-Type: multipart/form-data
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | string | Target project ID |
| `file` | file | Document to upload |

### Process Document

```http
POST /api/v1/process/{project_id}
Content-Type: application/json
```

```json
{
  "file_id": "abc123_document.pdf",
  "chunk_size": 1000,
  "chunk_overlap": 200
}
```

<br/>

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────┐
│                   FastAPI Server                    │
├────────────────────────────────────────────────────┤
│  Routes        Controllers        Helpers          │
│  ├─ base       ├─ Data           ├─ Config        │
│  └─ data       ├─ Process        └─ OCR           │
│                └─ Project                          │
├────────────────────────────────────────────────────┤
│  Models                                            │
│  ├─ ProjectModel    ├─ AssetModel    ├─ ChunkModel│
│  └─ scheme_db/      └─ enums/                     │
├────────────────────────────────────────────────────┤
│                 MongoDB (Motor)                    │
└────────────────────────────────────────────────────┘
```

<br/>

## 📁 Project Structure

```
Satr_Edu_Ai/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── docker/                 # Docker configs
└── src/
    ├── controllers/        # Business logic
    ├── routes/             # API endpoints
    ├── models/             # Data models
    ├── helpers/            # Utilities
    └── assets/             # File storage
```

<br/>

## �️ Tech Stack

| Category | Technologies |
|----------|-------------|
| **Backend** | FastAPI, Uvicorn, Pydantic |
| **AI/ML** | PyTorch, Transformers, LangChain |
| **Database** | MongoDB, Motor |
| **Documents** | PyPDF2, python-docx, Unstructured |

<br/>

## � License

MIT License © 2024

---

<div align="center">

**Built with ❤️ for the future of education**

</div>
