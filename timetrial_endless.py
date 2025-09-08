from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import math
import random
import time

# WINDOW AND VIEWPORT SETTINGS

WINDOW_W, WINDOW_H = 1500, 1000
ASPECT = WINDOW_W / WINDOW_H
FOVY = 75.0
NEAR, FAR = 0.1, 5000.0


ARENA_HALF = 900
ARENA_DEPTH = ARENA_HALF * 0.9
FLOOR_Z = 0.0
WALL_HEIGHT = 400

# Camera settings
CAM_HEIGHT = 140.0
MOVE_SPEED = 10.0
FOV_MIN, FOV_MAX, FOV_STEP = 30.0, 120.0, 2.0


# TARGET CONFIGURATION

TARGET_MIN_Z = 80
TARGET_MAX_Z = 220
TARGET_RADIUS = 24
MAX_TARGETS = 5
RAY_MAX_DIST = 3000.0

# Target spawn timing
SPAWN_INTERVAL_START = 0.3
SPAWN_INTERVAL_MIN = 0.05
SPAWN_ACCEL = 0.02  # Rate at which spawn interval decreases

# Animation settings for visual effects
SPHERE_MOVE_SPEED = 80.0     # Oscillation speed for animated targets
SPHERE_MOVE_RANGE = 200.0    # Oscillation distance


# GAME MODE CONFIGURATION

MODES = ["Normal", "Endless", "Time Trial"]
MODE_NORMAL, MODE_ENDLESS, MODE_TIMETRIAL = 0, 1, 2

# Duration options for game sessions
DURATION_OPTIONS = [15.0, 30.0, 60.0, 120.0]
DURATION_LABELS = ["15 sec", "30 sec", "1 min", "2 min"]

# Mode-specific constants
TIME_TRIAL_HIT_BONUS = 1.0   # Seconds added per hit in Time Trial
TT_MIN_RADIUS_FACTOR = 0.20  # Minimum size factor for shrinking targets


# GLOBAL STATE VARIABLES


# OpenGL quadric for sphere rendering
quadric = None

# Visual effect toggles
animated_spheres = False  # M key: horizontal oscillation
glowing_spheres = False   # G key: pulsing glow effect

# Player/Camera state (fixed forward orientation)
player_pos = [0.0, -300.0, CAM_HEIGHT]  # Camera eye position
current_fov = FOVY

# Camera orientation (for arrow key controls)
yaw_angle = 0.0    # left/right
pitch_angle = 0.0  # up/down

# Game session settings
selected_duration_index = 1  # Default: 30 seconds
selected_mode_index = MODE_ENDLESS  # Default: Endless mode
SESSION_TIME = DURATION_OPTIONS[selected_duration_index]

# Game statistics
score = 0
misses = 0
shots = 0
hits = 0
spawned_spheres_count = 0

# Timing variables
start_time = None
elapsed = 0.0
paused = False
pause_time = 0.0
time_bank = SESSION_TIME  # For Time Trial mode countdown

# Target management
spawn_interval = SPAWN_INTERVAL_START
targets = []  # List of active target dictionaries

# Game flow state: 'menu', 'running', 'summary'
game_state = 'menu'
summary_data = {}

# UI button rectangles (x, y, width, height)
duration_buttons = []
mode_buttons = []
START_BTN_RECT = (0, 0, 0, 0)
SUMMARY_PLAY_RECT = (0, 0, 0, 0)
SUMMARY_MENU_RECT = (0, 0, 0, 0)


# UTILITY FUNCTIONS


def clamp(v, a, b):
    """Constrain value v between a and b."""
    return max(a, min(b, v))

def add(a, b):
    """Vector addition for 3D points."""
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]

def look_dir_fixed():
    """Look direction based on yaw and pitch angles."""
    global yaw_angle, pitch_angle
    # Convert angles (degrees) to radians
    cy = math.cos(math.radians(yaw_angle))
    sy = math.sin(math.radians(yaw_angle))
    cp = math.cos(math.radians(pitch_angle))
    sp = math.sin(math.radians(pitch_angle))

    # Direction vector in 3D space
    return [sy * cp, cy * cp, sp]

def line_sphere_intersect(ro, rd, sc, sr):

    oc = [ro[0] - sc[0], ro[1] - sc[1], ro[2] - sc[2]]
    b = oc[0]*rd[0] + oc[1]*rd[1] + oc[2]*rd[2]
    c = oc[0]*oc[0] + oc[1]*oc[1] + oc[2]*oc[2] - sr*sr
    disc = b*b - c
    
    if disc < 0:
        return None
    
    t = -b - math.sqrt(disc)
    if t < 0:
        return None
    
    return t

def point_in_rect(px, py, rect):

    rx, ry, rw, rh = rect
    # Flip Y coordinate for OpenGL coordinate system
    py_flipped = WINDOW_H - py
    return (rx <= px <= rx + rw) and (ry <= py_flipped <= ry + rh)

def get_ray_from_mouse(mx, my):

    # Convert mouse to OpenGL window coordinates
    winX = float(mx)
    winY = float(WINDOW_H) - float(my)
    
    # Get current matrices and viewport
    model = glGetDoublev(GL_MODELVIEW_MATRIX)
    proj = glGetDoublev(GL_PROJECTION_MATRIX)
    viewport = glGetIntegerv(GL_VIEWPORT)
    
    # Unproject near and far points
    near = gluUnProject(winX, winY, 0.0, model, proj, viewport)
    far = gluUnProject(winX, winY, 1.0, model, proj, viewport)
    
    # Calculate ray origin and direction
    ro = [near[0], near[1], near[2]]
    rd = [far[0] - near[0], far[1] - near[1], far[2] - near[2]]
    
    # Normalize direction vector
    mag = math.sqrt(rd[0]*rd[0] + rd[1]*rd[1] + rd[2]*rd[2]) or 1.0
    rd = [rd[0]/mag, rd[1]/mag, rd[2]/mag]
    
    return ro, rd


# UI LAYOUT COMPUTATION

def compute_menu_layout():
    
    global START_BTN_RECT, SUMMARY_PLAY_RECT, SUMMARY_MENU_RECT
    global duration_buttons, mode_buttons
    
    # Main start button
    BUTTON_W, BUTTON_H = 420, 70
    START_BTN_RECT = (WINDOW_W//2 - BUTTON_W//2, WINDOW_H//2 + 40, BUTTON_W, BUTTON_H)
    
    # Summary screen buttons
    SUMMARY_PLAY_RECT = (WINDOW_W//2 - 240, WINDOW_H//2 - 180, 200, 64)
    SUMMARY_MENU_RECT = (WINDOW_W//2 + 40, WINDOW_H//2 - 180, 200, 64)
    
    # Duration selection buttons
    duration_buttons = []
    bw, bh, spacing = 180, 50, 20
    total_w = bw*4 + spacing*3
    start_x = WINDOW_W//2 - total_w//2
    for i in range(4):
        duration_buttons.append((start_x + i*(bw + spacing), WINDOW_H//2 - 120, bw, bh))
    
    # Mode selection buttons
    mode_buttons = []
    m_w, m_h, m_gap = 200, 54, 20
    total_w = len(MODES)*m_w + (len(MODES)-1)*m_gap
    mx0 = WINDOW_W//2 - total_w//2
    my = WINDOW_H//2 - 40
    for i in range(len(MODES)):
        mode_buttons.append((mx0 + i*(m_w + m_gap), my, m_w, m_h))


# TARGET MANAGEMENT


def random_target_pos():
   
    x = random.uniform(-ARENA_HALF * 0.5, ARENA_HALF * 0.5)
    y = random.uniform(50, ARENA_DEPTH * 0.9)
    z = random.uniform(TARGET_MIN_Z, TARGET_MAX_Z)
    return [x, y, z]

def endless_ttl_now():
 
    base_min, base_max = 2.0, 2.8
    min_min, min_max = 0.6, 1.2
    
    # Progress factor (0 to 1) based on elapsed time
    d = clamp((elapsed / SESSION_TIME) ** 1.5, 0.0, 1.0)
    
    # Interpolate between starting and ending TTL ranges
    mn = base_min * (1.0 - d) + min_min * d
    mx = base_max * (1.0 - d) + min_max * d
    
    return random.uniform(mn, mx)

def time_trial_size_factor():

    total = max(1.0, SESSION_TIME)
    d = clamp((elapsed / total) * 0.3, 0.0, 1.0)
    return (1.0 - d) * (1.0 - TT_MIN_RADIUS_FACTOR) + TT_MIN_RADIUS_FACTOR

def spawn_target():

    global spawned_spheres_count
    
    # Check max targets limit
    if len(targets) >= MAX_TARGETS:
        return
    
    # Determine target properties based on game mode
    if selected_mode_index == MODE_TIMETRIAL:
        size_factor = time_trial_size_factor()
        r = TARGET_RADIUS * size_factor
        ttl = endless_ttl_now()  
    elif selected_mode_index == MODE_ENDLESS:
        r = TARGET_RADIUS
        ttl = endless_ttl_now()
    else:  # MODE_NORMAL
        r = TARGET_RADIUS
        ttl = random.uniform(2.8, 4.5)
    
    # Create target dictionary with all necessary properties
    pos = random_target_pos()
    target = {
        'p': pos,                          # Current position [x,y,z]
        'original_x': pos[0],              # Starting X for oscillation
        'original_r': r,                   # Base radius (before effects)
        'r': r,                            # Current display radius
        'born': time.time(),               # Creation timestamp
        'ttl': ttl,                        # Time to live
        'move_direction': random.choice([-1, 1]),  # Direction for potential movement
        'glow_phase': random.uniform(0, 2 * math.pi)  # Random starting phase for glow
    }
    
    targets.append(target)
    spawned_spheres_count += 1

def update_targets():

    now = time.time()
    alive = []
    
    for t in targets:
        # Check if target is still alive
        if now - t['born'] <= t['ttl']:
            
            # Apply horizontal oscillation animation (M toggle)
            if animated_spheres:
                elapsed_time = now - t['born']
                # Sinusoidal horizontal movement
                offset = math.sin(elapsed_time * SPHERE_MOVE_SPEED / SPHERE_MOVE_RANGE) * SPHERE_MOVE_RANGE * 0.5
                t['p'][0] = t['original_x'] + offset
                # Keep within arena bounds
                t['p'][0] = clamp(t['p'][0], -ARENA_HALF * 0.8, ARENA_HALF * 0.8)
            
            # Apply glow effect and mode-specific radius adjustments
            if glowing_spheres:
                # Advance glow animation phase
                t['glow_phase'] += 0.03
                base_r = t['original_r']
                
                # Time Trial: shrink base radius before applying glow
                if selected_mode_index == MODE_TIMETRIAL:
                    base_r = max(TARGET_RADIUS * TT_MIN_RADIUS_FACTOR,
                                TARGET_RADIUS * time_trial_size_factor())
                
                # Apply pulsing glow effect
                t['r'] = base_r * (1.0 + 0.3 * math.sin(t['glow_phase']))
            else:
                # No glow: still apply Time Trial shrinking if active
                if selected_mode_index == MODE_TIMETRIAL:
                    t['r'] = max(TARGET_RADIUS * TT_MIN_RADIUS_FACTOR,
                                TARGET_RADIUS * time_trial_size_factor())
                else:
                    t['r'] = t['original_r']
            
            alive.append(t)
    

    targets[:] = alive


# RENDERING FUNCTIONS - TARGETS


def draw_targets():

    for t in targets:
        # Standard target rendering
        glPushMatrix()
        glTranslatef(t['p'][0], t['p'][1], t['p'][2])
        
        # Apply color based on visual effects
        if animated_spheres:
            # Animated targets are orange
            glColor3f(0.98, 0.48, 0.02)
        elif glowing_spheres:
            # Pulsing brightness for glowing targets
            intensity = 0.7 + 0.3 * math.sin(t['glow_phase'])
            glColor3f(0.02 * intensity, 0.48 * intensity, 0.98 * intensity)
        else:
            # Standard blue color
            glColor3f(0.02, 0.48, 0.98)
        
        gluSphere(quadric, t['r'], 32, 24)
        glPopMatrix()


# RENDERING FUNCTIONS - UI


def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    """Render text at specified position."""
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))

def draw_button(x, y, w, h, label, highlight=False):
    """Draw a UI button with optional highlight."""
    # Button background
    if highlight:
        glColor3f(0.10, 0.75, 0.25)  # Green for selected
    else:
        glColor3f(0.08, 0.55, 0.95)  # Blue for unselected
    
    glBegin(GL_QUADS)
    glVertex2f(x, y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x, y + h)
    glEnd()
    
    # Button border
    glColor3f(1, 1, 1)
    glBegin(GL_LINE_LOOP)
    glVertex2f(x, y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x, y + h)
    glEnd()
    
    # Button label
    glColor3f(1, 1, 1)
    draw_text(x + 18, y + h//2 - 8, label)

def draw_hud():

    # Set up 2D overlay projection
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    
    # Primary stats line (Score, Time, Accuracy)
    glColor3f(1, 1, 1)
    draw_text(50, WINDOW_H - 40, f"SCORE: {score}")
    
    # Time display (mode-specific)
    if selected_mode_index == MODE_TIMETRIAL:
        draw_text(WINDOW_W//2 - 60, WINDOW_H - 40, f"TIME: {max(0.0, time_bank):0.1f}s")
    else:
        time_remaining = max(0.0, SESSION_TIME - elapsed)
        draw_text(WINDOW_W//2 - 60, WINDOW_H - 40, f"TIME: {time_remaining:0.1f}s")
    
    # Accuracy percentage
    accuracy = 0 if shots == 0 else int(100 * (hits / max(1, shots)))
    draw_text(WINDOW_W - 260, WINDOW_H - 40, f"ACCURACY: {accuracy}%")
    
    # Mode indicator
    glColor3f(0.85, 0.85, 0.85)
    draw_text(WINDOW_W//2 - 60, WINDOW_H - 70, f"MODE: {MODES[selected_mode_index]}", 
             GLUT_BITMAP_HELVETICA_12)
    
    # Secondary info panel (left side)
    glColor3f(0.8, 0.8, 0.8)
    draw_text(18, WINDOW_H - 70, f"Targets: {len(targets)}/{MAX_TARGETS}", 
             GLUT_BITMAP_HELVETICA_12)
    draw_text(18, WINDOW_H - 90, f"FOV: {current_fov:.1f}°", 
             GLUT_BITMAP_HELVETICA_12)
    draw_text(18, WINDOW_H - 110, f"Pos: ({player_pos[0]:.0f}, {player_pos[1]:.0f})", 
             GLUT_BITMAP_HELVETICA_12)
    draw_text(18, WINDOW_H - 130, f"Animated: {'ON' if animated_spheres else 'OFF'}", 
             GLUT_BITMAP_HELVETICA_12)
    draw_text(18, WINDOW_H - 150, f"Glowing: {'ON' if glowing_spheres else 'OFF'}", 
             GLUT_BITMAP_HELVETICA_12)
    
    # Control instructions (bottom)
    glColor3f(0.7, 0.7, 0.7)
    draw_text(WINDOW_W//2 - 420, 30,
             "A/D: Move | W/S: FOV | Arrow Keys: Look around | M: Animation | G: Glowing | Space: Pause | R: Restart | P: Menu | Esc: Quit",
             GLUT_BITMAP_HELVETICA_12)
    
    # Pause overlay
    if paused:
        glColor3f(1, 0.5, 0.5)
        draw_text(WINDOW_W//2 - 80, WINDOW_H//2 + 20, "GAME PAUSED")
        draw_text(WINDOW_W//2 - 120, WINDOW_H//2 - 20, "Press SPACE to continue")
        glColor3f(1, 1, 1)
    
    # Restore 3D projection
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_start_screen():
    """Draw the main menu screen."""
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    # Set up 2D projection
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    # Draw panel background
    panel_w, panel_h = 980, 580
    px = WINDOW_W//2 - panel_w//2
    py = WINDOW_H//2 - panel_h//2
    glColor3f(0.04, 0.04, 0.05)
    glBegin(GL_QUADS)
    glVertex2f(px, py)
    glVertex2f(px + panel_w, py)
    glVertex2f(px + panel_w, py + panel_h)
    glVertex2f(px, py + panel_h)
    glEnd()
    
    # Title
    glColor3f(1, 1, 1)
    draw_text(WINDOW_W//2 - 200, WINDOW_H//2 + 200, "Enhanced Aim Lab 3D - Start")
    
    # Start button
    bx, by, bw, bh = START_BTN_RECT
    draw_button(bx, by, bw, bh, "Click Here to Start")
    
    # Duration selection
    draw_text(WINDOW_W//2 - 100, WINDOW_H//2 - 60, "Select Duration:")
    for i, rect in enumerate(duration_buttons):
        x, y, w, h = rect
        draw_button(x, y, w, h, DURATION_LABELS[i], highlight=(i == selected_duration_index))
    
    # Mode selection
    draw_text(WINDOW_W//2 - 80, WINDOW_H//2 + 20, "Select Mode:")
    for i, rect in enumerate(mode_buttons):
        x, y, w, h = rect
        draw_button(x, y, w, h, MODES[i], highlight=(i == selected_mode_index))
    
    # Mode descriptions
    draw_text(WINDOW_W//2 - 460, WINDOW_H//2 - 170, "Mode Descriptions:")
    mode_descriptions = [
        "Normal: Standard targets, fixed target lifetime",
        "Endless: Increasing difficulty, decreasing target lifetime",
        "Time Trial: Decreasing target radius and lifetime, +1s bonus per hit"
    ]
    for i, desc in enumerate(mode_descriptions):
        draw_text(WINDOW_W//2 - 460, WINDOW_H//2 - 200 - i*20, desc)

def draw_summary_screen():
    """Draw the game summary screen after a session ends."""
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    # Set up 2D projection
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    # Draw panel background
    panel_w, panel_h = 980, 600
    px = WINDOW_W//2 - panel_w//2
    py = WINDOW_H//2 - panel_h//2
    glColor3f(0.04, 0.04, 0.05)
    glBegin(GL_QUADS)
    glVertex2f(px, py)
    glVertex2f(px + panel_w, py)
    glVertex2f(px + panel_w, py + panel_h)
    glVertex2f(px, py + panel_h)
    glEnd()
    
    # Title
    glColor3f(1, 1, 1)
    draw_text(WINDOW_W//2 - 90, WINDOW_H//2 + 220, "Game Summary")
    
    # Game statistics
    y0 = WINDOW_H//2 + 140
    draw_text(WINDOW_W//2 - 180, y0, f"Mode: {summary_data.get('mode','')}")
    draw_text(WINDOW_W//2 - 180, y0 - 40, f"Game Duration (selected): {DURATION_OPTIONS[selected_duration_index]:.0f}s")
    draw_text(WINDOW_W//2 - 180, y0 - 80, f"Targets Spawned: {summary_data.get('spawned_spheres', 0)}")
    draw_text(WINDOW_W//2 - 180, y0 - 120, f"Score: {summary_data.get('score', 0)}")
    draw_text(WINDOW_W//2 - 180, y0 - 160, f"Shots Fired: {summary_data.get('shots', 0)}")
    draw_text(WINDOW_W//2 - 180, y0 - 200, f"Accuracy: {summary_data.get('accuracy', 0)}%")
    
    # Mode-specific results
    if summary_data.get('mode','') == "Time Trial":
        reason = summary_data.get('reason','')
        if reason == "out_of_time":
            draw_text(WINDOW_W//2 + 80, y0 - 40, "| Result: Timer reached zero")
        else:
            draw_text(WINDOW_W//2 + 80, y0 - 40, f"| Result: Ended early ({reason})")
    
    # Action buttons
    spx, spy, sw, sh = SUMMARY_PLAY_RECT
    mpx, mpy, mw, mh = SUMMARY_MENU_RECT
    draw_button(spx, spy, sw, sh, "Play Again")
    draw_button(mpx, mpy, mw, mh, "Main Menu")


# CAMERA AND INITIALIZATION


def setupCamera():

    # Set up perspective projection
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(current_fov, ASPECT, NEAR, FAR)
    
    # Set up camera view
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    # Calculate look-at parameters
    f = look_dir_fixed()
    eye = player_pos
    center = add(eye, f)
    up = [0, 0, 1]
    
    # Apply look-at transformation
    gluLookAt(eye[0], eye[1], eye[2], 
              center[0], center[1], center[2], 
              up[0], up[1], up[2])

def init_gl():
    """Initialize OpenGL settings."""
    global quadric
    
    # Set background color
    glClearColor(0.06, 0.07, 0.09, 1)
    
    # Create quadric for sphere rendering
    quadric = gluNewQuadric()
    gluQuadricNormals(quadric, GLU_SMOOTH)


# GAME STATE MANAGEMENT


def start_run():

    global game_state, start_time, score, misses, shots, targets, spawn_interval
    global player_pos, current_fov, paused, SESSION_TIME, yaw_angle, pitch_angle
    global spawned_spheres_count, hits, time_bank, elapsed
    global animated_spheres, glowing_spheres  # reset toggles

    # Set session duration
    SESSION_TIME = DURATION_OPTIONS[selected_duration_index]

    # Initialize game state
    game_state = 'running'
    start_time = time.time()
    elapsed = 0.0

    # Reset statistics
    score = misses = shots = hits = 0
    spawned_spheres_count = 0

    # Clear targets and reset spawn timing
    targets.clear()
    spawn_interval = SPAWN_INTERVAL_START

    # Reset game flags
    paused = False
    time_bank = SESSION_TIME  # For Time Trial mode

    # Reset player position and view
    player_pos[:] = [0.0, -300.0, CAM_HEIGHT]
    yaw_angle = 0.0
    pitch_angle = 0.0   
    current_fov = FOVY

    # Reset feature toggles to OFF by default
    animated_spheres = False
    glowing_spheres = False


def end_run(reason="time"):
    """End the current game session and prepare summary."""
    global game_state, summary_data
    
    game_state = 'summary'
    
    # Calculate final statistics
    accuracy_pct = (0 if shots == 0 else int(100 * hits / max(1, shots)))
    run_time = elapsed if selected_mode_index == MODE_TIMETRIAL else min(elapsed, SESSION_TIME)
    
    # Prepare summary data
    summary_data = {
        'mode': MODES[selected_mode_index],
        'score': score,
        'misses': misses,
        'shots': shots,
        'hits': hits,
        'accuracy': accuracy_pct,
        'time': run_time,
        'spawned_spheres': spawned_spheres_count,
        'reason': reason
    }


# INPUT HANDLERS


def keyboardListener(key, x, y):

    global player_pos, current_fov, animated_spheres, glowing_spheres
    global game_state, paused, pause_time, start_time

    # Escape key - quit application
    if key == b'\x1b':
        glutLeaveMainLoop()

    # R key - restart current game
    if (key == b'r' or key == b'R') and game_state == 'running':
        start_run()
        return

    # P key - return to main menu
    if (key == b'p' or key == b'P') and game_state == 'running':
        game_state = 'menu'
        globals()['start_time'] = None
        globals()['elapsed'] = 0.0
        return

    # Spacebar - pause/unpause
    if key == b' ' and game_state == 'running':
        if not paused:
            paused = True
            pause_time = time.time()
        else:
            paused = False
            dt = time.time() - pause_time
            if start_time is not None:
                globals()['start_time'] += dt
        return

    # G key - toggle glowing effect
    if key in (b'g', b'G'):
        glowing_spheres = not glowing_spheres
        return

    # M key - toggle animation effect
    if key in (b'm', b'M'):
        animated_spheres = not animated_spheres
        return

    # Movement and view controls (only during active gameplay)
    if game_state == 'running' and not paused:
        if key in (b'a', b'A'):
            player_pos[0] -= MOVE_SPEED
            player_pos[0] = clamp(player_pos[0], -ARENA_HALF + 50, ARENA_HALF - 50)
        if key in (b'd', b'D'):
            player_pos[0] += MOVE_SPEED
            player_pos[0] = clamp(player_pos[0], -ARENA_HALF + 50, ARENA_HALF - 50)

        if key in (b'w', b'W'):
            current_fov = clamp(current_fov - FOV_STEP, FOV_MIN, FOV_MAX)
        if key in (b's', b'S'):
            current_fov = clamp(current_fov + FOV_STEP, FOV_MIN, FOV_MAX)


def specialKeyListener(key, x, y):

    global yaw_angle, pitch_angle

    step = 3.0  # degrees per key press

    if key == GLUT_KEY_LEFT:
        yaw_angle -= step
    elif key == GLUT_KEY_RIGHT:
        yaw_angle += step
    elif key == GLUT_KEY_UP:
        pitch_angle = clamp(pitch_angle + step, -80.0, 80.0)  # limit up/down tilt
    elif key == GLUT_KEY_DOWN:
        pitch_angle = clamp(pitch_angle - step, -80.0, 80.0)


def mouseListener(button, state, x, y):

    global shots, score, misses, game_state, selected_duration_index, SESSION_TIME
    global selected_mode_index, time_bank, hits
    
    # Only process left mouse button clicks
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        
        # Menu state - handle button clicks
        if game_state == 'menu':
            # Check duration buttons
            for i, rect in enumerate(duration_buttons):
                if point_in_rect(x, y, rect):
                    selected_duration_index = i
                    SESSION_TIME = DURATION_OPTIONS[i]
                    return
            
            # Check mode buttons
            for i, rect in enumerate(mode_buttons):
                if point_in_rect(x, y, rect):
                    selected_mode_index = i
                    return
            
            # Check start button
            if point_in_rect(x, y, START_BTN_RECT):
                start_run()
                return
        
        # Summary state - handle navigation buttons
        elif game_state == 'summary':
            if point_in_rect(x, y, SUMMARY_PLAY_RECT):
                start_run()
                return
            if point_in_rect(x, y, SUMMARY_MENU_RECT):
                game_state = 'menu'
                globals()['start_time'] = None
                globals()['elapsed'] = 0.0
                return
        
        # Running state - handle shooting
        elif game_state == 'running' and not paused:
            shots += 1
            
            # Generate ray from camera through mouse position
            ro, rd = get_ray_from_mouse(x, y)
            
            # Find closest target hit
            best_t, best_idx = None, -1
            
            # Check all targets for intersection
            for i, t in enumerate(list(targets)):
                # Check body hit
                bt = line_sphere_intersect(ro, rd, t['p'], t['r'])
                if bt is not None and 0 <= bt <= RAY_MAX_DIST:
                    if best_t is None or bt < best_t:
                        best_t, best_idx = bt, i
            
            # Process hit or miss
            if best_idx >= 0:
                t = targets[best_idx]
                
                # Award points based on hit type
                score += 1
                hits += 1
                
                # Time Trial: add time bonus
                if selected_mode_index == MODE_TIMETRIAL:
                    time_bank += TIME_TRIAL_HIT_BONUS
                
                # Remove hit target
                del targets[best_idx]
            else:
                misses += 1

# MAIN LOOP AND TIMING


def idle():
    """Main game loop - handle timing, spawning, and game state updates."""
    global start_time, elapsed, spawn_interval, time_bank
    
    now = time.time()
    
    # Initialize start time if needed
    if start_time is None:
        start_time = now
    
    # Update elapsed time when not paused
    if not paused:
        elapsed = now - start_time
    
    # Process game logic when running
    if game_state == 'running' and not paused:

        # Calculate delta time for updates
        if not hasattr(idle, 'last'):
            idle.last = now
        dt = now - idle.last
        idle.last = now
        
        # Time Trial: countdown timer
        if selected_mode_index == MODE_TIMETRIAL:
            time_bank -= dt
            if time_bank <= 0.0:
                time_bank = 0.0
                end_run(reason="out_of_time")
                glutPostRedisplay()
                return
        
        # Update existing targets
        update_targets()
        
        # Spawn new targets at intervals
        if len(targets) < MAX_TARGETS:
            idle.spawn_accum = getattr(idle, 'spawn_accum', 0.0) + dt
            if idle.spawn_accum >= spawn_interval:
                idle.spawn_accum = 0.0
                spawn_target()
        
        # Check end conditions for non-Time Trial modes
        if selected_mode_index in (MODE_NORMAL, MODE_ENDLESS):
            if elapsed >= SESSION_TIME:
                end_run(reason="duration_reached")
    
    # Request display update
    glutPostRedisplay()

def reshape(w, h):
    """Handle window resize events."""
    global WINDOW_W, WINDOW_H, ASPECT
    
    # Update window dimensions
    WINDOW_W, WINDOW_H = max(1, w), max(1, h)
    ASPECT = WINDOW_W / WINDOW_H
    
    # Recalculate UI layout
    compute_menu_layout()
    
    # Update viewport
    glViewport(0, 0, WINDOW_W, WINDOW_H)

def showScreen():

    # Render menu screen
    if game_state == 'menu':
        draw_start_screen()
        glutSwapBuffers()
        return
    
    # Render summary screen
    if game_state == 'summary':
        draw_summary_screen()
        glutSwapBuffers()
        return
    
    # Render gameplay
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WINDOW_W, WINDOW_H)
    
    # Set up 3D scene
    setupCamera()
    draw_targets()
    
    # Draw 2D overlay
    draw_hud()
    
    glutSwapBuffers()

# APPLICATION ENTRY POINT


def main():

    # Initialize GLUT
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_W, WINDOW_H)
    glutInitWindowPosition(50, 10)
    glutCreateWindow(b"Enhanced Aim Lab 3D - PyOpenGL")
    
    # Initialize OpenGL
    init_gl()
    
    # Calculate initial UI layout
    compute_menu_layout()
    
    # Register GLUT callbacks
    glutDisplayFunc(showScreen)
    glutIdleFunc(idle)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    
    # Start main loop
    glutMainLoop()

if __name__ == "__main__":
    main()