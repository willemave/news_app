
# Newsly iOS App Architecture

## Overview
Newsly is a SwiftUI iOS application that serves as a client for the FastAPI backend news aggregation service. The app allows users to browse, read, and manage their news content from various sources.

## iOS App Structure

### Main Entry Points
- `newslyApp.swift`: App entry point with @main decorator
- `ContentView.swift`: Root view container

### Architecture Pattern: MVVM

#### Models (`newsly/Models/`)
- `ContentListResponse.swift`: Response model for content list API
- `ContentSummary.swift`: Individual content item in list view
- `ContentDetail.swift`: Full content details model
- `ContentType.swift`: Enum for article/podcast types
- `ContentStatus.swift`: Processing status enum
- `StructuredSummary.swift`: Structured summary data model

#### ViewModels (`newsly/ViewModels/`)
- `ContentListViewModel.swift`: Manages content list state and operations
- `ContentDetailViewModel.swift`: Manages individual content detail state

#### Views (`newsly/Views/`)
- `ContentListView.swift`: Main list view displaying all content
- `ContentDetailView.swift`: Detail view for individual content items

##### Components (`newsly/Views/Components/`)
- `ContentCard.swift`: Individual content item card in list
- `ContentTypeBadge.swift`: Visual badge for content type
- `FilterBar.swift`: Filter controls for content type and date
- `FilterSheet.swift`: Expandable filter options sheet
- `LoadingView.swift`: Loading state indicator
- `ErrorView.swift`: Error state display
- `StructuredSummaryView.swift`: Formatted summary display

#### Services (`newsly/Services/`)
- `APIClient.swift`: Network layer with async/await
- `APIEndpoints.swift`: API endpoint definitions
- `ContentService.swift`: Content-specific API operations

### API Integration

#### Backend API Endpoints (FastAPI)
The iOS app connects to the Python FastAPI backend at `http://localhost:8000`:

##### Content Endpoints (`/api/content/`)
- `GET /api/content/`: List all content with filters
  - Query params: `content_type`, `date`, `read_filter`
  - Returns: ContentListResponse with summaries
- `GET /api/content/{id}`: Get content details
- `POST /api/content/{id}/mark-read`: Mark as read
- `DELETE /api/content/{id}/mark-unread`: Mark as unread  
- `POST /api/content/bulk-mark-read`: Bulk mark multiple items

#### Data Flow
1. User interaction → View
2. View → ViewModel (via @StateObject/@ObservedObject)
3. ViewModel → ContentService
4. ContentService → APIClient
5. APIClient → FastAPI Backend
6. Response flows back through the same chain

### Key Features
- **Content Browsing**: List view with cards showing summaries
- **Filtering**: By content type (article/podcast) and date
- **Read Status**: Track read/unread items with visual indicators
- **Pull to Refresh**: SwiftUI native refresh support
- **Error Handling**: Graceful error states with retry options
- **Responsive Design**: Adapts to different iOS device sizes

### Build Configuration
- `newsly.xcodeproj`: Xcode project file
- `newsly.xcconfig`: Build configuration settings
- Target: iOS 15.0+
- Swift 5.5+

### Testing
- `newslyTests/`: Unit tests
- `newslyUITests/`: UI automation tests

---
# Original Python/FastAPI Guidelines

#### 1  Python / FastAPI Coding Rules
* **Functions over classes**.
* **Full type hints**; validate with **Pydantic v2** models. Use `typing` for complex types.
* **RORO** pattern (receive object, return object).
* `lower_snake_case` for files/dirs; verbs in variables (`is_valid`, `has_permission`).
* Guard-clause error handling; early returns over nested `else`.
* Raise `HTTPException` for expected errors; log + wrap unexpected ones.
* **Docstrings**: Use Google-style for all public functions/classes.
* **Constants**: Define in `app/constants.py` or module-level UPPER_CASE.
* Folder layout:
  app/
    routers/      # route groups
    models/       # Pydantic + DB models
    schemas/      # request/response schemas
    services/     # business logic layer
    repositories/ # data access layer
    utils/        # pure helpers
    types/        # shared type aliases
    middleware/   # custom middleware
    dependencies/ # FastAPI dependencies
    exceptions/   # custom exceptions
    static/
    tests/        # pytest test files
  logs/           # holds all log files
  scripts/.       # holds all scripts     
---
#### 2  FastAPI Best Practices
* Use **lifespan** context, not `startup/shutdown` events.
* Inject DB/session with dependencies; use `Annotated` for cleaner signatures.
* Middleware order matters: logging → tracing → CORS → error capture.

---
#### 3  Code Quality & Safety
* **No hardcoded secrets**; use `pydantic-settings` for config management.
* **Input validation**: Always validate at boundaries (API, external services).
* **SQL injection prevention**: Use parameterized queries, never f-strings.
* **Graceful degradation**: Circuit breakers for external services.
* **Error context**: Include request IDs, user context in error logs.

---
#### 4  Testing Requirements
* **Write tests for all new functionality** in `app/tests/` using idiomatic pytest.
* Test structure mirrors app structure: `tests/routers/`, `tests/services/`, etc.
* Test file naming: `test_<module_name>.py`.
* **Test categories**:
  - Unit tests: isolated function/class testing
  - Integration tests: API endpoints with test DB
  - Contract tests: external service interactions
* Use pytest fixtures for setup/teardown;
* **TestClient** from FastAPI for endpoint testing.
* Mock external dependencies with `pytest-mock` or `unittest.mock`.
* **Run tests after implementation**: 
  pytest app/tests/ -v  # verbose output

* **Test data**: Use factories or fixtures, never production data.
---
#### 5  Performance & Monitoring
* **Database queries**: Use `select_related`/`prefetch_related` to avoid N+1.
* **Connection pooling**: Configure appropriate pool sizes for DB/Redis.
* **Pagination**: Always paginate list endpoints; use cursor-based for large datasets.

---
#### 6  Dependencies
* **Core**: fastapi, pydantic[email], pydantic-settings, python-multipart
* **Database**: sqlalchemy>=2.0, alembic
* **Testing**: pytest, pytest-cov, httpx, pytest-mock
* **Utils**: python-dateutil
* **External**: httpx (HTTP), google-genai (not google-generativeai)
* Package with **uv**:
  uv add <pkg>
  uv add --dev pytest httpx pytest-mock pytest-cov
  source .venv/bin/activate

---
#### 7  Development Workflow
* **Pre-commit hooks**: `ruff` for linting, `black` for formatting, `mypy` for types.
* **Environment management**: `.env.example` template; never commit `.env`. Use app/core/settings.py and Pydantic to store settings for the app. 
* **Database migrations**: Alembic with descriptive revision messages.
* **OpenAPI**: Customize with tags, descriptions; generate client SDKs.
* **UI**: We use jinja and basic templates to render our html pages, we're not a javascript/react app. 
* **Error responses**: Consistent format with error codes, messages, details.
* We use tailwindcss, you write tailwind css to ./static/css/styles.css and then run `npx @tailwindcss/cli -i ./static/css/styles.css -o ./static/css/app.css` to build the ./static/css/styles.css
---
#### 8  Memory-Bank Workflow (Stateless Agent)
1. **At session start** read:
   `ai-memory/README.md`, `ai-memory/TASKS.md`.
2. **Treat `README.md` as canonical context**.
3. **Maintain `TASKS.md`**:
   * Fine-grained tasks with `- [ ]` / `- [x]`.
   * Include test writing/running as explicit tasks.
   * Group by feature/module for clarity.
   * Last task in every phase → record key learnings before reset.
4. **Propose updates** to memory files whenever you add patterns, finish major work, or clarify requirements.
5. **Missing folder?** Create `ai-memory/`, stub the three files, notify user.
---
#### 9  Memory-Bank File Roles
| File          | Purpose (keep Markdown headers)                                        |
| ------------- | ---------------------------------------------------------------------- |
| **README.md** | Product context, architecture, tech stack, key files, API contracts    |
| **TASKS.md**  | Living checklist (phases, tasks, reference files, learnings, new deps) |
---
#### 10  Updating the Memory Bank
- You MUST review ALL core memory bank files (ai-memory/README.md, ai-memory/TASKS.md) for necessary updates.
- Process:
  1. Execute a suitable command to get a project file listing:
     ```bash
     find . -maxdepth 4 -type f -name "*.py" -o -name "*.md" -o -name "*.yaml" -o -name "*.toml" | grep -v -E "(\.venv|__pycache__|\.git|\.pytest_cache|\.vscode|node_modules|logs|.*egg-info|\.ruff_cache|\.benchmarks|data)" | sort
     ```
  2. Identify key files and folders that need to be explored and add them to the 'Key Repository Folders and Files' section of ai-memory/README.md.
  3. Based on the file listing and recent project activity, identify other key project files (e.g., main application entry points, core modules, critical configuration files) that might require reading or re-reading to ensure ai-memory/README.md (especially 'System Patterns' and 'Tech Context') is comprehensive and up-to-date. Create a ai-memory/TASKS.md file with a list of files and folders to traverse. Include frequent tasks to "update the ai-memory/README.md" as part of the tasks list. Balance reading a group of 3 or 4 files before updating the ai-memory/README.md but waiting too long for updates.
  4. Execute the ai-memory/TASKS.md and check off tasks that are completed. If you identify new key files or folders that need to be read during execution, update the ai-memory/TASKS.md file.
  5. Record architectural decisions, API changes, and performance optimizations in README.md.
  6. Ask the user if there are other folders or files that need to be explored.
---
#### Tools
1. Use `uv add` to add python packages
2. Use `alembic` for database migrations
3. Use `ruff check` and `ruff format` for code quality
4. Use `mypy` for type checking
5. Make sure to ALWAYS run activate before the command. 

**Keep all replies short, technical, and complete.**
```