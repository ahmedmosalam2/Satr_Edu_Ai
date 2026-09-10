# AI Workspace — Premium Design Specification
**Satr Edu AI — Graduation Project**  
*Senior Product Designer perspective (OpenAI / Notion / Linear / Vercel standards)*

---

## 1. Design Philosophy

| Principle | Application |
|-----------|-------------|
| **Chat is the product** | Center panel = 60-70% viewport. Everything else supports it. |
| **Progressive disclosure** | Advanced tools hidden in floating drawer; only 4-6 quick actions visible. |
| **Alive, not static** | Agent status shows real-time thinking steps; widgets update live. |
| **Context over chrome** | No persistent feature lists. Show only what's relevant *right now*. |
| **Premium minimalism** | Generous whitespace, purposeful motion, no decorative clutter. |

**Reference feel:** ChatGPT / Claude / Cursor / Notion AI / Linear — not a dashboard, not a settings page.

---

## 2. Layout Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Top Bar (64px)  │  Logo/Title          │  User Menu / Notifications        │
├─────────┬───────────────────────────────────────────┬────────────────────────┤
│         │                                           │  Smart Sidebar (320px) │
│         │                                           │  ────────────────────  │
│  Left   │                                           │  Current Context       │
│  Nav    │     Chat Workspace (flex-1)               │  Attached Files        │
│  (248px │                                           │  Knowledge Status      │
│  collaps│                                           │  Agent Status (alive)  │
│  ible)  │                                           │  Running Tasks         │
│         │                                           │  Current Course        │
│         │                                           │  Recent Conversations  │
│         │                                           │  Pinned Documents      │
└─────────┴───────────────────────────────────────────┴────────────────────────┘
```

**Breakpoints:**
- Desktop (≥1280px): Three-panel
- Tablet (1024-1279px): Left nav collapsible, right sidebar → bottom sheet
- Mobile (<1024px): Left nav → drawer, right sidebar → bottom sheet, chat full-width

---

## 3. Component Specifications

### 3.1 Left Navigation (AppSidebar)
**Current:** Works well — keep collapsible behavior, icon-only mode.
**Enhancements:**
- Add "AI Workspace" as top-level nav item (routes to `/student/ai-workspace`)
- Badge for unread AI notifications (new conversations, completed tasks)
- Keyboard shortcut hint: `⌘ K` to focus chat

### 3.2 Top Bar (WorkspaceHeader)
```tsx
// Minimal — only:
- Logo (click → dashboard)
- Current course/context selector (dropdown)
- User avatar menu
- Global search (⌘ K) — opens command palette
```

### 3.3 Center: Chat Workspace (The Hero)

#### A. Conversation List (Left third on desktop, full-width on mobile)
```
┌──────────────────────────────────────────┐
│  Conversations          [+ New Chat]     │
├──────────────────────────────────────────┤
│  💬  Introduction to ML          2m ago  │
│     "How does gradient descent work?"    │
├──────────────────────────────────────────┤
│  📄  PDF Analysis: Chapter 3      1h ago │
│     "Summarize key concepts..."          │
├──────────────────────────────────────────┤
│  🧠  Study Plan Generation          3h   │
│     "Create 2-week schedule..."          │
└──────────────────────────────────────────┘
```

#### B. Active Conversation (Main area)
- **Message bubbles:** Subtle, generous padding, code blocks with syntax highlighting
- **Agent reasoning trace:** Collapsible "Thinking..." section per message (already implemented in `AIChatComponent`)
- **Sources:** Inline chips with document preview on hover
- **Follow-ups:** Rendered as actionable pills (already implemented)

#### C. Input Composer (Always visible, bottom)
```
┌────────────────────────────────────────────────────────────────────┐
│  [📎]  [📄]  [🖼️]  [🎤]  [🔍]  [⋯ More]    [Type a message...]   [▶]  │
└────────────────────────────────────────────────────────────────────┘
```
- **4-6 primary actions:** Upload, Add Context (course materials), OCR, Chat with PDF, Summarize
- **"More" (⋯):** Opens floating AI Tools drawer (300px from right)
- **Attached context chips:** Render above input when files added, removable with ×

### 3.4 Right: Smart Sidebar (Context-Aware Widgets)

**Widget Stack (top → bottom priority):**

| Widget | When Shown | Content |
|--------|------------|---------|
| **Current Context** | Always | Course name, active lesson, enrolled students (teacher) |
| **Attached Files** | Files in context | Chips with name, size, type, × remove |
| **Knowledge Base Status** | Course has AI project | `Healthy • 42 docs • Updated today` + sync button |
| **Agent Status** | During agent run | Live steps: `🔍 Searching KB… → 📖 Reading PDF… → 🧠 Synthesizing…` |
| **Running Tasks** | Background jobs | Progress rings: OCR (45%), Embedding (12%), Indexing |
| **Current Course** | Student view | Progress ring, next exam, weak areas (3 max) |
| **Recent Conversations** | Always | 5 most recent, click to switch |
| **Pinned Documents** | Teacher/Admin | Quick-access course materials |

**Behavior:** Widgets auto-collapse when empty. No empty states — just don't render.

---

## 4. AI Tools Drawer (Floating Panel)

**Trigger:** `⋯ More` button in composer, or `⌘ /` shortcut  
**Position:** Fixed right, 320px width, full height minus header  
**Animation:** Slide-in with backdrop blur

```tsx
const AI_TOOLS = [
  // Primary (shown in composer)
  { id: 'upload', label: 'Upload File', icon: Upload, shortcut: '⌘U', primary: true },
  { id: 'add-context', label: 'Add Course Context', icon: BookOpen, shortcut: '⌘K', primary: true },
  { id: 'ocr', label: 'OCR / Extract Text', icon: ScanText, shortcut: '⌘O', primary: true },
  { id: 'chat-pdf', label: 'Chat with PDF', icon: FileText, shortcut: '⌘P', primary: true },
  { id: 'summarize', label: 'Summarize', icon: Sparkles, shortcut: '⌘S', primary: true },
  
  // Secondary (in drawer only)
  { id: 'image-analysis', label: 'Analyze Image', icon: Image },
  { id: 'doc-summary', label: 'Document Summary', icon: FileText },
  { id: 'translate', label: 'Translate', icon: Languages },
  { id: 'quiz-gen', label: 'Generate Quiz', icon: HelpCircle },
  { id: 'study-plan', label: 'Create Study Plan', icon: Calendar },
  { id: 'flashcards', label: 'Generate Flashcards', icon: Layers },
  { id: 'assignment-help', label: 'Assignment Helper', icon: ClipboardList },
  { id: 'kb-search', label: 'Search Knowledge Base', icon: Search },
  { id: 'voice', label: 'Voice Assistant', icon: Mic },
  { id: 'future', label: 'Experimental Tools', icon: FlaskConical, badge: 'Beta' },
];
```

**Each tool opens a focused modal/panel** — not a new page. Example: "Chat with PDF" opens a split view (PDF left, chat right).

---

## 5. Agent Status — "Alive" Design

**Current implementation** in `AiAssistantPage` shows animated steps — **elevate this.**

### Visual States
```
┌─────────────────────────────────────┐
│  🤖  Agent: Tutor          ● Live   │
│  ─────────────────────────────────  │
│  🔍  Searching knowledge base…      │
│  ████████░░░░░░░░░░  45%            │
│                                     │
│  📖  Reading: lecture5.pdf (p.3)    │
│  🧠  Synthesizing answer…           │
└─────────────────────────────────────┘
```

### Implementation
- WebSocket or SSE from backend for real-time agent steps
- Fallback: Polling every 500ms during active run
- Each step: icon + label + subtle progress
- **Color coding:** Blue (search), Green (reading), Purple (reasoning), Orange (tool use), Emerald (complete)

---

## 6. Knowledge Base Widget (Compact)

```
┌─────────────────────────────────────┐
│  📚  Knowledge Base        ● Healthy │
│  ─────────────────────────────────  │
│  42 documents  •  1.2M tokens       │
│  Updated 2 hours ago                │
│  ─────────────────────────────────  │
│  [Sync Now]  [View Details]         │
└─────────────────────────────────────┘
```

- **Health states:** Healthy (green), Indexing (blue), Degraded (amber), Error (red)
- Click "View Details" → opens full KB management in drawer

---

## 7. Data Flow & Backend Integration

### Existing Endpoints (Ready to Use)
| Feature | Endpoint | Client Method |
|---------|----------|---------------|
| Multi-agent chat | `POST /agent/smart-ask` | `smart_ask()` |
| Document upload | `POST /upload/{project_id}` | `upload_file()` |
| List files | `GET /files/{project_id}` | `list_files()` |
| Summarize | `POST /ai/summarize` | `summarize()` |
| Generate exam | `POST /ai/exam/generate` | `generate_exam()` |
| Adaptive explain | `GET /adaptive/explain/{exam_id}` | `adaptive_explain()` |
| Study plan | `GET /adaptive/study-plan/{student_id}` | `adaptive_study_plan()` |
| Conversations | `GET/POST /chat/conversations` | `list_conversations()` |

### New Endpoints Needed
| Feature | Endpoint | Purpose |
|---------|----------|---------|
| Agent streaming | `POST /agent/smart-ask/stream` | SSE for live agent steps |
| Task status | `GET /tasks/{task_id}` | Poll OCR/embedding/indexing |
| KB health | `GET /projects/{id}/health` | Compact widget data |
| Pin document | `POST /projects/{id}/pin` | Pinned docs widget |

---

## 8. Implementation Roadmap

### Phase 1: Layout & Shell (Week 1)
- [ ] Create `AIWorkspaceLayout` (three-panel, responsive)
- [ ] Extract `SmartSidebar` with widget registry system
- [ ] Build `ConversationList` panel (left of chat)
- [ ] Wire routing: `/student/ai-workspace` (main), `/student/ai-workspace/:conversationId`

### Phase 2: Chat Workspace Core (Week 1-2)
- [ ] Refactor `AIChatComponent` → `ChatWorkspace` (conversation list + active chat)
- [ ] Implement composer with quick actions + context chips
- [ ] Add conversation persistence (list, create, delete, rename)
- [ ] Keyboard shortcuts: `⌘ N` new chat, `⌘ K` focus input, `⌘ /` tools drawer

### Phase 3: Smart Sidebar Widgets (Week 2)
- [ ] Current Context widget
- [ ] Attached Files widget (sync with composer)
- [ ] Knowledge Base Status widget (poll `/projects/{id}/health`)
- [ ] Agent Status widget (SSE integration)
- [ ] Running Tasks widget
- [ ] Current Course / Recent Conversations / Pinned Documents

### Phase 4: AI Tools Drawer (Week 2-3)
- [ ] Floating drawer component with tool registry
- [ ] Implement each tool as focused modal/panel:
  - Upload → existing upload flow
  - OCR → new endpoint integration
  - Chat with PDF → split view (PDF.js + chat)
  - Summarize → existing summarize endpoint
  - Quiz Generator → `generate_exam` with quiz config
  - Study Plan → existing adaptive endpoint
  - Flashcards / Assignment Helper / KB Search / Voice → new backend endpoints

### Phase 5: Polish & Premium Feel (Week 3)
- [ ] Micro-interactions: typing indicator, message animations, sidebar collapse
- [ ] Empty states with illustration + action
- [ ] Dark mode support (extend Tailwind config)
- [ ] Accessibility: ARIA labels, focus management, screen reader announcements
- [ ] Performance: Virtualized conversation list, lazy-load heavy tools

---

## 9. File Structure (New)

```
src/
├── layouts/
│   └── AIWorkspaceLayout.jsx          # Three-panel shell
├── pages/student/
│   └── AIWorkspacePage.jsx            # Main entry point
├── components/ai-workspace/
│   ├── ChatWorkspace.jsx              # Conversation list + active chat
│   ├── ConversationList.jsx           # Left panel
│   ├── ActiveConversation.jsx         # Message area
│   ├── Composer.jsx                   # Input + quick actions + context chips
│   ├── AIToolsDrawer.jsx              # Floating tools panel
│   ├── SmartSidebar.jsx               # Right panel widget container
│   ├── widgets/
│   │   ├── ContextWidget.jsx
│   │   ├── AttachedFilesWidget.jsx
│   │   ├── KnowledgeBaseWidget.jsx
│   │   ├── AgentStatusWidget.jsx
│   │   ├── RunningTasksWidget.jsx
│   │   ├── CurrentCourseWidget.jsx
│   │   ├── RecentConversationsWidget.jsx
│   │   └── PinnedDocumentsWidget.jsx
│   ├── tools/
│   │   ├── ToolRegistry.js
│   │   ├── ChatWithPDFPanel.jsx
│   │   ├── OCRPanel.jsx
│   │   ├── QuizGeneratorPanel.jsx
│   │   ├── StudyPlanPanel.jsx
│   │   ├── FlashcardsPanel.jsx
│   │   ├── AssignmentHelperPanel.jsx
│   │   ├── KBSearchPanel.jsx
│   │   └── VoiceAssistantPanel.jsx
│   └── hooks/
│       ├── useConversations.js
│       ├── useAgentStream.js
│       ├── useKBHealth.js
│       └── useRunningTasks.js
├── services/
│   └── aiWorkspace.service.js         # API calls for new endpoints
└── data/
    └── aiToolsRegistry.js             # Tool definitions
```

---

## 10. Design Tokens (Extend Tailwind)

```css
/* Add to index.css @theme */
--color-agent-search: #3b82f6;
--color-agent-read: #22c55e;
--color-agent-reason: #a855f7;
--color-agent-tool: #f97316;
--color-agent-done: #10b981;

--shadow-floating: 0 20px 60px rgba(56, 29, 109, 0.15), 0 8px 24px rgba(56, 29, 109, 0.08);
--sidebar-width: 320px;
--sidebar-collapsed: 72px;
--composer-height: 68px;
--header-height: 64px;
```

---

## 11. Keyboard Shortcuts (Power User)

| Shortcut | Action |
|----------|--------|
| `⌘ N` | New conversation |
| `⌘ K` | Focus composer / Command palette |
| `⌘ /` | Open AI Tools drawer |
| `⌘ ↑/⌘ ↓` | Navigate conversations |
| `⌘ Enter` | Send message |
| `⌘ Shift Enter` | New line in composer |
| `⌘ U` | Upload file |
| `⌘ O` | OCR tool |
| `⌘ P` | Chat with PDF |
| `⌘ S` | Summarize |
| `Esc` | Close drawer / modal / dismiss toasts |

---

## 12. Success Metrics (Product Quality)

| Metric | Target |
|--------|--------|
| Time to first message (cold) | < 2s |
| Agent step latency (SSE) | < 300ms per step |
| Sidebar widget load | < 500ms |
| Tools drawer open animation | 150ms |
| Conversation switch | < 100ms |
| Lighthouse Performance | ≥ 95 |
| Lighthouse Accessibility | 100 |

---

## 13. Backend Additions Required

### New Django Views (ai_integration/views.py)
```python
class AIProjectHealthView(APIView):
    """GET /api/v1/projects/{project_id}/health"""
    # Returns: { status, doc_count, token_count, last_updated, indexing_progress }

class AgentStreamView(APIView):
    """POST /api/v1/agent/smart-ask/stream"""
    # SSE endpoint yielding: { step, label, progress, metadata }

class TaskStatusView(APIView):
    """GET /api/v1/tasks/{task_id}"""
    # Returns: { type, status, progress, result, error }

class PinDocumentView(APIView):
    """POST /api/v1/projects/{project_id}/pin"""
    # Body: { file_id, pinned: true/false }
```

### AI Backend (FastAPI) — Streaming Support
- Modify `/agent/smart-ask` to support `stream=true` query param
- Yield Server-Sent Events for each reasoning step
- Expose task queue status for background jobs

---

## 14. Migration Strategy (Non-Breaking)

1. **Keep existing pages** (`/student/ai`, `/student/ai-summary`, etc.) functional
2. **Add new route** `/student/ai-workspace` as the premium entry point
3. **Reuse existing hooks/services** (`useAiChat`, `aiService`, `AIBackendClient`)
4. **Gradually migrate** — once workspace is stable, deprecate old pages

---

## 15. Visual Reference (Mental Model)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Satr Edu  ────────────────────────────────────────────  Ahmed ● Student  ▼  │
├─────────┬──────────────────────────────────────────────────────────┬────────┤
│  ☰      │  💬 Conversations                    Active Chat          │  📚    │
│  Dashboard│  ─────────────────────          ──────────────          │  KB    │
│  📖       │  💬 Gradient Descent Explained   ┌─────────────────┐    │  Healthy│
│  Courses  │     2 min ago                      │  How does       │    │  42 docs│
│  🔭       │  📄 PDF: Chapter 3 Analysis        │  backprop work? │    │  Updated│
│  Explorer │     1 hour ago                     │                 │    │  2h ago │
│  🤖       │  🧠 Study Plan: Final Exam         │  [Agent: Tutor] │    │  [Sync] │
│  AI Wksp ●│     3 hours ago                    │  🔍 Searching…  │    │         │
│  🧪       │  ─────────────────────             │  ████░░░░░░░░ 45%│    │  📎     │
│  Tools    │  [+ New Chat]                      │  📖 Reading…    │    │  Files  │
│  📝       │                                     │                 │    │  ────── │
│  Exams    │                                     │  Here's how:    │    │  📄 lec5│
│  📊       │                                     │  [code block]   │    │  📊 data│
│  Progress │                                     │                 │    │  🖼️ diag│
│  ─────────│  ───────────────────────────────── │  Sources: [×3]  │    │  [×]    │
│  ⚙️       │  [📎][📄][🖼️][🎤][🔍][⋯] Ask... ▶ │  Follow-ups:    │    │         │
│  👤       │                                     │  → Show math    │    │  ⚙️     │
│           │                                     │  → Visual proof │    │  Agent  │
└───────────┴─────────────────────────────────────┴─────────────────┴────────┘
```

---

*This specification transforms the current feature-scattered AI pages into a cohesive, premium AI Workspace that feels like a commercial product (Cursor/Notion AI/Linear) — not a university project.*