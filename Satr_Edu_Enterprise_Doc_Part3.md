# Satr Edu AI: Enterprise-Grade Technical Documentation (Part 3/4)

This is Part 3 of the enterprise-grade technical documentation for **Satr Edu AI**. It details the Multi-Agent System, Intent Classification, Agent Tools, Educational Features, Exam Engine, Analytics System, Model Management, and Performance scalability logic.

---

# 12. Multi-Agent System Analysis

Satr Edu AI relies on an agentic architecture built on a **ReAct (Reasoning + Acting)** execution pattern. Instead of using hard-coded logic paths, the system uses isolated agents, custom tools, and a centralized message bus to process complex user queries.

---

## 12.1. Multi-Agent Orchestration Flow

The execution cycle follows a structured pipeline:

```
                  ┌──────────────────────┐
                  │      User Query      │
                  └──────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │   IntentClassifier    │
                 └───────────┬───────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼ (Greeting)   ▼ (Off Topic)  ▼ (Educational Context)
        ┌───────────┐  ┌───────────┐  ┌───────────────────────┐
        │Greeting   │  │Off-Topic  │  │ Route to Target Agent │
        │Response   │  │Response   │  └──────────┬────────────┘
        └───────────┘  └───────────┘             │
                                    ┌────────────┼────────────┐
                                    ▼            ▼            ▼
                                ┌───────┐    ┌───────┐    ┌───────┐
                                │ Tutor │    │ Socratic   │ Quiz  │
                                │ Agent │    │ Agent │    │ Agent │
                                └───┬───┘    └───┬───┘    └───┬───┘
                                    │            │            │
                                    └────────────┼────────────┘
                                                 │
                                                 ▼
                                     ┌──────────────────────┐
                                     │  ResponseFormatter   │
                                     │  (Enriches Output)   │
                                     └───────────┬──────────┘
                                                 │
                                                 ▼
                                     ┌──────────────────────┐
                                     │ Generate Follow-ups  │
                                     └───────────┬──────────┘
                                                 │
                                                 ▼
                                     ┌──────────────────────┐
                                     │  SSE Stream to Client│
                                     └──────────────────────┘
```

### 1. Ingress and Routing
- The user query is sent to the `Orchestrator.run` method.
- The `Orchestrator` extracts the short-term chat context from the `AgentMemory` class.
- The query and its context are sent to the `IntentClassifier`.

### 2. Execution Routing
If the classification returns a confidence score above `0.5`, the query is routed to the corresponding agent:
- `"research"` $\rightarrow$ `RAGAgent`
- `"tutor"` $\rightarrow$ `TutorAgent`
- `"quiz"` $\rightarrow$ `QuizAgent`
- `"socratic"` $\rightarrow$ `SocraticAgent`
- `"concept_map"` $\rightarrow$ Triggers `ConceptMapTool` directly.
- `"python_scratchpad"` $\rightarrow$ Triggers `PythonScratchpadTool` directly.

If the confidence score drops below `0.5`, the orchestrator defaults to the `RAGAgent` (`"research"` intent) to ensure the user receives a factual, grounded response.

### 3. Agent Execution
- The selected agent executes its reasoning loop.
- It logs its steps as `AgentAction` objects (detailing `tool_name`, `tool_input`, `reasoning`, and `tool_output`).
- The agent returns an `AgentResult` object.

### 4. Output Formatting
- The orchestrator enriches the output with intent metadata, classification confidence, and trace records.
- It requests the LLM to generate 3 relevant follow-up questions.
- It pushes message transactions to the `MessageBus` memory before streaming the final response.

---

## 12.2. Isolated Agent Personas

### 1. Base Agent Class (`BaseAgent`)
Defined in `src/agent/base_agent.py`. It establishes a unified structure for all system agents:
- `run(query, **kwargs) -> AgentResult`: The core execution signature.
- `AgentAction`: A data class that stores step logs, tool parameters, and reasoning traces.
- `AgentResult`: A data class that standardizes agent outputs, containing the final answer, actions list, source citations, and step counts.

### 2. RAG Agent (`RAGAgent`)
- **Purpose**: Multi-step query decomposition and information retrieval.
- **Internal Logic**:
  - Instead of querying the vector database directly, it uses heuristics to decompose complex inputs (e.g. comparison queries) into sub-queries.
  - It loops through each sub-query, calls the `KnowledgeSearchTool` to retrieve context snippets, and merges citations to prevent duplication.
  - It checks if the query contains mathematical calculations. If detected, it routes the expression to the `CalculatorTool`.
  - It combines all retrieved contexts and math answers into a final prompt for the LLM.

### 3. Tutor Agent (`TutorAgent`)
- **Purpose**: Simplifies and explains academic concepts based on student proficiency levels.
- **Internal Logic**:
  - It calls the `KnowledgeSearchTool` to retrieve subject context.
  - It adapts the explanation to the student's mastery level:
    - **Beginner**: Focuses on core concepts, using real-world analogies and step-by-step breakdowns.
    - **Advanced**: Emphasizes detailed, technical details.
  - It constructs the response using a structured template (`TUTOR_PROMPT_AR` or `TUTOR_PROMPT_EN`).

### 4. Socratic Agent (`SocraticAgent`)
- **Purpose**: Guides students using the Socratic method, helping them discover answers through dialog instead of providing direct solutions.
- **Internal Logic**:
  - It retrieves reference context to understand the target concept.
  - It formats the conversation using a specialized system prompt (`SOCRATIC_PROMPT_AR` or `SOCRATIC_PROMPT_EN`).
  - **Core Rules**: It is strictly forbidden from providing direct answers. Instead, it must ask exactly one short, guiding question at a time to lead the student to the next step, providing subtle hints if the student gets stuck.

### 5. Quiz Agent (`QuizAgent`)
- **Purpose**: Generates quick, interactive questions to verify student comprehension.
- **Internal Logic**:
  - It searches the knowledge base for relevant snippets based on the recent chat history.
  - It prompts the LLM to generate $N$ quiz questions (defaults to 3) in a structured JSON format containing questions, options, correct answers, and hints.
  - It validates and parses the JSON response, returning a structured quiz object.

---

# 13. Intent Classification

The system uses an LLM-based intent classifier to route queries, falling back to a keyword-matching model if the LLM is unavailable.

---

## 13.1. Intent Classification Engine

### 1. The Classifier Class (`IntentClassifier`)
Defined in `src/agent/core/intent_classifier.py`. It receives the user query and recent chat context, formatting them into the `INTENT_SYSTEM_PROMPT`.

### 2. Classification System Prompt
The prompt instructs the LLM to act as a structured classifier and return a JSON object:
```json
{
  "intent": "research|tutor|quiz|greeting|off_topic|concept_map|python_scratchpad|socratic",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of the choice",
  "entities": ["entity1", "entity2"]
}
```

### 3. Post-Processing and Validation
- The classifier uses regex (`\{[\s\S]*\}`) to extract the JSON payload, stripping away any extra markdown decoration.
- It parses the JSON, validates that the returned intent is supported, and sets the confidence score.

---

## 13.2. Keyword Fallback Framework
If the LLM call fails, the system uses a fallback keyword matching parser:

| Intent | Keyword Triggers (Arabic & English) | Default Confidence |
| :--- | :--- | :--- |
| **`greeting`** | `مرحبا`, `أهلاً`, `هاي`, `سلام`, `hello`, `hi`, `hey` | `0.90` |
| **`concept_map`** | `خريطة مفاهيم`, `خريطة ذهنية`, `mindmap`, `concept map` | `0.85` |
| **`python_scratchpad`** | `شغل الكود`, `نفذ الكود`, `run python`, `sandbox`, `compiler` | `0.85` |
| **`socratic`** | `سقراط`, `سقراطي`, `ناقشني`, `طريقة سقراط`, `socratic` | `0.85` |
| **`tutor`** | `فهمني`, `اشرح`, `وضحلي`, `بسّط`, `explain`, `what is`, `how` | `0.75` |
| **`quiz`** | `اختبرني`, `امتحني`, `اسألني`, `كويز`, `quiz me`, `test me` | `0.75` |
| **`research`** | Activated if no keywords match. | `0.60` |

---

# 14. Agent Tools Analysis

Tools are modular components that agents call to execute specific tasks. They inherit from the `BaseTool` class (`src/agent/base_agent.py`).

---

## 14.1. Tool Directory

### 1. Knowledge Search Tool (`KnowledgeSearchTool`)
- **Purpose**: Queries the vector database and return context snippets with tracking metadata.
- **Inputs**: `query` (str), `limit` (int).
- **Outputs**: Plain-text segments for the LLM, and a list of `Citation` objects for the frontend (containing `chunk_id`, `source_file`, `page_number`, `relevance_score`, `chunk_order`, and `section_title`).
- **Internal Logic**: Calls the `NLPController.search_vector_db_collection` method. It extracts the returned payloads, parses metadata like page numbers and headers, and updates the `_last_citations` history.

### 2. Concept Map Tool (`ConceptMapTool`)
- **Purpose**: Generates conceptual diagrams and mind maps based on the course materials.
- **Inputs**: `query` (str), `limit` (int), `language` (str).
- **Outputs**: A Markdown response containing a brief introduction, a validated Mermaid.js diagram (`graph TD` or `mindmap`), and hierarchical text bullet points.
- **Internal Logic**: First, it queries the knowledge base for context. It then prompts the LLM to generate the mind map using a template (`MAP_PROMPT_AR` or `MAP_PROMPT_EN`).

### 3. Python Scratchpad Tool (`PythonScratchpadTool`)
- **Purpose**: Safely runs python code in a sandbox environment to evaluate math equations, code snippets, or logic problems.
- **Inputs**: `code` (str).
- **Outputs**: Standard output (`stdout`), errors (`stderr`), exit codes, and execution times.
- **Safety Profile**:
  - It cleans markdown code fences (` ```python `) and execution prefixes (e.g. `run code:`) from the input.
  - It executes the script using a separate subprocess (`subprocess.run`) with a configurable timeout (defaults to 3.0 seconds) to prevent infinite loops from hanging the server.
  - It isolates environment variables and enforces UTF-8 encoding.

### 4. Calculator Tool (`CalculatorTool`)
- **Purpose**: Safely evaluates math expressions.
- **Inputs**: `expression` (str).
- **Outputs**: The evaluated result, or division-by-zero/parsing errors.
- **Safety Profile**:
  - Evaluates expressions using a safe evaluation list (`SAFE_MATH`), exposing only standard math functions like `sqrt`, `sin`, `log`, and `factorial` while stripping access to built-in system variables (`__builtins__`).
  - Sanitizes the input string, allowing only numbers, standard math operators, and pre-approved function name keys.
  - Replaces power notation (`^` $\rightarrow$ `**`) to ensure correct Python evaluation.

---

# 15. Educational Features Analysis

The platform implements educational algorithms to support adaptive learning and personalized study schedules.

---

## 15.1. The Adaptive Difficulty Engine

The system uses an **Item Response Theory (IRT)** model to track student proficiency and adapt testing difficulty dynamically.

### 1. Proficiency Scoring (ELO-Inspired Mastery)
The system tracks the student's mastery score ($M \in [0, 1]$) for each topic. When a student submits an answer, the engine updates their score using a learning rate factor ($\alpha$):
- **Correct Answer**:
  $$M_{new} = M_{old} + \alpha \times (1.0 - M_{old})$$
- **Incorrect Answer**:
  $$M_{new} = M_{old} - \alpha \times M_{old}$$

### 2. Dynamic Learning Rates
The learning rate ($\alpha$) scales based on the difficulty of the question, rewarding students for answering hard questions correctly and penalizing them for missing easy ones:
- `easy`: $\alpha = 0.08$
- `medium`: $\alpha = 0.12$
- `hard`: $\alpha = 0.18$

### 3. Difficulty Level Transitions
The engine adjusts the active difficulty level (`easy`, `medium`, `hard`) based on consecutive correct or incorrect answer streaks:
- **Upgrade**: If a student answers $3$ consecutive questions correctly (`streak == 3`), the difficulty level is upgraded (e.g. from `medium` to `hard`), and the streak counter resets.
- **Downgrade**: If a student misses $2$ consecutive questions (`streak == -2`), the difficulty level is downgraded (e.g. from `medium` to `easy`), and the streak counter resets.

---

## 15.2. Spaced Repetition Scheduling

To support long-term memory retention, the system uses a spaced repetition algorithm to schedule review sessions based on the student's mastery level:

```
  Proficiency Mastery Score
            │
            ├─► Mastered (Score ≥ 85%) ────────► Review in 14 Days
            │
            ├─► Learning (Score 60% - 85%) ────► Review in 3 Days
            │
            ├─► Struggling (Score 30% - 60%) ──► Review in 24 Hours
            │
            └─► New (Score < 30%) ─────────────► Review in 1 Hour
```

The review date is calculated using the following formula:
$$\text{Next Review Date} = \text{Last Practice Date} + \text{Review Interval}$$

The dashboard identifies topics that are due for review by checking if the current time is past the calculated review date:
$$\text{Current Time} \ge \text{Next Review Date}$$

---

# 16. Exam Engine Analysis

The Exam Engine supports automated exam generation, options validation, and essay grading.

---

## 16.1. Exam Generation Workflow

```
Retrieve Lecture Chunks (from Project Workspace)
      │
      ▼
Sample context pages (based on student weaknesses)
      │
      ▼
LLM Exam Prompt Construction (MCQ, True/False, Essay)
      │
      ├─► Temperature: 0.7 (ensures question variety)
      │
      ▼
LLM Question Generation (Outputs structured JSON)
      │
      ├─► Truncates input context at 3000 chars to avoid memory issues
      │
      ▼
Question Validation Filters
      ├─► Option Verification: Checks that correct answers exist in options
      ├─► Option Bias Filter: Prevents A-bias (distributes keys across A, B, C, D)
      └─► Truncation Repair: Salvages valid JSON blocks from partial outputs
      │
      ▼
Save to Database (Inserts draft exam in MongoDB)
```

---

## 16.2. Post-Generation Validation

### 1. Correct Answer Verification
The validation filter checks that the correct answer key matches one of the provided options. If a mismatch is detected (e.g., correct answer is `"D"` but options only list `"A"` and `"B"`), the question is discarded to prevent errors during grading.

### 2. Option Bias Filtering (A-Bias Prevention)
LLMs often exhibit bias by repeatedly placing the correct answer in the first position (`"A"`). The validation filter checks the distribution of correct answer keys. If the generated questions contain identical keys (e.g. all correct answers are `"A"`), the system logs a warning, prompting the engine to redistribute correct answer positions.

### 3. Truncation Repair Logic
When generating large exams, LLM responses may exceed token limits, resulting in incomplete JSON payloads. The system runs a regex-based repair tool (`_repair_truncated_json`) to salvage completed question objects:
- It uses a regex parser to extract fully-formed question objects (`{ "question_text": ... }`) from the truncated payload.
- It parses these objects and packages them into a valid JSON array, salvaging complete questions instead of throwing a parsing error.

---

## 16.3. Essay Grading Framework
For essay questions, the system uses the LLM to grade submissions by comparing the student's input with a model answer key:
1. **Accuracy of key concepts (40%)**: Verifies that the student's answer includes core technical concepts.
2. **Completeness of the answer (30%)**: Checks if the student addressed all parts of the prompt.
3. **Clarity of explanation (20%)**: Evaluates formatting, readability, and logic.
4. **Extra relevant details (10%)**: Awards bonus points for demonstrating advanced understanding.

The system returns a structured response containing the score, feedback, missing points, and correct points:
```json
{
  "score": 8.5,
  "feedback": "The explanation of Newton's second law is clear. However, you did not mention acceleration units.",
  "missing_points": ["Mention that acceleration is measured in meters per second squared."],
  "correct_points": ["Correctly stated the relationship between force, mass, and acceleration."]
}
```

---

# 17. Analytics System

The analytics system generates performance metrics for both students and teachers.

---

## 17.1. Performance Analysis

### 1. Student Analytics
- Computes overall average grades across exams.
- Groups weak chunks to identify topics the student struggles with.
- **Risk Forecasting**: Predicts if a student is at risk of failing based on their average grade:
  - **Low Risk**: $\text{Average Grade} \ge 70\%$
  - **Medium Risk**: $50\% \le \text{Average Grade} < 70\%$
  - **High Risk**: $\text{Average Grade} < 50\%$
- The LLM uses these metrics to generate personalized study recommendations.

### 2. Teacher/Class Analytics
- Computes class-wide average grades, pass rates (percentage of scores $\ge 50\%$), and score distributions.
- **Weak Chunk Aggregation**: Uses a frequency counter to identify the most missed concepts across the class, highlighting topics the teacher should re-teach or review.

---

# 18. Model Management System

The platform uses a factory pattern to manage integrations with different LLM providers.

```
                   ┌────────────────────────┐
                   │    get_settings()      │
                   └───────────┬────────────┘
                               │ (Read config)
                               ▼
                   ┌────────────────────────┐
                   │  LLMProviderFactory    │
                   └───────────┬────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼ (OpenAI)            ▼ (Gemini)            ▼ (Ollama)
   ┌───────────┐         ┌───────────┐         ┌───────────┐
   │  OpenAI   │         │  Gemini   │         │  Ollama   │
   │ Provider  │         │ Provider  │         │ Provider  │
   └─────┬─────┘         └─────┬─────┘         └─────┬─────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                               ▼
                   ┌────────────────────────┐
                   │      LLMWrapper        │
                   │ (Handles Async/Sync,   │
                   │ Standardizes Outputs)  │
                   └────────────────────────┘
```

---

## 18.1. Provider Abstraction Layer

- **`LLMProviderFactory`**: Creates provider instances based on system configuration. It uses lazy imports to load provider packages (e.g. `cohere` or `google-generativeai`) only when needed, reducing startup times and memory overhead.
- **`LLMWrapper`**: Wraps the active provider to expose a standardized interface (`embed_text`, `generate_text`, and `construct_prompt`).
  - **Async/Sync Handling**: The wrapper runs synchronous provider calls in a separate thread pool using `asyncio.to_thread` to prevent blocking the main event loop.
  - **Embedding Normalization**: Standardizes embedding outputs into a 2D list (`[[float]]`), accommodating differences in provider return shapes.

---

# 19. Performance & Scalability

The system handles resource-heavy processing tasks using Celery and Redis.

---

## 19.1. Asynchronous Ingestion & Task Queues

- **Redis**: Serves as the message broker, managing task queues and storing job results.
- **Celery Workers**: Run background processing tasks to keep the main FastAPI web server responsive:
  - `process_file_task`: Extracts text, runs OCR if needed, and chunks document uploads.
  - `index_project_task`: Generates embeddings and indexes chunks in Qdrant.
  - **Task Time Limits**: Enforces a soft timeout limit of 10 minutes (`600s`) and a hard limit of 11 minutes (`660s`) to prevent hung processes from blocking queue workers.

---

## 19.2. Scaling Strategy

### 1. Scaling Bottlenecks
- **OCR Rendering**: Rendering PDF pages as high-resolution images and running local OCR models (e.g. Surya) is CPU and memory intensive.
- **Vector Operations**: Generating dense embeddings and performing similarity searches can create performance bottlenecks during peak hours.

### 2. Mitigation Strategy
- **Horizontal Scaling**: Scale Celery worker instances independently from the FastAPI web server to handle spikes in document uploads.
- **Resource Partitioning**: Run CPU-heavy OCR tasks and GPU-dependent embedding generation on dedicated workers, separating them from lightweight transactional tasks like attendance tracking and database writes.

---

> [!NOTE]
> This completes Part 3 (Sections 12-19).
> Please acknowledge to proceed to Part 4 (Sections 20-26: Deployment, Security, Design Decisions, Project Strengths/Weaknesses, 100 Viva Questions, and Final Evaluation).
