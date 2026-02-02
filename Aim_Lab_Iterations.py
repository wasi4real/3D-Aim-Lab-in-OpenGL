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

# ARENA SETTINGS
ARENA_HALF = 900
ARENA_DEPTH = ARENA_HALF * 0.9
FLOOR_Z = 0.0

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
SPAWN_ACCEL = 0.02

# Animation settings
SPHERE_MOVE_SPEED = 80.0
SPHERE_MOVE_RANGE = 200.0

# GAME MODE CONFIGURATION
MODES = ["Normal", "Endless", "Time Trial", "Precision"]
MODE_NORMAL, MODE_ENDLESS, MODE_TIMETRIAL, MODE_PRECISION = 0, 1, 2, 3

# DURATION OPTIONS
DURATION_OPTIONS = [15.0, 30.0, 60.0, 120.0]
DURATION_LABELS = ["15 sec", "30 sec", "1 min", "2 min"]

# Mode-specific constants
TIME_TRIAL_HIT_BONUS = 1.0   # Seconds added per hit in Time Trial
TT_MIN_RADIUS_FACTOR = 0.20  # Minimum size factor for shrinking targets
PRECISION_INNER_RATIO = 0.50  # Head-to-body ratio for precision targets

# GLOBAL STATE VARIABLES
quadric = None

# Visual effect toggles
animated_spheres = False  # M key
glowing_spheres = False   # G key

# Player/Camera state
player_pos = [0.0, -300.0, CAM_HEIGHT]
current_fov = FOVY
yaw_angle = 0.0
pitch_angle = 0.0

# Game settings
selected_duration_index = 1  # Default: 30 seconds
SESSION_TIME = DURATION_OPTIONS[selected_duration_index]

# Game statistics
score = 0
shots = 0
hits = 0
spawned_spheres_count = 0
headshot_hits = 0  # For Precision mode

# Timing variables
start_time = None
elapsed = 0.0
paused = False
pause_time = 0.0

# Target management
spawn_interval = SPAWN_INTERVAL_START
targets = []

# Game flow state
game_state = 'menu'
summary_data = {}

# UI button rectangles
duration_buttons = []
START_BTN_RECT = (0, 0, 0, 0)
SUMMARY_PLAY_RECT = (0, 0, 0, 0)
SUMMARY_MENU_RECT = (0, 0, 0, 0)


# UTILITY FUNCTIONS
def clamp(v, a, b):
    return max(a, min(b, v))

def add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]

def look_dir_fixed():
    cy = math.cos(math.radians(yaw_angle))
    sy = math.sin(math.radians(yaw_angle))
    cp = math.cos(math.radians(pitch_angle))
    sp = math.sin(math.radians(pitch_angle))
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
    py_flipped = WINDOW_H - py
    return (rx <= px <= rx + rw) and (ry <= py_flipped <= ry + rh)

def get_ray_from_mouse(mx, my):
    winX = float(mx)
    winY = float(WINDOW_H) - float(my)
    
    model = glGetDoublev(GL_MODELVIEW_MATRIX)
    proj = glGetDoublev(GL_PROJECTION_MATRIX)
    viewport = glGetIntegerv(GL_VIEWPORT)
    
    near = gluUnProject(winX, winY, 0.0, model, proj, viewport)
    far = gluUnProject(winX, winY, 1.0, model, proj, viewport)
    
    ro = [near[0], near[1], near[2]]
    rd = [far[0] - near[0], far[1] - near[1], far[2] - near[2]]
    
    mag = math.sqrt(rd[0]*rd[0] + rd[1]*rd[1] + rd[2]*rd[2]) or 1.0
    rd = [rd[0]/mag, rd[1]/mag, rd[2]/mag]
    
    return ro, rd


# UI LAYOUT
def compute_menu_layout():
    global START_BTN_RECT, SUMMARY_PLAY_RECT, SUMMARY_MENU_RECT, duration_buttons
    
    BUTTON_W, BUTTON_H = 420, 70
    START_BTN_RECT = (WINDOW_W//2 - BUTTON_W//2, WINDOW_H//2 + 40, BUTTON_W, BUTTON_H)
    
    SUMMARY_PLAY_RECT = (WINDOW_W//2 - 240, WINDOW_H//2 - 180, 200, 64)
    SUMMARY_MENU_RECT = (WINDOW_W//2 + 40, WINDOW_H//2 - 180, 200, 64)
    
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

def spawn_target():
    global spawned_spheres_count
    
    if len(targets) >= MAX_TARGETS:
        return

    # Determine target properties based on game mode
    if selected_mode_index == MODE_PRECISION:
        r = TARGET_RADIUS
        ttl = random.uniform(2.8, 4.5)
    
    pos = random_target_pos()
    target = {
        'p': pos,
        'original_x': pos[0],
        'r': TARGET_RADIUS,
        'born': time.time(),
        'ttl': random.uniform(2.8, 4.5),
        'glow_phase': random.uniform(0, 2 * math.pi)
    }
    
    targets.append(target)
    spawned_spheres_count += 1

def update_targets():
    now = time.time()
    alive = []
    
    for t in targets:
        if now - t['born'] <= t['ttl']:
            # Apply horizontal oscillation animation (M toggle)
            if animated_spheres:
                elapsed_time = now - t['born']
                offset = math.sin(elapsed_time * SPHERE_MOVE_SPEED / SPHERE_MOVE_RANGE) * SPHERE_MOVE_RANGE * 0.5
                t['p'][0] = t['original_x'] + offset
                t['p'][0] = clamp(t['p'][0], -ARENA_HALF * 0.8, ARENA_HALF * 0.8)
            
            # Apply glow effect (pulsing size)
            if glowing_spheres:
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


# RENDERING - ARENA
def draw_floor():
    glBegin(GL_QUADS)
    glColor3f(0.28, 0.28, 0.30)
    glVertex3f(-ARENA_HALF, -ARENA_HALF, FLOOR_Z)
    glVertex3f( ARENA_HALF, -ARENA_HALF, FLOOR_Z)
    glVertex3f( ARENA_HALF,  ARENA_HALF, FLOOR_Z)
    glVertex3f(-ARENA_HALF,  ARENA_HALF, FLOOR_Z)
    glEnd()


def draw_checkboard_wall(x0, x1, y0, y1, z0, z1, tile_w, tile_h):
    """Draw a checkered pattern wall between two points."""
    brown = (0.2, 0.2, 0.2)
    silver = (0.75, 0.75, 0.75)
    
    # Determine if wall is horizontal or vertical
    if abs(x1 - x0) > abs(y1 - y0):
        # Horizontal wall (varies in X)
        hstart = min(x0, x1)
        hend = max(x0, x1)
        vstart = min(z0, z1)
        vend = max(z0, z1)
        h_steps = int(math.ceil((hend - hstart) / tile_w))
        v_steps = int(math.ceil((vend - vstart) / tile_h))
        y_const = y0
        
        # Draw checkerboard tiles
        for i in range(h_steps):
            for j in range(v_steps):
                left = hstart + i * tile_w
                right = min(hstart + (i+1) * tile_w, hend)
                bottom = vstart + j * tile_h
                top = min(vstart + (j+1) * tile_h, vend)
                
                # Alternate colors for checkerboard pattern
                col = brown if ((i + j) % 2 == 0) else silver
                glColor3f(*col)
                
                glBegin(GL_QUADS)
                glVertex3f(left, y_const, bottom)
                glVertex3f(right, y_const, bottom)
                glVertex3f(right, y_const, top)
                glVertex3f(left, y_const, top)
                glEnd()
    else:
        # Vertical wall (varies in Y)
        hstart = min(y0, y1)
        hend = max(y0, y1)
        vstart = min(z0, z1)
        vend = max(z0, z1)
        h_steps = int(math.ceil((hend - hstart) / tile_w))
        v_steps = int(math.ceil((vend - vstart) / tile_h))
        x_const = x0
        
        # Draw checkerboard tiles
        for i in range(h_steps):
            for j in range(v_steps):
                left = hstart + i * tile_w
                right = min(hstart + (i+1) * tile_w, hend)
                bottom = vstart + j * tile_h
                top = min(vstart + (j+1) * tile_h, vend)
                
                # Alternate colors for checkerboard pattern
                col = brown if ((i + j) % 2 == 0) else silver
                glColor3f(*col)
                
                glBegin(GL_QUADS)
                glVertex3f(x_const, left, bottom)
                glVertex3f(x_const, right, bottom)
                glVertex3f(x_const, right, top)
                glVertex3f(x_const, left, top)
                glEnd()


def draw_walls():
    """Render all four arena walls with checkerboard pattern."""
    tile_w = 80.0
    tile_h = 80.0
    
    # Back wall (y = ARENA_HALF)
    draw_checkboard_wall(-ARENA_HALF, ARENA_HALF, ARENA_HALF, ARENA_HALF, 
                        FLOOR_Z, WALL_HEIGHT, tile_w, tile_h)
    
    # Left wall (x = -ARENA_HALF)
    draw_checkboard_wall(-ARENA_HALF, -ARENA_HALF, -ARENA_HALF, ARENA_HALF, 
                        FLOOR_Z, WALL_HEIGHT, tile_w, tile_h)
    
    # Right wall (x = ARENA_HALF)
    draw_checkboard_wall(ARENA_HALF, ARENA_HALF, -ARENA_HALF, ARENA_HALF, 
                        FLOOR_Z, WALL_HEIGHT, tile_w, tile_h)
    
    # Front wall (y = -ARENA_HALF)
    draw_checkboard_wall(-ARENA_HALF, ARENA_HALF, -ARENA_HALF, -ARENA_HALF, 
                        FLOOR_Z, WALL_HEIGHT, tile_w, tile_h)

def draw_precision_target(t):
    """Draw a precision mode target with body and headshot zone."""
    # Main body sphere (blue)
    glPushMatrix()
    glTranslatef(t['p'][0], t['p'][1], t['p'][2])
    glColor3f(0.02, 0.48, 0.98)
    gluSphere(quadric, t['r'], 32, 24)
    
    # Head sphere (red, positioned above body)
    glPushMatrix()
    glTranslatef(0, 0, t['r'] * 1.5)
    glColor3f(0.90, 0.20, 0.25)
    head_r = t['r'] * PRECISION_INNER_RATIO
    gluSphere(quadric, head_r, 24, 16)
    glPopMatrix()
    
    glPopMatrix()
    
# RENDERING - TARGETS
def draw_targets():
    for t in targets:
        if selected_mode_index == MODE_PRECISION: # Special rendering for Precision mode
            draw_precision_target(t)
            continue
        glPushMatrix()
        glTranslatef(t['p'][0], t['p'][1], t['p'][2])
        
        # Color based on effects
        if animated_spheres:
            glColor3f(0.98, 0.48, 0.02)  # Orange for animated
        elif glowing_spheres:
            intensity = 0.7 + 0.3 * math.sin(t['glow_phase'])
            glColor3f(0.02 * intensity, 0.48 * intensity, 0.98 * intensity)
            
        else:
            glColor3f(0.02, 0.48, 0.98)  # Standard blue
        
        gluSphere(quadric, t['r'], 32, 24)
        glPopMatrix()


# RENDERING - UI
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))

def draw_button(x, y, w, h, label, highlight=False):
    if highlight:
        glColor3f(0.10, 0.75, 0.25)
    else:
        glColor3f(0.08, 0.55, 0.95)
    
    glBegin(GL_QUADS)
    glVertex2f(x, y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x, y + h)
    glEnd()
    
    glColor3f(1, 1, 1)
    glBegin(GL_LINE_LOOP)
    glVertex2f(x, y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x, y + h)
    glEnd()
    
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
    
    # Precision mode: show headshot statistics
    if selected_mode_index == MODE_PRECISION:
        head_acc = 0 if shots == 0 else int(100 * headshot_hits / shots)
        draw_text(WINDOW_W - 260, WINDOW_H - 70, 
                 f"headshot: {head_acc}% ({headshot_hits}/{shots})", 
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
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    # Background panel
    panel_w, panel_h = 980, 400
    px = WINDOW_W//2 - panel_w//2
    py = WINDOW_H//2 - panel_h//2
    glColor3f(0.04, 0.04, 0.05)
    glBegin(GL_QUADS)
    glVertex2f(px, py)
    glVertex2f(px + panel_w, py)
    glVertex2f(px + panel_w, py + panel_h)
    glVertex2f(px, py + panel_h)
    glEnd()
    
    glColor3f(1, 1, 1)
    draw_text(WINDOW_W//2 - 150, WINDOW_H//2 + 120, "My Aim Lab 3D")
    
    bx, by, bw, bh = START_BTN_RECT
    draw_button(bx, by, bw, bh, "Click Here to Start")
    
    draw_text(WINDOW_W//2 - 100, WINDOW_H//2 - 60, "Select Duration:")
    for i, rect in enumerate(duration_buttons):
        x, y, w, h = rect
        draw_button(x, y, w, h, DURATION_LABELS[i], highlight=(i == selected_duration_index))

def draw_summary_screen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    # Background panel
    panel_w, panel_h = 800, 500
    px = WINDOW_W//2 - panel_w//2
    py = WINDOW_H//2 - panel_h//2
    glColor3f(0.04, 0.04, 0.05)
    glBegin(GL_QUADS)
    glVertex2f(px, py)
    glVertex2f(px + panel_w, py)
    glVertex2f(px + panel_w, py + panel_h)
    glVertex2f(px, py + panel_h)
    glEnd()
    
    glColor3f(1, 1, 1)
    draw_text(WINDOW_W//2 - 90, WINDOW_H//2 + 180, "Game Summary")
    
    y0 = WINDOW_H//2 + 100
    draw_text(WINDOW_W//2 - 150, y0, f"Duration: {DURATION_OPTIONS[selected_duration_index]:.0f}s")
    draw_text(WINDOW_W//2 - 150, y0 - 40, f"Targets Spawned: {summary_data.get('spawned_spheres', 0)}")
    draw_text(WINDOW_W//2 - 150, y0 - 80, f"Score: {summary_data.get('score', 0)}")
    draw_text(WINDOW_W//2 - 150, y0 - 120, f"Shots Fired: {summary_data.get('shots', 0)}")
    draw_text(WINDOW_W//2 - 150, y0 - 160, f"Accuracy: {summary_data.get('accuracy', 0)}%")
    
    spx, spy, sw, sh = SUMMARY_PLAY_RECT
    mpx, mpy, mw, mh = SUMMARY_MENU_RECT
    draw_button(spx, spy, sw, sh, "Play Again")
    draw_button(mpx, mpy, mw, mh, "Main Menu")


# CAMERA
def setupCamera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(current_fov, ASPECT, NEAR, FAR)
    
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    f = look_dir_fixed()
    eye = player_pos
    center = add(eye, f)
    up = [0, 0, 1]
    
    gluLookAt(eye[0], eye[1], eye[2], 
              center[0], center[1], center[2], 
              up[0], up[1], up[2])

def init_gl():
    global quadric
    glClearColor(0.06, 0.07, 0.09, 1)
    quadric = gluNewQuadric()
    gluQuadricNormals(quadric, GLU_SMOOTH)


# GAME STATE
def start_run():
    global game_state, start_time, score, shots, targets, spawn_interval
    global player_pos, current_fov, paused, SESSION_TIME, yaw_angle, pitch_angle
    global spawned_spheres_count, hits, elapsed, animated_spheres, glowing_spheres

    SESSION_TIME = DURATION_OPTIONS[selected_duration_index]
    
    game_state = 'running'
    start_time = time.time()
    elapsed = 0.0
    score = shots = hits = spawned_spheres_count = 0
    
    targets.clear()
    spawn_interval = SPAWN_INTERVAL_START
    paused = False
    
    player_pos[:] = [0.0, -300.0, CAM_HEIGHT]
    yaw_angle = pitch_angle = 0.0
    current_fov = FOVY
    animated_spheres = glowing_spheres = False

def end_run():
    global game_state, summary_data
    
    game_state = 'summary'
    accuracy_pct = 0 if shots == 0 else int(100 * hits / shots)
    
    summary_data = {
        'score': score,
        'shots': shots,
        'hits': hits,
        'accuracy': accuracy_pct,
        'spawned_spheres': spawned_spheres_count
    }


# INPUT
def keyboardListener(key, x, y):
    global player_pos, current_fov, animated_spheres, glowing_spheres
    global game_state, paused, pause_time, start_time

    if key == b'\x1b':
        glutLeaveMainLoop()

    if (key == b'r' or key == b'R') and game_state == 'running':
        start_run()
        return

    if (key == b'p' or key == b'P') and game_state == 'running':
        game_state = 'menu'
        return

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

    if key in (b'g', b'G'):
        glowing_spheres = not glowing_spheres
        return

    if key in (b'm', b'M'):
        animated_spheres = not animated_spheres
        return

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

    step = 3.0
    if key == GLUT_KEY_LEFT:
        yaw_angle -= step
    elif key == GLUT_KEY_RIGHT:
        yaw_angle += step
    elif key == GLUT_KEY_UP:
        pitch_angle = clamp(pitch_angle + step, -80.0, 80.0)
    elif key == GLUT_KEY_DOWN:
        pitch_angle = clamp(pitch_angle - step, -80.0, 80.0)

def mouseListener(button, state, x, y):
    global shots, score, game_state, selected_duration_index, SESSION_TIME, hits
    
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        if game_state == 'menu':
            for i, rect in enumerate(duration_buttons):
                if point_in_rect(x, y, rect):
                    selected_duration_index = i
                    SESSION_TIME = DURATION_OPTIONS[i]
                    return
            
            if point_in_rect(x, y, START_BTN_RECT):
                start_run()
                return
        
        elif game_state == 'summary':
            if point_in_rect(x, y, SUMMARY_PLAY_RECT):
                start_run()
                return
            if point_in_rect(x, y, SUMMARY_MENU_RECT):
                game_state = 'menu'
                return
        
        elif game_state == 'running' and not paused:
            shots += 1
            
            ro, rd = get_ray_from_mouse(x, y)
            # Find closest target hit
            headshot_hit = False           
            best_t, best_idx = None, -1
            for i, t in enumerate(list(targets)):
                # Precision mode: check headshot zone first
                if selected_mode_index == MODE_PRECISION:
                    head_pos = [t['p'][0], t['p'][1], t['p'][2] + t['r'] * 1.5]
                    head_r = t['r'] * PRECISION_INNER_RATIO
                    ht = line_sphere_intersect(ro, rd, head_pos, head_r)
                    
                    if ht is not None and 0 <= ht <= RAY_MAX_DIST:
                        if best_t is None or ht < best_t:
                            best_t, best_idx = ht, i
                            headshot_hit = True
                            continue
                
                # Check body hit
                bt = line_sphere_intersect(ro, rd, t['p'], t['r'])
                if bt is not None and 0 <= bt <= RAY_MAX_DIST:
                    if best_t is None or bt < best_t:
                        best_t, best_idx = bt, i
                        headshot_hit = False
            
            # Process hit or miss
            if best_idx >= 0:
                t = targets[best_idx]
                
                # Award points based on hit type
                if selected_mode_index == MODE_PRECISION:
                    if headshot_hit:
                        score += 5  # Headshot bonus
                        headshot_hits += 1
                        hits += 1
                    else:
                        score += 1  # Body hit
                        hits += 1
                else:
                    score += 1
                    hits += 1
                    
                    # Time Trial: add time bonus
                    if selected_mode_index == MODE_TIMETRIAL:
                        time_bank += TIME_TRIAL_HIT_BONUS
                
                # Remove hit target
                del targets[best_idx]
            else:
                misses += 1


# MAIN LOOP
def idle():
    global start_time, elapsed
    
    now = time.time()
    
    if start_time is None:
        start_time = now
    
    if not paused:
        elapsed = now - start_time
    
    if game_state == 'running' and not paused:
        if not hasattr(idle, 'last'):
            idle.last = now
        dt = now - idle.last
        idle.last = now
        
        update_targets()
        
        if len(targets) < MAX_TARGETS:
            idle.spawn_accum = getattr(idle, 'spawn_accum', 0.0) + dt
            if idle.spawn_accum >= spawn_interval:
                idle.spawn_accum = 0.0
                spawn_target()
        
        if selected_mode_index in (MODE_NORMAL, MODE_ENDLESS, MODE_PRECISION):
            if elapsed >= SESSION_TIME:
                end_run(reason="duration_reached")
    
    glutPostRedisplay()

def reshape(w, h):
    global WINDOW_W, WINDOW_H, ASPECT
    
    WINDOW_W, WINDOW_H = max(1, w), max(1, h)
    ASPECT = WINDOW_W / WINDOW_H
    
    compute_menu_layout()
    glViewport(0, 0, WINDOW_W, WINDOW_H)

def showScreen():
    if game_state == 'menu':
        draw_start_screen()
        glutSwapBuffers()
        return
    
    if game_state == 'summary':
        draw_summary_screen()
        glutSwapBuffers()
        return
    
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WINDOW_W, WINDOW_H)
    
    setupCamera()
    draw_floor()
    draw_targets()
    draw_hud()
    
    glutSwapBuffers()


# MAIN
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_W, WINDOW_H)
    glutInitWindowPosition(50, 10)
    glutCreateWindow(b"My Aim Lab 3D Features")
    
    init_gl()
    compute_menu_layout()
    
    glutDisplayFunc(showScreen)
    glutIdleFunc(idle)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    
    glutMainLoop()

if __name__ == "__main__":

    main()
