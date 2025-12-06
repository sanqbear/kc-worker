# Integration Example: Go API to Celery Worker

This document shows how to integrate the Go API server with the Celery worker for asynchronous AI task processing.

## Architecture Flow

```
┌─────────────┐                     ┌─────────────┐
│   Client    │                     │   Go API    │
│  (Browser)  │────HTTP Request────▶│   Server    │
└─────────────┘                     └──────┬──────┘
                                           │
                                           │ Submit Task
                                           │ (Redis)
                                           ▼
                                    ┌──────────────┐
                                    │    Redis     │
                                    │   (Broker)   │
                                    └──────┬───────┘
                                           │
                                           │ Consume
                                           ▼
                                    ┌──────────────┐
                                    │    Celery    │
                                    │    Worker    │
                                    └──────┬───────┘
                                           │
                                           │ HTTP POST
                                           ▼
                                    ┌──────────────┐
                                    │  LLM Server  │
                                    │(llama.cpp/   │
                                    │    vLLM)     │
                                    └──────────────┘
```

## Go Integration Code

### 1. Install Go Redis Client

```bash
cd server
go get github.com/redis/go-redis/v9
```

### 2. Create Celery Client Package

Create `server/internal/celery/client.go`:

```go
package celery

import (
    "context"
    "encoding/json"
    "fmt"
    "time"

    "github.com/google/uuid"
    "github.com/redis/go-redis/v9"
)

// CeleryClient handles task submission to Celery workers
type CeleryClient struct {
    rdb *redis.Client
}

// NewCeleryClient creates a new Celery client
func NewCeleryClient(redisURL string) (*CeleryClient, error) {
    opts, err := redis.ParseURL(redisURL)
    if err != nil {
        return nil, fmt.Errorf("invalid redis URL: %w", err)
    }

    rdb := redis.NewClient(opts)

    // Test connection
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    if err := rdb.Ping(ctx).Err(); err != nil {
        return nil, fmt.Errorf("redis connection failed: %w", err)
    }

    return &CeleryClient{rdb: rdb}, nil
}

// Close closes the Redis connection
func (c *CeleryClient) Close() error {
    return c.rdb.Close()
}

// CeleryTask represents a Celery task message
type CeleryTask struct {
    Task     string                 `json:"task"`
    ID       string                 `json:"id"`
    Args     []interface{}          `json:"args"`
    Kwargs   map[string]interface{} `json:"kwargs"`
    Retries  int                    `json:"retries"`
    ETA      *time.Time             `json:"eta,omitempty"`
    Expires  *time.Time             `json:"expires,omitempty"`
}

// TaskResult represents a task result from Redis
type TaskResult struct {
    Status    string          `json:"status"`
    Result    json.RawMessage `json:"result"`
    Traceback string          `json:"traceback,omitempty"`
    Children  []interface{}   `json:"children,omitempty"`
}

// SubmitTask submits a task to the specified queue
func (c *CeleryClient) SubmitTask(ctx context.Context, taskName string, queue string, kwargs map[string]interface{}) (string, error) {
    taskID := uuid.New().String()

    task := CeleryTask{
        Task:    taskName,
        ID:      taskID,
        Args:    []interface{}{},
        Kwargs:  kwargs,
        Retries: 0,
    }

    // Celery uses a specific message format
    message := map[string]interface{}{
        "body": base64Encode(task),
        "headers": map[string]interface{}{
            "id":   taskID,
            "task": taskName,
        },
        "content-type":     "application/json",
        "content-encoding": "utf-8",
        "properties": map[string]interface{}{
            "correlation_id": taskID,
            "reply_to":       uuid.New().String(),
            "delivery_mode":  2,
            "delivery_tag":   uuid.New().String(),
            "priority":       0,
        },
    }

    messageJSON, err := json.Marshal(message)
    if err != nil {
        return "", fmt.Errorf("failed to marshal task: %w", err)
    }

    // Push to the queue
    if err := c.rdb.LPush(ctx, queue, messageJSON).Err(); err != nil {
        return "", fmt.Errorf("failed to push task to queue: %w", err)
    }

    return taskID, nil
}

// GetTaskResult retrieves the result of a task
func (c *CeleryClient) GetTaskResult(ctx context.Context, taskID string, timeout time.Duration) (*TaskResult, error) {
    resultKey := fmt.Sprintf("celery-task-meta-%s", taskID)

    deadline := time.Now().Add(timeout)
    for time.Now().Before(deadline) {
        data, err := c.rdb.Get(ctx, resultKey).Result()
        if err == redis.Nil {
            // Task not finished yet, wait and retry
            time.Sleep(500 * time.Millisecond)
            continue
        } else if err != nil {
            return nil, fmt.Errorf("failed to get result: %w", err)
        }

        var result TaskResult
        if err := json.Unmarshal([]byte(data), &result); err != nil {
            return nil, fmt.Errorf("failed to unmarshal result: %w", err)
        }

        if result.Status == "SUCCESS" || result.Status == "FAILURE" {
            return &result, nil
        }

        // Task still pending/running
        time.Sleep(500 * time.Millisecond)
    }

    return nil, fmt.Errorf("task timeout after %v", timeout)
}

// Helper function to base64 encode the task body
func base64Encode(task CeleryTask) string {
    taskJSON, _ := json.Marshal(task)
    return string(taskJSON) // Celery expects JSON in the body
}
```

### 3. Create Task-Specific Helpers

Create `server/internal/celery/tasks.go`:

```go
package celery

import (
    "context"
    "encoding/json"
    "fmt"
    "time"
)

// SummarizeInput represents input for summarization task
type SummarizeInput struct {
    Text      string `json:"text"`
    MaxLength int    `json:"max_length,omitempty"`
    Language  string `json:"language,omitempty"`
}

// SummarizeOutput represents output from summarization task
type SummarizeOutput struct {
    Summary          string  `json:"summary"`
    OriginalLength   int     `json:"original_length"`
    SummaryLength    int     `json:"summary_length"`
    CompressionRatio float64 `json:"compression_ratio"`
}

// SubmitSummarizeTask submits a text summarization task
func (c *CeleryClient) SubmitSummarizeTask(ctx context.Context, input SummarizeInput) (string, error) {
    kwargs := map[string]interface{}{
        "text": input.Text,
    }
    if input.MaxLength > 0 {
        kwargs["max_length"] = input.MaxLength
    }
    if input.Language != "" {
        kwargs["language"] = input.Language
    }

    return c.SubmitTask(ctx, "celery_app.tasks.summarize.summarize_text", "summarize", kwargs)
}

// GetSummarizeResult retrieves the result of a summarization task
func (c *CeleryClient) GetSummarizeResult(ctx context.Context, taskID string, timeout time.Duration) (*SummarizeOutput, error) {
    result, err := c.GetTaskResult(ctx, taskID, timeout)
    if err != nil {
        return nil, err
    }

    if result.Status == "FAILURE" {
        return nil, fmt.Errorf("task failed: %s", result.Traceback)
    }

    var output SummarizeOutput
    if err := json.Unmarshal(result.Result, &output); err != nil {
        return nil, fmt.Errorf("failed to unmarshal result: %w", err)
    }

    return &output, nil
}

// KeywordsInput represents input for keyword extraction task
type KeywordsInput struct {
    Text        string `json:"text"`
    MaxKeywords int    `json:"max_keywords,omitempty"`
    Language    string `json:"language,omitempty"`
}

// KeywordsOutput represents output from keyword extraction task
type KeywordsOutput struct {
    Keywords []string `json:"keywords"`
    Count    int      `json:"count"`
}

// SubmitKeywordsTask submits a keyword extraction task
func (c *CeleryClient) SubmitKeywordsTask(ctx context.Context, input KeywordsInput) (string, error) {
    kwargs := map[string]interface{}{
        "text": input.Text,
    }
    if input.MaxKeywords > 0 {
        kwargs["max_keywords"] = input.MaxKeywords
    }
    if input.Language != "" {
        kwargs["language"] = input.Language
    }

    return c.SubmitTask(ctx, "celery_app.tasks.keywords.extract_keywords", "keywords", kwargs)
}

// GetKeywordsResult retrieves the result of a keyword extraction task
func (c *CeleryClient) GetKeywordsResult(ctx context.Context, taskID string, timeout time.Duration) (*KeywordsOutput, error) {
    result, err := c.GetTaskResult(ctx, taskID, timeout)
    if err != nil {
        return nil, err
    }

    if result.Status == "FAILURE" {
        return nil, fmt.Errorf("task failed: %s", result.Traceback)
    }

    var output KeywordsOutput
    if err := json.Unmarshal(result.Result, &output); err != nil {
        return nil, fmt.Errorf("failed to unmarshal result: %w", err)
    }

    return &output, nil
}

// NormalizeInput represents input for JSON normalization task
type NormalizeInput struct {
    Request  string                   `json:"request"`
    Schema   map[string]interface{}   `json:"schema"`
    Examples []map[string]interface{} `json:"examples,omitempty"`
    Language string                   `json:"language,omitempty"`
}

// NormalizeOutput represents output from JSON normalization task
type NormalizeOutput struct {
    Normalized map[string]interface{} `json:"normalized"`
    Confidence float64                `json:"confidence"`
}

// SubmitNormalizeTask submits a JSON normalization task
func (c *CeleryClient) SubmitNormalizeTask(ctx context.Context, input NormalizeInput) (string, error) {
    kwargs := map[string]interface{}{
        "request": input.Request,
        "schema":  input.Schema,
    }
    if len(input.Examples) > 0 {
        kwargs["examples"] = input.Examples
    }
    if input.Language != "" {
        kwargs["language"] = input.Language
    }

    return c.SubmitTask(ctx, "celery_app.tasks.normalize.normalize_json", "normalize", kwargs)
}

// GetNormalizeResult retrieves the result of a JSON normalization task
func (c *CeleryClient) GetNormalizeResult(ctx context.Context, taskID string, timeout time.Duration) (*NormalizeOutput, error) {
    result, err := c.GetTaskResult(ctx, taskID, timeout)
    if err != nil {
        return nil, err
    }

    if result.Status == "FAILURE" {
        return nil, fmt.Errorf("task failed: %s", result.Traceback)
    }

    var output NormalizeOutput
    if err := json.Unmarshal(result.Result, &output); err != nil {
        return nil, fmt.Errorf("failed to unmarshal result: %w", err)
    }

    return &output, nil
}
```

### 4. Create HTTP Handler

Create `server/internal/ai/handler.go`:

```go
package ai

import (
    "encoding/json"
    "net/http"
    "time"

    "github.com/go-chi/chi/v5"
    "yourproject/internal/celery"
)

type Handler struct {
    celeryClient *celery.CeleryClient
}

func NewHandler(celeryClient *celery.CeleryClient) *Handler {
    return &Handler{
        celeryClient: celeryClient,
    }
}

// POST /api/ai/summarize
func (h *Handler) Summarize(w http.ResponseWriter, r *http.Request) {
    var input celery.SummarizeInput
    if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
        http.Error(w, "Invalid request body", http.StatusBadRequest)
        return
    }

    // Submit task
    taskID, err := h.celeryClient.SubmitSummarizeTask(r.Context(), input)
    if err != nil {
        http.Error(w, "Failed to submit task", http.StatusInternalServerError)
        return
    }

    // Return task ID immediately (async)
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{
        "task_id": taskID,
        "status":  "PENDING",
    })
}

// GET /api/ai/summarize/:taskId
func (h *Handler) GetSummarizeResult(w http.ResponseWriter, r *http.Request) {
    taskID := chi.URLParam(r, "taskId")

    // Get result with 30 second timeout
    result, err := h.celeryClient.GetSummarizeResult(r.Context(), taskID, 30*time.Second)
    if err != nil {
        http.Error(w, err.Error(), http.StatusNotFound)
        return
    }

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(result)
}

// Similar handlers for keywords and normalize...
```

### 5. Wire Up in Main

Update `server/cmd/api/main.go`:

```go
package main

import (
    "log"
    "os"

    "yourproject/internal/celery"
    "yourproject/internal/ai"
    "yourproject/internal/server"
)

func main() {
    // Initialize Celery client
    redisURL := os.Getenv("REDIS_URL")
    celeryClient, err := celery.NewCeleryClient(redisURL)
    if err != nil {
        log.Fatalf("Failed to create Celery client: %v", err)
    }
    defer celeryClient.Close()

    // Initialize AI handler
    aiHandler := ai.NewHandler(celeryClient)

    // Create server with AI routes
    srv := server.New(":8080")
    srv.RegisterRoutes()
    srv.RegisterAIRoutes(aiHandler) // Add this

    log.Printf("Server starting on %s", srv.Addr)
    if err := srv.ListenAndServe(); err != nil {
        log.Fatalf("Server failed: %v", err)
    }
}
```

## Usage Examples

### From Frontend (JavaScript)

```javascript
// Submit summarization task
async function summarizeText(text) {
    const response = await fetch('/api/ai/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text: text,
            max_length: 200,
            language: 'en'
        })
    });
    const data = await response.json();
    return data.task_id;
}

// Poll for result
async function getSummary(taskId) {
    const response = await fetch(`/api/ai/summarize/${taskId}`);
    if (!response.ok) {
        throw new Error('Task not ready yet');
    }
    return await response.json();
}

// Usage
const taskId = await summarizeText("Long article text...");
const result = await getSummary(taskId);
console.log(result.summary);
```

### Synchronous API (Wait for Result)

```go
// POST /api/ai/summarize/sync
func (h *Handler) SummarizeSynec(w http.ResponseWriter, r *http.Request) {
    var input celery.SummarizeInput
    if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
        http.Error(w, "Invalid request body", http.StatusBadRequest)
        return
    }

    // Submit task
    taskID, err := h.celeryClient.SubmitSummarizeTask(r.Context(), input)
    if err != nil {
        http.Error(w, "Failed to submit task", http.StatusInternalServerError)
        return
    }

    // Wait for result (blocking)
    result, err := h.celeryClient.GetSummarizeResult(r.Context(), taskID, 60*time.Second)
    if err != nil {
        http.Error(w, err.Error(), http.StatusRequestTimeout)
        return
    }

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(result)
}
```

## Testing

```bash
# Start Redis
docker-compose up -d redis

# Start LLM server
docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml up -d llm-server

# Start Celery worker
cd worker
source venv/bin/activate
./start_worker.sh

# Start Go API
cd server
make run

# Test summarization
curl -X POST http://localhost:8080/api/ai/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Long article about machine learning...",
    "max_length": 100
  }'

# Response: {"task_id": "abc-123", "status": "PENDING"}

# Get result
curl http://localhost:8080/api/ai/summarize/abc-123

# Response: {
#   "summary": "Concise summary...",
#   "original_length": 50,
#   "summary_length": 12,
#   "compression_ratio": 0.24
# }
```

## Production Considerations

1. **Connection Pooling**: Redis client uses connection pooling automatically
2. **Timeouts**: Adjust task timeouts based on expected LLM response time
3. **Error Handling**: Handle task failures gracefully
4. **Rate Limiting**: Add rate limiting to prevent worker overload
5. **Monitoring**: Track task submission and completion rates
6. **Dead Letter Queues**: Monitor DLQs for permanently failed tasks

## Summary

This integration provides a clean, type-safe way to submit AI tasks from the Go API server to the Celery worker. The async pattern allows the API to respond quickly while heavy AI processing happens in the background.
