# Yeux

> AI-powered eye tracking and human-computer interaction (HCI) research project by Lukintosh.

## Overview

Yeux is an experimental eye-tracking system that enables hands-free computer interaction using standard webcams, computer vision, and artificial intelligence.

The project explores alternative input methods, accessibility technologies, gaze estimation, and next-generation human-computer interaction.

## Features

- 👀 Webcam-based eye tracking
- 🧠 AI-assisted gaze estimation
- 🎯 Face landmark detection
- 🖱️ Cursor control through eye movement
- ♿ Accessibility-focused design
- ⚡ ONNX Runtime + DirectML acceleration
- 🔬 Human-Computer Interaction research

## Technologies

- Python
- MediaPipe Face Landmarker
- ONNX Runtime
- DirectML
- Computer Vision
- Machine Learning
- Human-Computer Interaction (HCI)

## Repository Structure

```text
.
├── *.py
├── face_landmarker.task
├── hand_landmarker.task
├── directml_test.onnx
├── README.md
└── LICENSE
```

## Models

This repository includes:

- `face_landmarker.task`
- `hand_landmarker.task`
- `directml_test.onnx`

Large model files are managed using Git LFS.

## Installation

Clone the repository:

```bash
git clone https://github.com/LukintoshCorp/yeux.git
cd yeux
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the main application:

```bash
python main.py
```

Or execute individual scripts as needed.

## Goals

Yeux aims to provide:

- Accessible computing experiences
- Alternative input systems
- Eye-based cursor control
- AI-powered interaction methods
- Research into future computer interfaces

## Status

```text
Project Status: Active Development
Stage: Experimental
Maintainer: Lukintosh
```

## Roadmap

- [ ] Improved gaze estimation
- [ ] Better blink detection
- [ ] Calibration system
- [ ] Multi-monitor support
- [ ] Accessibility enhancements
- [ ] Open-source community contributions

## Contributing

Contributions, bug reports, and feature requests are welcome.

## License

License information will be added in a future release.

## About Lukintosh

Lukintosh develops software, AI solutions, developer tools, digital platforms, and human-computer interaction technologies.

Website: https://www.lukintosh.com
