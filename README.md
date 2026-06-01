# ProtoPlanner
.

📂 README.md
Markdown
# 🛠️ Perfboard Planner

Perfboard Planner is a lightweight, responsive Python desktop application built using Tkinter. It acts as a digital prototyping sandbox, allowing hardware developers, students, and makers to cleanly map out their point-to-point wiring, component labels, and layouts digitally *before* making permanent physical mistakes with a soldering iron.

No more accidentally bridging the wrong pins or tracing messy wires in your head!

![License](https://img.shields.io/github/license/yourusername/perfboard-planner?style=flat-square)
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)

---

## ✨ Features

- **Auto-Scaling Viewport:** The entire grid dynamically frames itself to match your window size. No scrolling required, whether you are planning a massive 50x60 matrix or a tiny breakout board.
- **Interactive Matrix Modes:**
  - ✏️ **Label Mode:** Assign custom text tags to individual pads (e.g., `VCC`, `GND`, `SDA`, `SCL`). Hovering over a pad brings up a tool-tip readout.
  - 〰️ **Wire Mode:** Point-and-click to route wires with Manhattan-style (orthogonal) pathing.
  - ✕ **Delete Mode:** Clean up errors quickly by clicking directly on existing wires or pin text labels.
- **Color-Coded Tracks:** A dedicated sidebar palette allows you to easily color-code your power rails, ground nets, and data signals.
- **Layout Export:** Export your final layouts as high-resolution images or vector files directly to your machine.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- `Pillow` (PIL) for advanced rendering and image export

### Installation
1. Clone the repository to your local machine:
```bash
git clone https://github.com/yourusername/perfboard-planner.git
cd perfboard-planner
```
2. Install dependencies:
```bash
pip install Pillow
```
3. Run the application:
```bash
python perfboard_planner.py
```

---

## 🗺️ Roadmap & Upcoming Features

[ ] Pre-built Component Footprints: Drop-down footprints for standard ICs (DIP-8, DIP-16), microcontrollers (Arduino Nano, Teensy, ESP32), and passive modules.

[ ] Multi-layer Support: Add a toggle to switch viewports between the Top Side (component layout) and Bottom Side (soldering path mirroring).

[ ] Bill of Materials (BOM) Tracker: A basic list generator that counts up the estimated length of your wires and list of custom labels.

[ ] Undo / Redo Stack: Keyboard shortcuts (Ctrl+Z / Ctrl+Y) for faster editing flow.

🤝 How to Contribute
Contributions are what make the open-source community an amazing place to learn, inspire, and create. Any contributions you make are greatly appreciated.

## 🧭 Branching Workflow
- `main` is the shipping branch and always contains stable, release-ready code.
- `dev` is the development branch where active work happens.
- Open an issue first, then create a feature branch from `dev`.
- When your work is complete, open a pull request targeting `dev`.
- Once changes on `dev` are reviewed and validated, they can be merged toward the next release.

## 🛠️ Step-by-Step Contribution Guide
1. Fork the project.
2. Create an issue describing your idea or bug.
3. Create a feature branch from `dev`:
```bash
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name
```
4. Make your changes and commit them with clear messages.
5. Push your branch to your fork:
```bash
git push origin feature/your-feature-name
```
6. Open a pull request from your branch into `dev`.
7. Once reviewed, the PR can be merged into `dev`.

## 📜 Development Guidelines
- Keep it lightweight: Avoid adding massive external third-party GUI or rendering frameworks. This project aims to stay native-friendly using Python's standard libraries where possible.
- Maintain object-oriented principles: Keep the core business logic distinct from rendering updates.
- Respect the canvas scale engine: Ensure any new UI widget or component rendering hooks into the dynamic math inside `generate_board()`.

## 🛑 What NOT to Do
- Do not push directly to `main`. Changes should go through feature branches and PRs into `dev`.
- Do not break the scroll-less layout. Any UI implementation that forces the viewport canvas outside the visible screen boundaries will be flagged during review.
- Do not commit local metadata files. Ensure your `.vscode/`, `__pycache__/`, or local design test exports are not accidentally tracked.

📄 License
Distributed under the MIT License. See LICENSE for more information.