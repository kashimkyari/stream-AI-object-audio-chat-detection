import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Hls from 'hls.js';
import './AgentDashboard.css'

// Error Boundary Component to catch runtime errors and display fallback UI.
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true };
  }
  componentDidCatch(error, errorInfo) {
    console.error("AgentDashboard Error:", error, errorInfo);
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

const AgentDashboard = () => {
  const [dashboardData, setDashboardData] = useState({ ongoing_streams: 0, assignments: [] });
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [agentName, setAgentName] = useState('');
  const [detectionAlerts, setDetectionAlerts] = useState({});
  // Use a ref to throttle notifications (one per minute)
  const lastNotificationRef = useRef(Date.now());

  // Video player state refs and HLS instances
  const videoRefs = useRef({});
  const hlsInstances = useRef({});
  const [streamStates, setStreamStates] = useState({});

  // Fetch session and assigned streams
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        // Fetch session data
        const sessionRes = await axios.get('/api/session');
        if (sessionRes.data.logged_in) {
          setAgentName(`${sessionRes.data.user.firstname} ${sessionRes.data.user.lastname}`);
        }
        // Fetch assigned streams for the agent
        const dashboardRes = await axios.get('/api/agent/dashboard');
        const assignments = dashboardRes.data.assignments || [];

        // Initialize stream states for each assignment
        const initialStreamStates = {};
        assignments.forEach(assignment => {
          initialStreamStates[assignment.id] = {
            isStreamLoaded: false,
            isLoadingStream: true,
            hasError: false,
            errorMessage: "",
            isStreamOnline: false,
            isMuted: true,
            volume: 0
          };
        });
        setStreamStates(initialStreamStates);
        setDashboardData({
          ongoing_streams: dashboardRes.data.ongoing_streams,
          assignments: assignments
        });
        setLoading(false);
      } catch (error) {
        console.error('Error fetching initial data:', error);
        setLoading(false);
      }
    };

    fetchInitialData();

    // Set up EventSource for real-time detection events
    const eventSource = new EventSource('/api/notification-events');
    eventSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (!data.error) {
        setDetectionAlerts(prev => ({
          ...prev,
          [data.stream_url]: data.detections
        }));
        // Throttle notifications to one per minute.
        if (data.detections?.length > 0 && Date.now() - lastNotificationRef.current > 60000) {
          const detectedItems = data.detections.map(d => d.class).join(', ');
          if (Notification.permission === 'granted') {
            new Notification('Object Detected', {
              body: `Detected ${detectedItems} in ${data.stream_url}`
            });
            lastNotificationRef.current = Date.now();
          }
        }
      }
    };
    eventSource.onerror = (err) => {
      console.error('EventSource error:', err);
      eventSource.close();
    };

    return () => {
      // Clean up HLS instances on unmount
      Object.values(hlsInstances.current).forEach(hls => {
        if (hls) hls.destroy();
      });
      eventSource.close();
    };
  }, []);

  // Initialize HLS player for a given assignment and video element.
  const initializePlayer = (assignment, videoElement) => {
    if (!videoElement) return;
    const assignmentId = assignment.id;
    // Clean up any existing HLS instance for this assignment.
    if (hlsInstances.current[assignmentId]) {
      hlsInstances.current[assignmentId].destroy();
      delete hlsInstances.current[assignmentId];
    }
    // Choose the appropriate m3u8 URL based on the stream's platform.
    const m3u8Url = assignment.platform.toLowerCase() === 'chaturbate'
      ? assignment.chaturbate_m3u8_url
      : assignment.stripchat_m3u8_url;

    if (!m3u8Url) {
      setStreamStates(prev => ({
        ...prev,
        [assignmentId]: {
          ...prev[assignmentId],
          isLoadingStream: false,
          hasError: true,
          errorMessage: "Invalid stream URL",
          isStreamOnline: false
        }
      }));
      return;
    }

    if (Hls.isSupported()) {
      const hls = new Hls({ autoStartLoad: true, startLevel: -1, debug: false });
      hls.loadSource(m3u8Url);
      hls.attachMedia(videoElement);
      hlsInstances.current[assignmentId] = hls;
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        setStreamStates(prev => ({
          ...prev,
          [assignmentId]: {
            ...prev[assignmentId],
            isLoadingStream: false,
            isStreamLoaded: true,
            isStreamOnline: true
          }
        }));
        videoElement.play().catch(console.error);
      });
      hls.on(Hls.Events.ERROR, (event, data) => {
        if (data.fatal) {
          setStreamStates(prev => ({
            ...prev,
            [assignmentId]: {
              ...prev[assignmentId],
              isLoadingStream: false,
              hasError: true,
              isStreamOnline: false,
              errorMessage: data.details || 'Playback error'
            }
          }));
        }
      });
    } else if (videoElement.canPlayType('application/vnd.apple.mpegurl')) {
      // For Safari support.
      videoElement.src = m3u8Url;
      videoElement.addEventListener('loadedmetadata', () => {
        setStreamStates(prev => ({
          ...prev,
          [assignmentId]: {
            ...prev[assignmentId],
            isLoadingStream: false,
            isStreamLoaded: true,
            isStreamOnline: true
          }
        }));
        videoElement.play().catch(console.error);
      });
      videoElement.addEventListener('error', () => {
        setStreamStates(prev => ({
          ...prev,
          [assignmentId]: {
            ...prev[assignmentId],
            isLoadingStream: false,
            hasError: true,
            isStreamOnline: false,
            errorMessage: "Playback error"
          }
        }));
      });
    } else {
      setStreamStates(prev => ({
        ...prev,
        [assignmentId]: {
          ...prev[assignmentId],
          isLoadingStream: false,
          hasError: true,
          isStreamOnline: false,
          errorMessage: "HLS not supported"
        }
      }));
    }
  };

  // Handle video element references.
  const handleVideoRef = (element, assignmentId) => {
    if (element && !videoRefs.current[assignmentId]) {
      videoRefs.current[assignmentId] = element;
      const assignment = dashboardData.assignments.find(a => a.id === assignmentId);
      if (assignment) {
        initializePlayer(assignment, element);
      }
    }
  };

  // Toggle mute for a given stream.
  const toggleMute = (assignmentId) => {
    setStreamStates(prev => {
      const currentState = prev[assignmentId];
      const newMutedState = !currentState.isMuted;
      if (videoRefs.current[assignmentId]) {
        videoRefs.current[assignmentId].muted = newMutedState;
        if (!newMutedState) {
          videoRefs.current[assignmentId].volume = currentState.volume > 0 ? currentState.volume : 0.5;
        }
      }
      return {
        ...prev,
        [assignmentId]: {
          ...currentState,
          isMuted: newMutedState,
          volume: newMutedState ? 0 : (currentState.volume > 0 ? currentState.volume : 0.5)
        }
      };
    });
  };

  // Set volume for a given stream.
  const setStreamVolume = (assignmentId, newVolume) => {
    setStreamStates(prev => {
      const currentState = prev[assignmentId];
      if (videoRefs.current[assignmentId]) {
        videoRefs.current[assignmentId].volume = newVolume;
        videoRefs.current[assignmentId].muted = newVolume === 0;
      }
      return {
        ...prev,
        [assignmentId]: {
          ...currentState,
          volume: newVolume,
          isMuted: newVolume === 0
        }
      };
    });
  };

  const closeModal = () => setSelectedAssignment(null);

  // Render the video container with controls and stream status.
  const renderStreamVideo = (assignment, isModal = false) => {
    const assignmentId = assignment.id;
    const streamState = streamStates[assignmentId] || {
      isStreamLoaded: false,
      isLoadingStream: true,
      hasError: false,
      errorMessage: "",
      isStreamOnline: false,
      isMuted: true,
      volume: 0
    };

    return (
      <div className="video-container">
        <video
          ref={(el) => handleVideoRef(el, assignmentId)}
          muted={streamState.isMuted}
          autoPlay
          playsInline
          style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}
        />
        {streamState.isStreamLoaded && streamState.isStreamOnline && (
          <div className="live-indicator">
            <div className="red-dot"></div>
            <span className="live-text">LIVE</span>
          </div>
        )}
        {streamState.isLoadingStream && (
          <div className="loading-overlay">
            <div className="loading-spinner"></div>
            <div className="loading-text">Loading stream...</div>
          </div>
        )}
        {streamState.hasError && (
          <div className="error-overlay">
            <div className="error-icon">⚠️</div>
            <div className="error-text">{streamState.errorMessage}</div>
          </div>
        )}
        {!streamState.isStreamOnline && !streamState.isLoadingStream && (
          <div className="offline-message">
            <span>Offline</span>
          </div>
        )}
        {isModal && (
          <div className="volume-controls">
            <button className="mute-button" onClick={() => toggleMute(assignmentId)}>
              {streamState.isMuted ? '🔇' : streamState.volume > 0 ? '🔊' : '🔈'}
            </button>
            <input
              type="range"
              className="volume-slider"
              min="0"
              max="1"
              step="0.1"
              value={streamState.volume}
              onChange={(e) => setStreamVolume(assignmentId, parseFloat(e.target.value))}
            />
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="agent-dashboard">
        <div className="loading-page">
          <div className="loading-spinner"></div>
          <div className="loading-text">Loading dashboard...</div>
        </div>
        
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="agent-dashboard">
        <div className="dashboard-content">
          <h1>Welcome, {agentName}</h1>
          <section className="streams-section">
            <h2>Assigned Streams ({dashboardData.ongoing_streams})</h2>
            <div className="assignment-grid">
              {dashboardData.assignments.length > 0 ? (
                dashboardData.assignments.map((assignment) => (
                  <div 
                    key={assignment.id} 
                    className="assignment-card" 
                    onClick={() => setSelectedAssignment(assignment)}
                  >
                    {renderStreamVideo(assignment)}
                    {(detectionAlerts[assignment.room_url]?.length > 0) && (
                      <div className="detection-alert-badge">
                        {detectionAlerts[assignment.room_url].length} DETECTIONS
                        <div className="detection-preview">
                          <img 
                            src={detectionAlerts[assignment.room_url][0].image_url} 
                            alt="Detection preview" 
                            className="preview-image"
                          />
                          <div className="detection-info">
                            <span>{detectionAlerts[assignment.room_url][0].class} </span>
                            <span>({(detectionAlerts[assignment.room_url][0].confidence * 100).toFixed(1)}%)</span>
                          </div>
                        </div>
                      </div>
                    )}
                    <div className="assignment-details">
                      <p><strong>Streamer:</strong> {assignment.streamer_username}</p>
                      <p><strong>Platform:</strong> {assignment.platform}</p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="no-streams-message">No streams assigned.</p>
              )}
            </div>
          </section>
        </div>

        {selectedAssignment && (
          <div className="modal-overlay" onClick={closeModal}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <button className="close-button" onClick={closeModal}>×</button>
              <h2>{selectedAssignment.streamer_username}'s Stream</h2>
              {renderStreamVideo(selectedAssignment, true)}
              <div className="stream-info">
                <p><strong>Platform:</strong> {selectedAssignment.platform}</p>
                <p><strong>URL:</strong> {selectedAssignment.room_url}</p>
                {detectionAlerts[selectedAssignment.room_url]?.length > 0 && (
                  <div className="detections-list">
                    <h3>Recent Detections</h3>
                    <ul>
                      {detectionAlerts[selectedAssignment.room_url].map((detection, index) => (
                        <li key={index}>
                          {detection.class} ({(detection.confidence * 100).toFixed(1)}%)
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

       
      </div>
    </ErrorBoundary>
  );
};



export default AgentDashboard;
