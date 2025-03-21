import React, { useState, useEffect } from 'react';
import axios from 'axios';

// Error Boundary to catch and display errors without crashing the entire page.
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="error-overlay">
          <div className="error-message">
            Something went wrong: {this.state.error?.toString()}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const StreamTable = ({ streams, platform, onDelete, newStreamId }) => {
  const [sortConfig, setSortConfig] = useState({ key: 'id', direction: 'asc' });
  const [searchTerm, setSearchTerm] = useState('');
  const [showCardView, setShowCardView] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => {
      setShowCardView(window.innerWidth < 768);
    };
    
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
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
            <span role="img" aria-label="Table">📋</span>
          </button>
          <button 
            className={`view-button ${showCardView ? 'active' : ''}`}
            onClick={() => setShowCardView(true)}
            aria-label="Card view"
          >
            <span role="img" aria-label="Cards">📱</span>
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
                <p><strong>Agent:</strong> {stream.assignments?.[0]?.agent?.username || 'Unassigned'}</p>
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
                  <td data-label="Assigned Agent">{stream.assignments?.[0]?.agent?.username || 'Unassigned'}</td>
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
  const [isFormExpanded, setIsFormExpanded] = useState(window.innerWidth >= 768);

  useEffect(() => {
    const handleResize = () => {
      setIsFormExpanded(window.innerWidth >= 768);
    };
    
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

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
        agent_id: selectedAgentId  
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
      refreshStreams();
      const fetchNewStream = async () => {
        try {
          const res = await axios.get('/api/streams?platform=' + platform);
          const newStream = res.data[res.data.length - 1];
          onAddStream(newStream);
          setSubmitSuccess(true);
          setTimeout(() => setSubmitSuccess(false), 5000);
          setRoomUrl('');
          setIsSubmitting(false);
          // Call parent callback to trigger toast notification
          if (onStreamAdded) {
            onStreamAdded();
          }
        } catch (err) {
          console.error('Failed to fetch new stream:', err);
        }
      };
      fetchNewStream();
    }
  }, [progress, jobId, platform, onAddStream, refreshStreams, onStreamAdded]);

  const toggleForm = () => {
    setIsFormExpanded(!isFormExpanded);
  };

  return (
    <div className="form-container">
      <div className="form-header" onClick={toggleForm}>
        <h2 className="form-title">Add New Stream</h2>
        <button className="toggle-form-button" aria-label={isFormExpanded ? "Collapse form" : "Expand form"}>
          {isFormExpanded ? '▲' : '▼'}
        </button>
      </div>
      
      {isFormExpanded && (
        <>
          {error && <div className="error-message">{error}</div>}

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

            <div className="form-group">
              <label htmlFor="agent-select">Assign Agent:</label>
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
        </>
      )}
    </div>
  );
};

function StreamsPage() {
  const [streams, setStreams] = useState({
    chaturbate: [],
    stripchat: []
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('chaturbate');
  const [newStreamId, setNewStreamId] = useState(null);
  const [toast, setToast] = useState(null);

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

  const refreshStreams = async () => {
    try {
      await Promise.all([fetchStreams('chaturbate'), fetchStreams('stripchat')]);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteStream = async (streamId, platform) => {
    if (!window.confirm('Are you sure you want to delete this stream?')) return;
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

  useEffect(() => {
    refreshStreams();
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

  // Callback when a stream is added successfully; show toast notification.
  const handleStreamAdded = () => {
    showToast("Stream created successfully", "success");
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
        <h1 className="page-title">Stream Management</h1>

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
                <span className="platform-name">{platform.charAt(0).toUpperCase() + platform.slice(1)}</span>
                <span className="stream-count">{streams[platform].length}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="tables-container">
          <StreamTable 
            streams={streams[activeTab]} 
            platform={activeTab}
            onDelete={(streamId) => handleDeleteStream(streamId, activeTab)}
            newStreamId={newStreamId}
          />
        </div>

        {toast && (
          <div className={`toast ${toast.type}`}>
            <span className="toast-icon">{toast.type === 'success' ? '✅' : ''}</span>
            <span className="toast-message">{toast.message}</span>
          </div>
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
            cursor: pointer;
          }
          .toggle-form-button {
            background: none;
            border: none;
            color: #888;
            font-size: 1.2rem;
            cursor: pointer;
          }
          .form-title {
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 0;
          }
          .error-message {
            margin: 1rem 0;
            padding: 0.5rem;
            background: rgba(255, 68, 68, 0.1);
            color: #ff4444;
            border-radius: 4px;
            border-left: 3px solid #ff4444;
          }
          .form-group {
            margin-bottom: 1rem;
          }
          .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            color: #a0a0a0;
          }
          .form-select,
          .form-input {
            width: 100%;
            padding: 0.75rem;
            background: #252525;
            border: 1px solid #333;
            border-radius: 4px;
            color: #e0e0e0;
            transition: all 0.3s ease;
            font-size: 16px; /* Prevents iOS zoom */
          }
          .form-select:focus,
          .form-input:focus {
            border-color: #007bff;
            outline: none;
            box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.2);
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
            color: #a0a0a0;
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
          }
          .search-input {
            flex-grow: 1;
            padding: 0.75rem;
            background: #252525;
            border: 1px solid #333;
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
            border: 1px solid #333;
            border-radius: 4px;
            color: #888;
            padding: 0 10px;
            cursor: pointer;
          }
          .view-button.active {
            background: #333;
            color: #fff;
            border-color: #555;
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
            border-bottom: 1px solid #333;
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
            color: #888;
            font-size: 0.9rem;
          }
          .delete-button {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 1.2rem;
            padding: 4px;
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
          
          /* Card view styles */
          .stream-cards {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 16px;
          }
          .stream-card {
            background: #252525;
            border-radius: 8px;
            padding: 16px;
            border: 1px solid #333;
            transition: all 0.3s ease;
          }
          .stream-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
          }
          .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
          }
          .card-title {
            margin: 0;
            font-size: 1.1rem;
            font-weight: 500;
          }
          .card-content p {
            margin: 8px 0;
            word-break: break-word;
          }
          
          /* Loading and error states */
          .loading-overlay,
          .error-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            color: white;
          }
          .loading-spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #007bff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin-bottom: 1rem;
          }
          .retry-button {
            margin-top: 1rem;
            padding: 0.75rem 1.25rem;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.3s ease;
          }
          .retry-button {
            margin-top: 1rem;
            padding: 0.75rem 1.25rem;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.3s ease;
          }
          .retry-button:hover {
            background: #0056b3;
          }
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
          @keyframes slideUp {
            0% { opacity: 0; transform: translateY(20px); }
            100% { opacity: 1; transform: translateY(0); }
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
          .add-button.success {
            background: #28a745 !important;
          }
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
        `}</style>
      </div>
    </ErrorBoundary>
  );
}

export default StreamsPage;
