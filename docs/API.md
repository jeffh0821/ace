# ACE API Reference

**ACE — Assistant for Connector Engineering**
Version: 0.1.0

Base URL: `http://localhost:8000`

---

## Table of Contents

- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Health](#health)
  - [Auth](#auth)
  - [Users](#users)
  - [Documents](#documents)
  - [Questions](#questions)
  - [Escalations](#escalations)
  - [Feedback](#feedback)
  - [Analytics](#analytics)
  - [Config](#config)

---

## Authentication

ACE uses **cookie-based JWT authentication**. After a successful login, the server
sets an `access_token` httpOnly cookie (SameSite=lax, max-age=8 hours). All
subsequent requests must include this cookie.

### Roles

| Role       | Description                                        |
|------------|----------------------------------------------------|
| `sales`    | Can ask questions, view own history, give feedback  |
| `engineer` | Can upload documents, respond to escalations        |
| `admin`    | Full access — user management, analytics, config    |

---

## Endpoints

---

### Health

#### `GET /health`

Health check endpoint. No authentication required.

**Response** `200 OK`

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

### Auth

All auth endpoints are prefixed with `/api/auth`.

---

#### `POST /api/auth/login`

Authenticate a user and receive a session cookie.

**Auth required:** None

**Request Body:**

| Field      | Type   | Required | Description          |
|------------|--------|----------|----------------------|
| `username` | string | Yes      | The user's username  |
| `password` | string | Yes      | The user's password  |

```json
{
  "username": "admin",
  "password": "changeme"
}
```

**Response** `200 OK`

Sets an `access_token` httpOnly cookie on the response.

```json
{
  "message": "Login successful",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "display_name": "Admin User",
    "role": "admin"
  }
}
```

**Error Responses:**

| Status | Detail                 | Condition                              |
|--------|------------------------|----------------------------------------|
| `401`  | Invalid credentials    | Wrong username or password             |
| `403`  | Account disabled       | User account has been deactivated      |
| `422`  | Validation error       | Missing or malformed request body      |

---

#### `POST /api/auth/logout`

Clear the session cookie and log out.

**Auth required:** None (cookie is cleared regardless)

**Request Body:** None

**Response** `200 OK`

Deletes the `access_token` cookie.

```json
{
  "message": "Logged out"
}
```

---

#### `GET /api/auth/me`

Get the currently authenticated user's profile.

**Auth required:** Any authenticated user

**Response** `200 OK`

```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "display_name": "Admin User",
  "role": "admin"
}
```

**Response Schema — `UserResponse`:**

| Field          | Type   | Description                              |
|----------------|--------|------------------------------------------|
| `id`           | int    | User ID                                  |
| `username`     | string | Unique username                          |
| `email`        | string | Email address                            |
| `display_name` | string | Display name                             |
| `role`         | string | One of: `sales`, `engineer`, `admin`     |

**Error Responses:**

| Status | Detail           | Condition                          |
|--------|------------------|------------------------------------|
| `401`  | Not authenticated | Missing or invalid access_token cookie |

---

### Users

All user endpoints are prefixed with `/api/users`. **Admin only.**

---

#### `POST /api/users/`

Create a new user account.

**Auth required:** `admin`

**Request Body:**

| Field          | Type   | Required | Description                              |
|----------------|--------|----------|------------------------------------------|
| `username`     | string | Yes      | Unique username                          |
| `email`        | string | Yes      | Unique email address                     |
| `display_name` | string | Yes      | User's display name                      |
| `password`     | string | Yes      | Plain-text password (hashed on server)   |
| `role`         | string | Yes      | One of: `sales`, `engineer`, `admin`     |

```json
{
  "username": "jdoe",
  "email": "jdoe@example.com",
  "display_name": "Jane Doe",
  "password": "securePass123",
  "role": "sales"
}
```

**Response** `201 Created`

```json
{
  "id": 2,
  "username": "jdoe",
  "email": "jdoe@example.com",
  "display_name": "Jane Doe",
  "role": "sales",
  "is_active": true
}
```

**Response Schema — `UserResponse`:**

| Field          | Type    | Description                              |
|----------------|---------|------------------------------------------|
| `id`           | int     | User ID                                  |
| `username`     | string  | Unique username                          |
| `email`        | string  | Email address                            |
| `display_name` | string  | Display name                             |
| `role`         | string  | One of: `sales`, `engineer`, `admin`     |
| `is_active`    | boolean | Whether the account is active            |

**Error Responses:**

| Status | Detail                              | Condition                            |
|--------|-------------------------------------|--------------------------------------|
| `400`  | Username or email already exists    | Duplicate username or email          |
| `401`  | Not authenticated                   | Missing or invalid cookie            |
| `403`  | Forbidden                           | Non-admin user                       |
| `422`  | Validation error                    | Missing or malformed request body    |

---

#### `GET /api/users/`

List all user accounts.

**Auth required:** `admin`

**Response** `200 OK`

Returns a JSON array of `UserResponse` objects, ordered by creation date (newest first).

```json
[
  {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "display_name": "Admin User",
    "role": "admin",
    "is_active": true
  },
  {
    "id": 2,
    "username": "jdoe",
    "email": "jdoe@example.com",
    "display_name": "Jane Doe",
    "role": "sales",
    "is_active": true
  }
]
```

**Error Responses:**

| Status | Detail            | Condition                            |
|--------|-------------------|--------------------------------------|
| `401`  | Not authenticated | Missing or invalid cookie            |
| `403`  | Forbidden         | Non-admin user                       |

---

#### `PATCH /api/users/{user_id}/deactivate`

Deactivate a user account. Sets `is_active` to `false`.

**Auth required:** `admin`

**Path Parameters:**

| Parameter | Type | Description           |
|-----------|------|-----------------------|
| `user_id` | int  | ID of user to deactivate |

**Request Body:** None

**Response** `200 OK`

```json
{
  "message": "User jdoe deactivated"
}
```

**Error Responses:**

| Status | Detail            | Condition                            |
|--------|-------------------|--------------------------------------|
| `401`  | Not authenticated | Missing or invalid cookie            |
| `403`  | Forbidden         | Non-admin user                       |
| `404`  | User not found    | No user with that ID exists          |

---

### Documents

All document endpoints are prefixed with `/api/documents`.

---

#### `POST /api/documents/`

Upload a PDF document for ingestion into the knowledge base. The file is saved
to disk and background processing is triggered (text extraction, chunking,
embedding, and indexing into ChromaDB).

**Auth required:** `engineer` or `admin`

**Request:** `multipart/form-data`

| Field  | Type          | Required | Description                        |
|--------|---------------|----------|------------------------------------|
| `file` | UploadFile    | Yes      | PDF file (must have `.pdf` extension) |

**Example (curl):**

```bash
curl -X POST http://localhost:8000/api/documents/ \
  -b "access_token=<token>" \
  -F "file=@connector_spec.pdf"
```

**Response** `201 Created`

```json
{
  "id": 1,
  "title": "connector_spec",
  "filename": "connector_spec.pdf",
  "file_size_bytes": 245760,
  "page_count": null,
  "chunk_count": 0,
  "status": "pending",
  "error_message": null,
  "uploaded_at": "2025-01-15T10:30:00",
  "processed_at": null
}
```

**Response Schema — `DocumentResponse`:**

| Field              | Type         | Description                                         |
|--------------------|--------------|-----------------------------------------------------|
| `id`               | int          | Document ID                                         |
| `title`            | string       | Document title (derived from filename without ext)   |
| `filename`         | string       | Original filename                                   |
| `file_size_bytes`  | int          | File size in bytes                                  |
| `page_count`       | int or null  | Number of pages (set after processing)              |
| `chunk_count`      | int          | Number of text chunks (set after processing)        |
| `status`           | string       | One of: `pending`, `processing`, `completed`, `failed` |
| `error_message`    | string or null | Error details if processing failed                |
| `uploaded_at`      | string       | ISO 8601 timestamp of upload                        |
| `processed_at`     | string or null | ISO 8601 timestamp when processing completed      |

**Error Responses:**

| Status | Detail                              | Condition                                |
|--------|-------------------------------------|------------------------------------------|
| `400`  | Only PDF files are supported        | Non-PDF file uploaded                    |
| `400`  | File exceeds {N}MB limit            | File size exceeds configured max         |
| `401`  | Not authenticated                   | Missing or invalid cookie                |
| `403`  | Forbidden                           | User is not engineer or admin            |

**Notes:**
- Processing happens asynchronously in the background. Poll `GET /api/documents/{id}` to check the `status` field.
- The `status` field transitions: `pending` → `processing` → `completed` (or `failed`).

---

#### `GET /api/documents/`

List all uploaded documents.

**Auth required:** Any authenticated user

**Response** `200 OK`

Returns a JSON array of `DocumentResponse` objects, ordered by upload date (newest first).

```json
[
  {
    "id": 1,
    "title": "connector_spec",
    "filename": "connector_spec.pdf",
    "file_size_bytes": 245760,
    "page_count": 42,
    "chunk_count": 128,
    "status": "completed",
    "error_message": null,
    "uploaded_at": "2025-01-15T10:30:00",
    "processed_at": "2025-01-15T10:30:45"
  }
]
```

**Error Responses:**

| Status | Detail            | Condition                  |
|--------|-------------------|----------------------------|
| `401`  | Not authenticated | Missing or invalid cookie  |

---

#### `GET /api/documents/{document_id}`

Get a single document by ID.

**Auth required:** Any authenticated user

**Path Parameters:**

| Parameter     | Type | Description       |
|---------------|------|-------------------|
| `document_id` | int  | ID of the document |

**Response** `200 OK`

Returns a single `DocumentResponse` object.

```json
{
  "id": 1,
  "title": "connector_spec",
  "filename": "connector_spec.pdf",
  "file_size_bytes": 245760,
  "page_count": 42,
  "chunk_count": 128,
  "status": "completed",
  "error_message": null,
  "uploaded_at": "2025-01-15T10:30:00",
  "processed_at": "2025-01-15T10:30:45"
}
```

**Error Responses:**

| Status | Detail             | Condition                    |
|--------|--------------------|------------------------------|
| `401`  | Not authenticated  | Missing or invalid cookie    |
| `404`  | Document not found | No document with that ID     |

---

#### `DELETE /api/documents/{document_id}`

Delete a document, removing it from the database, ChromaDB vector store, and disk.

**Auth required:** `admin`

**Path Parameters:**

| Parameter     | Type | Description       |
|---------------|------|-------------------|
| `document_id` | int  | ID of the document |

**Response** `204 No Content`

No response body.

**Error Responses:**

| Status | Detail             | Condition                    |
|--------|--------------------|------------------------------|
| `401`  | Not authenticated  | Missing or invalid cookie    |
| `403`  | Forbidden          | Non-admin user               |
| `404`  | Document not found | No document with that ID     |

**Notes:**
- This removes the document record from the SQL database, deletes all associated chunk embeddings from ChromaDB (filtered by `document_id`), and removes the PDF file from disk.

---

### Questions

All question endpoints are prefixed with `/api/questions`.

---

#### `POST /api/questions/`

Submit a question to the ACE system. The system will:
1. Retrieve relevant document chunks from ChromaDB
2. Generate an answer via the configured LLM
3. Compute a confidence score (combining retrieval similarity and LLM confidence)
4. If confidence is above threshold → return the answer directly
5. If confidence is below threshold → escalate to an engineer

**Auth required:** Any authenticated user

**Request Body:**

| Field      | Type   | Required | Description                |
|------------|--------|----------|----------------------------|
| `question` | string | Yes      | The question text (non-empty) |

```json
{
  "question": "What is the maximum operating temperature for the X200 connector?"
}
```

**Response** `200 OK` — Answered directly (confidence above threshold):

```json
{
  "id": 5,
  "question_text": "What is the maximum operating temperature for the X200 connector?",
  "answer_text": "The maximum operating temperature for the X200 connector is 125°C as specified in Section 3.2 of the datasheet.",
  "citations": [
    {
      "document_title": "X200 Datasheet",
      "page_number": 8,
      "excerpt": "Operating temperature range: -40°C to +125°C"
    }
  ],
  "confidence_score": 0.87,
  "status": "answered",
  "asked_at": "2025-01-15T14:22:00",
  "feedback_positive": null,
  "engineer_response": null
}
```

**Response** `200 OK` — Escalated (confidence below threshold):

```json
{
  "id": 6,
  "question_text": "Can the X200 be used in deep-sea applications?",
  "answer_text": null,
  "citations": null,
  "confidence_score": 0.32,
  "status": "escalated",
  "asked_at": "2025-01-15T14:25:00",
  "feedback_positive": null,
  "engineer_response": null
}
```

**Response Schema — `QuestionResponse`:**

| Field               | Type              | Description                                           |
|---------------------|-------------------|-------------------------------------------------------|
| `id`                | int               | Question ID                                           |
| `question_text`     | string            | The original question                                 |
| `answer_text`       | string or null    | Generated answer (null if escalated)                  |
| `citations`         | array or null     | List of citation objects (null if escalated)          |
| `confidence_score`  | float or null     | Combined confidence score (0.0–1.0)                   |
| `status`            | string            | One of: `answered`, `escalated`, `resolved`           |
| `asked_at`          | string            | ISO 8601 timestamp                                    |
| `feedback_positive` | boolean or null   | User feedback (null if no feedback given)             |
| `engineer_response` | string or null    | Engineer's response (only for resolved escalations)   |

**Citation Object — `CitationOut`:**

| Field            | Type   | Description                          |
|------------------|--------|--------------------------------------|
| `document_title` | string | Title of the source document         |
| `page_number`    | int    | Page number in the source document   |
| `excerpt`        | string | Relevant text excerpt                |

**Error Responses:**

| Status | Detail                  | Condition                    |
|--------|-------------------------|------------------------------|
| `400`  | Question cannot be empty | Empty or whitespace-only question |
| `401`  | Not authenticated       | Missing or invalid cookie    |
| `422`  | Validation error        | Missing request body fields  |

**Notes:**
- When a question is escalated, an `Escalation` record is automatically created with the retrieved context chunks for engineer review.
- The `status` field values: `answered` = answered directly by the system, `escalated` = awaiting engineer response, `resolved` = engineer has responded to the escalation.

---

#### `GET /api/questions/`

List question history. Sales users see only their own questions; engineers and
admins see all questions.

**Auth required:** Any authenticated user

**Query Parameters:** None

**Response** `200 OK`

Returns a JSON array of `QuestionResponse` objects, ordered by ask date (newest first).

```json
[
  {
    "id": 5,
    "question_text": "What is the maximum operating temperature for the X200 connector?",
    "answer_text": "The maximum operating temperature is 125°C.",
    "citations": [
      {
        "document_title": "X200 Datasheet",
        "page_number": 8,
        "excerpt": "Operating temperature range: -40°C to +125°C"
      }
    ],
    "confidence_score": 0.87,
    "status": "answered",
    "asked_at": "2025-01-15T14:22:00",
    "feedback_positive": true,
    "engineer_response": null
  },
  {
    "id": 6,
    "question_text": "Can the X200 be used in deep-sea applications?",
    "answer_text": "Yes, the X200 is rated for deep-sea use up to 3000m depth.",
    "citations": null,
    "confidence_score": 0.32,
    "status": "resolved",
    "asked_at": "2025-01-15T14:25:00",
    "feedback_positive": null,
    "engineer_response": "Yes, the X200 is rated for deep-sea use up to 3000m depth."
  }
]
```

**Error Responses:**

| Status | Detail            | Condition                  |
|--------|-------------------|----------------------------|
| `401`  | Not authenticated | Missing or invalid cookie  |

**Notes:**
- For questions with `status: "resolved"`, the `engineer_response` field contains the engineer's answer from the resolved escalation.
- The `answer_text` for resolved escalations is updated to the engineer's response.

---

### Escalations

All escalation endpoints are prefixed with `/api/escalations`. **Engineer or admin only.**

---

#### `GET /api/escalations/`

List escalated questions, optionally filtered by status.

**Auth required:** `engineer` or `admin`

**Query Parameters:**

| Parameter       | Type   | Required | Description                               |
|-----------------|--------|----------|-------------------------------------------|
| `status_filter` | string | No       | Filter by status: `pending` or `resolved` |

**Example:** `GET /api/escalations/?status_filter=pending`

**Response** `200 OK`

```json
[
  {
    "id": 1,
    "question_id": 6,
    "question_text": "Can the X200 be used in deep-sea applications?",
    "retrieved_context": [
      {
        "text": "The X200 series connectors feature IP68 rating...",
        "document_title": "X200 Datasheet",
        "page_number": 12,
        "similarity": 0.72
      }
    ],
    "asked_by_name": "Jane Doe",
    "status": "pending",
    "engineer_response": null,
    "created_at": "2025-01-15T14:25:00",
    "resolved_at": null
  }
]
```

**Response Schema — `EscalationResponse`:**

| Field               | Type              | Description                                            |
|---------------------|-------------------|--------------------------------------------------------|
| `id`                | int               | Escalation ID                                          |
| `question_id`       | int               | ID of the associated question                          |
| `question_text`     | string            | The original question text                             |
| `retrieved_context` | array or null     | List of context chunk objects retrieved during Q&A     |
| `asked_by_name`     | string            | Display name of the user who asked the question        |
| `status`            | string            | One of: `pending`, `resolved`                          |
| `engineer_response` | string or null    | The engineer's response text (null if pending)         |
| `created_at`        | string            | ISO 8601 timestamp of escalation creation              |
| `resolved_at`       | string or null    | ISO 8601 timestamp of resolution (null if pending)     |

**Retrieved Context Object:**

| Field            | Type   | Description                                      |
|------------------|--------|--------------------------------------------------|
| `text`           | string | The chunk text                                   |
| `document_title` | string | Source document title                             |
| `page_number`    | int    | Page number in the source document               |
| `similarity`     | float  | Cosine similarity score from vector search        |

**Error Responses:**

| Status | Detail            | Condition                          |
|--------|-------------------|------------------------------------|
| `401`  | Not authenticated | Missing or invalid cookie          |
| `403`  | Forbidden         | User is not engineer or admin      |

---

#### `POST /api/escalations/{escalation_id}/respond`

Submit an engineer response to an escalated question. This action:
1. Records the engineer's response on the escalation
2. Updates the escalation status to `resolved`
3. Updates the associated question's `answer_text` and status to `resolved`
4. Embeds the Q&A pair and adds it to ChromaDB for future retrieval (learning loop)

**Auth required:** `engineer` or `admin`

**Path Parameters:**

| Parameter       | Type | Description              |
|-----------------|------|--------------------------|
| `escalation_id` | int  | ID of the escalation     |

**Request Body:**

| Field      | Type   | Required | Description                  |
|------------|--------|----------|------------------------------|
| `response` | string | Yes      | The engineer's answer text   |

```json
{
  "response": "Yes, the X200 is rated for deep-sea use up to 3000m depth per MIL-STD-810G testing."
}
```

**Response** `200 OK`

```json
{
  "message": "Response submitted and added to knowledgebase",
  "escalation_id": 1
}
```

**Error Responses:**

| Status | Detail                          | Condition                            |
|--------|---------------------------------|--------------------------------------|
| `400`  | Escalation already resolved     | Attempting to respond twice          |
| `401`  | Not authenticated               | Missing or invalid cookie            |
| `403`  | Forbidden                       | User is not engineer or admin        |
| `404`  | Escalation not found            | No escalation with that ID           |
| `404`  | Associated question not found   | Orphaned escalation (data integrity) |
| `422`  | Validation error                | Missing request body fields          |

**Notes:**
- The engineer's response is embedded as a Q&A pair (`Q: {question}\nA: {response}`) and stored in ChromaDB with metadata `source: "escalation_response"`. This enables the system to learn from engineer responses and answer similar questions directly in the future.
- An escalation can only be responded to once. Subsequent attempts return a `400` error.

---

### Feedback

All feedback endpoints are prefixed with `/api/feedback`.

---

#### `POST /api/feedback/`

Submit thumbs-up or thumbs-down feedback on a question's answer.

**Auth required:** Any authenticated user (can only provide feedback on their own questions)

**Request Body:**

| Field        | Type    | Required | Description                            |
|--------------|---------|----------|----------------------------------------|
| `question_id`| int     | Yes      | ID of the question to give feedback on |
| `positive`   | boolean | Yes      | `true` for thumbs-up, `false` for thumbs-down |

```json
{
  "question_id": 5,
  "positive": true
}
```

**Response** `200 OK`

```json
{
  "message": "Feedback recorded",
  "question_id": 5,
  "positive": true
}
```

**Error Responses:**

| Status | Detail                                          | Condition                              |
|--------|-------------------------------------------------|----------------------------------------|
| `401`  | Not authenticated                               | Missing or invalid cookie              |
| `403`  | Can only provide feedback on your own questions  | Feedback on another user's question    |
| `404`  | Question not found                              | No question with that ID               |
| `422`  | Validation error                                | Missing or malformed request body      |

---

### Analytics

All analytics endpoints are prefixed with `/api/analytics`. **Admin only.**

---

#### `GET /api/analytics/`

Get aggregated platform metrics and statistics.

**Auth required:** `admin`

**Response** `200 OK`

```json
{
  "total_questions": 150,
  "answered_directly": 120,
  "escalated": 30,
  "pending_escalations": 5,
  "escalation_rate": 0.200,
  "positive_feedback": 95,
  "negative_feedback": 10,
  "feedback_satisfaction_rate": 0.905,
  "average_confidence": 0.742,
  "document_count": 12,
  "user_count": 8
}
```

**Response Schema:**

| Field                        | Type  | Description                                                       |
|------------------------------|-------|-------------------------------------------------------------------|
| `total_questions`            | int   | Total number of questions asked                                   |
| `answered_directly`          | int   | Questions answered directly by the system (status=`answered`)     |
| `escalated`                  | int   | Questions that were escalated or resolved (status=`escalated` or `resolved`) |
| `pending_escalations`        | int   | Escalations still awaiting engineer response                     |
| `escalation_rate`            | float | Ratio of escalated questions to total questions                  |
| `positive_feedback`          | int   | Number of thumbs-up feedback entries                             |
| `negative_feedback`          | int   | Number of thumbs-down feedback entries                           |
| `feedback_satisfaction_rate` | float | Ratio of positive to total feedback                              |
| `average_confidence`         | float | Average confidence score across all questions                    |
| `document_count`             | int   | Total number of uploaded documents                               |
| `user_count`                 | int   | Total number of registered users                                 |

**Error Responses:**

| Status | Detail            | Condition                  |
|--------|-------------------|----------------------------|
| `401`  | Not authenticated | Missing or invalid cookie  |
| `403`  | Forbidden         | Non-admin user             |

**Notes:**
- `escalation_rate` is calculated as `escalated / max(total_questions, 1)`.
- `feedback_satisfaction_rate` is calculated as `positive_feedback / max(positive_feedback + negative_feedback, 1)`.
- `average_confidence` is rounded to 3 decimal places.

---

### Config

All config endpoints are prefixed with `/api/config`. **Admin only.**

---

#### `GET /api/config/`

Get the current runtime configuration.

**Auth required:** `admin`

**Response** `200 OK`

```json
{
  "llm_model": "gpt-4o-mini",
  "confidence_threshold": 0.6,
  "retrieval_top_k": 5,
  "embedding_model": "all-MiniLM-L6-v2"
}
```

**Response Schema — `ConfigResponse`:**

| Field                  | Type   | Description                                       |
|------------------------|--------|---------------------------------------------------|
| `llm_model`            | string | Currently configured LLM model name               |
| `confidence_threshold` | float  | Minimum confidence score to answer directly (0–1)  |
| `retrieval_top_k`      | int    | Number of chunks retrieved from vector search      |
| `embedding_model`      | string | Sentence-transformer model used for embeddings     |

**Error Responses:**

| Status | Detail            | Condition                  |
|--------|-------------------|----------------------------|
| `401`  | Not authenticated | Missing or invalid cookie  |
| `403`  | Forbidden         | Non-admin user             |

---

#### `PATCH /api/config/`

Update runtime configuration. Only the provided fields are updated; omitted
fields remain unchanged.

**Auth required:** `admin`

**Request Body:**

| Field                  | Type   | Required | Description                                       |
|------------------------|--------|----------|---------------------------------------------------|
| `llm_model`            | string | No       | LLM model name to use                             |
| `confidence_threshold` | float  | No       | Minimum confidence score threshold (0–1)           |
| `retrieval_top_k`      | int    | No       | Number of chunks to retrieve per query             |

```json
{
  "confidence_threshold": 0.7,
  "retrieval_top_k": 10
}
```

**Response** `200 OK`

```json
{
  "message": "Config updated",
  "changes": {
    "confidence_threshold": 0.7,
    "retrieval_top_k": 10
  }
}
```

**Error Responses:**

| Status | Detail            | Condition                    |
|--------|-------------------|------------------------------|
| `401`  | Not authenticated | Missing or invalid cookie    |
| `403`  | Forbidden         | Non-admin user               |
| `422`  | Validation error  | Invalid field types           |

**Notes:**
- Changes are applied in-memory to the running server instance. They do not persist across server restarts.
- The `embedding_model` is read-only and cannot be changed at runtime.
- The `changes` object in the response only includes fields that were actually updated.

---

## Common Error Format

All error responses follow FastAPI's standard error format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Validation errors (422) include additional detail:

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Enumerations Reference

### UserRole

| Value      | Description                         |
|------------|-------------------------------------|
| `sales`    | Sales team member                   |
| `engineer` | Connector engineer                  |
| `admin`    | System administrator                |

### ProcessingStatus (Documents)

| Value        | Description                          |
|--------------|--------------------------------------|
| `pending`    | Upload received, processing not started |
| `processing` | Text extraction and embedding in progress |
| `completed`  | Successfully processed and indexed   |
| `failed`     | Processing failed (see `error_message`) |

### QuestionStatus

| Value      | Description                                     |
|------------|-------------------------------------------------|
| `answered` | Answered directly by the system with high confidence |
| `escalated`| Below confidence threshold, awaiting engineer   |
| `resolved` | Engineer has provided a response                |

### EscalationStatus

| Value      | Description                          |
|------------|--------------------------------------|
| `pending`  | Awaiting engineer response           |
| `resolved` | Engineer has responded               |
