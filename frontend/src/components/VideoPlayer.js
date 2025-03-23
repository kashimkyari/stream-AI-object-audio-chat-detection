import React, { useState, useEffect } from 'react';
import Hls from 'hls.js';
import axios from 'axios';

const HlsPlayer = ({ m3u8Url, isModalOpen, posterUrl, platform, streamerName }) => {
  const videoRef = React.useRef(null);
  const [isStreamLoaded, setIsStreamLoaded] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isMuted, setIsMuted] = useState(true);
  const [volume, setVolume] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  // Sync volume/mute state with video element.
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.muted = isMuted;
      videoRef.current.volume = volume;
    }
  }, [isMuted, volume]);

  // Initialize HLS player.
  useEffect(() => {
    let hls;
    if (!m3u8Url) {
      setIsLoading(false);
      setHasError(true);
      setErrorMessage("Invalid stream URL");
      return;
    }
    const initializePlayer = () => {
      if (Hls.isSupported()) {
        hls = new Hls({ autoStartLoad: true, startLevel: -1, debug: false });
        hls.loadSource(m3u8Url);
        hls.attachMedia(videoRef.current);

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          setIsLoading(false);
          setIsStreamLoaded(true);
          videoRef.current.play().catch(console.error);
        });

        hls.on(Hls.Events.ERROR, (event, data) => {
          if (data.fatal) {
            setHasError(true);
            setIsLoading(false);
            setErrorMessage(data.details || 'Playback error');
          }
        });
      } else if (videoRef.current.canPlayType('application/vnd.apple.mpegurl')) {
        videoRef.current.src = m3u8Url;
        videoRef.current.addEventListener('loadedmetadata', () => {
          setIsLoading(false);
          setIsStreamLoaded(true);
          videoRef.current.play().catch(console.error);
        });
      } else {
        setHasError(true);
        setIsLoading(false);
        setErrorMessage("HLS not supported");
      }
    };

    initializePlayer();
    return () => hls?.destroy();
  }, [m3u8Url, refreshKey]);

  // Trigger detection when the stream is online.
  useEffect(() => {
    if (isStreamLoaded && m3u8Url) {
      axios.post('/api/trigger-detection', {
        stream_url: m3u8Url,
        timestamp: new Date().toISOString(),
        platform: platform,
        streamer_name: streamerName
      })
      .then(response => {
        console.log("Server-side detection triggered:", response.data);
      })
      .catch(error => {
        console.error("Error triggering server-side detection:", error);
      });
    }
  }, [isStreamLoaded, m3u8Url, platform, streamerName]);

  // Refresh handler for Chaturbate streams only.
  const handleRefresh = async () => {
    setHasError(false);
    setIsLoading(true);
    setErrorMessage("");
    if (platform.toLowerCase() === 'chaturbate') {
      try {
        const response = await axios.post('/api/streams/refresh/chaturbate', {
          room_slug: streamerName
        });
        if (response.data && response.data.m3u8_url) {
          // Update m3u8Url with the new URL from the refresh endpoint.
          // Also trigger a refresh of the player.
          setRefreshKey(prev => prev + 1);
          // It's important to update the URL if necessary:
          // Optionally, you can call a prop callback to update the m3u8Url state higher up.
          // For now, we'll assume the player uses the new refreshKey to reinitialize.
          console.log("Refreshed m3u8 URL:", response.data.m3u8_url);
        } else {
          console.error("Refresh response missing m3u8_url");
        }
      } catch (error) {
        console.error("Error refreshing stream:", error);
        setErrorMessage("Error refreshing stream");
      }
    } else {
      // For other platforms, simply reinitialize the player.
      setRefreshKey(prev => prev + 1);
    }
  };

  return (
    <div className="hls-player-container">
      {isStreamLoaded && (
        <div className="live-indicator">
          <div className="red-dot"></div>
          <span className="live-text">LIVE</span>
        </div>
      )}
      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <div className="loading-text">Loading stream...</div>
        </div>
      )}
      {hasError && (
        <div className="error-overlay">
          <div className="error-icon">⚠️</div>
          <div className="error-text">{errorMessage}</div>
          {errorMessage.includes("manifestLoadError") && (
            <button className="refresh-button" onClick={handleRefresh}>
              Refresh Stream
            </button>
          )}
        </div>
      )}
      <video
        ref={videoRef}
        muted
        autoPlay
        playsInline
        poster={posterUrl}
        style={{ width: '100%', height: '100%' }}
      />
      {isModalOpen && (
        <div className="volume-controls">
          <button 
            className="mute-button"
            onClick={() => setIsMuted(!isMuted)}
          >
            {isMuted ? '🔇' : volume > 0 ? '🔊' : '🔈'}
          </button>
          <input
            type="range"
            className="volume-slider"
            min="0"
            max="1"
            step="0.1"
            value={volume}
            onChange={(e) => {
              const newVolume = parseFloat(e.target.value);
              setVolume(newVolume);
              if (newVolume > 0) setIsMuted(false);
            }}
          />
        </div>
      )}
      <style jsx>{`
        .hls-player-container {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
        }
        .live-indicator {
          position: absolute;
          top: 10px;
          left: 10px;
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(0, 0, 0, 0.7);
          padding: 4px 8px;
          border-radius: 4px;
          z-index: 10;
          color: white;
        }
        .red-dot {
          width: 8px;
          height: 8px;
          background: #ff0000;
          border-radius: 50%;
          animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
          0% { opacity: 1; }
          50% { opacity: 0.5; }
          100% { opacity: 1; }
        }
        .volume-controls {
          position: absolute;
          bottom: 10px;
          right: 10px;
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(0, 0, 0, 0.7);
          padding: 8px;
          border-radius: 20px;
          z-index: 10;
        }
        .mute-button {
          background: none;
          border: none;
          cursor: pointer;
          color: white;
          font-size: 20px;
          padding: 0;
        }
        .volume-slider {
          width: 80px;
          height: 4px;
          accent-color: white;
        }
        .loading-overlay {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          background: rgba(0, 0, 0, 0.7);
          z-index: 5;
        }
        .loading-spinner {
          width: 40px;
          height: 40px;
          border: 4px solid rgba(255, 255, 255, 0.3);
          border-radius: 50%;
          border-top: 4px solid white;
          animation: spin 1s linear infinite;
        }
        .loading-text {
          color: white;
          margin-top: 10px;
          font-size: 14px;
        }
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        .error-overlay {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          background: rgba(0, 0, 0, 0.8);
          z-index: 5;
          color: white;
        }
        .error-icon {
          font-size: 32px;
          margin-bottom: 10px;
        }
        .error-text {
          text-align: center;
          max-width: 80%;
          margin-bottom: 10px;
        }
        .refresh-button {
          background: #ff4444;
          border: none;
          padding: 8px 16px;
          color: white;
          border-radius: 4px;
          cursor: pointer;
        }
        .refresh-button:hover {
          background: #ff2222;
        }
      `}</style>
    </div>
  );
};

const VideoPlayer = ({
  platform = "stripchat",
  streamerUid,
  streamerName,
  staticThumbnail,
  onDetection,
}) => {
  const [thumbnail, setThumbnail] = useState(null);
  const [isOnline, setIsOnline] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [m3u8Url, setM3u8Url] = useState(null);
  const [fetchedStreamerUsername, setFetchedStreamerUsername] = useState(null);
  const [posterUrl, setPosterUrl] = useState(null);

  // Fetch m3u8 URL based on platform and streamerName.
  useEffect(() => {
    if (platform.toLowerCase() === 'chaturbate' && streamerName) {
      const fetchM3u8Url = async () => {
        try {
          const response = await fetch(`/api/streams?platform=chaturbate&streamer=${streamerName}`);
          if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
          }
          const data = await response.json();
          if (data.length > 0 && data[0].chaturbate_m3u8_url) {
            setM3u8Url(data[0].chaturbate_m3u8_url);
          } else {
            throw new Error("No m3u8 URL found for the stream");
          }
        } catch (error) {
          console.error("Error fetching m3u8 URL for Chaturbate:", error);
          setIsOnline(false);
          const fallbackPosterUrl = `https://jpeg.live.mmcdn.com/stream?room=${streamerName}&f=${Math.random()}`;
          setPosterUrl(fallbackPosterUrl);
        } finally {
          setLoading(false);
        }
      };
      fetchM3u8Url();
    } else if (platform.toLowerCase() === 'stripchat' && streamerName) {
      const fetchM3u8Url = async () => {
        try {
          const response = await fetch(`/api/streams?platform=stripchat&streamer=${streamerName}`);
          if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
          }
          const data = await response.json();
          if (data.length > 0 && data[0].stripchat_m3u8_url) {
            setM3u8Url(data[0].stripchat_m3u8_url);
            setFetchedStreamerUsername(data[0].streamer_username);
          } else {
            throw new Error("No m3u8 URL found for the stream");
          }
        } catch (error) {
          console.error("Error fetching m3u8 URL for Stripchat:", error);
          setIsOnline(false);
        } finally {
          setLoading(false);
        }
      };
      fetchM3u8Url();
    } else {
      setLoading(false);
    }
  }, [platform, streamerName, staticThumbnail]);

  const handleThumbnailError = () => {
    setIsOnline(false);
    setThumbnail(null);
  };

  const handleModalToggle = () => {
    setIsModalOpen(!isModalOpen);
  };

  const renderPlayer = (isModal) => {
    return m3u8Url ? (
      <HlsPlayer
        m3u8Url={m3u8Url}
        isModalOpen={isModal}
        posterUrl={posterUrl}
        platform={platform}
        streamerName={streamerName}
      />
    ) : (
      <div className="error-message">No valid m3u8 URL provided for {platform}.</div>
    );
  };

  return (
    <div className="video-container">
      {loading ? (
        <div className="loading-message">Loading...</div>
      ) : thumbnail && isOnline && !isModalOpen ? (
        <div className="thumbnail-wrapper">
          <img
            src={thumbnail}
            alt="Live stream thumbnail"
            className="thumbnail-image"
            onClick={handleModalToggle}
            onError={handleThumbnailError}
          />
          {!isOnline && (
            <div className="thumbnail-live-indicator">
              <span>Offline</span>
            </div>
          )}
        </div>
      ) : (
        renderPlayer(false)
      )}

      {!loading && !isOnline && (
        <div className="error-message">
          {platform.toLowerCase() === 'stripchat'
            ? 'Stripchat stream is offline.'
            : 'Chaturbate stream is offline.'}
        </div>
      )}

      {isModalOpen && (
        <div className="modal-overlay" onClick={handleModalToggle}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            {renderPlayer(true)}
            <button className="close-modal" onClick={handleModalToggle}>
              &times;
            </button>
          </div>
        </div>
      )}

      <style jsx>{`
        .video-container {
          position: relative;
          width: 100%;
          height: 0;
          padding-top: 56.25%;
          overflow: hidden;
          background: #000;
          border-radius: 8px;
          object-fit: cover;
        }
        .loading-message {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          background: #000;
        }
        .thumbnail-wrapper {
          position: relative;
          width: 100%;
          height: 100%;
        }
        .thumbnail-image {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          object-fit: cover;
          cursor: pointer;
        }
        .thumbnail-live-indicator {
          position: absolute;
          top: 10px;
          left: 10px;
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(0, 0, 0, 0.7);
          padding: 4px 8px;
          border-radius: 4px;
          color: white;
          z-index: 2;
        }
        .error-message {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          background: rgba(0, 0, 0, 0.7);
          font-size: 1em;
          text-align: center;
          padding: 20px;
        }
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0, 0, 0, 0.8);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }
        .modal-content {
          position: relative;
          width: 90%;
          max-width: 1200px;
          background: #1a1a1a;
          border-radius: 8px;
          padding: 20px;
        }
        .close-modal {
          position: absolute;
          top: 10px;
          right: 10px;
          background: transparent;
          border: none;
          color: white;
          font-size: 24px;
          cursor: pointer;
        }
        .close-modal:hover {
          color: #ff4444;
        }
      `}</style>
    </div>
  );
};

export default VideoPlayer;
