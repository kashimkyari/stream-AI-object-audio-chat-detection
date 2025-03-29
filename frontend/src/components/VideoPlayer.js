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
  onRefresh 
}) => {
  const videoRef = React.useRef(null);
  const [isStreamLoaded, setIsStreamLoaded] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isMuted, setIsMuted] = useState(true);
  const [volume, setVolume] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.muted = isMuted;
      videoRef.current.volume = volume;
    }
  }, [isMuted, volume]);

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

        hls.on(Hls.Events.ERROR, (event, data) => {
          if (data.fatal) {
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

  useEffect(() => {
    if (isStreamLoaded && m3u8Url) {
      axios.post('/api/trigger-detection', {
        stream_url: m3u8Url,
        timestamp: new Date().toISOString(),
        platform: platform,
        streamer_name: streamerName
      }).catch(console.error);
    }
  }, [isStreamLoaded, m3u8Url, platform, streamerName]);

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
          {(platform === 'chaturbate' || platform === 'stripchat') && (
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

  useEffect(() => {
    if (!isOnline || videoHasError) {
      setIsModalOpen(false);
    }
  }, [isOnline, videoHasError]);

  useEffect(() => {
    const fetchM3u8Url = async () => {
      try {
        const endpoint = `/api/streams?platform=${platform}&streamer=${streamerName}`;
        const response = await fetch(endpoint);
        
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        
        const data = await response.json();
        const urlKey = platform === 'chaturbate' ? 'chaturbate_m3u8_url' : 'stripchat_m3u8_url';
        
        if (data.length > 0 && data[0][urlKey]) {
          setM3u8Url(data[0][urlKey]);
          setPosterUrl(staticThumbnail);
          setIsOnline(true);
          setVideoHasError(false);
        } else {
          throw new Error("No M3U8 URL found");
        }
      } catch (error) {
        console.error(`Error fetching ${platform} stream:`, error);
        setIsOnline(false);
        setVideoHasError(true);
        setPosterUrl(`https://jpeg.live.mmcdn.com/stream?room=${streamerName}&f=${Math.random()}`);
      } finally {
        setLoading(false);
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
    }
  };

  const handleModalToggle = () => {
    if (isOnline && !videoHasError) {
      setIsModalOpen(!isModalOpen);
    }
  };

  return (
    <div className="video-container">
      {loading ? (
        <div className="loading-message">Loading...</div>
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
              />
              
              {!isModalOpen && (
                <div className="thumbnail-overlay">
                  <span className="click-to-expand">Click to expand</span>
                </div>
              )}
            </div>
          ) : (
            <div className="error-state">
              <div className="error-message">
                {platform === 'stripchat' 
                  ? 'Stripchat stream is offline' 
                  : 'Chaturbate stream is offline'}
              </div>
              <button 
                className="refresh-button" 
                onClick={handleRefresh}
                disabled={loading}
              >
                {loading ? 'Refreshing...' : 'Try Refresh'}
              </button>
            </div>
          )}

          {isModalOpen && (
            <div className="modal-overlay" onClick={handleModalToggle}>
              <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                <HlsPlayer
                  m3u8Url={m3u8Url}
                  isModalOpen={true}
                  posterUrl={posterUrl}
                  platform={platform}
                  streamerName={streamerName}
                  onError={setVideoHasError}
                  onRefresh={handleRefresh}
                />
                <button className="close-modal" onClick={handleModalToggle}>
                  &times;
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default VideoPlayer;