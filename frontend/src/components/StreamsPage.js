import React, { useState, useEffect } from 'react';
import axios from 'axios';
import VideoPlayer from './VideoPlayer';
import './StreamsPage.css';

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
        </div>
      );
    }
    return this.props.children;
  }
}

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
    </div>
  );
};

// Modal for adding a new agent (opens as an overlay)
const AddAgentModal = ({ onClose, onAgentCreated }) => {
  const [form, setForm] = useState({ username: '', password: '' });
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const handleCreate = async () => {
    setError('');
    setMessage('');
    if (!form.username.trim() || !form.password.trim()) {
      setError('Both username and password are required.');
      return;
    }
    const payload = {
      username: form.username.trim(),
      password: form.password.trim(),
      firstname: form.username.trim(),
      lastname: 'User',
      email: `${form.username.trim()}@example.com`,
      phonenumber: 'N/A'
    };
    try {
      const res = await axios.post('/api/agents', payload);
      setMessage(res.data.message || 'Agent created successfully');
      onAgentCreated(); // Refresh agents list
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.message || 'Error creating agent.');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">Add Agent</h3>
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
              placeholder="Password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="form-input"
            />
          </div>
          {error && <div className="error-message">{error}</div>}
          {message && <div className="success-message">{message}</div>}
          <button className="submit-button" onClick={handleCreate}>Create Agent</button>
        </div>
      </div>
    </div>
  );
};

// Modal to manage assignments for a given stream
const ManageAssignmentsModal = ({ stream, agents, onClose, onSave }) => {
  // Preselect agents based on the stream's assignments
  const [selectedAgentIds, setSelectedAgentIds] = useState(
    stream.assignments ? stream.assignments.map(a => a.agent_id) : []
  );

  const toggleAgentSelection = (agentId) => {
    if (selectedAgentIds.includes(agentId)) {
      setSelectedAgentIds(selectedAgentIds.filter(id => id !== agentId));
    } else {
      setSelectedAgentIds([...selectedAgentIds, agentId]);
    }
  };

  const handleSave = async () => {
    try {
      // Update assignments via a PUT request to a traditional endpoint
      await axios.put(`/api/streams/${stream.id}/assignments`, { assignments: selectedAgentIds });
      onSave(stream.id, selectedAgentIds);
      onClose();
    } catch (err) {
      console.error("Failed to update assignments:", err);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">Manage Assignments for Stream {stream.id}</h3>
        <button className="close-button" onClick={onClose}>×</button>
        <div className="assignments-form">
          <p>Select agents to assign to this stream:</p>
          <div className="agent-checkboxes">
            {agents.map(agent => (
              <label key={agent.id}>
                <input 
                  type="checkbox" 
                  checked={selectedAgentIds.includes(agent.id)} 
                  onChange={() => toggleAgentSelection(agent.id)} 
                />
                {agent.username}
              </label>
            ))}
          </div>
        </div>
        <button className="submit-button" onClick={handleSave}>Save Assignments</button>
      </div>
    </div>
  );
};

// Component to render Streams Table (with card view for mobile)
const StreamTable = ({ streams, platform, onDelete, newStreamId, agents, onManageAssignments }) => {
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

  // Render agent info based on the assignments field.
  // Update renderAgentInfo in StreamTable component
const renderAgentInfo = (stream) => {
  if (stream.assignments && stream.assignments.length > 0) {
    return (
      <div className="assigned-agents">
        {stream.assignments.map((assignment, index) => {
          const agent = agents.find(a => a.id === assignment.agent_id);
          return agent ? (
            <div key={index} className="agent-tag">
              <span className="agent-icon">👤</span>
              {agent.username}
            </div>
          ) : null;
        })}
      </div>
    );
  }
  return <span className="unassigned-badge">⚠️ UNASSIGNED</span>;
};

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
                  {stream[`${platform.toLowerCase()}_m3u8_url`] ? (
                    <a
                      href={stream[`${platform.toLowerCase()}_m3u8_url`]}
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
                  {renderAgentInfo(stream)}
                </div>
                <div className="action-buttons">
                  <button
                    className="manage-button"
                    onClick={() => onManageAssignments(stream)}
                    title="Manage Assignments"
                  >
                    Manage
                  </button>
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
                <th>ID</th>
                <th>Username</th>
                <th>Agent</th>
                <th>M3U8 URL</th>
                <th>Actions</th>
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
                  <td data-label="Agent">{renderAgentInfo(stream)}</td>
                  <td data-label="M3U8 URL">
                    {stream[`${platform.toLowerCase()}_m3u8_url`] ? (
                      <a
                        href={stream[`${platform.toLowerCase()}_m3u8_url`]}
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
                  <td data-label="Actions">
                    <button
                      onClick={() => onDelete(stream.id)}
                      className="delete-button"
                      title="Delete stream"
                      aria-label="Delete stream"
                    >
                      🗑️
                    </button>
                    <button
                      onClick={() => onManageAssignments(stream)}
                      className="manage-button"
                      title="Manage Assignments"
                      aria-label="Manage Assignments"
                    >
                      Manage
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

// Agent Table with search and pagination (also supports card view for mobile)
const AgentTable = ({ agents, onEdit, onDelete, onAddAgent }) => {
  const [showCardView, setShowCardView] = useState(window.innerWidth < 768);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  useEffect(() => {
    const handleResize = () => setShowCardView(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const filteredAgents = agents.filter(agent =>
    agent.username.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const totalPages = Math.ceil(filteredAgents.length / itemsPerPage);
  const indexOfLast = currentPage * itemsPerPage;
  const indexOfFirst = indexOfLast - itemsPerPage;
  const currentAgents = filteredAgents.slice(indexOfFirst, indexOfLast);

  const paginate = (pageNumber) => {
    if (pageNumber < 1 || pageNumber > totalPages) return;
    setCurrentPage(pageNumber);
  };

  if (agents.length === 0) return <p className="empty-state">No agents available.</p>;

  return (
    <div className="agent-table-container">
      <h2 className="section-title">Agents Management</h2>
      <div className="search-container">
        <input
          type="text"
          placeholder="Search agents..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setCurrentPage(1);
          }}
          className="search-input"
        />
      </div>
      {showCardView ? (
        <div className="agent-cards">
          {currentAgents.map(agent => (
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
        <table className="streams-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Username</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {currentAgents.map(agent => (
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
      <div className="table-footer">
        Showing {currentAgents.length} of {filteredAgents.length} agents
      </div>
    </div>
  );
};

const AddStreamForm = ({ onAddStream, refreshStreams, onStreamAdded, refreshAgents }) => {
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
  const [isFormExpanded] = useState(true);
  const [showAddAgentModal, setShowAddAgentModal] = useState(false);
  const [submitError, setSubmitError] = useState(false);



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

    // Handle completion
    if (data.progress >= 100) {
      if (data.error) {
        setSubmitError(true);
        setError(data.error);
        setIsSubmitting(false);
      }
      eventSource.close();
    }
  };

  eventSource.onerror = (err) => {
    console.error("SSE error:", err);
    setSubmitError(true);
    setError('Connection to progress updates failed');
    setIsSubmitting(false);
    eventSource.close();
  };
};

useEffect(() => {
  const fetchNewStream = async () => {
    try {
      const res = await axios.get('/api/streams?platform=' + platform);
      const newStream = res.data[res.data.length - 1];
      onAddStream(newStream);
      setSubmitSuccess(true);
      setSubmitError(false);
      setIsSubmitting(false);
      
      if (onStreamAdded) onStreamAdded();
    } catch (err) {
      console.error('Failed to fetch new stream:', err);
      setSubmitError(true);
      setIsSubmitting(false);
    }
  };

  if (progress >= 100 && jobId && !submitError) {
    fetchNewStream();
  }
}, [progress, jobId, platform, onAddStream, onStreamAdded, submitError]);

// Reset form after success
useEffect(() => {
  if (submitSuccess) {
    const timer = setTimeout(() => {
      setRoomUrl('');
      setProgress(0);
      setJobId(null);
    }, 2000); // Clear form after 2 seconds

    return () => clearTimeout(timer);
  }
}, [submitSuccess]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    
    setProgress(0);
    setProgressMessage('Initializing...');
    setJobId(null);
    setSubmitError(false);
  setSubmitSuccess(false);
    
    try {
      const response = await axios.post('/api/streams/interactive', {
        room_url: roomUrl,
        platform: platform,
        agent_id: selectedAgentId
      });
      const { job_id } = response.data;
      setJobId(job_id);
      subscribeToProgress(job_id);
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to start stream creation');
      setSubmitError(true);
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
    setSubmitError(false);
    
    
    if (onStreamAdded) onStreamAdded();
  } catch (err) {
    console.error('Failed to fetch new stream:', err);
    setSubmitSuccess(true);
    setSubmitError(true);
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
              onClick={() => setShowAddAgentModal(true)}
              aria-label="Quick add agent"
            >
              + Add Agent
            </button>
          </div>
        </div>
        <button
  type="submit"
  className={`add-button 
    ${isSubmitting ? 'submitting' : ''} 
    ${submitSuccess ? 'success' : ''}
    ${submitError ? 'error' : ''}`}
  disabled={isSubmitting && !submitError}
  style={{ width: '100%', position: 'relative', overflow: 'hidden' }}
>
  {submitError ? (
    'Retry Now'
  ) : isSubmitting ? (
    <div className="button-progress">
      <div className="progress-fill" style={{ width: `${progress}%` }}></div>
      <div className="progress-text">
        {progress}% - {progressMessage} {estimatedTime > 0 && `(Est. ${estimatedTime}s left)`}
      </div>
    </div>
  ) : submitSuccess ? (
    'Stream Created Successfully!'
  ) : (
    'Add Stream'
  )}
</button>
      </form>
      {showAddAgentModal && (
        <AddAgentModal 
          onClose={() => setShowAddAgentModal(false)}
          onAgentCreated={() => {
            axios.get('/api/agents')
              .then(res => {
                setAgents(res.data);
                if (res.data.length > 0) {
                  setSelectedAgentId(res.data[res.data.length - 1].id.toString());
                }
                if (refreshAgents) refreshAgents();
              })
              .catch(err => console.error('Error refreshing agents:', err));
          }}
        />
      )}
    </div>
  );
};

function StreamsPage() {
  const [streams, setStreams] = useState({
    chaturbate: [],
    stripchat: []
  });
  const [agents, setAgents] = useState([]);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('chaturbate');
  const [newStreamId, setNewStreamId] = useState(null);
  const [toast, setToast] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState({ show: false, streamId: null });
  const [editAgent, setEditAgent] = useState(null);
  const [manageAssignmentStream, setManageAssignmentStream] = useState(null);

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

  const openEditAgentModal = (agent) => {
    setEditAgent(agent);
  };

  const closeEditAgentModal = () => {
    setEditAgent(null);
  };

  // Open manage assignments modal for a given stream.
  const openManageAssignments = (stream) => {
    setManageAssignmentStream(stream);
  };

  // Callback after assignments are updated.
  const handleAssignmentsUpdated = (streamId, updatedAssignments) => {
    // For simplicity, refresh the streams list.
    refreshStreams();
  };

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
          refreshAgents={fetchAgents}
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
            agents={agents}
            onManageAssignments={openManageAssignments}
          />
        </div>

        <div className="tables-container">
          <AgentTable 
            agents={agents}
            onEdit={openEditAgentModal}
            onDelete={(id) => setConfirmDelete({ show: true, streamId: `agent-${id}` })}
            onAddAgent={() => {}}
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

        {manageAssignmentStream && (
          <ManageAssignmentsModal 
            stream={manageAssignmentStream}
            agents={agents}
            onClose={() => setManageAssignmentStream(null)}
            onSave={handleAssignmentsUpdated}
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
      </div>
    </ErrorBoundary>
  );
}

export default StreamsPage;
