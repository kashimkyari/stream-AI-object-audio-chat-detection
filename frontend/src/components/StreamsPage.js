import React, { useState, useEffect, lazy, Suspense } from 'react';
import axios from 'axios';
import VideoPlayer from './VideoPlayer';

// Lazy load additional pages
const StreamsPageComponent = lazy(() => import('./StreamsPage'));
const FlagSettingsPage = lazy(() => import('./FlagSettingsPage'));

// Error Boundary to catch errors without crashing the entire page.
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-container">
          <h3>Something went wrong.</h3>
          <p>Please try refreshing the page.</p>
          <button onClick={() => window.location.reload()}>Refresh</button>
          <style jsx>{`
            .error-container {
              display: flex;
              flex-direction: column;
              justify-content: center;
              align-items: center;
              height: 200px;
              color: #e0e0e0;
              background: #2a2a2a;
              border-radius: 8px;
              padding: 20px;
            }
            button {
              background: #007bff;
              color: white;
              border: none;
              padding: 8px 16px;
              border-radius: 4px;
              margin-top: 10px;
              cursor: pointer;
            }
          `}</style>
        </div>
      );
    }
    return this.props.children;
  }
}

// Loading fallback component
const LoadingFallback = () => (
  <div className="loading-container">
    <p>Loading...</p>
    <style jsx>{`
      .loading-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 200px;
        color: #e0e0e0;
      }
    `}</style>
  </div>
);

// Confirmation Dialog Component
const ConfirmDialog = ({ message, onConfirm, onCancel }) => (
  <div className="confirm-overlay">
    <div className="confirm-dialog">
      <p className="confirm-message">{message}</p>
      <div className="confirm-actions">
        <button className="confirm-button" onClick={onConfirm}>Yes</button>
        <button className="cancel-button" onClick={onCancel}>No</button>
      </div>
    </div>
    <style jsx>{`
      .confirm-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.6);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 2000;
      }
      .confirm-dialog {
        background: #1a1a1a;
        padding: 24px;
        border-radius: 8px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
        animation: fadeIn 0.3s ease;
        max-width: 90%;
      }
      .confirm-message {
        font-size: 1.1rem;
        margin-bottom: 16px;
        color: #e0e0e0;
      }
      .confirm-actions {
        display: flex;
        justify-content: center;
        gap: 16px;
      }
      .confirm-button,
      .cancel-button {
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        font-size: 1rem;
        cursor: pointer;
        transition: background 0.2s ease;
      }
      .confirm-button {
        background: #28a745;
        color: white;
      }
      .confirm-button:hover {
        background: #218838;
      }
      .cancel-button {
        background: #ff4444;
        color: white;
      }
      .cancel-button:hover {
        background: #e63946;
      }
      @keyframes fadeIn {
        from { opacity: 0; transform: scale(0.9); }
        to { opacity: 1; transform: scale(1); }
      }
    `}</style>
  </div>
);

// Modal for editing agent details (only username and password)
const EditAgentModal = ({ agent, onClose, onSave }) => {
  const [form, setForm] = useState({
    username: agent.username,
    password: ''
  });
  const [error, setError] = useState('');

  const handleSave = async () => {
    setError('');
    if (!form.username.trim()) {
      setError('Username is required.');
      return;
    }
    const payload = { username: form.username.trim() };
    if (form.password.trim()) {
      payload.password = form.password.trim();
    }
    try {
      await onSave(agent.id, payload);
      onClose();
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to update agent.');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">Edit Agent</h3>
        <button className="close-button" onClick={onClose}>×</button>
        <div className="agent-form">
          <div className="form-group">
            <input
              type="text"
              placeholder="Username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="form-input"
            />
          </div>
          <div className="form-group">
            <input
              type="password"
              placeholder="New Password (optional)"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="form-input"
            />
          </div>
          {error && <div className="error-message">{error}</div>}
          <button className="submit-button" onClick={handleSave}>Save Changes</button>
        </div>
      </div>
      <style jsx>{`
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0, 0, 0, 0.8);
          backdrop-filter: blur(5px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }
        .modal-content {
          background: #1a1a1a;
          padding: 2rem;
          border-radius: 8px;
          max-width: 600px;
          width: 90%;
          position: relative;
          animation: zoomIn 0.3s ease;
          border: 1px solid #2d2d2d;
        }
        .modal-title {
          font-size: 1.5rem;
          margin-bottom: 1.5rem;
          color: #e0e0e0;
        }
        .close-button {
          position: absolute;
          top: 1rem;
          right: 1rem;
          background: none;
          border: none;
          color: #e0e0e0;
          font-size: 1.5rem;
          cursor: pointer;
          transition: color 0.3s ease;
        }
        .close-button:hover {
          color: #ff4444;
        }
        .agent-form {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        .form-group {
          width: 100%;
        }
        .form-input {
          width: 100%;
          padding: 0.75rem;
          background: #252525;
          border: 1px solid #333;
          border-radius: 4px;
          color: #e0e0e0;
          transition: all 0.3s ease;
        }
        .form-input:focus {
          border-color: #007bff;
          outline: none;
          box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.2);
        }
        .submit-button {
          padding: 0.75rem 1.25rem;
          background: linear-gradient(135deg, #007bff, #0056b3);
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.3s ease;
          font-weight: 500;
          margin-top: 1rem;
        }
        .submit-button:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
        }
        @keyframes zoomIn {
          from { transform: scale(0.8); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
};

// Component to render Streams Table (with card view for mobile)
const StreamTable = ({ streams, platform, onDelete, newStreamId }) => {
  const [sortConfig, setSortConfig] = useState({ key: 'id', direction: 'asc' });
  const [searchTerm, setSearchTerm] = useState('');
  const [showCardView, setShowCardView] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setShowCardView(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const sortedStreams = [...streams].sort((a, b) => {
    if (a[sortConfig.key] < b[sortConfig.key]) {
      return sortConfig.direction === 'asc' ? -1 : 1;
    }
    if (a[sortConfig.key] > b[sortConfig.key]) {
      return sortConfig.direction === 'asc' ? 1 : -1;
    }
    return 0;
  });

  const filteredStreams = sortedStreams.filter(stream =>
    Object.values(stream).some(value =>
      String(value).toLowerCase().includes(searchTerm.toLowerCase())
    )
  );

  if (streams.length === 0) return <p className="empty-state">No {platform} streams available.</p>;

  return (
    <div className="table-container">
      <div className="search-container">
        <input
          type="text"
          placeholder="Search streams..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
        <div className="view-toggle">
          <button 
            className={`view-button ${!showCardView ? 'active' : ''}`}
            onClick={() => setShowCardView(false)}
            aria-label="Table view"
          >
            📋
          </button>
          <button 
            className={`view-button ${showCardView ? 'active' : ''}`}
            onClick={() => setShowCardView(true)}
            aria-label="Card view"
          >
            📱
          </button>
        </div>
      </div>

      {showCardView ? (
        <div className="stream-cards">
          {filteredStreams.map((stream) => (
            <div
              key={stream.id}
              className={`stream-card ${newStreamId === stream.id ? 'new-stream-blink' : ''}`}
            >
              <div className="card-header">
                <h3 className="card-title">ID: {stream.id}</h3>
                <button
                  onClick={() => onDelete(stream.id)}
                  className="delete-button mobile"
                  title="Delete stream"
                  aria-label="Delete stream"
                >
                  🗑️
                </button>
              </div>
              <div className="card-content">
                <p><strong>Username:</strong> {stream.streamer_username}</p>
                <p>
                  <strong>Stream:</strong>{' '}
                  {stream[`${platform}_m3u8_url`] ? (
                    <a
                      href={stream[`${platform}_m3u8_url`]}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="stream-link"
                    >
                      Open Stream
                    </a>
                  ) : (
                    'N/A'
                  )}
                </p>
                <div className="agent-assignment">
                  <span className="assignment-label">AGENT:</span>
                  {stream.agent ? (
                    <div className="assigned-agent">
                      <span className="agent-icon">👤</span>
                      {stream.agent.username}
                    </div>
                  ) : (
                    <span className="unassigned-badge">⚠️ UNASSIGNED</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="table-scroll">
          <table className="streams-table">
            <thead>
              <tr>
                {['ID', 'Username', 'M3U8 URL', 'Assigned Agent', 'Actions'].map((header) => (
                  <th key={header}>
                    <button
                      className="sort-header"
                      onClick={() => handleSort(header.toLowerCase().replace(' ', '_'))}
                      aria-label={`Sort by ${header}`}
                    >
                      {header}
                      {sortConfig.key === header.toLowerCase().replace(' ', '_') && (
                        <span className="sort-arrow">
                          {sortConfig.direction === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredStreams.map((stream) => (
                <tr
                  key={stream.id}
                  className={`stream-row ${newStreamId === stream.id ? 'new-stream-blink' : ''}`}
                >
                  <td data-label="ID">{stream.id}</td>
                  <td data-label="Username">{stream.streamer_username}</td>
                  <td data-label="M3U8 URL">
                    {stream[`${platform}_m3u8_url`] ? (
                      <a
                        href={stream[`${platform}_m3u8_url`]}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="stream-link"
                      >
                        Open Stream
                      </a>
                    ) : (
                      'N/A'
                    )}
                  </td>
                  <td data-label="Assigned Agent">
                    {stream.agent ? (
                      <div className="assigned-agent">
                        <span className="agent-icon">👤</span>
                        {stream.agent.username}
                      </div>
                    ) : (
                      <span className="unassigned-badge">⚠️ UNASSIGNED</span>
                    )}
                  </td>
                  <td>
                    <button
                      onClick={() => onDelete(stream.id)}
                      className="delete-button"
                      title="Delete stream"
                      aria-label="Delete stream"
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="table-footer">
        Showing {filteredStreams.length} of {streams.length} streams
      </div>
    </div>
  );
};

// Fancier Agent Table using card view on mobile and table view on larger screens.
const AgentTable = ({ agents, onEdit, onDelete }) => {
  const [showCardView, setShowCardView] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setShowCardView(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (agents.length === 0) return <p className="empty-state">No agents available.</p>;

  return (
    <div className="agent-table-container">
      <h2 className="section-title">Agents Management</h2>
      {showCardView ? (
        <div className="agent-cards">
          {agents.map(agent => (
            <div key={agent.id} className="agent-card">
              <div className="agent-card-header">
                <h3>ID: {agent.id}</h3>
              </div>
              <div className="agent-card-content">
                <p><strong>Username:</strong> {agent.username}</p>
              </div>
              <div className="agent-card-actions">
                <button className="edit-button" onClick={() => onEdit(agent)} title="Edit Agent">
                  ✏️
                </button>
                <button className="delete-button" onClick={() => onDelete(agent.id)} title="Delete Agent">
                  🗑️
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <table className="agents-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Username</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {agents.map(agent => (
              <tr key={agent.id}>
                <td>{agent.id}</td>
                <td>{agent.username}</td>
                <td>
                  <button className="edit-button" onClick={() => onEdit(agent)} title="Edit Agent">
                    ✏️
                  </button>
                  <button className="delete-button" onClick={() => onDelete(agent.id)} title="Delete Agent">
                    🗑️
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <style jsx>{`
        .agent-table-container {
          margin-top: 2rem;
          background: #1a1a1a;
          padding: 1rem;
          border-radius: 8px;
          border: 1px solid #2d2d2d;
        }
        .section-title {
          font-size: 1.25rem;
          font-weight: 600;
          margin-bottom: 1rem;
          color: #e0e0e0;
        }
        .agents-table {
          width: 100%;
          border-collapse: collapse;
        }
        .agents-table th, .agents-table td {
          padding: 0.75rem 1rem;
          border-bottom: 1px solid #444;
          color: #e0e0e0;
          text-align: left;
        }
        .agents-table th {
          background: #252525;
        }
        .agent-cards {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
          gap: 16px;
        }
        .agent-card {
          background: #252525;
          border-radius: 8px;
          padding: 16px;
          border: 1px solid #444;
          transition: transform 0.3s ease, box-shadow 0.3s ease;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }
        .agent-card:hover {
          transform: translateY(-4px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        }
        .agent-card-header h3 {
          margin: 0;
          font-size: 1.1rem;
          color: #fff;
        }
        .agent-card-content p {
          margin: 0.5rem 0;
          font-size: 0.95rem;
          color: #ccc;
        }
        .agent-card-actions {
          display: flex;
          gap: 8px;
          margin-top: 0.75rem;
        }
        .edit-button {
          padding: 0.4rem 0.75rem;
          background: #007bff;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          transition: background 0.3s ease;
        }
        .edit-button:hover {
          background: #0056b3;
        }
        .delete-button {
          padding: 0.4rem 0.75rem;
          background: #ff4444;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          transition: background 0.3s ease;
        }
        .delete-button:hover {
          background: #cc3333;
        }
      `}</style>
    </div>
  );
};

const AddStreamForm = ({ onAddStream, refreshStreams, onStreamAdded }) => {
  const [platform, setPlatform] = useState('chaturbate');
  const [roomUrl, setRoomUrl] = useState('');
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [agents, setAgents] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [error, setError] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [estimatedTime, setEstimatedTime] = useState(0);
  // Keep form expanded on mobile
  const [isFormExpanded] = useState(true);
  // Quick add agent inline form fields
  const [quickAgent, setQuickAgent] = useState({ username: '', password: '' });
  const [showQuickAgent, setShowQuickAgent] = useState(false);
  const [quickAgentMsg, setQuickAgentMsg] = useState('');
  const [quickAgentError, setQuickAgentError] = useState('');

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const res = await axios.get('/api/agents');
        setAgents(res.data);
        if (res.data.length > 0) {
          setSelectedAgentId(res.data[0].id.toString());
        }
      } catch (err) {
        console.error('Failed to fetch agents:', err);
      }
    };
    fetchAgents();
  }, []);

  useEffect(() => {
    if (roomUrl.toLowerCase().includes('stripchat.com')) {
      setPlatform('stripchat');
    } else {
      setPlatform('chaturbate');
    }
  }, [roomUrl]);

  const subscribeToProgress = (jobId) => {
    const eventSource = new EventSource(`/api/streams/interactive/sse?job_id=${jobId}`);
    eventSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setProgress(data.progress);
      setProgressMessage(data.message);
      setEstimatedTime(data.estimated_time || 0);
      if (data.progress >= 100) {
        eventSource.close();
      }
    };
    eventSource.onerror = (err) => {
      console.error("SSE error:", err);
      eventSource.close();
    };
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setProgress(0);
    setProgressMessage('Initializing...');
    try {
      const response = await axios.post('/api/streams/interactive', {
        room_url: roomUrl,
        platform: platform,
        agent_id: selectedAgentId // Ensure the selected agent is assigned
      });
      const { job_id } = response.data;
      setJobId(job_id);
      subscribeToProgress(job_id);
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to start stream creation');
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    if (progress >= 100 && jobId) {
      const fetchNewStream = async () => {
        try {
          const res = await axios.get('/api/streams?platform=' + platform);
          const newStream = res.data[res.data.length - 1];
          onAddStream(newStream);
          setSubmitSuccess(true);
          setTimeout(() => setSubmitSuccess(false), 5000);
          setRoomUrl('');
          setIsSubmitting(false);
          if (onStreamAdded) onStreamAdded();
        } catch (err) {
          console.error('Failed to fetch new stream:', err);
        }
      };
      fetchNewStream();
    }
  }, [progress, jobId, platform, onAddStream, onStreamAdded]);

  return (
    <div className="form-container">
      <div className="form-header">
        <h2 className="form-title">Stream Management</h2>
      </div>
      
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="platform-select">Platform:</label>
          <select
            id="platform-select"
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className={`form-select ${roomUrl.includes('stripchat.com') ? 'platform-switch' : ''}`}
          >
            <option value="chaturbate">Chaturbate</option>
            <option value="stripchat">Stripchat</option>
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="room-url">Room URL:</label>
          <input
            id="room-url"
            type="url"
            value={roomUrl}
            onChange={(e) => setRoomUrl(e.target.value)}
            placeholder={`Enter ${platform} room URL`}
            className="form-input"
            required
            inputMode="url"
          />
        </div>
        <div className="form-group assign-group">
          <label htmlFor="agent-select">Assign Agent:</label>
          <div className="assign-wrapper">
            <select
              id="agent-select"
              value={selectedAgentId}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              className="form-select"
            >
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.username}
                </option>
              ))}
            </select>
            <button 
              type="button"
              className="quick-add-button"
              onClick={() => setShowQuickAgent(!showQuickAgent)}
              aria-label="Quick add agent"
            >
              + Add Agent
            </button>
          </div>
          {showQuickAgent && (
            <div className="quick-agent-form">
              <input
                type="text"
                placeholder="Username"
                value={quickAgent.username}
                onChange={(e) => setQuickAgent({ ...quickAgent, username: e.target.value })}
                className="form-input quick-input"
              />
              <input
                type="password"
                placeholder="Password"
                value={quickAgent.password}
                onChange={(e) => setQuickAgent({ ...quickAgent, password: e.target.value })}
                className="form-input quick-input"
              />
              <button 
                type="button"
                onClick={async () => {
                  setQuickAgentError('');
                  setQuickAgentMsg('');
                  if (!quickAgent.username.trim() || !quickAgent.password.trim()) {
                    setQuickAgentError('Both username and password are required.');
                    return;
                  }
                  try {
                    const payload = {
                      username: quickAgent.username.trim(),
                      password: quickAgent.password.trim(),
                      firstname: quickAgent.username.trim(),
                      lastname: 'User',
                      email: `${quickAgent.username.trim()}@example.com`,
                      phonenumber: 'N/A'
                    };
                    const res = await axios.post('/api/agents', payload);
                    setQuickAgentMsg(res.data.message);
                    setQuickAgent({ username: '', password: '' });
                    const agentsRes = await axios.get('/api/agents');
                    setAgents(agentsRes.data);
                    if (agentsRes.data.length > 0) {
                      setSelectedAgentId(agentsRes.data[agentsRes.data.length - 1].id.toString());
                    }
                    setShowQuickAgent(false);
                  } catch (error) {
                    setQuickAgentError(error.response?.data.message || 'Error creating agent.');
                  }
                }}
                className="quick-submit-button"
              >
                Create
              </button>
              {quickAgentError && <div className="error-message">{quickAgentError}</div>}
              {quickAgentMsg && <div className="success-message">{quickAgentMsg}</div>}
            </div>
          )}
        </div>
        <button
          type="submit"
          className={`add-button ${isSubmitting ? 'submitting' : ''} ${submitSuccess ? 'success' : ''}`}
          disabled={isSubmitting}
          style={{ width: '100%', position: 'relative', overflow: 'hidden' }}
        >
          {isSubmitting ? (
            <div className="button-progress">
              <div className="progress-fill" style={{ width: `${progress}%` }}></div>
              <div className="progress-text">
                {progress}% - {progressMessage} {estimatedTime > 0 && `(Est. ${estimatedTime}s left)`}
              </div>
            </div>
          ) : (
            'Add Stream'
          )}
        </button>
      </form>
      <style jsx>{`
        .assign-group {
          display: flex;
          flex-direction: column;
        }
        .assign-wrapper {
          display: flex;
          gap: 8px;
          align-items: center;
        }
        .quick-add-button {
          padding: 0.5rem 0.75rem;
          background: #007bff;
          border: none;
          border-radius: 4px;
          color: white;
          cursor: pointer;
          transition: background 0.3s ease;
          font-size: 0.9rem;
        }
        .quick-add-button:hover {
          background: #0056b3;
        }
        .quick-agent-form {
          margin-top: 0.75rem;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          background: #2d2d2d;
          padding: 0.75rem;
          border-radius: 4px;
        }
        .quick-input {
          font-size: 0.9rem;
          padding: 0.5rem;
        }
        .quick-submit-button {
          padding: 0.5rem;
          background: #28a745;
          border: none;
          border-radius: 4px;
          color: white;
          cursor: pointer;
          transition: background 0.3s ease;
          font-size: 0.9rem;
          margin-top: 0.5rem;
        }
        .quick-submit-button:hover {
          background: #218838;
        }
      `}</style>
    </div>
  );
};

function StreamsPage() {
  const [streams, setStreams] = useState({
    chaturbate: [],
    stripchat: []
  });
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('chaturbate');
  const [newStreamId, setNewStreamId] = useState(null);
  const [toast, setToast] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState({ show: false, streamId: null });
  const [editAgent, setEditAgent] = useState(null);

  const showToast = (message, type = 'success', duration = 3000) => {
    setToast({ message, type });
    setTimeout(() => setToast(null), duration);
  };

  const fetchStreams = async (platform) => {
    try {
      const response = await axios.get(`/api/streams?platform=${platform}`);
      setStreams(prev => ({
        ...prev,
        [platform]: response.data.map(stream => ({
          ...stream,
          platform: platform
        }))
      }));
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to fetch streams');
      console.error('Stream fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchAgents = async () => {
    try {
      const res = await axios.get('/api/agents');
      setAgents(res.data);
    } catch (err) {
      console.error('Error fetching agents:', err);
    }
  };

  const refreshStreams = async () => {
    try {
      await Promise.all([fetchStreams('chaturbate'), fetchStreams('stripchat')]);
    } catch (err) {
      console.error(err);
    }
  };

  const confirmDeleteStream = (streamId) => {
    setConfirmDelete({ show: true, streamId });
  };

  const handleDeleteStream = async (streamId, platform) => {
    try {
      await axios.delete(`/api/streams/${streamId}`);
      setStreams(prev => ({
        ...prev,
        [platform]: prev[platform].filter(stream => stream.id !== streamId)
      }));
      showToast("Stream deleted successfully", "success");
    } catch (err) {
      alert(err.response?.data?.message || 'Failed to delete stream');
      console.error('Delete error:', err);
    }
  };

  const handleConfirmDelete = () => {
    if (confirmDelete.streamId) {
      if (confirmDelete.streamId.toString().startsWith('agent-')) {
        const agentId = confirmDelete.streamId.split('-')[1];
        handleDeleteAgent(agentId);
      } else {
        handleDeleteStream(confirmDelete.streamId, activeTab);
      }
    }
    setConfirmDelete({ show: false, streamId: null });
  };

  const handleCancelDelete = () => {
    setConfirmDelete({ show: false, streamId: null });
  };

  useEffect(() => {
    refreshStreams();
    fetchAgents();
  }, []);

  const handleAddStream = (newStream) => {
    const platform = newStream.type.toLowerCase();
    setActiveTab(platform);
    setNewStreamId(newStream.id);
    setStreams(prev => ({
      ...prev,
      [platform]: [...prev[platform], newStream]
    }));
  };

  const handleStreamAdded = () => {
    showToast("Stream created successfully", "success");
  };

  // Agent edit & delete functions
  const handleEditAgent = async (agentId, payload) => {
    try {
      await axios.put(`/api/agents/${agentId}`, payload);
      showToast("Agent updated successfully", "info");
      fetchAgents();
    } catch (err) {
      showToast(err.response?.data?.message || "Failed to update agent", "error");
      console.error("Error updating agent:", err);
    }
  };

  const handleDeleteAgent = async (agentId) => {
    try {
      await axios.delete(`/api/agents/${agentId}`);
      showToast("Agent deleted successfully", "success");
      fetchAgents();
    } catch (err) {
      showToast(err.response?.data?.message || "Failed to delete agent", "error");
      console.error("Error deleting agent:", err);
    }
  };

  // Open edit modal for agent
  const openEditAgentModal = (agent) => {
    setEditAgent(agent);
  };

  const closeEditAgentModal = () => {
    setEditAgent(null);
  };

  if (loading) return (
    <div className="loading-overlay">
      <div className="loading-spinner"></div>
      <p>Loading streams...</p>
    </div>
  );

  if (error) return (
    <div className="error-overlay">
      <div className="error-message">{error}</div>
      <button onClick={refreshStreams} className="retry-button">
        Retry
      </button>
    </div>
  );

  return (
    <ErrorBoundary>
      <div className="streams-container">
        
        <AddStreamForm 
          onAddStream={(newStream) => {
            handleAddStream(newStream);
            handleStreamAdded();
          }} 
          refreshStreams={refreshStreams} 
        />

        <div className="tabs-container">
          <nav className="tabs-nav">
            {['chaturbate', 'stripchat'].map(platform => (
              <button
                key={platform}
                onClick={() => setActiveTab(platform)}
                className={`tab-button ${activeTab === platform ? 'active' : ''}`}
              >
                <span className="platform-name">
                  {platform.charAt(0).toUpperCase() + platform.slice(1)}
                </span>
                <span className="stream-count">{streams[platform].length}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="tables-container">
          <StreamTable 
            streams={streams[activeTab]} 
            platform={activeTab}
            onDelete={(id) => setConfirmDelete({ show: true, streamId: id })}
            newStreamId={newStreamId}
          />
        </div>

        <div className="tables-container">
          <AgentTable 
            agents={agents}
            onEdit={openEditAgentModal}
            onDelete={(id) => setConfirmDelete({ show: true, streamId: `agent-${id}` })}
          />
        </div>

        {toast && (
          <div className={`toast ${toast.type}`}>
            <span className="toast-icon">
              {toast.type === 'success' ? '✅' : toast.type === 'error' ? '❌' : 'ℹ️'}
            </span>
            <span className="toast-message">{toast.message}</span>
          </div>
        )}

        {confirmDelete.show && (
          <ConfirmDialog 
            message={
              confirmDelete.streamId && confirmDelete.streamId.toString().startsWith('agent-')
                ? "Are you sure you want to delete this agent?"
                : "Are you sure you want to delete this stream?"
            }
            onConfirm={handleConfirmDelete}
            onCancel={handleCancelDelete}
          />
        )}

        {editAgent && (
          <EditAgentModal 
            agent={editAgent}
            onClose={closeEditAgentModal}
            onSave={handleEditAgent}
          />
        )}

        <div className="fab-container">
          <button 
            className="fab refresh-button" 
            onClick={refreshStreams}
            title="Refresh streams"
            aria-label="Refresh streams"
          >
            ↻
          </button>
        </div>

        <style jsx>{`
          /* Base styles */
          .streams-container {
            padding: 16px;
            max-width: 1200px;
            margin: 0 auto;
            animation: slideUp 0.6s cubic-bezier(0.22, 1, 0.36, 1);
            color: #e0e0e0;
            font-family: 'Inter', sans-serif;
          }
          .page-title {
            font-size: 1.8rem;
            font-weight: bold;
            margin-bottom: 1.5rem;
            text-align: center;
          }
          /* Form styles */
          .form-container {
            margin: 1.5rem 0;
            padding: 1rem;
            background: #1a1a1a;
            border-radius: 8px;
            border: 1px solid #2d2d2d;
          }
          .form-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: default;
          }
          .toggle-form-button {
            background: none;
            border: none;
            color: #aaa;
            font-size: 1.2rem;
            cursor: default;
          }
          .form-title {
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 1rem;
            color: #e0e0e0;
          }
          .error-message {
            margin: 1rem 0;
            padding: 0.5rem;
            background: rgba(255, 68, 68, 0.1);
            color: #ff4444;
            border-radius: 4px;
            border-left: 3px solid #ff4444;
          }
          .success-message {
            margin: 1rem 0;
            padding: 0.5rem;
            background: rgba(40, 167, 69, 0.1);
            color: #28a745;
            border-radius: 4px;
            border-left: 3px solid #28a745;
          }
          .form-group {
            margin-bottom: 1rem;
          }
          .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            color: #ccc;
          }
          .form-select,
          .form-input {
            width: 100%;
            padding: 0.75rem;
            background: #252525;
            border: 1px solid #444;
            border-radius: 4px;
            color: #e0e0e0;
            transition: all 0.3s ease;
            font-size: 16px;
          }
          .form-select:focus,
          .form-input:focus {
            border-color: #007bff;
            outline: none;
            box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.3);
          }
          /* Button styles */
          .add-button {
            padding: 0.75rem 1.25rem;
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 500;
          }
          .add-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
          }
          .add-button:disabled {
            background: #333;
            cursor: not-allowed;
          }
          .add-button.submitting {
            position: relative;
            padding: 0;
            height: 50px;
            overflow: hidden;
          }
          .add-button.success {
            background: #28a745 !important;
          }
          .button-progress {
            position: relative;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            z-index: 1;
          }
          .progress-fill {
            position: absolute;
            top: 0;
            left: 0;
            height: 100%;
            background: #007bff;
            transition: width 0.3s ease;
            z-index: 0;
          }
          .progress-text {
            position: relative;
            z-index: 1;
            text-align: center;
            padding: 0 10px;
            font-size: 14px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          /* Tabs styles */
          .tabs-container {
            margin-bottom: 1rem;
            border-bottom: 1px solid #2d2d2d;
          }
          .tabs-nav {
            display: flex;
            gap: 0.5rem;
            justify-content: center;
          }
          .tab-button {
            padding: 0.75rem 1.25rem;
            background: none;
            border: none;
            color: #aaa;
            cursor: pointer;
            position: relative;
            transition: all 0.3s ease;
            flex: 1;
            max-width: 200px;
          }
          .tab-button::before {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: #007bff;
            transform: scaleX(0);
            transition: transform 0.3s ease;
          }
          .tab-button.active,
          .tab-button:hover {
            color: #fff;
          }
          .tab-button.active::before {
            transform: scaleX(1);
          }
          .platform-name {
            margin-right: 8px;
          }
          .stream-count {
            background: rgba(255, 255, 255, 0.1);
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.9rem;
          }
          /* Table container */
          .tables-container {
            margin-top: 1.5rem;
          }
          .table-container {
            position: relative;
            background: #1a1a1a;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 1rem;
          }
          .empty-state {
            text-align: center;
            padding: 2rem;
            color: #888;
          }
          /* Search and view toggle */
          .search-container {
            margin-bottom: 1rem;
            display: flex;
            gap: 10px;
            align-items: center;
          }
          .search-input {
            flex-grow: 1;
            padding: 0.75rem;
            background: #252525;
            border: 1px solid #444;
            border-radius: 4px;
            color: #e0e0e0;
            font-size: 16px;
          }
          .view-toggle {
            display: flex;
            gap: 5px;
          }
          .view-button {
            background: #252525;
            border: 1px solid #444;
            border-radius: 4px;
            color: #ccc;
            padding: 0 10px;
            cursor: pointer;
            transition: background 0.3s ease;
          }
          .view-button.active {
            background: #333;
            color: #fff;
            border-color: #666;
          }
          /* Table styles */
          .table-scroll {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
          }
          .streams-table {
            width: 100%;
            border-collapse: collapse;
            background: #1a1a1a;
            border-radius: 8px;
            overflow: hidden;
          }
          .streams-table th {
            padding: 0.75rem 1rem;
            text-align: left;
            background: #252525;
            color: #e0e0e0;
            font-weight: 500;
            border-bottom: 1px solid #444;
            white-space: nowrap;
          }
          .streams-table td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #2d2d2d;
            color: #e0e0e0;
          }
          .sort-header {
            background: none;
            border: none;
            color: inherit;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: inherit;
            font-weight: inherit;
            padding: 0;
          }
          .sort-arrow {
            color: #007bff;
          }
          .stream-row:hover {
            background: #252525;
          }
          .new-stream-blink {
            animation: blink 1s ease-in-out 3;
          }
          @keyframes blink {
            0%, 100% { background-color: transparent; }
            50% { background-color: #444; }
          }
          .stream-link {
            color: #007bff;
            text-decoration: none;
          }
          .stream-link:hover {
            text-decoration: underline;
          }
          .table-footer {
            padding: 1rem;
            text-align: right;
            color: #aaa;
            font-size: 0.9rem;
          }
          .delete-button {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 1.1rem;
            padding: 6px;
            border-radius: 4px;
            transition: all 0.2s ease;
          }
          .delete-button:hover {
            color: #ff4444;
            background: rgba(255, 68, 68, 0.1);
          }
          .delete-button.mobile {
            padding: 8px;
            font-size: 1.3rem;
          }
          /* Card view styles for mobile (Streams) */
          .stream-cards {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 16px;
          }
          .stream-card {
            background: #252525;
            border-radius: 8px;
            padding: 16px;
            border: 1px solid #444;
            transition: all 0.3s ease;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
          }
          .stream-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
          }
          .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            border-bottom: 1px solid #444;
            padding-bottom: 8px;
          }
          .card-title {
            margin: 0;
            font-size: 1.2rem;
            font-weight: 500;
            color: #fff;
          }
          .card-content p {
            margin: 0.75rem 0;
            font-size: 0.9rem;
            color: #e0e0e0;
          }
          .card-content strong {
            color: #fff;
            font-weight: 500;
          }
          .agent-assignment {
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 12px 0;
          }
          .assignment-label {
            color: #888;
            font-size: 0.8rem;
            text-transform: uppercase;
          }
          .assigned-agent {
            display: flex;
            align-items: center;
            gap: 6px;
            color: #28a745;
          }
          .unassigned-badge {
            background: rgba(255, 68, 68, 0.1);
            color: #ff4444;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85rem;
          }
          .agent-icon {
            font-size: 0.9rem;
          }
          /* Toast Notification Styles */
          .toast {
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #28a745;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            gap: 8px;
            z-index: 3000;
            animation: slideDown 0.3s ease-out;
          }
          .toast-icon {
            font-size: 1.2rem;
          }
          @keyframes slideDown {
            from { transform: translate(-50%, -100%); opacity: 0; }
            to { transform: translate(-50%, 0); opacity: 1; }
          }
          /* FAB (Refresh) Styles */
          .fab-container {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 3000;
          }
          .fab {
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            border: none;
            border-radius: 50%;
            width: 56px;
            height: 56px;
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            cursor: pointer;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
          }
          .fab:hover {
            transform: translateY(-4px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.4);
          }
          /* Modal Styles for Editing Agent */
          .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(5px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
          }
          .modal-content {
            background: #1a1a1a;
            padding: 2rem;
            border-radius: 8px;
            max-width: 600px;
            width: 90%;
            position: relative;
            animation: zoomIn 0.3s ease;
            border: 1px solid #2d2d2d;
          }
          .modal-title {
            font-size: 1.5rem;
            margin-bottom: 1.5rem;
            color: #e0e0e0;
          }
          .close-button {
            position: absolute;
            top: 1rem;
            right: 1rem;
            background: none;
            border: none;
            color: #e0e0e0;
            font-size: 1.5rem;
            cursor: pointer;
            transition: color 0.3s ease;
          }
          .close-button:hover {
            color: #ff4444;
          }
          .agent-form {
            display: flex;
            flex-direction: column;
            gap: 1rem;
          }
          @keyframes zoomIn {
            from { transform: scale(0.8); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
          }
          @keyframes slideUp {
            0% { transform: translateY(20px); opacity: 0; }
            100% { transform: translateY(0); opacity: 1; }
          }
          @media (max-width: 768px) {
            .streams-container {
              padding: 10px;
            }
            .tab-button {
              flex: 1;
              display: flex;
              flex-direction: column;
              align-items: center;
              padding: 12px 8px;
              font-size: 0.8rem;
            }
            .streams-table,
            .streams-table th,
            .streams-table td {
              font-size: 0.9rem;
              padding: 0.5rem;
            }
            .form-input,
            .form-select {
              font-size: 16px;
            }
          }
          /* Fancier Agent Table Styles */
          .agent-table-container {
            margin-top: 2rem;
            background: #1a1a1a;
            padding: 1rem;
            border-radius: 8px;
            border: 1px solid #2d2d2d;
          }
          .agent-cards {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 16px;
          }
          .agent-card {
            background: #252525;
            border-radius: 8px;
            padding: 16px;
            border: 1px solid #444;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
          }
          .agent-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
          }
          .agent-card-header h3 {
            margin: 0;
            font-size: 1.1rem;
            color: #fff;
          }
          .agent-card-content p {
            margin: 0.5rem 0;
            font-size: 0.95rem;
            color: #ccc;
          }
          .agent-card-actions {
            display: flex;
            gap: 8px;
            margin-top: 0.75rem;
          }
          .edit-button {
            padding: 0.4rem 0.75rem;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.3s ease;
          }
          .edit-button:hover {
            background: #0056b3;
          }
          .delete-button {
            padding: 0.4rem 0.75rem;
            background: #ff4444;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.3s ease;
          }
          .delete-button:hover {
            background: #cc3333;
          }
        `}</style>
      </div>
    </ErrorBoundary>
  );
}

export default StreamsPage;