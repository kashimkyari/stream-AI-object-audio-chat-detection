import React, { useState, useEffect, useRef } from 'react';
import Hls from 'hls.js';
import axios from 'axios';
import * as tf from '@tensorflow/tfjs';
import * as cocossd from '@tensorflow-models/coco-ssd';

const HlsPlayer = ({ m3u8Url, onDetection, isModalOpen, posterUrl }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  // Playback states
  const [isMuted, setIsMuted] = useState(true);
  const [volume, setVolume] = useState(0);
  const [isStreamLoaded, setIsStreamLoaded] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [model, setModel] = useState(null); // TensorFlow model state

  // To throttle server calls and reduce load on the client
  const [detectionCooldown, setDetectionCooldown] = useState(false);

  // Load TensorFlow model
  useEffect(() => {
    const loadModel = async () => {
      try {
        const cocoModel = await cocossd.load();
        setModel(cocoModel);
      } catch (err) {
        console.error("Error loading TensorFlow model:", err);
      }
    };
    loadModel();
  }, []);

  // Sync volume and mute state with the video element
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.muted = isMuted;
      videoRef.current.volume = volume;
    }
  }, [isMuted, volume]);

  // Visual detection: capture frames and perform TensorFlow detection
  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !model) return;

    const ctx = canvas.getContext('2d');
    let detectionInterval;

    // Update canvas size to match video dimensions
    const updateCanvasSize = () => {
      if (!video.parentElement) return;
      const rect = video.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    };

    // Perform TensorFlow object detection
    const detectObjects = async () => {
      try {
        if (video.videoWidth === 0 || video.videoHeight === 0) return;
        updateCanvasSize();

        // Capture frame and convert to image
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = canvas.toDataURL('image/jpeg');

        if (!detectionCooldown) {
          setDetectionCooldown(true);

          // Run TensorFlow detection
          const img = new Image();
          img.src = imageData;
          await img.decode();
          const predictions = await model.detect(img);

          // Draw detections on canvas
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          predictions.forEach(pred => {
            const [x, y, width, height] = pred.bbox;
            ctx.strokeStyle = '#FF0000';
            ctx.lineWidth = 2;
            ctx.strokeRect(x, y, width, height);
            ctx.fillStyle = '#FF0000';
            ctx.font = '14px Arial';
            ctx.fillText(
              `${pred.class} (${Math.round(pred.score * 100)}%)`,
              x,
              y > 10 ? y - 5 : 10
            );
          });

          // Get annotated image
          const annotatedImage = canvas.toDataURL('image/jpeg');

          // Send detection data to backend
          await axios.post('/api/detect-objects', {
            stream_url: m3u8Url,
            timestamp: new Date().toISOString(),
            detections: predictions.map(p => ({
              class: p.class,
              confidence: p.score,
              bbox: p.bbox,
            })),
            annotated_image: annotatedImage,
            captured_image: imageData,
          });

          if (onDetection) onDetection(predictions);
          setTimeout(() => setDetectionCooldown(false), 10000);
        }
      } catch (err) {
        console.error("Detection error:", err);
      }
    };

    const handlePlay = () => {
      updateCanvasSize();
      detectionInterval = setInterval(detectObjects, 1000); // Trigger detection every second
    };

    const handlePause = () => {
      clearInterval(detectionInterval);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    };

    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('ended', handlePause);

    return () => {
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
      video.removeEventListener('ended', handlePause);
      clearInterval(detectionInterval);
    };
  }, [onDetection, m3u8Url, detectionCooldown, model]);

  // HLS player initialization with proper cleanup
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
    return () => {
      if (hls) {
        hls.destroy();
      }
    };
  }, [m3u8Url]);

  return (
    <div className="hls-player-container">
      {/* Live Indicator */}
      {isStreamLoaded && (
        <div className="live-indicator">
          <div className="red-dot"></div>
          <span className="live-text">LIVE</span>
        </div>
      )}

      {/* Volume Controls (displayed in modal view) */}
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

      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
        }}
      />

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
  const [posterUrl, setPosterUrl] = useState(null); // Fallback poster URL

  // Fetch the m3u8 URL based on the platform and streamer name with proper cleanup
  useEffect(() => {
    const abortController = new AbortController();
    if (platform.toLowerCase() === 'chaturbate' && streamerName) {
      const fetchM3u8Url = async () => {
        try {
          const response = await fetch(
            `/api/streams?platform=chaturbate&streamer=${streamerName}`,
            { signal: abortController.signal }
          );
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
          if (error.name !== 'AbortError') {
            console.error("Error fetching m3u8 URL for Chaturbate:", error);
            setIsOnline(false);
            // Use a fallback poster URL if the stream is unavailable
            const fallbackPosterUrl = `https://jpeg.live.mmcdn.com/stream?room=${streamerName}&f=${Math.random()}`;
            setPosterUrl(fallbackPosterUrl);
          }
        } finally {
          setLoading(false);
        }
      };
      fetchM3u8Url();
    } else if (platform.toLowerCase() === 'stripchat' && streamerName) {
      const fetchM3u8Url = async () => {
        try {
          const response = await fetch(
            `/api/streams?platform=stripchat&streamer=${streamerName}`,
            { signal: abortController.signal }
          );
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
          if (error.name !== 'AbortError') {
            console.error("Error fetching m3u8 URL for Stripchat:", error);
            setIsOnline(false);
          }
        } finally {
          setLoading(false);
        }
      };
      fetchM3u8Url();
    } else {
      setLoading(false);
    }
    return () => {
      abortController.abort();
    };
  }, [platform, streamerName, staticThumbnail]);

  const handleThumbnailError = () => {
    setIsOnline(false);
    setThumbnail(null);
  };

  const handleModalToggle = () => {
    setIsModalOpen(!isModalOpen);
  };

  const renderPlayer = (isModal) => {
    if (platform.toLowerCase() === 'stripchat') {
      return m3u8Url ? (
        <HlsPlayer
          m3u8Url={m3u8Url}
          onDetection={onDetection}
          isModalOpen={isModal}
          posterUrl={posterUrl}
        />
      ) : (
        <div className="error-message">No valid m3u8 URL provided for Stripchat.</div>
      );
    }
    if (platform.toLowerCase() === 'chaturbate') {
      return m3u8Url ? (
        <HlsPlayer
          m3u8Url={m3u8Url}
          onDetection={onDetection}
          isModalOpen={isModal}
          posterUrl={posterUrl}
        />
      ) : (
        <div className="error-message">No valid m3u8 URL provided for Chaturbate.</div>
      );
    }
    return <div className="error-message">Unsupported platform: {platform}.</div>;
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