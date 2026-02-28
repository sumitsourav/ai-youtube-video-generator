# AI YouTube Video Generator

An automated Python application that generates complete YouTube videos using AI technology. The tool orchestrates AI-powered script generation, text-to-speech conversion, image creation, and video composition into polished YouTube-ready content.

## 🎯 Project Overview

This project implements a modular pipeline for creating videos end-to-end:
1. **Script Generation** - Creates video scripts from topics/prompts
2. **Text-to-Speech (TTS)** - Converts scripts to natural-sounding audio
3. **Image Generation** - Creates relevant visual content
4. **Video Composition** - Assembles audio, images, and effects into final video

## 📋 Features

- ✅ Fully automated video generation pipeline
- ✅ AI-powered script and content creation
- ✅ Natural language text-to-speech synthesis
- ✅ Intelligent image generation and sourcing
- ✅ Professional video composition with MoviePy
- ✅ Modular service-oriented architecture
- ✅ Configurable parameters and settings
- ✅ Docker containerization support
- ✅ Asset management (audio, images, videos)

## 📁 Project Structure

```
.
├── app/                              # Main application code
│   ├── __init__.py                   # Package initialization
│   ├── main.py                       # Main entry point
│   ├── config.py                     # Configuration management
│   ├── services/                     # Core service modules
│   │   ├── script_service.py         # AI script generation
│   │   ├── tts_service.py            # Text-to-speech synthesis
│   │   ├── image_service.py          # Image generation/sourcing
│   │   └── video_service.py          # Video composition and assembly
│   └── utils/                        # Utility functions
│       └── file_utils.py             # File I/O operations
├── assets/                           # Generated and source assets
│   ├── audio/                        # Generated audio files
│   ├── images/                       # Generated images
│   └── videos/                       # Output video files
├── requirements.txt                  # Python dependencies
├── Dockerfile                        # Container configuration
└── README.md                         # This file
```

## ⚙️ Architecture

### Service Components

**Script Service** (`app/services/script_service.py`)
- Generates engaging video scripts from topics or prompts
- Handles content structuring and outline generation
- Ensures scripts are optimized for spoken delivery

**TTS Service** (`app/services/tts_service.py`)
- Converts scripts to natural-sounding audio
- Supports multiple voices and languages
- Generates timing metadata for synchronization

**Image Service** (`app/services/image_service.py`)
- Generates relevant images for visual content
- Can source from APIs or generate using AI models
- Manages image preprocessing and optimization

**Video Service** (`app/services/video_service.py`)
- Composes final videos from audio and images
- Handles synchronization and timing
- Applies transitions, effects, and formatting
- Exports to YouTube-ready formats

### Data Flow

```
Topic/Prompt
    ↓
[Script Service] → Script with timing
    ↓
[TTS Service] → Audio file + timing info
    ↓
[Image Service] → Images/visuals
    ↓
[Video Service] → Final YouTube video
    ↓
Output: assets/videos/
```

## 🚀 Installation

### Prerequisites
- Python 3.8+
- FFmpeg (for video processing)
- pip (Python package manager)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "Ai youtube video generator"
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   - Copy `.env.example` to `.env` (if available)
   - Set required API keys and configuration values
   - See Configuration section below

4. **Verify installation**
   ```bash
   python app/main.py --help
   ```

## 📦 Dependencies

Key packages (see `requirements.txt`):
- **moviepy** - Video composition and editing
- **requests** - HTTP requests for API calls
- **TTS** - Text-to-speech synthesis (gTTS/pyttsx3 alternative)
- **python-dotenv** - Environment configuration management

## ⚙️ Configuration

Create a `.env` file in the project root with these settings:

```env
# API Keys (if using AI services)
OPENAI_API_KEY=your_key_here
HUGGINGFACE_API_KEY=your_key_here

# Output settings
OUTPUT_QUALITY=1080p
FRAMERATE=30
BITRATE=5000k

# TTS Settings
TTS_VOICE=default
TTS_LANGUAGE=en

# Asset paths
ASSETS_DIR=./assets
OUTPUT_DIR=./assets/videos
```

## 💻 Usage

### Basic Video Generation

```python
from app.services.script_service import ScriptService
from app.services.tts_service import TTSService
from app.services.image_service import ImageService
from app.services.video_service import VideoService

# Initialize services
script_service = ScriptService()
tts_service = TTSService()
image_service = ImageService()
video_service = VideoService()

# Generate video
topic = "Introduction to Python"
script = script_service.generate_script(topic)
audio = tts_service.generate_audio(script)
images = image_service.generate_images(topic)
video = video_service.compose_video(audio, images)
```

### Command Line Usage

```bash
# Generate video from topic
python app/main.py generate --topic "Your Topic" --output output.mp4

# Use existing script
python app/main.py generate --script script.txt --output output.mp4

# Show available options
python app/main.py --help
```

## 📂 Asset Management

Generated assets are organized as follows:

- **`assets/audio/`** - TTS audio files and voice synthesis outputs
- **`assets/images/`** - Generated or sourced images for video content
- **`assets/videos/`** - Final video outputs ready for YouTube upload

## 🐳 Docker Support

Build and run the application in a container:

```bash
# Build image
docker build -t ai-youtube-generator .

# Run container
docker run --env-file .env -v $(pwd)/assets:/app/assets ai-youtube-generator
```

## 📝 Development

### File Utilities

Utility functions in `app/utils/file_utils.py`:
- File creation and removal
- Directory management
- Asset organization
- Cleanup operations

### Main Entry Point

The `app/main.py` file serves as the primary entry point:
- Handles command-line arguments
- Orchestrates service initialization
- Manages the complete video generation pipeline

## 🔧 Troubleshooting

### FFmpeg Not Found
Ensure FFmpeg is installed and in your system PATH:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (via Chocolatey)
choco install ffmpeg
```

### API Key Issues
Ensure `.env` file is properly configured with valid API keys for any external services used.

### Audio Synchronization Issues
Check that TTS service provides accurate timing metadata for proper video-audio sync.

## 📋 Requirements

See `requirements.txt` for a complete list of dependencies. Key requirements:
- moviepy>=1.0.0 - Video processing
- requests>=2.25.0 - HTTP client
- TTS - Text-to-speech engine
- python-dotenv - Configuration management

## 📄 License

[Add license information here]

## 🤝 Contributing

[Add contribution guidelines here]

## 📧 Support

For issues and questions:
- Open an issue in the repository
- Check existing documentation and examples
- Review service implementations for usage patterns

## 🎬 Next Steps

1. Implement core service modules
2. Add configuration validation
3. Create example scripts
4. Add error handling and logging
5. Build comprehensive test suite
6. Optimize video rendering performance
