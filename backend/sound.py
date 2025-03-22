#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import numpy as np
import librosa
from scipy import signal
import datetime
import warnings
import threading
import queue
import argparse
import whisper  # Open source ASR model by OpenAI
import pyaudio  # For real-time audio playback

warnings.filterwarnings('ignore')

# ANSI color codes for terminal output
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    
    @staticmethod
    def colorize(text, color):
        return f"{color}{text}{Colors.RESET}"

class RealTimeHLSAudioTranscriber:
    def __init__(self, hls_url, chunk_duration=3):
        """
        Initialize real-time HLS audio transcriber and detector using Whisper.
        
        Args:
            hls_url (str): URL to the M3U8 HLS stream.
            chunk_duration (int): Duration (in seconds) of each audio chunk to process.
        """
        self.hls_url = hls_url
        self.chunk_duration = chunk_duration
        self.sample_rate = 16000         # Hz
        self.channels = 1                # Mono audio
        self.sample_width = 2            # bytes per sample for PCM s16le
        self.chunk_bytes = self.sample_rate * self.sample_width * self.chunk_duration
        
        # Load Whisper model (using "base"; adjust as needed)
        try:
            print(f"{Colors.CYAN}[i] Loading Whisper model...{Colors.RESET}")
            self.whisper_model = whisper.load_model("base")
            print(f"{Colors.GREEN}[+] Whisper model loaded successfully{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}[!] Error loading Whisper model: {e}{Colors.RESET}")
            sys.exit(1)
        
        # Queue and thread for asynchronous transcription
        self.transcription_queue = queue.Queue()
        self.transcription_thread = threading.Thread(target=self._transcription_worker)
        self.transcription_thread.daemon = True
        self.transcription_thread.start()
        
        # Counters for sound detection summary
        self.sound_counters = {
            "silence": 0,
            "speech": 0,
            "music": 0,
            "alarm_or_alert": 0,
            "environmental_sound": 0,
            "impact_or_explosion": 0,
            "unknown_sound": 0
        }
        self.transcriptions = []
        
        # Initialize PyAudio for real-time playback
        self.pyaudio_instance = pyaudio.PyAudio()
        self.audio_stream = self.pyaudio_instance.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            output=True
        )
        
        self._print_banner()
    
    def _print_banner(self):
        """Print a startup banner"""
        banner = f"""
{Colors.BOLD}{Colors.BLUE}╔══════════════════════════════════════════════════════════╗
║       REAL-TIME HLS AUDIO DETECTOR & TRANSCRIPTION           ║
╚══════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.CYAN}Stream URL: {self.hls_url}
Chunk Duration: {self.chunk_duration} sec
Sample Rate: {self.sample_rate} Hz{Colors.RESET}

{Colors.YELLOW}[i] Press Ctrl+C to stop processing{Colors.RESET}
"""
        print(banner)
    
    def _transcription_worker(self):
        """Worker thread for processing transcription tasks from in-memory audio chunks."""
        while True:
            try:
                audio_chunk_np = self.transcription_queue.get()
                self._transcribe_audio(audio_chunk_np)
                self.transcription_queue.task_done()
            except Exception as e:
                print(f"{Colors.RED}[!] Error in transcription worker: {e}{Colors.RESET}")
    
    def _transcribe_audio(self, audio_np):
        """
        Transcribe speech from the given NumPy audio array using Whisper.
        The array is expected to be a 1D float32 NumPy array sampled at 16kHz.
        """
        try:
            # Pad or trim the audio to fit Whisper's input length requirements.
            audio_input = whisper.pad_or_trim(audio_np)
            # Compute the log-mel spectrogram
            mel = whisper.log_mel_spectrogram(audio_input).to(self.whisper_model.device)
            options = whisper.DecodingOptions(fp16=False)
            result = whisper.decode(self.whisper_model, mel, options)
            text = result.text.strip()
            if text:
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                self.transcriptions.append({'timestamp': timestamp, 'text': text})
                print(f"\n{Colors.BOLD}{Colors.GREEN}╔═ TRANSCRIPTION at {timestamp} ════════════════════════╗{Colors.RESET}")
                print(f"{Colors.GREEN}║ \"{text}\"{Colors.RESET}")
                print(f"{Colors.BOLD}{Colors.GREEN}╚═══════════════════════════════════════════════════╝{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}[!] Transcription error: {e}{Colors.RESET}")
    
    def _analyze_audio(self, audio_np):
        """
        Analyze audio features from a NumPy array.
        Args:
            audio_np (np.ndarray): 1D float32 NumPy array of audio samples.
        Returns:
            dict: Dictionary of extracted audio features.
        """
        try:
            y = audio_np
            sr = self.sample_rate
            rms = librosa.feature.rms(y=y)[0].mean()
            zcr = librosa.feature.zero_crossing_rate(y)[0].mean()
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0].mean()
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0].mean()
            rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0].mean()
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfcc_means = np.mean(mfccs, axis=1)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)[0]
            peak_indices = signal.find_peaks(np.abs(y), height=0.5, distance=sr//4)[0]
            peak_count = len(peak_indices)
            return {
                'rms_energy': float(rms),
                'zero_crossing_rate': float(zcr),
                'spectral_centroid': float(spectral_centroid),
                'spectral_bandwidth': float(spectral_bandwidth),
                'spectral_rolloff': float(rolloff),
                'mfcc_means': mfcc_means.tolist(),
                'tempo': float(tempo),
                'peak_count': peak_count
            }
        except Exception as e:
            print(f"{Colors.RED}[!] Error analyzing audio: {e}{Colors.RESET}")
            return None
    
    def _classify_audio(self, features):
        """
        Simple rule-based classification based on extracted audio features.
        Returns:
            str: Detected sound type.
        """
        if features is None:
            return "unknown_sound"
        rms = features['rms_energy']
        zcr = features['zero_crossing_rate']
        centroid = features['spectral_centroid']
        bandwidth = features['spectral_bandwidth']
        peak_count = features['peak_count']
        tempo = features['tempo']
        if rms < 0.01:
            return "silence"
        if 0.02 < rms < 0.2 and zcr > 0.05:
            return "speech"
        if tempo > 50 and 0.02 < rms < 0.3:
            return "music"
        if rms > 0.2 and centroid > 3000 and peak_count > 5:
            return "alarm_or_alert"
        if rms > 0.05 and bandwidth > 2000:
            return "environmental_sound"
        if peak_count > 10 and rms > 0.3:
            return "impact_or_explosion"
        return "unknown_sound"
    
    def _print_sound_detection(self, sound_type, features):
        """Print sound detection results in a formatted output."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        color_map = {
            "silence": Colors.RESET,
            "speech": Colors.GREEN,
            "music": Colors.CYAN,
            "alarm_or_alert": Colors.RED,
            "environmental_sound": Colors.BLUE,
            "impact_or_explosion": Colors.MAGENTA,
            "unknown_sound": Colors.YELLOW
        }
        color = color_map.get(sound_type, Colors.RESET)
        self.sound_counters[sound_type] += 1
        rms = features['rms_energy']
        intensity_level = min(int(rms * 100), 20)
        intensity_bar = "█" * intensity_level
        print(f"\n{Colors.BOLD}{color}╔═ SOUND DETECTED at {timestamp} ═══════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOLD}{color}║ Type: {sound_type.upper()}{' ' * (42 - len(sound_type))}{Colors.RESET}")
        print(f"{color}║ Intensity: [{intensity_bar}{' ' * (20 - intensity_level)}] {rms:.4f} RMS{Colors.RESET}")
        if sound_type == "speech":
            print(f"{color}║ Speech characteristics: ZCR={features['zero_crossing_rate']:.4f}{Colors.RESET}")
        elif sound_type == "music":
            print(f"{color}║ Musical tempo: {features['tempo']:.2f} BPM{Colors.RESET}")
        elif sound_type == "alarm_or_alert":
            print(f"{color}║ Alert frequency: {features['spectral_centroid']:.2f} Hz{Colors.RESET}")
        elif sound_type == "impact_or_explosion":
            print(f"{color}║ Impact peaks: {features['peak_count']}{Colors.RESET}")
        print(f"{Colors.BOLD}{color}╚═══════════════════════════════════════════════════╝{Colors.RESET}")
    
    def process_stream(self):
        """
        Process the HLS stream in real time:
         - Uses FFmpeg to output raw PCM audio from the m3u8 stream.
         - Plays audio using PyAudio.
         - Processes each chunk in memory for audio analysis and transcription.
        """
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', self.hls_url,
            '-f', 's16le',          # Raw PCM format
            '-acodec', 'pcm_s16le',   # PCM 16-bit little endian
            '-ar', str(self.sample_rate),
            '-ac', str(self.channels),
            '-'
        ]
        try:
            process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"{Colors.RED}[!] Failed to start FFmpeg: {e}{Colors.RESET}")
            return
        
        print(f"{Colors.CYAN}[i] Starting real-time processing...{Colors.RESET}")
        try:
            while True:
                # Read a chunk of raw audio data from FFmpeg (in-memory)
                audio_chunk = process.stdout.read(self.chunk_bytes)
                if not audio_chunk or len(audio_chunk) < self.chunk_bytes:
                    continue  # insufficient data, skip
                
                # Play the audio chunk in real time
                self.audio_stream.write(audio_chunk)
                
                # Convert raw PCM bytes to NumPy array (int16) then normalize to float32 in range [-1,1]
                audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
                audio_float = audio_int16.astype(np.float32) / 32768.0
                
                # Analyze audio features from the in-memory array
                features = self._analyze_audio(audio_float)
                if features:
                    sound_type = self._classify_audio(features)
                    self._print_sound_detection(sound_type, features)
                    
                    # Queue for transcription if sound is classified as speech
                    if sound_type == "speech":
                        self.transcription_queue.put(audio_float)
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}[i] Stopping real-time processing{Colors.RESET}")
        finally:
            self._print_summary()
            self.cleanup()
    
    def _print_summary(self):
        """Print a summary of detected sounds and transcriptions."""
        print(f"\n{Colors.BOLD}{Colors.BLUE}╔══════════════════════════════════════════════════════════╗")
        print("║                   DETECTION SUMMARY                    ║")
        print("╚══════════════════════════════════════════════════════════╝" + Colors.RESET)
        for sound_type, count in self.sound_counters.items():
            if count > 0:
                print(f"{Colors.CYAN}{sound_type.upper()}: {count} occurrences{Colors.RESET}")
        if self.transcriptions:
            print(f"\n{Colors.BOLD}{Colors.GREEN}╔══════════════════════════════════════════════════════════╗")
            print("║                TRANSCRIPTION SUMMARY                  ║")
            print("╚══════════════════════════════════════════════════════════╝" + Colors.RESET)
            for trans in self.transcriptions:
                print(f"{Colors.GREEN}[{trans['timestamp']}] {trans['text']}{Colors.RESET}")
    
    def cleanup(self):
        """Clean up audio resources."""
        try:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.pyaudio_instance.terminate()
        except Exception as e:
            print(f"{Colors.RED}[!] Error closing audio stream: {e}{Colors.RESET}")

def process_local_video(video_path):
    """
    Process a local MP4 video:
    - This mode extracts audio and processes it (using temporary files).
      (Local mode is kept for testing purposes.)
    """
    temp_dir = os.path.join(os.path.dirname(video_path), "temp_audio")
    os.makedirs(temp_dir, exist_ok=True)
    wav_path = os.path.join(temp_dir, "extracted_audio.wav")
    
    print(f"{Colors.CYAN}[i] Extracting audio from {video_path}...{Colors.RESET}")
    try:
        command = [
            'ffmpeg',
            '-i', video_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            '-y',
            wav_path
        ]
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"{Colors.GREEN}[+] Audio extraction complete: {wav_path}{Colors.RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}[!] Error extracting audio: {e}{Colors.RESET}")
        return
    
    try:
        print(f"{Colors.CYAN}[i] Loading Whisper model...{Colors.RESET}")
        model = whisper.load_model("base")
        print(f"{Colors.GREEN}[+] Whisper model loaded successfully{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}[!] Error loading Whisper model: {e}{Colors.RESET}")
        return
    
    try:
        print(f"{Colors.CYAN}[i] Transcribing audio...{Colors.RESET}")
        result = model.transcribe(wav_path)
        text = result.get("text", "").strip()
        if text:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"\n{Colors.BOLD}{Colors.GREEN}╔═ TRANSCRIPTION at {timestamp} ════════════════════════╗{Colors.RESET}")
            print(f"{Colors.GREEN}║ \"{text}\"{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.GREEN}╚═══════════════════════════════════════════════════╝{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}[i] No transcription obtained.{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}[!] Transcription error: {e}{Colors.RESET}")
    
    try:
        os.remove(wav_path)
        os.rmdir(temp_dir)
        print(f"{Colors.GREEN}[+] Cleaned up temporary files.{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}[!] Error during cleanup: {e}{Colors.RESET}")

def main():
    parser = argparse.ArgumentParser(description="Real-Time Audio Detector with Transcription")
    parser.add_argument("mode", choices=["hls", "local"], help="Mode: 'hls' for real-time HLS stream, 'local' for local MP4 video")
    parser.add_argument("source", help="HLS URL or local MP4 file path")
    parser.add_argument("--duration", type=int, default=0, help="(Optional) Duration for processing (in seconds)")
    args = parser.parse_args()
    
    if args.mode == "hls":
        transcriber = RealTimeHLSAudioTranscriber(args.source)
        transcriber.process_stream()
    elif args.mode == "local":
        if not os.path.isfile(args.source):
            print(f"{Colors.RED}[!] File not found: {args.source}{Colors.RESET}")
            sys.exit(1)
        process_local_video(args.source)

if __name__ == "__main__":
    main()
