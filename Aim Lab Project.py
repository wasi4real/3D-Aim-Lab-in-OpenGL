from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import math, random, time

# =============================
# Config
# =============================
WINDOW_W, WINDOW_H = 1500, 1000
ASPECT = WINDOW_W / WINDOW_H
FOVY = 75.0
NEAR, FAR = 0.1, 5000.0

ARENA_HALF = 900
ARENA_DEPTH = ARENA_HALF * 0.9
FLOOR_Z = 0.0
CAM_HEIGHT = 140.0
WALL_HEIGHT = 400

TARGET_MIN_Z = 80
TARGET_MAX_Z = 220
TARGET_RADIUS = 24
SPAWN_INTERVAL_START = 1.0
SPAWN_INTERVAL_MIN = 0.45
SPAWN_ACCEL = 0.0006
MAX_TARGETS = 5
RAY_MAX_DIST = 3000
SESSION_TIME = 60.0  # seconds per run

# Movement and FOV settings
MOVE_SPEED = 10.0
FOV_MIN = 30.0
FOV_MAX = 120.0
FOV_STEP = 2.0

# Animation settings
SPHERE_MOVE_SPEED = 80.0  # units per second
SPHERE_MOVE_RANGE = 200.0  # total distance to move left/right

# =============================
# State
# =============================
quadric = None

player_pos = [0.0, -300.0, CAM_HEIGHT]
yaw = 0.0
pitch = -5.0
mouse_locked = False
current_fov = FOVY
animated_spheres = False

score = 0
misses = 0
shots = 0
start_time = None
elapsed = 0

spawn_interval = SPAWN_INTERVAL_START
targets = []

sensitivity = 0.12

# UI / Screens: 'menu', 'running', 'summary'
game_state = 'menu'

# Layout placeholders (computed)
START_BTN_RECT = (0, 0, 0, 0)
SENS_DEC_RECT = (0, 0, 0, 0)
SENS_INC_RECT = (0, 0, 0, 0)
SUMMARY_PLAY_RECT = (0, 0, 0, 0)
SUMMARY_MENU_RECT = (0, 0, 0, 0)

summary_data = {}

# =============================
# Helpers
# =============================
def clamp(v, a, b):
    return max(a, min(b, v))

def deg2rad(a):
    return a * math.pi / 180.0

def look_dir_from_angles(yaw_deg, pitch_deg):
    cy, sy = math.cos(deg2rad(yaw_deg)), math.sin(deg2rad(yaw_deg))
    cp, sp = math.cos(deg2rad(pitch_deg)), math.sin(deg2rad(pitch_deg))
    fx = sy * cp
    fy = cy * cp
    fz = sp
    l = math.sqrt(fx*fx + fy*fy + fz*fz)
    return [fx/l, fy/l, fz/l]

def add(a, b):
    return [a[0]+b[0], a[1]+b[1], a[2]+b[2]]

def line_sphere_intersect(ro, rd, sc, sr):
    oc = [ro[0]-sc[0], ro[1]-sc[1], ro[2]-sc[2]]
    b = oc[0]*rd[0] + oc[1]*rd[1] + oc[2]*rd[2]
    c = oc[0]*oc[0] + oc[1]*oc[1] + oc[2]*oc[2] - sr*sr
    disc = b*b - c
    if disc < 0: return None
    t = -b - math.sqrt(disc)
    if t < 0: return None
    return t

# =============================
# Menu layout
# =============================
def compute_menu_layout():
    global START_BTN_RECT, SENS_DEC_RECT, SENS_INC_RECT, SUMMARY_PLAY_RECT, SUMMARY_MENU_RECT
    BUTTON_W = 420; BUTTON_H = 70
    START_BTN_RECT = (WINDOW_W//2 - BUTTON_W//2, WINDOW_H//2 + 40, BUTTON_W, BUTTON_H)
    SENS_DEC_RECT = (WINDOW_W//2 - 160, WINDOW_H//2 - 70, 120, 60)
    SENS_INC_RECT = (WINDOW_W//2 + 40, WINDOW_H//2 - 70, 120, 60)
    SUMMARY_PLAY_RECT = (WINDOW_W//2 - 240, WINDOW_H//2 - 80, 200, 64)
    SUMMARY_MENU_RECT = (WINDOW_W//2 + 40, WINDOW_H//2 - 80, 200, 64)

compute_menu_layout()

# =============================
# Target logic
# =============================
def random_target_pos():
    # spawn only in front of the player
    x = random.uniform(-ARENA_HALF * 0.5, ARENA_HALF * 0.5)
    y = random.uniform(50, ARENA_DEPTH * 0.9)
    z = random.uniform(TARGET_MIN_Z, TARGET_MAX_Z)
    return [x, y, z]

def spawn_target():
    if len(targets) >= MAX_TARGETS:
        return
    ttl = random.uniform(2.8, 4.5)
    pos = random_target_pos()
    target = {
        'p': pos,
        'original_x': pos[0],  # Store original X position for animation
        'r': TARGET_RADIUS, 
        'born': time.time(), 
        'ttl': ttl,
        'move_direction': random.choice([-1, 1])  # Random initial direction
    }
    targets.append(target)

def update_targets():
    global targets
    now = time.time()
    alive = []
    
    for t in targets:
        # Check if target is still alive
        if now - t['born'] <= t['ttl']:
            # Update position if animation is enabled
            if animated_spheres:
                elapsed_time = now - t['born']
                # Calculate oscillating movement
                offset = math.sin(elapsed_time * SPHERE_MOVE_SPEED / SPHERE_MOVE_RANGE) * SPHERE_MOVE_RANGE * 0.5
                t['p'][0] = t['original_x'] + offset
                
                # Keep target within arena bounds
                if t['p'][0] < -ARENA_HALF * 0.8:
                    t['p'][0] = -ARENA_HALF * 0.8
                elif t['p'][0] > ARENA_HALF * 0.8:
                    t['p'][0] = ARENA_HALF * 0.8
            
            alive.append(t)
    
    targets = alive[:MAX_TARGETS]
    return targets

# =============================
# Input Handlers (Following 3D OpenGL Intro pattern)
# =============================
def keyboardListener(key, x, y):
    """
    Handles keyboard inputs for movement, FOV adjustment, and game controls.
    """
    global player_pos, current_fov, animated_spheres, mouse_locked, game_state
    
    # Exit game
    if key == b'\x1b':  # Escape key
        glutLeaveMainLoop()
    
    # Space to toggle mouse lock (only during gameplay)
    if key == b' ' and game_state == 'running':
        mouse_locked = not mouse_locked
        if mouse_locked:
            glutSetCursor(GLUT_CURSOR_NONE)
            glutWarpPointer(WINDOW_W//2, WINDOW_H//2)
        else:
            glutSetCursor(GLUT_CURSOR_LEFT_ARROW)
    
    # Movement controls (A and D for left/right)
    if game_state == 'running':
        if key == b'a' or key == b'A':  # Move left
            player_pos[0] -= MOVE_SPEED
            # Keep player within arena bounds
            if player_pos[0] < -ARENA_HALF + 50:
                player_pos[0] = -ARENA_HALF + 50
        
        if key == b'd' or key == b'D':  # Move right
            player_pos[0] += MOVE_SPEED
            # Keep player within arena bounds
            if player_pos[0] > ARENA_HALF - 50:
                player_pos[0] = ARENA_HALF - 50
        
        # FOV controls (W and S)
        if key == b'w' or key == b'W':  # Decrease FOV (zoom in)
            current_fov = clamp(current_fov - FOV_STEP, FOV_MIN, FOV_MAX)
        
        if key == b's' or key == b'S':  # Increase FOV (zoom out)
            current_fov = clamp(current_fov + FOV_STEP, FOV_MIN, FOV_MAX)
        
        # Toggle animated spheres
        if key == b'm' or key == b'M':
            animated_spheres = not animated_spheres

def specialKeyListener(key, x, y):
    """
    Handles special key inputs (arrow keys) - currently unused but following pattern.
    """
    pass

def mouseListener(button, state, x, y):
    """
    Handles mouse inputs for firing bullets and UI interactions.
    """
    global shots, score, misses, sensitivity, game_state
    
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        if game_state == 'menu':
            if point_in_rect(x, y, START_BTN_RECT):
                start_run()
                return
            if point_in_rect(x, y, SENS_DEC_RECT):
                sensitivity = clamp(sensitivity - 0.02, 0.02, 1.0)
                return
            if point_in_rect(x, y, SENS_INC_RECT):
                sensitivity = clamp(sensitivity + 0.02, 0.02, 1.0)
                return
            return

        if game_state == 'summary':
            if point_in_rect(x, y, SUMMARY_PLAY_RECT):
                start_run()
                return
            if point_in_rect(x, y, SUMMARY_MENU_RECT):
                game_state = 'menu'
                return
            return

        if game_state == 'running':
            shots += 1
            ro = list(player_pos)
            rd = look_dir_from_angles(yaw, pitch)
            best_t, best_idx = None, -1
            for i, t in enumerate(targets):
                tt = line_sphere_intersect(ro, rd, t['p'], t['r'])
                if tt is not None and 0 <= tt <= RAY_MAX_DIST:
                    if best_t is None or tt < best_t:
                        best_t, best_idx = tt, i
            if best_idx >= 0:
                score += 1
                del targets[best_idx]
            else:
                misses += 1

def motionListener(x, y):
    """
    Handles mouse motion for camera rotation.
    """
    global yaw, pitch
    if not mouse_locked or game_state != 'running':
        return
    dx = x - WINDOW_W//2
    dy = y - WINDOW_H//2
    yaw += dx * sensitivity
    pitch -= dy * sensitivity
    pitch = clamp(pitch, -85, 85)
    glutWarpPointer(WINDOW_W//2, WINDOW_H//2)

# =============================
# Helper functions
# =============================
def point_in_rect(px, py, rect):
    rx, ry, rw, rh = rect
    # GLUT mouse y origin is top, our UI uses bottom-left origin -> flip Y
    py_flipped = WINDOW_H - py
    return (rx <= px <= rx + rw) and (ry <= py_flipped <= ry + rh)

def start_run():
    global game_state, start_time, score, misses, shots, targets, mouse_locked, spawn_interval
    global player_pos, current_fov, animated_spheres
    game_state = 'running'
    start_time = time.time()
    score = misses = shots = 0
    targets = []
    spawn_interval = SPAWN_INTERVAL_START
    mouse_locked = True
    
    # Reset player position and FOV
    player_pos = [0.0, -300.0, CAM_HEIGHT]
    current_fov = FOVY
    animated_spheres = False
    
    glutSetCursor(GLUT_CURSOR_NONE)
    glutWarpPointer(WINDOW_W//2, WINDOW_H//2)

def end_run():
    global game_state, summary_data, mouse_locked
    game_state = 'summary'
    summary_data = {
        'score': score,
        'misses': misses,
        'shots': shots,
        'accuracy': (0 if shots == 0 else int(100 * score / max(1, shots))),
        'time': elapsed
    }
    mouse_locked = False
    glutSetCursor(GLUT_CURSOR_LEFT_ARROW)

# =============================
# Drawing helpers
# =============================
def draw_floor():
    glDisable(GL_LIGHTING)
    glBegin(GL_QUADS)
    glColor3f(0.28, 0.28, 0.30)
    glVertex3f(-ARENA_HALF, -ARENA_HALF, FLOOR_Z)
    glVertex3f( ARENA_HALF, -ARENA_HALF, FLOOR_Z)
    glVertex3f( ARENA_HALF,  ARENA_HALF, FLOOR_Z)
    glVertex3f(-ARENA_HALF,  ARENA_HALF, FLOOR_Z)
    glEnd()

    # subtle grid lines for depth cues
    glLineWidth(1)
    glBegin(GL_LINES)
    glColor3f(0.33, 0.33, 0.38)
    step = 100
    for i in range(int(-ARENA_HALF), int(ARENA_HALF)+1, step):
        glVertex3f(i, -ARENA_HALF, FLOOR_Z + 0.5)
        glVertex3f(i, ARENA_HALF, FLOOR_Z + 0.5)
        glVertex3f(-ARENA_HALF, i, FLOOR_Z + 0.5)
        glVertex3f(ARENA_HALF, i, FLOOR_Z + 0.5)
    glEnd()

def draw_checkboard_wall(x0, x1, y0, y1, z0, z1, tile_w, tile_h, flip_x=False, flip_y=False):
    """Helper draws a wall rectangle from (x0,y0,z0) to (x1,y1,z1) as a checkboard of tiles.
       tile_w: tile size in the horizontal / lateral axis, tile_h: vertical tile size."""
    # choose brown and silver
    brown = (0.2, 0.2, 0.2)
    silver = (0.75, 0.75, 0.75)
    # For vertical walls, two axes vary; determine which axes to iterate
    # We'll iterate along horizontal axis and vertical axis (z)
    # compute ranges
    # horizontal axis length:
    if abs(x1 - x0) > abs(y1 - y0):
        # varying along X horizontally
        hstart = min(x0, x1); hend = max(x0, x1)
        vstart = min(z0, z1); vend = max(z0, z1)
        hx = hstart
        h_steps = int(math.ceil((hend - hstart) / tile_w))
        v_steps = int(math.ceil((vend - vstart) / tile_h))
        for i in range(h_steps):
            for j in range(v_steps):
                left = hstart + i * tile_w
                right = min(hstart + (i+1) * tile_w, hend)
                bottom = vstart + j * tile_h
                top = min(vstart + (j+1) * tile_h, vend)
                idx = (i + j) % 2
                col = brown if idx == 0 else silver
                glColor3f(*col)
                glBegin(GL_QUADS)
                # Determine y coordinate (constant)
                y_const = y0
                glVertex3f(left, y_const, bottom)
                glVertex3f(right, y_const, bottom)
                glVertex3f(right, y_const, top)
                glVertex3f(left, y_const, top)
                glEnd()
    else:
        # varying along Y horizontally
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
                idx = (i + j) % 2
                col = brown if idx == 0 else silver
                glColor3f(*col)
                glBegin(GL_QUADS)
                x_const = x0
                glVertex3f(x_const, left, bottom)
                glVertex3f(x_const, right, bottom)
                glVertex3f(x_const, right, top)
                glVertex3f(x_const, left, top)
                glEnd()

def draw_walls():
    # Four surrounding walls with checkboard texture
    glDisable(GL_LIGHTING)
    glDisable(GL_CULL_FACE)  # Disable culling for walls to ensure visibility

    tile_w = 80.0
    tile_h = 80.0

    # back wall (y = ARENA_HALF)
    draw_checkboard_wall(-ARENA_HALF, ARENA_HALF, ARENA_HALF, ARENA_HALF, FLOOR_Z, WALL_HEIGHT, tile_w, tile_h)

    # left wall (x = -ARENA_HALF)
    draw_checkboard_wall(-ARENA_HALF, -ARENA_HALF, -ARENA_HALF, ARENA_HALF, FLOOR_Z, WALL_HEIGHT, tile_w, tile_h)

    # right wall (x = ARENA_HALF)
    draw_checkboard_wall(ARENA_HALF, ARENA_HALF, -ARENA_HALF, ARENA_HALF, FLOOR_Z, WALL_HEIGHT, tile_w, tile_h)

    # front wall (y = -ARENA_HALF)
    draw_checkboard_wall(-ARENA_HALF, ARENA_HALF, -ARENA_HALF, -ARENA_HALF, FLOOR_Z, WALL_HEIGHT, tile_w, tile_h)

    glEnable(GL_CULL_FACE)  # Re-enable culling

def draw_targets():
    # Blue spheres with material/specular highlight
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHT1)

    for t in targets:
        glPushMatrix()
        glTranslatef(t['p'][0], t['p'][1], t['p'][2])
        
        # Different color for animated spheres
        if animated_spheres:
            glColor3f(0.98, 0.48, 0.02)  # Orange for animated
        else:
            glColor3f(0.02, 0.48, 0.98)  # Blue for static
            
        spec = (GLfloat * 4)(0.9, 0.9, 1.0, 1.0)
        glMaterialfv(GL_FRONT, GL_SPECULAR, spec)
        glMaterialf(GL_FRONT, GL_SHININESS, 60.0)
        gluSphere(quadric, t['r'], 32, 24)
        glPopMatrix()

    glDisable(GL_COLOR_MATERIAL)

def draw_crosshair():
    glDisable(GL_LIGHTING)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    cx, cy = WINDOW_W//2, WINDOW_H//2
    size = 10
    glLineWidth(2)
    glBegin(GL_LINES)
    glColor3f(1, 1, 1)
    glVertex2f(cx - size, cy); glVertex2f(cx + size, cy)
    glVertex2f(cx, cy - size); glVertex2f(cx, cy + size)
    glEnd()
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)

def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))

def draw_button(x, y, w, h, label):
    # background
    glColor3f(0.08, 0.55, 0.95)
    glBegin(GL_QUADS)
    glVertex2f(x, y); glVertex2f(x + w, y); glVertex2f(x + w, y + h); glVertex2f(x, y + h)
    glEnd()
    # border
    glColor3f(1, 1, 1)
    glBegin(GL_LINE_LOOP)
    glVertex2f(x, y); glVertex2f(x + w, y); glVertex2f(x + w, y + h); glVertex2f(x, y + h)
    glEnd()
    # label
    glColor3f(1, 1, 1)
    draw_text(x + 18, y + h//2 - 8, label)

# =============================
# Camera & Main Loop
# =============================
def setupCamera():
    """
    Configures the camera's projection and view settings with dynamic FOV.
    """
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(current_fov, ASPECT, NEAR, FAR)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    f = look_dir_from_angles(yaw, pitch)
    eye = player_pos
    center = add(eye, f)
    up = [0, 0, 1]
    gluLookAt(eye[0], eye[1], eye[2], center[0], center[1], center[2], up[0], up[1], up[2])

def idle():
    """
    Idle function that runs continuously for real-time updates.
    """
    global start_time, elapsed, spawn_interval
    now = time.time()
    if start_time is None:
        start_time = now
    elapsed = now - start_time

    if game_state == 'running':
        spawn_interval = max(SPAWN_INTERVAL_MIN, spawn_interval - SPAWN_ACCEL)
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

        if elapsed >= SESSION_TIME:
            end_run()

    glutPostRedisplay()

def draw_hud():
    # Setup 2D rendering properly
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    
    draw_crosshair()
    glColor3f(1, 1, 1)
    draw_text(18, WINDOW_H - 36, f"Score: {score}   Misses: {misses}   Acc: { (0 if shots == 0 else int(100 * score / max(1, shots))) }%")
    draw_text(18, WINDOW_H - 68, f"Targets: {len(targets)}/{MAX_TARGETS}   Time: {elapsed:0.1f}s   Sens: {sensitivity:.2f}")
    draw_text(18, WINDOW_H - 100, f"FOV: {current_fov:.1f}°   Pos: ({player_pos[0]:.0f}, {player_pos[1]:.0f})")
    draw_text(18, WINDOW_H - 132, f"Animated: {'ON' if animated_spheres else 'OFF'}   [M] Toggle Animation")
    draw_text(18, WINDOW_H - 164, f"Controls: A/D=Move, W/S=FOV, M=Animation, Space=Mouse Lock")
    
    # Restore 3D state
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

def draw_start_screen():
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    # Setup 2D projection properly
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    # dim background panel
    panel_w, panel_h = 820, 520
    px = WINDOW_W//2 - panel_w//2
    py = WINDOW_H//2 - panel_h//2
    glColor3f(0.04, 0.04, 0.05)
    glBegin(GL_QUADS)
    glVertex2f(px, py)
    glVertex2f(px + panel_w, py)
    glVertex2f(px + panel_w, py + panel_h)
    glVertex2f(px, py + panel_h)
    glEnd()

    # Title & controls
    glColor3f(1, 1, 1)
    draw_text(WINDOW_W//2 - 160, WINDOW_H//2 + 180, "Enhanced Aim Lab 3D - Menu")
    bx, by, bw, bh = START_BTN_RECT
    draw_button(bx, by, bw, bh, "Click Here to Start")
    glColor3f(1, 1, 1)
    draw_text(WINDOW_W//2 - 110, WINDOW_H//2 + 20, "Adjust Mouse Sensitivity")
    sd = SENS_DEC_RECT; si = SENS_INC_RECT
    draw_button(sd[0], sd[1], sd[2], sd[3], "- Decrease")
    draw_button(si[0], si[1], si[2], si[3], "+ Increase")
    glColor3f(1, 1, 1)
    draw_text(WINDOW_W//2 - 60, WINDOW_H//2 - 130, f"Current Sensitivity: {sensitivity:.2f}")
    draw_text(WINDOW_W//2 - 200, WINDOW_H//2 - 170, "Game Controls:")
    draw_text(WINDOW_W//2 - 200, WINDOW_H//2 - 200, "A/D: Move Left/Right | W/S: Adjust FOV")
    draw_text(WINDOW_W//2 - 200, WINDOW_H//2 - 230, "M: Toggle Sphere Animation | Space: Lock Mouse")

def draw_summary_screen():
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    # Setup 2D projection properly
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    panel_w, panel_h = 820, 420
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
    draw_text(WINDOW_W//2 - 120, WINDOW_H//2 + 120, "Run Summary")
    draw_text(WINDOW_W//2 - 180, WINDOW_H//2 + 40, f"Time: {summary_data.get('time', 0):.1f}s")
    draw_text(WINDOW_W//2 - 180, WINDOW_H//2 + 10, f"Score: {summary_data.get('score', 0)}")
    draw_text(WINDOW_W//2 - 180, WINDOW_H//2 - 20, f"Shots: {summary_data.get('shots', 0)}")
    draw_text(WINDOW_W//2 - 180, WINDOW_H//2 - 50, f"Misses: {summary_data.get('misses', 0)}")
    draw_text(WINDOW_W//2 - 180, WINDOW_H//2 - 80, f"Accuracy: {summary_data.get('accuracy', 0)}%")

    spx, spy, sw, sh = SUMMARY_PLAY_RECT
    mpx, mpy, mw, mh = SUMMARY_MENU_RECT
    draw_button(spx, spy, sw, sh, "Play Again")
    draw_button(mpx, mpy, mw, mh, "Main Menu")

# =============================
# Display (Following 3D OpenGL Intro pattern)
# =============================
def showScreen():
    """
    Display function to render the game scene based on current state.
    """
    if game_state == 'menu':
        draw_start_screen()
        glutSwapBuffers()
        return

    if game_state == 'summary':
        draw_summary_screen()
        glutSwapBuffers()
        return

    # running
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WINDOW_W, WINDOW_H)

    setupCamera()

    draw_floor()
    draw_walls()
    draw_targets()

    # overlay HUD
    draw_hud()

    glutSwapBuffers()

# =============================
# Initialization / Lighting
# =============================
def init_gl():
    global quadric
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_CULL_FACE)
    glCullFace(GL_BACK)

    # brighter clear color but still contrasty
    glClearColor(0.06, 0.07, 0.09, 1)

    # Lighting: main directional + soft fill
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHT1)

    # directional key light
    light0_pos = (GLfloat * 4)(-0.2, -0.5, 1.0, 0.0)   # directional
    light0_diff = (GLfloat * 4)(0.95, 0.95, 1.0, 1.0)
    light0_amb = (GLfloat * 4)(0.12, 0.12, 0.14, 1.0)
    light0_spec = (GLfloat * 4)(0.9, 0.9, 0.95, 1.0)
    glLightfv(GL_LIGHT0, GL_POSITION, light0_pos)
    glLightfv(GL_LIGHT0, GL_DIFFUSE, light0_diff)
    glLightfv(GL_LIGHT0, GL_AMBIENT, light0_amb)
    glLightfv(GL_LIGHT0, GL_SPECULAR, light0_spec)

    # soft overhead fill
    light1_pos = (GLfloat * 4)(0.0, 0.0, 1.0, 0.0)
    light1_diff = (GLfloat * 4)(0.40, 0.42, 0.48, 1.0)
    light1_amb = (GLfloat * 4)(0.06, 0.06, 0.07, 1.0)
    glLightfv(GL_LIGHT1, GL_POSITION, light1_pos)
    glLightfv(GL_LIGHT1, GL_DIFFUSE, light1_diff)
    glLightfv(GL_LIGHT1, GL_AMBIENT, light1_amb)

    # default material
    mat_amb = (GLfloat * 4)(0.12, 0.12, 0.14, 1.0)
    mat_diff = (GLfloat * 4)(0.9, 0.9, 0.9, 1.0)
    mat_spec = (GLfloat * 4)(0.4, 0.4, 0.45, 1.0)
    glMaterialfv(GL_FRONT, GL_AMBIENT, mat_amb)
    glMaterialfv(GL_FRONT, GL_DIFFUSE, mat_diff)
    glMaterialfv(GL_FRONT, GL_SPECULAR, mat_spec)
    glMaterialf(GL_FRONT, GL_SHININESS, 25.0)

    quadric = gluNewQuadric()
    gluQuadricNormals(quadric, GLU_SMOOTH)

def reshape(w, h):
    global WINDOW_W, WINDOW_H, ASPECT
    WINDOW_W, WINDOW_H = max(1, w), max(1, h)
    ASPECT = WINDOW_W / WINDOW_H
    compute_menu_layout()
    glViewport(0, 0, WINDOW_W, WINDOW_H)

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_W, WINDOW_H)
    glutInitWindowPosition(50, 10)
    glutCreateWindow(b"Enhanced Aim Lab 3D - PyOpenGL")

    init_gl()

    glutDisplayFunc(showScreen)
    glutIdleFunc(idle)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutPassiveMotionFunc(motionListener)
    glutMotionFunc(motionListener)
    glutReshapeFunc(reshape)

    glutMainLoop()

if __name__ == '__main__':

    main()
