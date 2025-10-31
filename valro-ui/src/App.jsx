import { useEffect, useState, useRef } from "react";
import "./App.css";

// Get API base URL from environment variable or use deployed API Gateway
const API_BASE = import.meta.env.VITE_API_BASE || "https://pgwnhr0bnh.execute-api.us-east-1.amazonaws.com";

function App() {
  const [tasks, setTasks] = useState([]);
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [selectedTask, setSelectedTask] = useState(null);
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  // Fetch all tasks on mount
  useEffect(() => {
    fetchTasks();
  }, []);

  // Poll selected task every 3 seconds while task is active
  useEffect(() => {
    if (selectedTaskId) {
      // Fetch immediately
      fetchTask(selectedTaskId);

      // Start polling
      intervalRef.current = setInterval(() => {
        fetchTask(selectedTaskId);
      }, 3000);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [selectedTaskId]);

  // Stop polling when task reaches terminal state
  useEffect(() => {
    if (selectedTask?.status === "completed" || selectedTask?.status === "error") {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
  }, [selectedTask?.status]);

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${API_BASE}/tasks`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      setTasks(data);
      setError(null);
    } catch (err) {
      console.error("Error fetching tasks:", err);
      setError(`Failed to load tasks: ${err.message}`);
    }
  };

  const fetchTask = async (taskId) => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      setSelectedTask(data);

      // Update the task in the tasks array so sidebar shows latest state
      setTasks(prevTasks =>
        prevTasks.map(t => t.id === taskId ? data : t)
      );

      setError(null);
    } catch (err) {
      console.error("Error fetching task:", err);
      setError(`Failed to load task: ${err.message}`);
    }
  };

  const createTask = async () => {
    if (!description.trim()) {
      setError("Please enter a task description");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setDescription("");
      await fetchTasks();
      setSelectedTaskId(data.id);
      setError(null);
    } catch (err) {
      console.error("Error creating task:", err);
      setError(`Failed to create task: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && e.ctrlKey) {
      createTask();
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case "completed":
        return "#10b981";
      case "processing":
        return "#3b82f6";
      case "error":
        return "#ef4444";
      default:
        return "#6b7280";
    }
  };

  const getEventTypeColor = (type) => {
    switch (type) {
      case "success":
        return "#10b981";
      case "error":
        return "#ef4444";
      case "info":
      default:
        return "#3b82f6";
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h1>Valro</h1>
          <p className="subtitle">Home Services Concierge</p>
        </div>

        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        <div className="task-list">
          <h3>Your Tasks</h3>
          {tasks.length === 0 ? (
            <p className="empty-state">No tasks yet. Create one below!</p>
          ) : (
            <ul>
              {tasks.map((t) => (
                <li
                  key={t.id}
                  className={`task-item ${t.id === selectedTaskId ? "selected" : ""}`}
                  onClick={() => {
                    setSelectedTaskId(t.id);
                    setSelectedTask(t);
                  }}
                >
                  <div className="task-description">
                    {t.description?.slice(0, 60) || "No description"}
                    {t.description?.length > 60 && "..."}
                  </div>
                  <div className="task-meta">
                    <span
                      className="status-badge"
                      style={{ backgroundColor: getStatusColor(t.status) }}
                    >
                      {t.status}
                    </span>
                    <span className="task-time">
                      {new Date(t.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="task-creator">
          <h4>Create New Task</h4>
          <textarea
            rows={4}
            placeholder="Describe what you need... (e.g., 'Find me a landscaper in Charlotte under $300')"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyDown={handleKeyPress}
            disabled={loading}
          />
          <button onClick={createTask} disabled={loading}>
            {loading ? "Creating..." : "Create Task"}
          </button>
          <p className="hint">Ctrl+Enter to submit</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">
        {selectedTask ? (
          <div className="task-detail">
            <div className="task-header">
              <h2>{selectedTask.description}</h2>
              <span
                className="status-badge large"
                style={{ backgroundColor: getStatusColor(selectedTask.status) }}
              >
                {selectedTask.status}
              </span>
            </div>

            <div className="task-info">
              <div className="info-item">
                <span className="label">Created:</span>
                <span>{new Date(selectedTask.created_at).toLocaleString()}</span>
              </div>
              <div className="info-item">
                <span className="label">Updated:</span>
                <span>{new Date(selectedTask.updated_at).toLocaleString()}</span>
              </div>
              {selectedTask.emails_sent > 0 && (
                <div className="info-item">
                  <span className="label">Emails Sent:</span>
                  <span>{selectedTask.emails_sent}</span>
                </div>
              )}
            </div>

            {selectedTask.agent_response && (
              <div className="section">
                <h3>Agent Response</h3>
                <div className="agent-response">
                  {selectedTask.agent_response}
                </div>
              </div>
            )}

            {selectedTask.vendors && selectedTask.vendors.length > 0 && (
              <div className="section">
                <h3>Vendors Contacted</h3>
                <div className="vendors-grid">
                  {selectedTask.vendors.map((v) => (
                    <div key={v.id} className="vendor-card">
                      <div className="vendor-name">{v.name}</div>
                      <div className="vendor-detail">{v.email}</div>
                      <div className="vendor-detail">
                        {v.service} • {v.city}
                      </div>
                      {v.emails && v.emails.length > 0 && (
                        <div className="vendor-emails">
                          <div className="email-badge">
                            Email sent {new Date(v.emails[0].timestamp).toLocaleString()}
                          </div>
                          <details className="email-details">
                            <summary>View email</summary>
                            <div className="email-content">
                              <div><strong>Subject:</strong> {v.emails[0].subject}</div>
                              <div className="email-body">{v.emails[0].body}</div>
                            </div>
                          </details>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {selectedTask.quotes && selectedTask.quotes.length > 0 && (
              <div className="section">
                <h3>Quotes Received</h3>
                <div className="quotes-list">
                  {selectedTask.quotes.map((q, idx) => (
                    <div key={idx} className="quote-card">
                      <div>
                        <strong>Vendor {q.vendor_id}</strong>
                      </div>
                      <div className="quote-amount">${q.amount}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="section">
              <h3>Activity Timeline</h3>
              <div className="timeline">
                {(selectedTask.events || []).map((e, idx) => (
                  <div key={idx} className="timeline-item">
                    <div
                      className="timeline-marker"
                      style={{ backgroundColor: getEventTypeColor(e.type) }}
                    />
                    <div className="timeline-content">
                      <div className="timeline-message">{e.message}</div>
                      {e.ts && (
                        <div className="timeline-time">
                          {new Date(e.ts).toLocaleString()}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="empty-detail">
            <div className="empty-icon">📋</div>
            <h2>No Task Selected</h2>
            <p>Select a task from the sidebar or create a new one to get started.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
