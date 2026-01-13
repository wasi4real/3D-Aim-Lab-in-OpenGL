# Enhanced Aim Lab 3D

A high-performance 3D aim trainer developed in Python using **PyOpenGL**. This project provides a simulated environment for competitive shooters to practice tracking, flicking, and precision shooting across multiple game modes and difficulty levels.

---

## Features

### 1. Game Modes

* **Normal**: Standard practice with fixed target lifetimes and consistent spawn rates.
* **Endless**: Progressive difficulty curve where target lifetimes decrease exponentially as the session progresses.
* **Time Trial**: Survival-based mode. Targets shrink over time; each successful hit adds a **1.0s bonus** to the timer.
* **Precision**: Accuracy-focused mode featuring dual-sphere targets. Hits on the "headshot" zone (red) grant **5x points** compared to body hits (blue).

### 2. Interactive Mechanics

* **Ray-Sphere Intersection**: Custom mathematical implementation for high-fidelity hit detection.
* **Dynamic FOV**: Real-time Field of View adjustment to match specific game engine settings (e.g., Valorant, CS2).
* **Visual Toggles**: Optional **Oscillation** (moving targets) and **Glow/Pulse** effects to increase visual complexity.
* **Statistical Analysis**: Post-game summary screen providing hits, misses, total shots, accuracy percentage, and headshot ratios.

### 3. Visual Environment

* **3D Arena**: A textured grid floor and checkerboard walls for spatial orientation.
* **Lighting Engine**: Dual-light setup (directional and ambient fill) with specular highlights for realistic sphere depth.
* **Responsive UI**: Custom-built menu system and HUD rendered using orthographic 2D overlays.

---

## Controls

| Key | Action |
| --- | --- |
| **Mouse Move** | Look / Aim |
| **Left Click** | Shoot / UI Selection |
| **W / S** | Increase / Decrease FOV |
| **A / D** | Lateral Player Movement |
| **Space** | Pause / Unpause |
| **R** | Restart Session |
| **M** | Toggle Target Animation (Movement) |
| **G** | Toggle Target Glow |
| **Esc** | Quit Application |

---

## Installation & Requirements

### Prerequisites

* Python 3.x
* OpenGL-compatible Graphics Card

### Dependencies

Install the required libraries via pip:

```bash
pip install PyOpenGL PyOpenGL_accelerate

```

*Note: Depending on your OS, you may need to install additional GLUT binaries (e.g., freeglut).*

### Running the Application

```bash
python "Aim Lab Project_Buffed.py"

```

---

## Technical Overview

The project is structured into several core modules:

* **Physics/Math**: Custom functions for 3D vector addition, clamping, and ray-sphere intersection logic.
* **Target Management**: A system that handles spawning, TTL (Time-To-Live) logic, and mode-specific scaling factors.
* **Rendering Pipeline**: Uses `GLUT` for windowing and `PyOpenGL` for the fixed-function pipeline, managing 3D perspective and 2D orthographic projections.
* **State Machine**: Manages transitions between `menu`, `running`, and `summary` states to ensure clean session resets.
