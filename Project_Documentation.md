# FastAPI - API Documentation (v0.1.0)

Comprehensive API Documentation for all routes in the system.


---

## Table of Contents

- [Ai Routes](#ai-routes)
- [Adaptive learning Routes](#adaptive learning-routes)
- [Admin Routes](#admin-routes)
- [Agent — agentic rag Routes](#agent — agentic rag-routes)
- [Analytics Routes](#analytics-routes)
- [Chat Routes](#chat-routes)
- [Documents — file management Routes](#documents — file management-routes)
- [Evaluation — rag quality Routes](#evaluation — rag quality-routes)
- [Exam Routes](#exam-routes)
- [Model settings Routes](#model settings-routes)
- [Ocr Routes](#ocr-routes)
- [Pipeline — document processing Routes](#pipeline — document processing-routes)
- [Projects Routes](#projects-routes)
- [Api_v1 Routes](#api_v1-routes)
- [Auth Routes](#auth-routes)
- [Nlp Routes](#nlp-routes)

---

## Ai Routes

### `POST` /api/v1/ai/exam/generate
**Summary:** Generate Exam From Text

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/ai/exam/generate/file
**Summary:** Generate Exam From File

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| num_questions | query | No | integer |
| difficulty | query | No | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/ai/summarize
**Summary:** Summarize Content

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/ai/summarize/file
**Summary:** Summarize File

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/ai/grade/essay
**Summary:** Grade Essay

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Agent — Multi-Agent System Routes

### `POST` /api/v1/agent/ask
**Summary:** Single RAG Agent — search + answer with multi-step reasoning

**Request Body:**
```json
{
  "project_id": "...",
  "query": "your question",
  "language": "ar"
}
```

**Responses:**
- **200**: Successful Response with answer + reasoning steps
- **422**: Validation Error

---

### `POST` /api/v1/agent/smart-ask
**Summary:** Multi-Agent Smart Ask — automatically routes to the right agent

**Request Body:**
```json
{
  "project_id": "...",
  "query": "your question or command",
  "language": "ar",
  "student_id": "optional — loads student level from exam history",
  "conversation_id": "optional — continue existing conversation",
  "auto_quiz": false
}
```

**Features:**
- **Intent Detection:** Automatically routes to the right agent
- **Conversation Persistence:** Saves to MongoDB, send `conversation_id` to continue
- **Student Adaptation:** Send `student_id` to adapt explanations to student level
- **Auto-Handoff:** Set `auto_quiz: true` → after Tutor explains, Quiz generates questions

**Intent Detection:**
- "explain" / "what is" / "how" → **Tutor Agent** (adaptive explanation)
- "quiz me" / "test me" → **Quiz Agent** (quick questions)
- Any other question → **Research Agent** (RAG search + answer)

**Responses:**
- **200**: Returns answer + agent_used + intent + conversation_id + auto_quiz (if enabled)
- **404**: Project or conversation not found
- **422**: Validation Error

---

### `GET` /api/v1/agent/tools
**Summary:** List available agent tools

**Responses:**
- **200**: Successful Response

---

### `POST` /api/v1/agent/batch
**Summary:** Batch Agent Queries — ask multiple questions at once (max 10)

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Adaptive learning Routes

### `GET` /api/v1/adaptive/explain/{exam_id}
**Summary:** Explain Weaknesses

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| exam_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/adaptive/recommendations/{student_id}
**Summary:** Get Recommendations

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| student_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/adaptive/study-plan/{student_id}
**Summary:** Get Study Plan

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| student_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/adaptive/progress/{student_id}
**Summary:** Get Student Progress

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| student_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Admin Routes

### `GET` /api/v1/admin/users
**Summary:** List Users

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| role | query | No | string |
| page | query | No | integer |
| page_size | query | No | integer |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/admin/users/pending
**Summary:** List Pending Teachers

**Responses:**
- **200**: Successful Response

---

### `GET` /api/v1/admin/users/{user_id}
**Summary:** Get User

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| user_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `DELETE` /api/v1/admin/users/{user_id}
**Summary:** Delete User

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| user_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `PUT` /api/v1/admin/users/{user_id}/activate
**Summary:** Toggle User Activation

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| user_id | path | Yes | string |
| active | query | Yes | boolean |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `PUT` /api/v1/admin/users/{user_id}/role
**Summary:** Change User Role

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| user_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/admin/stats
**Summary:** Get System Stats

**Responses:**
- **200**: Successful Response

---

### `GET` /api/v1/admin/projects
**Summary:** List All Projects

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| page | query | No | integer |
| page_size | query | No | integer |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/admin/storage/status
**Summary:** Get Storage Status

**Responses:**
- **200**: Successful Response

---

## Agent — agentic rag Routes

### `POST` /api/v1/agent/ask
**Summary:** Agent Ask

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/agent/tools
**Summary:** List Available Tools

**Responses:**
- **200**: Successful Response

---

### `POST` /api/v1/agent/batch
**Summary:** Agent Batch Ask

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | query | Yes | string |
| language | query | No | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Analytics Routes

### `GET` /api/v1/analytics/student/{student_id}
**Summary:** Get Student Analytics

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| student_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/analytics/exam/{exam_id}
**Summary:** Get Exam Analytics

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| exam_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/analytics/leaderboard/{project_id}
**Summary:** Get Project Leaderboard

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |
| top_n | query | No | integer |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/analytics/teacher/{teacher_id}/overview
**Summary:** Get Teacher Overview

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| teacher_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Chat Routes

### `POST` /api/v1/chat/{project_id}
**Summary:** Chat

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/chat/conversations
**Summary:** List My Conversations

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | query | No | string |
| page | query | No | integer |
| page_size | query | No | integer |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/chat/conversations/{conversation_id}
**Summary:** Get Conversation

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| conversation_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `DELETE` /api/v1/chat/conversations/{conversation_id}
**Summary:** Delete Conversation

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| conversation_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/chat/conversations/{conversation_id}/clear
**Summary:** Clear Conversation

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| conversation_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Documents — file management Routes

### `POST` /api/v1/documents/{project_id}/upload
**Summary:** Upload And Process

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/documents/{project_id}/batch-upload
**Summary:** Batch Upload

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/documents/{project_id}/stats
**Summary:** Project Stats

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/documents/{project_id}
**Summary:** List Documents

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |
| status | query | No | string |
| page | query | No | integer |
| page_size | query | No | integer |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/documents/{project_id}/{document_id}
**Summary:** Get Document

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |
| document_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `DELETE` /api/v1/documents/{project_id}/{document_id}
**Summary:** Delete Document

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |
| document_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `PATCH` /api/v1/documents/{project_id}/{document_id}/toggle
**Summary:** Toggle Document

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |
| document_id | path | Yes | string |
| enabled | query | Yes | boolean |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/documents/{project_id}/{document_id}/reprocess
**Summary:** Reprocess Document

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |
| document_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Evaluation — rag quality Routes

### `POST` /api/v1/eval/retrieval
**Summary:** Evaluate Retrieval

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/eval/rag
**Summary:** Evaluate Rag

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Exam Routes

### `POST` /api/v1/exam/create
**Summary:** Create Exam

Teacher generates an AI exam from project content.
Exam is saved as DRAFT — not visible to students yet.

**Responses:**
- **201**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/exam/{exam_id}
**Summary:** Get Exam

Get exam details.
- Students can only see APPROVED exams (correct_answer hidden).
- Teachers can see their own drafts and approved exams.

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| exam_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `DELETE` /api/v1/exam/{exam_id}
**Summary:** Delete Exam

Teacher: حذف امتحان مسودة. لا يمكن حذف الامتحانات المعتمدة.

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| exam_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/exam/student/project/{project_id}
**Summary:** Student List Exams

Student: عرض الامتحانات المتاحة (Approved فقط) لمشروع معين.

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/exam/student/results
**Summary:** Student My Results

Student: عرض كل نتائجه في كل الامتحانات.

**Responses:**
- **200**: Successful Response

---

### `GET` /api/v1/exam/project/{project_id}
**Summary:** List Exams By Project

Teacher: List all exams (draft + approved) for a project.

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `PUT` /api/v1/exam/{exam_id}/approve
**Summary:** Approve Exam

Teacher approves a DRAFT exam → becomes visible to students.
Only the teacher who created the exam can approve it.

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| exam_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/exam/{exam_id}/submit
**Summary:** Submit Exam

Student submits answers → system auto-grades:
- MCQ / TRUE_FALSE: exact match
- ESSAY: AI-based grading via existing AIController.grade_essay()
Returns score, feedback, and weak_chunks for lecture highlighting.

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| exam_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/exam/{exam_id}/results/{student_id}
**Summary:** Get Student Result

Get a student's exam result.
Students can only see their own result.
Teachers can see any student's result.

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| exam_id | path | Yes | string |
| student_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/exam/{exam_id}/results
**Summary:** Get All Results

Teacher: Get all student results for an exam.

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| exam_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Model settings Routes

### `GET` /api/v1/models/current
**Summary:** Get Current Model

**Responses:**
- **200**: Successful Response

---

### `GET` /api/v1/models/available
**Summary:** List Available Models

**Responses:**
- **200**: Successful Response

---

### `PUT` /api/v1/models/set
**Summary:** Set Model

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/models/test
**Summary:** Test Model

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Ocr Routes

### `GET` /api/v1/ocr/status
**Summary:** Ocr Status

**Responses:**
- **200**: Successful Response

---

### `POST` /api/v1/ocr/extract
**Summary:** Extract From Image

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/ocr/extract/pdf
**Summary:** Extract From Pdf

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/ocr/surya/status
**Summary:** Surya Status

**Responses:**
- **200**: Successful Response

---

## Pipeline — document processing Routes

### `GET` /api/v1/pipeline/info
**Summary:** Pipeline Info

**Responses:**
- **200**: Successful Response

---

### `GET` /api/v1/pipeline/strategies
**Summary:** List Strategies

**Responses:**
- **200**: Successful Response

---

### `POST` /api/v1/pipeline/process
**Summary:** Process File

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/pipeline/process-text
**Summary:** Process Text

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Projects Routes

### `POST` /api/v1/projects
**Summary:** Create Project

**Responses:**
- **201**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/projects
**Summary:** List Projects

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| page | query | No | integer |
| page_size | query | No | integer |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/projects/{project_id}
**Summary:** Get Project

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `DELETE` /api/v1/projects/{project_id}
**Summary:** Delete Project

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `PUT` /api/v1/projects/{project_id}/settings
**Summary:** Update Project Settings

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/projects/{project_id}/stats
**Summary:** Get Project Stats

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Api_v1 Routes

### `GET` /api/v1/
**Summary:** Welcome

**Responses:**
- **200**: Successful Response

---

### `GET` /api/v1/health
**Summary:** Health Check

**Responses:**
- **200**: Successful Response

---


### `POST` /api/v1/nlp/index/push/{project_id}
**Summary:** Index Project

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/nlp/index/info/{project_id}
**Summary:** Get Project Index Info

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/nlp/search/{project_id}
**Summary:** Nlp Search

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/nlp/answer/{project_id}
**Summary:** Nlp Answer

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Auth Routes

### `POST` /api/v1/auth/register
**Summary:** Register

**Responses:**
- **201**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/auth/login
**Summary:** Login

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/auth/me
**Summary:** Get Me

**Responses:**
- **200**: Successful Response

---

### `PUT` /api/v1/auth/me/profile
**Summary:** Update Profile

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `PUT` /api/v1/auth/me/change-password
**Summary:** Change Password

**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `PUT` /api/v1/auth/approve/{user_id}
**Summary:** Approve Teacher

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| user_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

## Nlp Routes

### `POST` /api/v1/nlp/index/push/{project_id}
**Summary:** Index Project

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `GET` /api/v1/nlp/index/info/{project_id}
**Summary:** Get Project Index Info

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/nlp/search/{project_id}
**Summary:** Nlp Search

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/nlp/answer/{project_id}
**Summary:** Nlp Answer

**Parameters:**
| Name | In | Required | Type |
| --- | --- | --- | --- |
| project_id | path | Yes | string |


**Responses:**
- **200**: Successful Response
- **422**: Validation Error

---

### `POST` /api/v1/nlp/search-multi
**Summary:** Multi-Project Search — Search across multiple projects at once

**Request Body:**
```json
{
  "text": "your search query",
  "project_ids": ["project_1", "project_2", "project_3"],
  "limit_per_project": 5
}
```

**Responses:**
- **200**: Returns merged results from all projects sorted by relevance
- **404**: None of the requested projects were found
- **422**: Validation Error

---

### `POST` /api/v1/nlp/answer-multi
**Summary:** Multi-Project RAG Answer — Generate answer using context from multiple projects

**Request Body:**
```json
{
  "text": "your question",
  "project_ids": ["project_1", "project_2", "project_3"],
  "limit_per_project": 5
}
```

**Responses:**
- **200**: Returns AI answer with sources from multiple projects
- **400**: No relevant content found
- **404**: None of the requested projects were found
- **422**: Validation Error

---

