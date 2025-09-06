from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import math, random, time

# =============================
# CONFIGURATION CONSTANTS
# =============================

# Window and display settings
WINDOW_W, WINDOW_H = 1500, 1000
ASPECT = WINDOW_W / WINDOW_H
FOVY = 75.0
NEAR, FAR = 0.1, 5000.0

# Arena dimensions
ARENA_HALF = 900
ARENA_DEPTH = ARENA_HALF * 0.9
FLOOR_Z = 0.0
CAM_HEIGHT = 140.0
WALL_HEIGHT = 400

# Target configuration
TARGET_MIN_Z = 80
TARGET_MAX_Z = 220
TARGET_RADIUS = 24
MAX_TARGETS = 5

# Game duration options
DURATION_OPTIONS = [15.0, 30.0, 60.0, 120.0]  # seconds
DURATION_LABELS = ["15 sec", "30 sec", "1 min", "2 min"]

# Spawn mechanics - controls target appearance rate
SPAWN_INTERVAL_START = 1.2   # initial spawn delay (seconds)
SPAWN_INTERVAL_MIN = 0.20    # minimum spawn delay (fastest)
SPAWN_ACCEL = 0.002          # spawn rate acceleration factor

# Player controls
MOVE_SPEED = 10.0            # lateral movement speed
FOV_MIN = 30.0               # minimum field of view
FOV_MAX = 120.0              # maximum field of view
FOV_STEP = 2.0               # FOV adjustment step size
RAY_MAX_DIST = 3000          # maximum shooting distance

# Animation settings
SPHERE_MOVE_SPEED = 80.0     # oscillation speed for animated targets
SPHERE_MOVE_RANGE = 200.0    # oscillation distance

# Game mode constants
MODES = ["Normal", "Endless", "Time Trial", "Precision"]
MODE_NORMAL, MODE_ENDLESS, MODE_TIMETRIAL, MODE_PRECISION = 0, 1, 2, 3

# Mode-specific settings
TIME_TRIAL_HIT_BONUS = 1.0         # bonus time per hit in Time Trial
TT_MIN_RADIUS_FACTOR = 0.45        # minimum target size in Time Trial (45% of original)
PRECISION_INNER_RATIO = 0.50       # headshot radius ratio for Precision mode

# =============================
# GLOBAL STATE VARIABLES
# =============================

# OpenGL quadric for rendering spheres
quadric = None

# Player state
player_pos = [0.0, -300.0, CAM_HEIGHT]  # [x, y, z] position
yaw = 0.0                                # horizontal rotation (degrees)
pitch = -5.0                             # vertical rotation (degrees)
current_fov = FOVY                       # current field of view
sensitivity = 0.12                       # mouse sensitivity
mouse_locked = True                      # mouse lock state

# Game configuration state
selected_duration_index = 1              # index into DURATION_OPTIONS (default: 30s)
selected_mode_index = MODE_ENDLESS       # current game mode
SESSION_TIME = DURATION_OPTIONS[selected_duration_index]  # current session duration

# Visual effects toggles
animated_spheres = False                 # targets oscillate left/right
glowing_spheres = False                  # targets pulse in size/brightness

# Game statistics
score = 0                                # points earned
misses = 0                               # shots that missed
shots = 0                                # total shots fired
hits = 0                                 # successful hits
headshot_hits = 0                        # precision headshots (Precision mode only)
spawned_spheres_count = 0                # total targets spawned this session

# Timing state
start_time = None                        # game start timestamp
elapsed = 0.0                            # elapsed game time
paused = False                           # pause state
pause_time = 0.0                         # timestamp when paused
time_bank = SESSION_TIME                 # remaining time (Time Trial mode)

# Target management
spawn_interval = SPAWN_INTERVAL_START    # current spawn delay
targets = []                             # active targets list

# UI state and game flow
game_state = 'menu'                      # 'menu', 'running', 'summary'
duration_buttons = []                    # UI button rectangles for duration selection
mode_buttons = []                        # UI button rectangles for mode selection
summary_data = {}                        # post-game statistics

# UI layout rectangles (computed dynamically)
START_BTN_RECT = (0, 0, 0, 0)
SUMMARY_PLAY_RECT = (0, 0, 0, 0)
SUMMARY_MENU_RECT = (0, 0, 0, 0)

# =============================
# UTILITY FUNCTIONS
# =============================

def clamp(v, a, b):
    """Clamp value v between min a and max b"""
    return max(a, min(b, v))

def deg2rad(a):
    """Convert degrees to radians"""
    return a * math.pi / 180.0

def look_dir_from_angles(yaw_deg, pitch_deg):
    """Calculate 3D look direction vector from yaw/pitch angles"""
    cy, sy = math.cos(deg2rad(yaw_deg)), math.sin(deg2rad(yaw_deg))
    cp, sp = math.cos(deg2rad(pitch_deg)), math.sin(deg2rad(pitch_deg))
    fx = sy * cp
    fy = cy * cp
    fz = sp
    # Normalize vector
    l = math.sqrt(fx*fx + fy*fy + fz*fz)
    return [fx/l, fy/l, fz/l]

def add(a, b):
    """Add two 3D vectors"""
    return [a[0]+b[0], a[1]+b[1], a[2]+b[2]]

def line_sphere_intersect(ro, rd, sc, sr):
    """
    Ray-sphere intersection test
    ro: ray origin, rd: ray direction, sc: sphere center, sr: sphere radius
    Returns distance to intersection or None if no hit
    """
    oc = [ro[0]-sc[0], ro[1]-sc[1], ro[2]-sc[2]]
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
    """Check if point (px, py) is inside rectangle rect"""
    rx, ry, rw, rh = rect
    py_flipped = WINDOW_H - py  # Flip Y coordinate for OpenGL
    return (rx <= px <= rx + rw) and (ry <= py_flipped <= ry + rh)

# =============================
# UI LAYOUT COMPUTATION
# =============================

def compute_menu_layout():
    """Calculate positions and sizes for all UI elements"""
    global START_BTN_RECT, SUMMARY_PLAY_RECT, SUMMARY_MENU_RECT, duration_buttons, mode_buttons
    
    # Main start button
    BUTTON_W, BUTTON_H = 420, 70
    START_BTN_RECT = (WINDOW_W//2 - BUTTON_W//2, WINDOW_H//2 + 40, BUTTON_W, BUTTON_H)

    # Summary screen buttons
    SUMMARY_PLAY_RECT = (WINDOW_W//2 - 240, WINDOW_H//2 - 180, 200, 64)
    SUMMARY_MENU_RECT = (WINDOW_W//2 + 40,  WINDOW_H//2 - 180, 200, 64)

    # Duration selection buttons (horizontal row)
    duration_buttons = []
    button_width = 180
    button_height = 50
    button_spacing = 20
    total_width = (button_width * 4) + (button_spacing * 3)
    start_x = WINDOW_W//2 - total_width//2
    for i in range(4):
        x = start_x + i * (button_width + button_spacing)
        y = WINDOW_H//2 - 120
        duration_buttons.append((x, y, button_width, button_height))

    # Mode selection buttons (horizontal row)
    mode_buttons = []
    m_w, m_h, m_gap = 200, 54, 20
    total_w = len(MODES) * m_w + (len(MODES) - 1) * m_gap
    mx0 = WINDOW_W//2 - total_w//2
    my = WINDOW_H//2 - 40
    for i in range(len(MODES)):
        mode_buttons.append((mx0 + i*(m_w + m_gap), my, m_w, m_h))

# =============================
# TARGET MANAGEMENT
# =============================

def random_target_pos():
    """Generate random position within arena bounds for new target"""
    x = random.uniform(-ARENA_HALF * 0.5, ARENA_HALF * 0.5)
    y = random.uniform(50, ARENA_DEPTH * 0.9)
    z = random.uniform(TARGET_MIN_Z, TARGET_MAX_Z)
    return [x, y, z]

def endless_ttl_now():
    """
    Calculate target time-to-live for Endless mode
    TTL decreases as game progresses to increase difficulty
    """
    base_min, base_max = 2.0, 2.8   # early-game TTL range
    min_min,  min_max  = 0.6, 1.2   # late-game TTL range
    # Exponential difficulty curve
    d = clamp((elapsed / SESSION_TIME) ** 1.5, 0.0, 1.0)
    mn = base_min*(1.0-d) + min_min*d
    mx = base_max*(1.0-d) + min_max*d
    return random.uniform(mn, mx)

def time_trial_size_factor():
    """
    Calculate target size reduction for Time Trial mode
    Targets shrink linearly over session duration
    """
    total = max(1.0, SESSION_TIME)
    d = clamp(elapsed / total, 0.0, 1.0)
    return (1.0 - d) * (1.0 - TT_MIN_RADIUS_FACTOR) + TT_MIN_RADIUS_FACTOR

def spawn_target():
    """Create new target based on current game mode"""
    global spawned_spheres_count
    
    if len(targets) >= MAX_TARGETS:
        return

    # Mode-specific target configuration
    if selected_mode_index == MODE_TIMETRIAL:
        # Time Trial: shrinking targets, fixed TTL
        size_factor = time_trial_size_factor()
        r = TARGET_RADIUS * size_factor
        ttl = 4.0
    elif selected_mode_index == MODE_ENDLESS:
        # Endless: normal size, decreasing TTL
        r = TARGET_RADIUS
        ttl = endless_ttl_now()
    elif selected_mode_index == MODE_PRECISION:
        # Precision: normal size, standard TTL, special scoring
        r = TARGET_RADIUS
        ttl = random.uniform(2.8, 4.5)
    else:  # MODE_NORMAL
        # Normal: consistent behavior
        r = TARGET_RADIUS
        ttl = random.uniform(2.8, 4.5)

    pos = random_target_pos()
    target = {
        'p': pos,                                    # current position [x, y, z]
        'original_x': pos[0],                       # initial x for animation oscillation
        'original_r': r,                            # base radius before effects
        'r': r,                                     # current rendered radius
        'born': time.time(),                        # creation timestamp
        'ttl': ttl,                                 # time to live (seconds)
        'move_direction': random.choice([-1, 1]),   # oscillation direction
        'glow_phase': random.uniform(0, 2 * math.pi)  # glow animation phase
    }
    targets.append(target)
    spawned_spheres_count += 1

def update_targets():
    """Update all active targets (animation, effects, lifetime)"""
    global targets
    now = time.time()
    alive = []

    for t in targets:
        # Remove targets that have exceeded their TTL
        if now - t['born'] <= t['ttl']:
            # Apply horizontal oscillation if animation enabled
            if animated_spheres:
                elapsed_time = now - t['born']
                offset = math.sin(elapsed_time * SPHERE_MOVE_SPEED / SPHERE_MOVE_RANGE) * SPHERE_MOVE_RANGE * 0.5
                t['p'][0] = t['original_x'] + offset
                t['p'][0] = clamp(t['p'][0], -ARENA_HALF*0.8, ARENA_HALF*0.8)

            # Apply glow effect if enabled
            if glowing_spheres:
                t['glow_phase'] += 0.03
                base_r = t['original_r']
                
                # Time Trial: apply shrink effect before glow
                if selected_mode_index == MODE_TIMETRIAL:
                    base_r = max(TARGET_RADIUS*TT_MIN_RADIUS_FACTOR, TARGET_RADIUS * time_trial_size_factor())
                
                # Apply pulsing glow effect
                t['r'] = base_r * (1.0 + 0.3 * math.sin(t['glow_phase']))
            else:
                # No glow: apply mode-specific radius only
                if selected_mode_index == MODE_TIMETRIAL:
                    t['r'] = max(TARGET_RADIUS*TT_MIN_RADIUS_FACTOR, TARGET_RADIUS * time_trial_size_factor())
                else:
                    t['r'] = t['original_r']

            alive.append(t)

    targets = alive[:MAX_TARGETS]
    return targets

# =============================
# GAME FLOW CONTROL
# =============================

def start_run():
    """Initialize new game session"""
    global game_state, start_time, score, misses, shots, targets, spawn_interval
    global player_pos, current_fov, animated_spheres, glowing_spheres, paused, SESSION_TIME
    global spawned_spheres_count, hits, headshot_hits, time_bank, elapsed

    # Update session time based on current selection
    SESSION_TIME = DURATION_OPTIONS[selected_duration_index]
    game_state = 'running'
    start_time = time.time()
    elapsed = 0.0

    # Reset all statistics
    score = misses = shots = 0
    hits = headshot_hits = 0
    spawned_spheres_count = 0
    targets = []
    spawn_interval = SPAWN_INTERVAL_START
    paused = False

    # Initialize Time Trial time bank
    time_bank = SESSION_TIME

    # Reset player state
    player_pos[:] = [0.0, -300.0, CAM_HEIGHT]
    current_fov = FOVY
    animated_spheres = False
    glowing_spheres = False

    # Lock cursor for gameplay
    glutSetCursor(GLUT_CURSOR_NONE)
    glutWarpPointer(WINDOW_W//2, WINDOW_H//2)

def end_run(reason="time"):
    """End current game session and prepare summary"""
    global game_state, summary_data
    game_state = 'summary'

    # Calculate final statistics
    accuracy_pct = (0 if shots == 0 else int(100 * hits / max(1, shots)))
    headshot_acc = (0 if shots == 0 else int(100 * headshot_hits / shots))

    # Determine actual run time based on mode
    if selected_mode_index in (MODE_NORMAL, MODE_ENDLESS, MODE_PRECISION):
        run_time = min(elapsed, SESSION_TIME)  # Cap at session time
    else:  # Time Trial shows survival time
        run_time = elapsed

    summary_data = {
        'mode': MODES[selected_mode_index],
        'score': score,
        'misses': misses,
        'shots': shots,
        'hits': hits,
        'accuracy': accuracy_pct,
        'time': run_time,
        'spawned_spheres': spawned_spheres_count,
        'reason': reason,
        'headshot_hits': headshot_hits,
        'headshot_accuracy': headshot_acc
    }

    # Unlock cursor
    glutSetCursor(GLUT_CURSOR_LEFT_ARROW)

# =============================
# INPUT HANDLING
# =============================

def keyboardListener(key, x, y):
    """Handle keyboard input"""
    global player_pos, current_fov, animated_spheres, glowing_spheres, game_state, paused, pause_time, start_time

    if key == b'\x1b':  # Escape key - quit game
        glutLeaveMainLoop()

    # Restart current game (R key)
    if (key == b'r' or key == b'R') and game_state == 'running':
        start_run()
        return

    # Pause/unpause (Spacebar)
    if key == b' ' and game_state == 'running':
        if not paused:
            paused = True
            pause_time = time.time()
        else:
            paused = False
            # Adjust start time to exclude pause duration
            dt = time.time() - pause_time
            if start_time is not None:
                globals()['start_time'] += dt
        return

    # Toggle visual effects
    if key in (b'g', b'G'):  # Toggle glowing spheres
        glowing_spheres = not glowing_spheres
        return
    if key in (b'm', b'M'):  # Toggle animated spheres
        animated_spheres = not animated_spheres
        return

    # Player movement and view controls (only during active gameplay)
    if game_state == 'running' and not paused:
        # Lateral movement (A/D keys)
        if key in (b'a', b'A'):
            player_pos[0] -= MOVE_SPEED
            player_pos[0] = clamp(player_pos[0], -ARENA_HALF + 50, ARENA_HALF - 50)
        if key in (b'd', b'D'):
            player_pos[0] += MOVE_SPEED
            player_pos[0] = clamp(player_pos[0], -ARENA_HALF + 50, ARENA_HALF - 50)
        
        # Field of view adjustment (W/S keys)
        if key in (b'w', b'W'):
            current_fov = clamp(current_fov - FOV_STEP, FOV_MIN, FOV_MAX)
        if key in (b's', b'S'):
            current_fov = clamp(current_fov + FOV_STEP, FOV_MIN, FOV_MAX)

def specialKeyListener(key, x, y):
    """Handle special keys (arrow keys, function keys, etc.)"""
    pass

def mouseListener(button, state, x, y):
    """Handle mouse button clicks"""
    global shots, score, misses, game_state, selected_duration_index, SESSION_TIME
    global selected_mode_index, time_bank, hits, headshot_hits

    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        if game_state == 'menu':
            # Duration selection buttons
            for i, rect in enumerate(duration_buttons):
                if point_in_rect(x, y, rect):
                    selected_duration_index = i
                    SESSION_TIME = DURATION_OPTIONS[i]
                    return
            
            # Mode selection buttons
            for i, rect in enumerate(mode_buttons):
                if point_in_rect(x, y, rect):
                    selected_mode_index = i
                    return
            
            # Start game button
            if point_in_rect(x, y, START_BTN_RECT):
                start_run()
                return

        elif game_state == 'summary':
            # Play again button
            if point_in_rect(x, y, SUMMARY_PLAY_RECT):
                start_run()
                return
            # Return to main menu button
            if point_in_rect(x, y, SUMMARY_MENU_RECT):
                game_state = 'menu'
                globals()['start_time'] = None
                globals()['elapsed'] = 0.0
                return

        elif game_state == 'running' and not paused:
            # Shooting during gameplay
            shots += 1
            ro = list(player_pos)
            rd = look_dir_from_angles(yaw, pitch)
            best_t, best_idx = None, -1
            headshot_hit = False
            
            # Check for target hits
            for i, t in enumerate(targets):
                if selected_mode_index == MODE_PRECISION:
                    # Precision mode: check headshot first (red sphere on top)
                    headshot_pos = [t['p'][0], t['p'][1], t['p'][2] + t['r'] * 1.5]
                    headshot_radius = t['r'] * PRECISION_INNER_RATIO
                    
                    headshot_tt = line_sphere_intersect(ro, rd, headshot_pos, headshot_radius)
                    if headshot_tt is not None and 0 <= headshot_tt <= RAY_MAX_DIST:
                        if best_t is None or headshot_tt < best_t:
                            best_t, best_idx = headshot_tt, i
                            headshot_hit = True
                            continue
                
                # Check main target sphere
                tt = line_sphere_intersect(ro, rd, t['p'], t['r'])
                if tt is not None and 0 <= tt <= RAY_MAX_DIST:
                    if best_t is None or tt < best_t:
                        best_t, best_idx = tt, i
                        headshot_hit = False

            # Process hit or miss
            if best_idx >= 0:
                t = targets[best_idx]
                if selected_mode_index == MODE_PRECISION:
                    if headshot_hit:
                        score += 5  # Bonus points for headshot
                        headshot_hits += 1
                        hits += 1
                    else:
                        score += 1  # Standard points for body hit
                        hits += 1
                else:
                    score += 1
                    hits += 1
                    # Time Trial: add bonus time for hits
                    if selected_mode_index == MODE_TIMETRIAL:
                        time_bank += TIME_TRIAL_HIT_BONUS

                del targets[best_idx]
            else:
                misses += 1

def motionListener(x, y):
    """Handle mouse movement for camera control"""
    global yaw, pitch
    
    if game_state != 'running' or paused:
        return
    
    # Calculate mouse delta from screen center
    dx = x - WINDOW_W//2
    dy = y - WINDOW_H//2
    
    # Apply mouse sensitivity to camera rotation
    yaw += dx * sensitivity
    pitch -= dy * sensitivity
    pitch = clamp(pitch, -85, 85)  # Prevent camera flipping
    
    # Reset mouse to center for continuous movement
    glutWarpPointer(WINDOW_W//2, WINDOW_H//2)

# =============================
# RENDERING FUNCTIONS
# =============================

def draw_floor():
    """Render arena floor with grid pattern"""
    glDisable(GL_LIGHTING)
    
    # Floor base
    glBegin(GL_QUADS)
    glColor3f(0.28, 0.28, 0.30)
    glVertex3f(-ARENA_HALF, -ARENA_HALF, FLOOR_Z)
    glVertex3f( ARENA_HALF, -ARENA_HALF, FLOOR_Z)
    glVertex3f( ARENA_HALF,  ARENA_HALF, FLOOR_Z)
    glVertex3f(-ARENA_HALF,  ARENA_HALF, FLOOR_Z)
    glEnd()

    # Grid lines
    glLineWidth(1)
    glBegin(GL_LINES)
    glColor3f(0.33, 0.33, 0.38)
    step = 100
    for i in range(int(-ARENA_HALF), int(ARENA_HALF)+1, step):
        # Vertical grid lines
        glVertex3f(i, -ARENA_HALF, FLOOR_Z + 0.5)
        glVertex3f(i, ARENA_HALF, FLOOR_Z + 0.5)
        # Horizontal grid lines
        glVertex3f(-ARENA_HALF, i, FLOOR_Z + 0.5)
        glVertex3f(ARENA_HALF, i, FLOOR_Z + 0.5)
    glEnd()

def draw_checkboard_wall(x0, x1, y0, y1, z0, z1, tile_w, tile_h, flip_x=False, flip_y=False):
    """Render checkerboard pattern on wall surface"""
    brown = (0.2, 0.2, 0.2)
    silver = (0.75, 0.75, 0.75)
    
    # Determine wall orientation and dimensions
    if abs(x1 - x0) > abs(y1 - y0):
        # Horizontal wall (varies in X)
        hstart = min(x0, x1); hend = max(x0, x1)
        vstart = min(z0, z1); vend = max(z0, z1)
        h_steps = int(math.ceil((hend - hstart) / tile_w))
        v_steps = int(math.ceil((vend - vstart) / tile_h))
        
        for i in range(h_steps):
            for j in range(v_steps):
                left = hstart + i * tile_w
                right = min(hstart + (i+1) * tile_w, hend)
                bottom = vstart + j * tile_h
                top = min(vstart + (j+1) * tile_h, vend)
                
                # Alternate colors in checkerboard pattern
                col = brown if ((i + j) % 2 == 0) else silver
                glColor3f(*col)
                glBegin(GL_QUADS)
                y_const = y0
                glVertex3f(left, y_const, bottom)
                glVertex3f(right, y_const, bottom)
                glVertex3f(right, y_const, top)
                glVertex3f(left, y_const, top)
                glEnd()
    else:
        # Vertical wall (varies in Y)
        hstart = min(y0, y1); hend = max(y0, y1)
        vstart = min(z0, z1); vend = max(z0, z1)
        h_steps = int(math.ceil((hend - hstart) / tile_w))
        v_steps = int(math.ceil((vend - vstart) / tile_h))
        
        for i in range(h_steps):
            for j in range(v_steps):
                left = hstart + i * tile_w
                right = min(hstart + (i+1) * tile_w, hend)
                bottom = vstart + j * tile_h
                top = min(vstart + (j+1) * tile_h, vend)
                
                col = brown if ((i + j) % 2 == 0) else silver
                glColor3f(*col)
                glBegin(GL_QUADS)
                x_const = x0
                glVertex3f(x_const, left, bottom)
                glVertex3f(x_const, right, bottom)
                glVertex3f(x_const, right, top)
                glVertex3f(x_const, left, top)
                glEnd()

def draw_walls():
    """Render all arena walls with checkerboard pattern"""
    glDisable(GL_LIGHTING)
    glDisable(GL_CULL_FACE)

    tile_w = 80.0
    tile_h = 80.0
    
    # Render each wall
    draw_checkboard_wall(-ARENA_HALF, ARENA_HALF, ARENA_HALF, ARENA_HALF, FLOOR_Z, WALL_HEIGHT, tile_w, tile_h)   # back wall
    draw_checkboard_wall(-ARENA_HALF, -ARENA_HALF, -ARENA_HALF, ARENA_HALF, FLOOR_Z, WALL_HEIGHT, tile_w, tile_h) # left wall
    draw_checkboard_wall( ARENA_HALF,  ARENA_HALF, -ARENA_HALF, ARENA_HALF, FLOOR_Z, WALL_HEIGHT, tile_w, tile_h) # right wall
    draw_checkboard_wall(-ARENA_HALF, ARENA_HALF, -ARENA_HALF, -ARENA_HALF, FLOOR_Z, WALL_HEIGHT, tile_w, tile_h) # front wall

    glEnable(GL_CULL_FACE)

def draw_precision_target(t):
    """
    Render Precision mode target: blue body sphere with red headshot sphere on top
    Body hit = 1 point, headshot = 5 points
    """
    # Draw main blue sphere (body)
    glPushMatrix()
    glTranslatef(t['p'][0], t['p'][1], t['p'][2])
    glColor3f(0.02, 0.48, 0.98)  # blue color
    spec = (GLfloat * 4)(0.2, 0.48, 0.98, 1.0)
    glMaterialfv(GL_FRONT, GL_SPECULAR, spec)
    glMaterialf(GL_FRONT, GL_SHININESS, 40.0)
    gluSphere(quadric, t['r'], 32, 24)
    
    # Draw red headshot sphere positioned above body
    glPushMatrix()
    glTranslatef(0, -5, t['r'] * 1.5)  # Position on top
    glColor3f(0.90, 0.20, 0.25)  # red color
    spec_red = (GLfloat * 4)(0.9, 0.2, 0.25, 1.0)
    glMaterialfv(GL_FRONT, GL_SPECULAR, spec_red)
    glMaterialf(GL_FRONT, GL_SHININESS, 60.0)
    headshot_radius = t['r'] * PRECISION_INNER_RATIO
    gluSphere(quadric, headshot_radius, 24, 16)
    glPopMatrix()
    
    glPopMatrix()

def draw_targets():
    """Render all active targets with mode-specific appearance"""
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHT1)

    for t in targets:
        # Precision mode uses special dual-sphere rendering
        if selected_mode_index == MODE_PRECISION:
            draw_precision_target(t)
            continue

        # Standard target rendering for other modes
        glPushMatrix()
        glTranslatef(t['p'][0], t['p'][1], t['p'][2])

        # Apply visual effects based on toggles
        if animated_spheres:
            glColor3f(0.98, 0.48, 0.02)  # orange for animated targets
        elif glowing_spheres:
            # Pulsing brightness effect
            intensity = 0.7 + 0.3 * math.sin(t['glow_phase'])
            glColor3f(0.02 * intensity, 0.48 * intensity, 0.98 * intensity)
        else:
            glColor3f(0.02, 0.48, 0.98)  # standard blue

        # Set material properties for realistic lighting
        spec = (GLfloat * 4)(0.9, 0.9, 1.0, 1.0)
        glMaterialfv(GL_FRONT, GL_SPECULAR, spec)
        glMaterialf(GL_FRONT, GL_SHININESS, 60.0)
        gluSphere(quadric, t['r'], 32, 24)
        glPopMatrix()

    glDisable(GL_COLOR_MATERIAL)

def draw_crosshair():
    """Render crosshair at screen center"""
    glDisable(GL_LIGHTING)
    
    # Switch to 2D orthographic projection
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    
    cx, cy = WINDOW_W//2, WINDOW_H//2
    size = 10
    glLineWidth(2)
    glBegin(GL_LINES)
    glColor3f(1, 1, 1)  # white crosshair
    # Horizontal line
    glVertex2f(cx - size, cy)
    glVertex2f(cx + size, cy)
    # Vertical line
    glVertex2f(cx, cy - size)
    glVertex2f(cx, cy + size)
    glEnd()
    
    # Restore 3D projection
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    """Render text at specified screen coordinates"""
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))

def draw_button(x, y, w, h, label, highlight=False):
    """Render UI button with optional highlight for selection"""
    # Button background
    if highlight:
        glColor3f(0.10, 0.75, 0.25)  # green for selected
    else:
        glColor3f(0.08, 0.55, 0.95)  # blue for unselected
    
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
    """Render heads-up display during gameplay"""
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    
    # Switch to 2D rendering
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    draw_crosshair()

    # Top status bar
    glColor3f(1, 1, 1)
    draw_text(50, WINDOW_H - 40, f"SCORE: {score}")

    # Time display (varies by mode)
    if selected_mode_index == MODE_TIMETRIAL:
        draw_text(WINDOW_W//2 - 60, WINDOW_H - 40, f"TIME: {max(0.0, time_bank):0.1f}s")
    else:
        time_remaining = max(0.0, SESSION_TIME - elapsed)
        draw_text(WINDOW_W//2 - 60, WINDOW_H - 40, f"TIME: {time_remaining:0.1f}s")

    # Accuracy display
    accuracy = 0 if shots == 0 else int(100 * (hits / max(1, shots)))
    draw_text(WINDOW_W - 260, WINDOW_H - 40, f"ACCURACY: {accuracy}%")

    # Mode indicator
    glColor3f(0.85, 0.85, 0.85)
    draw_text(WINDOW_W//2 - 60, WINDOW_H - 70, f"MODE: {MODES[selected_mode_index]}", GLUT_BITMAP_HELVETICA_12)

    # Precision mode specific stats
    if selected_mode_index == MODE_PRECISION:
        head_acc = 0 if shots == 0 else int(100 * headshot_hits / shots)
        draw_text(WINDOW_W - 260, WINDOW_H - 70, f"headshot: {head_acc}% ({headshot_hits}/{shots})", GLUT_BITMAP_HELVETICA_12)

    # Secondary information panel
    glColor3f(0.8, 0.8, 0.8)
    draw_text(18, WINDOW_H - 70, f"Targets: {len(targets)}/{MAX_TARGETS}", GLUT_BITMAP_HELVETICA_12)
    draw_text(18, WINDOW_H - 90, f"FOV: {current_fov:.1f}°", GLUT_BITMAP_HELVETICA_12)
    draw_text(18, WINDOW_H - 110, f"Pos: ({player_pos[0]:.0f}, {player_pos[1]:.0f})", GLUT_BITMAP_HELVETICA_12)
    draw_text(18, WINDOW_H - 130, f"Animated: {'ON' if animated_spheres else 'OFF'}", GLUT_BITMAP_HELVETICA_12)
    draw_text(18, WINDOW_H - 150, f"Glowing: {'ON' if glowing_spheres else 'OFF'}", GLUT_BITMAP_HELVETICA_12)

    # Control instructions
    glColor3f(0.7, 0.7, 0.7)
    draw_text(WINDOW_W//2 - 300, 30, "A/D: Move | W/S: FOV | M: Animation | G: Glowing | Space: Pause | R: Restart | Esc: Quit", GLUT_BITMAP_HELVETICA_12)

    # Pause overlay
    if paused:
        glColor3f(1, 0.5, 0.5)
        draw_text(WINDOW_W//2 - 80, WINDOW_H//2 + 20, "GAME PAUSED")
        draw_text(WINDOW_W//2 - 120, WINDOW_H//2 - 20, "Press SPACE to continue")

    # Restore 3D rendering
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

def draw_start_screen():
    """Render main menu screen"""
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    # Setup 2D rendering
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    # Background panel
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

    # Duration selection section
    glColor3f(1, 1, 1)
    draw_text(WINDOW_W//2 - 100, WINDOW_H//2 - 60, "Select Duration:")
    for i, rect in enumerate(duration_buttons):
        x, y, w, h = rect
        draw_button(x, y, w, h, DURATION_LABELS[i], highlight=(i == selected_duration_index))

    # Mode selection section
    glColor3f(1, 1, 1)
    draw_text(WINDOW_W//2 - 80, WINDOW_H//2 + 20, "Select Mode:")
    for i, rect in enumerate(mode_buttons):
        x, y, w, h = rect
        draw_button(x, y, w, h, MODES[i], highlight=(i == selected_mode_index))

    # Mode descriptions
    draw_text(WINDOW_W//2 - 460, WINDOW_H//2 - 170, "Mode Descriptions:")
    mode_descriptions = [
        "Normal: Standard targets, fixed target lifetime",
        "Endless: Increasing difficulty, decreasing target lifetime",
        "Time Trial: Targets shrink over time, +1s bonus per hit",
        "Precision: Targets have headshot zone, +5 points for headshots"
    ]
    for i, desc in enumerate(mode_descriptions):
        draw_text(WINDOW_W//2 - 460, WINDOW_H//2 - 200 - i*20, desc)

def draw_summary_screen():
    """Render post-game summary screen"""
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    # Setup 2D rendering
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    # Background panel
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

    # Statistics display
    y0 = WINDOW_H//2 + 140
    draw_text(WINDOW_W//2 - 180, y0,             f"Mode: {summary_data.get('mode','')}")
    draw_text(WINDOW_W//2 - 180, y0 - 40,        f"Game Duration (selected): {DURATION_OPTIONS[selected_duration_index]:.0f}s")
    draw_text(WINDOW_W//2 - 180, y0 - 80,       f"Targets Spawned: {summary_data.get('spawned_spheres', 0)}")
    draw_text(WINDOW_W//2 - 180, y0 - 120,       f"Score: {summary_data.get('score', 0)}")
    draw_text(WINDOW_W//2 - 180, y0 - 160,       f"Shots Fired: {summary_data.get('shots', 0)}")
    draw_text(WINDOW_W//2 - 180, y0 - 200,       f"Accuracy: {summary_data.get('accuracy', 0)}%")

    # Mode-specific information
    if summary_data.get('mode','') == "Time Trial":
        reason = summary_data.get('reason','')
        if reason == "out_of_time":
            draw_text(WINDOW_W//2 - 180, y0 - 280, "Result: Timer reached zero")
        else:
            draw_text(WINDOW_W//2 - 180, y0 - 280, f"Result: Ended early ({reason})")
    elif summary_data.get('mode','') == "Precision":
        draw_text(WINDOW_W//2 - 50, y0 - 200, f"| Headshot Hits: {summary_data.get('headshot_hits', 0)}")
        draw_text(WINDOW_W//2 + 120, y0 - 200, f"| Headshot Accuracy: {summary_data.get('headshot_accuracy', 0)}%")

    # Action buttons
    spx, spy, sw, sh = SUMMARY_PLAY_RECT
    mpx, mpy, mw, mh = SUMMARY_MENU_RECT
    draw_button(spx, spy, sw, sh, "Play Again")
    draw_button(mpx, mpy, mw, mh, "Main Menu")

# =============================
# CAMERA AND RENDERING SETUP
# =============================

def setupCamera():
    """Configure 3D camera view based on player position and orientation"""
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(current_fov, ASPECT, NEAR, FAR)
    
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    # Calculate look direction from yaw/pitch angles
    f = look_dir_from_angles(yaw, pitch)
    eye = player_pos
    center = add(eye, f)
    up = [0, 0, 1]  # Z-up coordinate system
    
    gluLookAt(eye[0], eye[1], eye[2], center[0], center[1], center[2], up[0], up[1], up[2])

def init_gl():
    """Initialize OpenGL settings and lighting"""
    global quadric
    
    # Basic OpenGL setup
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_CULL_FACE)
    glCullFace(GL_BACK)
    glClearColor(0.06, 0.07, 0.09, 1)  # Dark blue background

    # Lighting setup
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHT1)

    # Primary light (bright, directional)
    light0_pos = (GLfloat * 4)(-0.2, -0.5, 1.0, 0.0)  # Directional light
    light0_diff = (GLfloat * 4)(0.95, 0.95, 1.0, 1.0)
    light0_amb  = (GLfloat * 4)(0.12, 0.12, 0.14, 1.0)
    light0_spec = (GLfloat * 4)(0.9, 0.9, 0.95, 1.0)
    glLightfv(GL_LIGHT0, GL_POSITION, light0_pos)
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  light0_diff)
    glLightfv(GL_LIGHT0, GL_AMBIENT,  light0_amb)
    glLightfv(GL_LIGHT0, GL_SPECULAR, light0_spec)

    # Secondary fill light (softer)
    light1_pos = (GLfloat * 4)(0.0, 0.0, 1.0, 0.0)
    light1_diff = (GLfloat * 4)(0.40, 0.42, 0.48, 1.0)
    light1_amb  = (GLfloat * 4)(0.06, 0.06, 0.07, 1.0)
    glLightfv(GL_LIGHT1, GL_POSITION, light1_pos)
    glLightfv(GL_LIGHT1, GL_DIFFUSE,  light1_diff)
    glLightfv(GL_LIGHT1, GL_AMBIENT,  light1_amb)

    # Default material properties
    mat_amb  = (GLfloat * 4)(0.12, 0.12, 0.14, 1.0)
    mat_diff = (GLfloat * 4)(0.9, 0.9, 0.9, 1.0)
    mat_spec = (GLfloat * 4)(0.4, 0.4, 0.45, 1.0)
    glMaterialfv(GL_FRONT, GL_AMBIENT,  mat_amb)
    glMaterialfv(GL_FRONT, GL_DIFFUSE,  mat_diff)
    glMaterialfv(GL_FRONT, GL_SPECULAR, mat_spec)
    glMaterialf(GL_FRONT, GL_SHININESS, 25.0)

    # Create quadric for sphere rendering
    quadric = gluNewQuadric()
    gluQuadricNormals(quadric, GLU_SMOOTH)

# =============================
# MAIN GAME LOOP AND TIMING
# =============================

def idle():
    """Main game update loop - handles timing, spawning, and game state"""
    global start_time, elapsed, spawn_interval, time_bank

    now = time.time()
    if start_time is None:
        start_time = now

    if not paused:
        elapsed = now - start_time

    if game_state == 'running' and not paused:
        # Progressive difficulty: spawn rate increases over time
        if selected_mode_index in (MODE_NORMAL, MODE_ENDLESS, MODE_PRECISION):
            if selected_mode_index == MODE_ENDLESS:
                # Endless mode spawns targets faster
                spawn_interval = max(SPAWN_INTERVAL_MIN, spawn_interval - SPAWN_ACCEL * 2.0)
            else:
                spawn_interval = max(SPAWN_INTERVAL_MIN, spawn_interval - SPAWN_ACCEL)

        # Delta time calculation for frame-rate independent updates
        if not hasattr(idle, 'last'):
            idle.last = now
        dt = now - idle.last
        idle.last = now

        # Time Trial mode countdown
        if selected_mode_index == MODE_TIMETRIAL:
            time_bank -= dt
            if time_bank <= 0.0:
                time_bank = 0.0
                end_run(reason="out_of_time")
                glutPostRedisplay()
                return

        # Update all active targets
        update_targets()

        # Spawn new targets based on current spawn rate
        if len(targets) < MAX_TARGETS:
            idle.spawn_accum = getattr(idle, 'spawn_accum', 0.0) + dt
            if idle.spawn_accum >= spawn_interval:
                idle.spawn_accum = 0.0
                spawn_target()

        # Check for session end conditions
        if selected_mode_index in (MODE_NORMAL, MODE_ENDLESS, MODE_PRECISION):
            if elapsed >= SESSION_TIME:
                end_run(reason="duration_reached")

    glutPostRedisplay()

def reshape(w, h):
    """Handle window resize events"""
    global WINDOW_W, WINDOW_H, ASPECT
    WINDOW_W, WINDOW_H = max(1, w), max(1, h)
    ASPECT = WINDOW_W / WINDOW_H
    compute_menu_layout()  # Recalculate UI positions
    glViewport(0, 0, WINDOW_W, WINDOW_H)

def showScreen():
    """Main display function - routes to appropriate screen renderer"""
    if game_state == 'menu':
        draw_start_screen()
        glutSwapBuffers()
        return

    if game_state == 'summary':
        draw_summary_screen()
        glutSwapBuffers()
        return

    # Gameplay rendering
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WINDOW_W, WINDOW_H)

    setupCamera()
    draw_floor()
    draw_walls()
    draw_targets()
    draw_hud()

    glutSwapBuffers()

# =============================
# PROGRAM ENTRY POINT
# =============================

def main():
    """Initialize GLUT and start the main application loop"""
    # Initialize GLUT
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_W, WINDOW_H)
    glutInitWindowPosition(50, 10)
    glutCreateWindow(b"Enhanced Aim Lab 3D - PyOpenGL")

    # Initialize OpenGL and compute UI layout
    init_gl()
    compute_menu_layout()

    # Register GLUT callback functions
    glutDisplayFunc(showScreen)          # Rendering
    glutIdleFunc(idle)                   # Update loop
    glutReshapeFunc(reshape)             # Window resize
    glutKeyboardFunc(keyboardListener)   # Keyboard input
    glutSpecialFunc(specialKeyListener)  # Special keys
    glutMouseFunc(mouseListener)         # Mouse clicks
    glutPassiveMotionFunc(motionListener) # Mouse movement (passive)
    glutMotionFunc(motionListener)       # Mouse movement (active)

    # Start the main event loop
    glutMainLoop()

# Run the application
if __name__ == "__main__":
    main()