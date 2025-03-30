import React, { useState, useEffect } from 'react';
import Hls from 'hls.js';
import axios from 'axios';
import './VideoPlayer.css';

const HlsPlayer = ({ 
  m3u8Url, 
  isModalOpen, 
  posterUrl, 
  platform, 
  streamerName, 
  onError,
  onRefresh,
  loading 
}) => {
  const videoRef = React.useRef(null);
  const [isStreamLoaded, setIsStreamLoaded] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isMuted, setIsMuted] = useState(true);
  const [volume, setVolume] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  // Update video properties when mute or volume changes
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.muted = isMuted;
      videoRef.current.volume = volume;
    }
  }, [isMuted, volume]);

  // Initialize HLS player and attach error handling for m3u8 fetch failures
  useEffect(() => {
    let hls;
    if (!m3u8Url) {
      setIsLoading(false);
      setHasError(true);
      setErrorMessage("Invalid stream URL");
      onError?.(true);
      return;
    }

    const initializePlayer = () => {
      if (Hls.isSupported()) {
        hls = new Hls({ 
          autoStartLoad: true, 
          startLevel: -1, 
          debug: false 
        });
        hls.loadSource(m3u8Url);
        hls.attachMedia(videoRef.current);

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          setIsLoading(false);
          setIsStreamLoaded(true);
          videoRef.current.play().catch(console.error);
        });

        // Handle errors specifically related to fetching the m3u8 (manifest)
        hls.on(Hls.Events.ERROR, (event, data) => {
          // If a fatal error related to the manifest load occurs, mark offline
          if (data.fatal && data.type === Hls.ErrorTypes.NETWORK_ERROR && data.details === Hls.ErrorDetails.MANIFEST_LOAD_ERROR) {
            setHasError(true);
            setIsLoading(false);
            setErrorMessage(data.details || 'Playback error');
            onError?.(true);
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
        onError?.(true);
      }
    };

    initializePlayer();
    return () => hls?.destroy();
  }, [m3u8Url, refreshKey, onError]);

  const handleRefresh = async () => {
    setHasError(false);
    setIsLoading(true);
    setErrorMessage("");
    try {
      await onRefresh();
      setRefreshKey(prev => prev + 1);
    } catch (error) {
      setErrorMessage("Error refreshing stream");
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

      {(isLoading || loading) && (
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <div className="loading-text">Loading stream...</div>
        </div>
      )}

      {hasError && (
        <div className="interactive-overlay" onClick={handleRefresh}>
          <div className="offline-content">
            <img 
              src={posterUrl || '/default-thumbnail.jpg'} 
              alt="Stream preview" 
              className="offline-thumbnail"
            />
            <div className="offline-message">
              <div className="offline-icon">🔴</div>
              <h3>Stream Offline</h3>
              <p>We're trying to reconnect automatically</p>
              <button 
                className="refresh-button interactive-button"
                onClick={handleRefresh}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <span className="spinner"></span>
                    Refreshing...
                  </>
                ) : (
                  'Try Now'
                )}
              </button>
              <div className="retry-timer">
                <div className="timer-bar" style={{ width: `${loading ? 100 : 0}%` }}></div>
              </div>
            </div>
          </div>
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
            aria-label={isMuted ? "Unmute" : "Mute"}
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
            aria-label="Volume control"
          />
        </div>
      )}
    </div>
  );
};

const VideoPlayer = ({
  platform = "stripchat",
  streamerName,
  staticThumbnail,
}) => {
  const [isOnline, setIsOnline] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [m3u8Url, setM3u8Url] = useState(null);
  const [posterUrl, setPosterUrl] = useState(null);
  const [videoHasError, setVideoHasError] = useState(false);
  const [lastChecked, setLastChecked] = useState(new Date());

  // Ensure modal remains closed if offline or error exists
  useEffect(() => {
    if (!isOnline || videoHasError) {
      setIsModalOpen(false);
    }
  }, [isOnline, videoHasError]);

  // Fetch stream URL without explicitly triggering offline state for API errors
  useEffect(() => {
    const fetchM3u8Url = async () => {
      try {
        const endpoint = `/api/streams?platform=${platform}&streamer=${streamerName}`;
        const response = await fetch(endpoint);
        
        // Even if the API returns a 404 or error, we do not mark the stream offline here.
        // Instead, we let the HLS player determine if the m3u8 cannot be fetched.
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const data = await response.json();
        const urlKey = platform === 'chaturbate' ? 'chaturbate_m3u8_url' : 'stripchat_m3u8_url';
        
        if (data.length > 0 && data[0][urlKey]) {
          setM3u8Url(data[0][urlKey]);
          setPosterUrl(staticThumbnail);
          setIsOnline(true);
          setVideoHasError(false);
        } else {
          // No valid m3u8 URL; let HlsPlayer handle the error state
          setM3u8Url(null);
        }
      } catch (error) {
        console.error(`Error fetching ${platform} stream:`, error);
        // Do not set offline state here; the HLS player will display the error if m3u8 fails to load.
        setM3u8Url(null);
      } finally {
        setLoading(false);
        setLastChecked(new Date());
      }
    };

    if (streamerName) fetchM3u8Url();
  }, [platform, streamerName, staticThumbnail]);

  const handleRefresh = async () => {
    try {
      setLoading(true);
      let response;
      
      if (platform === 'chaturbate') {
        response = await axios.post('/api/streams/refresh/chaturbate', {
          room_slug: streamerName
        });
      } else if (platform === 'stripchat') {
        const roomUrl = `https://stripchat.com/${streamerName}/`;
        response = await axios.post('/api/streams/refresh/stripchat', {
          room_url: roomUrl
        });
      }

      if (response?.data?.m3u8_url) {
        setM3u8Url(response.data.m3u8_url);
        setIsOnline(true);
        setVideoHasError(false);
      }
    } catch (error) {
      console.error("Refresh failed:", error);
      setIsOnline(false);
      setVideoHasError(true);
    } finally {
      setLoading(false);
      setLastChecked(new Date());
    }
  };

  // Allow modal toggle only when the stream is live (i.e. online and without errors)
  const handleModalToggle = () => {
    if (isOnline && !videoHasError) {
      setIsModalOpen(!isModalOpen);
    }
  };

  return (
    <div className="video-container">
      {loading ? (
        <div className="loading-state">
          <div className="loading-animation"></div>
          <p>Checking stream status...</p>
        </div>
      ) : (
        <>
          {isOnline && !videoHasError ? (
            <div className="stream-wrapper" onClick={handleModalToggle}>
              <HlsPlayer
                m3u8Url={m3u8Url}
                isModalOpen={isModalOpen}
                posterUrl={posterUrl}
                platform={platform}
                streamerName={streamerName}
                onError={(error) => {
                  setVideoHasError(error);
                  setIsOnline(!error);
                }}
                onRefresh={handleRefresh}
                loading={loading}
              />
              
              {!isModalOpen && (
                <div className="thumbnail-overlay">
                  <span className="click-to-expand">Click to expand</span>
                </div>
              )}
            </div>
          ) : (
            <div className="interactive-offline">
              <div className="offline-card">
                <div className="platform-icon">
                  {platform === 'chaturbate' ? '🎥' : '📡'}
                </div>
                <h3>{streamerName} is Offline</h3>
                <p className="last-checked">
                  Last checked: {lastChecked.toLocaleTimeString()}
                </p>
                <div className="action-buttons">
                  <button 
                    className="refresh-button" 
                    onClick={handleRefresh}
                    disabled={loading}
                  >
                    {loading ? 'Checking...' : 'Check Again'}
                  </button>
                  <button 
                    className="notify-button"
                    onClick={() => {/* Implement notification logic */}
                    }
                  >
                    Notify Me When Live
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default VideoPlayer;
