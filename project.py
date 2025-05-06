from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import math
import random
import time
import sys # For glutInit

# --- Constants and Global Game Variables ---
# Window
SCREEN_WIDTH, SCREEN_HEIGHT = 1024, 768
# Game States
STATE_PLAYING = 0
STATE_LEVEL_TRANSITION = 1
STATE_GAME_OVER_TRANSITION = 2
STATE_YOU_WIN = 3
STATE_RESTART_LEVEL_TRANSITION = 4 # For when game over, then restart

game_state = STATE_PLAYING
current_level = 1
max_levels = 10
score = 0

# Player settings
PLAYER_SPEED = 5.0  # Units per second
PLAYER_ROTATE_SPEED = 90.0 # Degrees per second
PLAYER_HEIGHT = 1.0 # For 1st person view y-offset
PLAYER_EYE_HEIGHT = 1.6
PLAYER_RADIUS = 0.4 # For collision
PLAYER_MAX_HEALTH = 100
PLAYER_MAX_AMMO = 50
PLAYER_RELOAD_TIME = 0.3 # seconds
PLAYER_SHOOT_COOLDOWN_TIME = 0.3 # seconds

# Bullet settings
BULLET_SPEED = 20.0
BULLET_RADIUS = 0.1
BULLET_LIFESPAN = 3.0 # seconds

# Enemy settings (base values, will be scaled by type)
ENEMY_BASE_SPEED_MULTIPLIER = 1.0
ENEMY_BASE_RELOAD_TIME = 1.0
ENEMY_BASE_HEALTH = 5
ENEMY_RADIUS = 0.5 # For collision

# Perk settings
PERK_RADIUS = 0.3
PERK_DURATION = 5.0 # seconds
PERK_ROTATION_SPEED = 90.0 # degrees per second
PERK_DROP_CHANCE = 0.2 # 20% chance

# Dungeon settings
DUNGEON_SIZE_X = 30.0
DUNGEON_SIZE_Z = 30.0
WALL_HEIGHT = 5.0

# Camera
CAMERA_MODE_FIRST_PERSON = 0
CAMERA_MODE_THIRD_PERSON = 1
camera_mode = CAMERA_MODE_FIRST_PERSON
# Third person camera
tp_camera_distance = 5.0
tp_camera_pitch = -20.0 # Angle up/down
tp_camera_yaw_offset = 0.0 # Angle around player

# Global lists for game objects
player = {}
enemies = []
bullets = []
perks = []

# Timing
last_time = 0.0
transition_timer = 0.0
TRANSITION_DURATION = 2.0 # seconds
transition_color = [0.0, 0.0, 0.0] # r, g, b

# Input states
keys_pressed = {} # Store state of W,A,S,D, Space
special_keys_pressed = {} # Store state of arrow keys

# --- Helper Functions (Math, etc.) ---
def vector_length(v):
    return math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)

def normalize_vector(v):
    l = vector_length(v)
    if l == 0:
        return [0, 0, 0]
    return [v[0]/l, v[1]/l, v[2]/l]

def distance_3d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)

def check_aabb_collision(obj1_pos, obj1_size, obj2_pos, obj2_size):
    # Assuming size is a scalar (radius) and pos is center
    # This is a sphere collision, more accurate for circular/spherical objects
    dist = distance_3d(obj1_pos, obj2_pos)
    return dist < (obj1_size + obj2_size)

# --- Game Object Initialization and Management ---
def init_player():
    global player
    player = {
        'pos': [DUNGEON_SIZE_X / 2, PLAYER_HEIGHT / 2, DUNGEON_SIZE_Z / 2],
        'rotation_y': 0.0, # Yaw
        'rotation_x': 0.0, # Pitch (for first person view)
        'health': PLAYER_MAX_HEALTH,
        'ammo': PLAYER_MAX_AMMO,
        'shoot_cooldown': 0.0,
        'reload_cooldown': 0.0, # Not used per bullet, but for a potential reload action
        'active_perks': {}, # {'type': end_time}
        'score': 0,
        'speed': PLAYER_SPEED,
        'bullets_to_kill_enemy': 0 # This will be set by perk
    }

def get_enemy_config(level):
    if 1 <= level <= 3: # Weak
        return {'type': 'weak', 'health': 5, 'speed_mult': 2.0, 'reload': 1.5, 'points': 10, 'color': [0.5, 0.4, 0.3], 'size': 0.5}
    elif 4 <= level <= 6: # Medium
        return {'type': 'medium', 'health': 7, 'speed_mult': 1.7, 'reload': 0.1, 'points': 15, 'color': [0.8, 0.2, 0.1], 'size': 0.6}
    elif 7 <= level <= 9: # Strong
        return {'type': 'strong', 'health': 10, 'speed_mult': 1.3, 'reload': 0.5, 'points': 20, 'color': [0.2, 0.2, 0.6], 'size': 0.7}
    elif level == 10: # Boss
        return {'type': 'boss', 'health': 50, 'speed_mult': 1.0, 'reload': PLAYER_RELOAD_TIME, 'points': 100, 'color': [0.1, 0.1, 0.1], 'size': 1.5, 'is_boss': True}
    return {}

def spawn_enemy(level):
    config = get_enemy_config(level)
    if not config: return

    # Spawn away from center and walls
    margin = 2.0
    x = random.uniform(margin, DUNGEON_SIZE_X - margin)
    z = random.uniform(margin, DUNGEON_SIZE_Z - margin)
    
    # Ensure enemy is not spawned too close to player
    while distance_3d([x, config['size'], z], player['pos']) < 5.0:
        x = random.uniform(margin, DUNGEON_SIZE_X - margin)
        z = random.uniform(margin, DUNGEON_SIZE_Z - margin)

    enemies.append({
        'pos': [x, config['size'], z], # y is half size so it sits on ground
        'type': config['type'],
        'max_health': config['health'],
        'health': config['health'],
        'speed': PLAYER_SPEED * config['speed_mult'],
        'reload_time': config['reload'],
        'shoot_cooldown': random.uniform(0, config['reload']), # Stagger initial shots
        'points': config['points'],
        'color': config['color'],
        'size': config['size'],
        'is_boss': config.get('is_boss', False)
    })

def init_level(level_num):
    global current_level, enemies, bullets, perks, player
    current_level = level_num
    enemies.clear()
    bullets.clear()
    perks.clear()

    # Reset player position slightly for new level feel, or keep same
    # player['pos'] = [DUNGEON_SIZE_X / 2, PLAYER_HEIGHT / 2, DUNGEON_SIZE_Z / 2]


    num_enemies = 0
    if 1 <= level_num <= 3:
        num_enemies = 2 + level_num # 3, 4, 5 enemies
    elif 4 <= level_num <= 6:
        num_enemies = 3 + (level_num - 3) # 4, 5, 6 enemies
    elif 7 <= level_num <= 9:
        num_enemies = 4 + (level_num - 6) # 5, 6, 7 enemies
    elif level_num == 10: # Boss level
        spawn_enemy(10) # Spawn the boss
        # Spawn a few other types for chaos
        for _ in range(2): spawn_enemy(random.randint(1,3)) # weak
        for _ in range(1): spawn_enemy(random.randint(4,6)) # medium
        num_enemies = 0 # Boss handled separately

    for _ in range(num_enemies):
        spawn_enemy(level_num)
    
    # Ensure player health/ammo is not reset unless it's a new game or restart
    # For level progression, keep current health/ammo unless a perk gives it back.

def create_bullet(pos, direction_vec, owner, damage):
    start_pos = list(pos) # Create a copy
    # Offset bullet start slightly in front of shooter
    offset_dist = 0.5 # Player/Enemy radius + bullet radius
    start_pos[0] += direction_vec[0] * offset_dist
    start_pos[1] += direction_vec[1] * offset_dist
    start_pos[2] += direction_vec[2] * offset_dist

    bullets.append({
        'pos': start_pos,
        'dir': direction_vec,
        'owner': owner,
        'damage': damage,
        'lifespan': BULLET_LIFESPAN,
        'color': [1.0, 1.0, 0.0] if owner == 'PLAYER' else [1.0, 0.5, 0.0] # Yellow for player, Orange for enemy
    })

def spawn_perk(position, perk_type):
    color_map = {
        "AMMO": [0.0, 1.0, 1.0], # Cyan
        "HEALTH": [0.0, 1.0, 0.0], # Green
        "DAMAGE": [1.0, 0.0, 1.0]  # Magenta
    }
    perks.append({
        'pos': [position[0], PERK_RADIUS, position[2]], # Sit on ground
        'type': perk_type,
        'color': color_map.get(perk_type, [1.0,1.0,1.0]),
        'rotation_angle': 0.0
    })

# --- Update Functions ---
def update_player(delta_time):
    global player, camera_mode, tp_camera_pitch, tp_camera_yaw_offset

    # Perks
    active_perk_types = list(player['active_perks'].keys())
    for perk_type in active_perk_types:
        if time.time() > player['active_perks'][perk_type]:
            del player['active_perks'][perk_type]
            if perk_type == "DAMAGE":
                print("Double Damage ended") # For debug
    
    if "HEALTH" in player['active_perks']:
        player['health'] = PLAYER_MAX_HEALTH # Unlimited health effect

    # Movement
    speed = player['speed'] * delta_time
    dx, dz = 0, 0

    # Calculate forward vector based on player's Y rotation (yaw)
    forward_x = math.sin(math.radians(player['rotation_y']))
    forward_z = -math.cos(math.radians(player['rotation_y']))

    # Calculate right vector (strafe)
    right_x = math.cos(math.radians(player['rotation_y']))
    right_z = math.sin(math.radians(player['rotation_y']))

    if keys_pressed.get(b'w'):
        dx += forward_x * speed
        dz += forward_z * speed
    if keys_pressed.get(b's'):
        dx -= forward_x * speed
        dz -= forward_z * speed
    if keys_pressed.get(b'a'): # Strafe left
        dx -= right_x * speed
        dz -= right_z * speed
    if keys_pressed.get(b'd'): # Strafe right
        dx += right_x * speed
        dz += right_z * speed
    
    # First person camera pitch (mouse would be better, but using keys for now)
    if camera_mode == CAMERA_MODE_FIRST_PERSON:
        if special_keys_pressed.get(GLUT_KEY_UP):
            player['rotation_x'] = max(-89.0, player['rotation_x'] - PLAYER_ROTATE_SPEED * delta_time * 0.5)
        if special_keys_pressed.get(GLUT_KEY_DOWN):
            player['rotation_x'] = min(89.0, player['rotation_x'] + PLAYER_ROTATE_SPEED * delta_time * 0.5)
        if special_keys_pressed.get(GLUT_KEY_LEFT):
            player['rotation_y'] -= PLAYER_ROTATE_SPEED * delta_time
        if special_keys_pressed.get(GLUT_KEY_RIGHT):
            player['rotation_y'] += PLAYER_ROTATE_SPEED * delta_time
    
    # Third person camera controls
    if camera_mode == CAMERA_MODE_THIRD_PERSON:
        if special_keys_pressed.get(GLUT_KEY_UP):
            tp_camera_pitch = max(-89.0, tp_camera_pitch - PLAYER_ROTATE_SPEED * delta_time * 0.5)
        if special_keys_pressed.get(GLUT_KEY_DOWN):
            tp_camera_pitch = min(0.0, tp_camera_pitch + PLAYER_ROTATE_SPEED * delta_time * 0.5) # Don't go below player
        if special_keys_pressed.get(GLUT_KEY_LEFT):
            tp_camera_yaw_offset -= PLAYER_ROTATE_SPEED * delta_time
        if special_keys_pressed.get(GLUT_KEY_RIGHT):
            tp_camera_yaw_offset += PLAYER_ROTATE_SPEED * delta_time


    new_x = player['pos'][0] + dx
    new_z = player['pos'][2] + dz

    # Collision with dungeon walls
    half_player_w = PLAYER_RADIUS
    if new_x - half_player_w < 0: new_x = half_player_w
    if new_x + half_player_w > DUNGEON_SIZE_X: new_x = DUNGEON_SIZE_X - half_player_w
    if new_z - half_player_w < 0: new_z = half_player_w
    if new_z + half_player_w > DUNGEON_SIZE_Z: new_z = DUNGEON_SIZE_Z - half_player_w
    
    player['pos'][0] = new_x
    player['pos'][2] = new_z

    # Shooting
    if player['shoot_cooldown'] > 0:
        player['shoot_cooldown'] -= delta_time
    
    if keys_pressed.get(b' ') and player['shoot_cooldown'] <= 0:
        current_ammo = player['ammo']
        if "AMMO" in player['active_perks']:
            current_ammo = PLAYER_MAX_AMMO + 1 # Effectively infinite

        if current_ammo > 0:
            player['shoot_cooldown'] = PLAYER_SHOOT_COOLDOWN_TIME
            if "AMMO" not in player['active_perks']:
                player['ammo'] -= 1

            # Calculate bullet direction based on player's full orientation (yaw and pitch)
            pitch_rad = math.radians(player['rotation_x'])
            yaw_rad = math.radians(player['rotation_y'])

            bullet_dir_x = math.sin(yaw_rad) * math.cos(pitch_rad)
            bullet_dir_y = -math.sin(pitch_rad) # Negative for up
            bullet_dir_z = -math.cos(yaw_rad) * math.cos(pitch_rad)
            
            direction = normalize_vector([bullet_dir_x, bullet_dir_y, bullet_dir_z])
            
            # Bullet start position: player's eye position for first person
            bullet_start_pos = [player['pos'][0], player['pos'][1] + PLAYER_EYE_HEIGHT - PLAYER_HEIGHT/2, player['pos'][2]]
            
            damage = 1
            if "DAMAGE" in player['active_perks']:
                damage = 2
            create_bullet(bullet_start_pos, direction, 'PLAYER', damage)

def update_enemies(delta_time):
    global game_state, score
    for enemy in list(enemies): # Iterate over a copy for safe removal
        # Movement towards player
        dir_to_player = [player['pos'][0] - enemy['pos'][0], 0, player['pos'][2] - enemy['pos'][2]] # Enemies stay on ground
        dir_to_player_normalized = normalize_vector(dir_to_player)
        
        move_dist = enemy['speed'] * delta_time
        
        # Simple avoidance: if too close, don't move closer
        if distance_3d(player['pos'], enemy['pos']) > enemy['size'] + PLAYER_RADIUS + 0.1: # Don't get stuck
            enemy['pos'][0] += dir_to_player_normalized[0] * move_dist
            enemy['pos'][2] += dir_to_player_normalized[2] * move_dist

        # Collision with dungeon walls for enemies
        half_enemy_w = enemy['size']
        if enemy['pos'][0] - half_enemy_w < 0: enemy['pos'][0] = half_enemy_w
        if enemy['pos'][0] + half_enemy_w > DUNGEON_SIZE_X: enemy['pos'][0] = DUNGEON_SIZE_X - half_enemy_w
        if enemy['pos'][2] - half_enemy_w < 0: enemy['pos'][2] = half_enemy_w
        if enemy['pos'][2] + half_enemy_w > DUNGEON_SIZE_Z: enemy['pos'][2] = DUNGEON_SIZE_Z - half_enemy_w


        # Shooting
        if enemy['shoot_cooldown'] > 0:
            enemy['shoot_cooldown'] -= delta_time
        else:
            enemy['shoot_cooldown'] = enemy['reload_time']
            # Aim at player's current center position when bullet is fired
            bullet_target_pos = [player['pos'][0], player['pos'][1], player['pos'][2]]
            
            enemy_bullet_dir = normalize_vector([
                bullet_target_pos[0] - enemy['pos'][0],
                bullet_target_pos[1] - enemy['pos'][1], # Aim slightly up if player is higher
                bullet_target_pos[2] - enemy['pos'][2]
            ])

            if enemy.get('is_boss'): # Boss spread shot
                num_boss_bullets = 3
                spread_angle = 15 # degrees
                base_yaw = math.degrees(math.atan2(enemy_bullet_dir[0], -enemy_bullet_dir[2])) # Get base yaw from dir

                for i in range(num_boss_bullets):
                    angle_offset = (i - (num_boss_bullets - 1) / 2.0) * spread_angle
                    current_yaw = base_yaw + angle_offset
                    
                    dir_x = math.sin(math.radians(current_yaw))
                    dir_y = enemy_bullet_dir[1] # Keep original Y component for simplicity or adjust
                    dir_z = -math.cos(math.radians(current_yaw))
                    
                    spread_dir = normalize_vector([dir_x, dir_y, dir_z])
                    create_bullet(enemy['pos'], spread_dir, 'ENEMY', 1)
            else:
                 create_bullet(enemy['pos'], enemy_bullet_dir, 'ENEMY', 1)


def update_bullets(delta_time):
    global player, game_state, score
    for bullet in list(bullets): # Iterate over a copy for safe removal
        bullet['pos'][0] += bullet['dir'][0] * BULLET_SPEED * delta_time
        bullet['pos'][1] += bullet['dir'][1] * BULLET_SPEED * delta_time
        bullet['pos'][2] += bullet['dir'][2] * BULLET_SPEED * delta_time
        bullet['lifespan'] -= delta_time

        # Remove old bullets or out-of-bounds bullets
        if bullet['lifespan'] <= 0 or \
           bullet['pos'][0] < -1 or bullet['pos'][0] > DUNGEON_SIZE_X + 1 or \
           bullet['pos'][1] < -1 or bullet['pos'][1] > WALL_HEIGHT + 1 or \
           bullet['pos'][2] < -1 or bullet['pos'][2] > DUNGEON_SIZE_Z + 1:
            bullets.remove(bullet)
            continue

        # Collision detection
        if bullet['owner'] == 'PLAYER':
            for enemy in list(enemies):
                if check_aabb_collision(bullet['pos'], BULLET_RADIUS, enemy['pos'], enemy['size']):
                    if bullet in bullets: bullets.remove(bullet) # Bullet hits once
                    
                    damage_dealt = bullet['damage']
                    enemy['health'] -= damage_dealt
                    
                    if enemy['health'] <= 0:
                        player['score'] += enemy['points']
                        enemies.remove(enemy)
                        if random.random() < PERK_DROP_CHANCE:
                            perk_type = random.choice(["AMMO", "HEALTH", "DAMAGE"])
                            spawn_perk(enemy['pos'], perk_type)
                    break # Bullet can only hit one enemy
        elif bullet['owner'] == 'ENEMY':
            if check_aabb_collision(bullet['pos'], BULLET_RADIUS, player['pos'], PLAYER_RADIUS):
                if "HEALTH" not in player['active_perks']: # Invincible if health perk active
                    player['health'] -= bullet['damage']
                
                if bullet in bullets: bullets.remove(bullet)

                if player['health'] <= 0 and game_state == STATE_PLAYING:
                    player['health'] = 0
                    start_transition(STATE_GAME_OVER_TRANSITION, [1.0, 0.0, 0.0]) # Red
                    break


def update_perks(delta_time):
    global player
    for perk in list(perks):
        perk['rotation_angle'] = (perk['rotation_angle'] + PERK_ROTATION_SPEED * delta_time) % 360
        if check_aabb_collision(player['pos'], PLAYER_RADIUS, perk['pos'], PERK_RADIUS):
            perk_type = perk['type']
            player['active_perks'][perk_type] = time.time() + PERK_DURATION
            
            if perk_type == "AMMO":
                player['ammo'] = PLAYER_MAX_AMMO # Refill ammo too
                print("Unlimited Ammo activated!")
            elif perk_type == "HEALTH":
                player['health'] = PLAYER_MAX_HEALTH # Refill health too
                print("Unlimited Health activated!")
            elif perk_type == "DAMAGE":
                print("Double Damage activated!")

            perks.remove(perk)

def check_level_completion():
    global game_state, current_level
    if not enemies and game_state == STATE_PLAYING:
        if current_level == max_levels: # Beat the boss on level 10
            game_state = STATE_YOU_WIN
        else:
            start_transition(STATE_LEVEL_TRANSITION, [0.0, 1.0, 0.0]) # Green

def start_transition(next_state_after_transition, color):
    global game_state, transition_timer, transition_color, next_game_state_after_transition
    game_state = next_state_after_transition # This is the transition state itself
    transition_timer = TRANSITION_DURATION
    transition_color = color
    # Store what the actual next state should be (e.g. STATE_PLAYING for next level)
    if next_state_after_transition == STATE_LEVEL_TRANSITION:
        next_game_state_after_transition = STATE_PLAYING 
    elif next_state_after_transition == STATE_GAME_OVER_TRANSITION:
        next_game_state_after_transition = STATE_RESTART_LEVEL_TRANSITION


def update_game_state(delta_time):
    global game_state, transition_timer, current_level, player

    if game_state == STATE_PLAYING:
        update_player(delta_time)
        update_enemies(delta_time)
        update_bullets(delta_time)
        update_perks(delta_time)
        check_level_completion()

    elif game_state == STATE_LEVEL_TRANSITION:
        transition_timer -= delta_time
        if transition_timer <= 0:
            current_level += 1
            init_level(current_level)
            game_state = STATE_PLAYING
            
    elif game_state == STATE_GAME_OVER_TRANSITION:
        transition_timer -= delta_time
        if transition_timer <= 0:
            # Game over, option to restart level (or could go to a menu)
            player['health'] = PLAYER_MAX_HEALTH # Restore health for restart
            player['ammo'] = PLAYER_MAX_AMMO   # Restore ammo
            init_level(current_level) # Restart current level
            game_state = STATE_PLAYING
    
    elif game_state == STATE_YOU_WIN:
        # Display "You Win!" message, game essentially pauses here
        pass


# --- Drawing Functions ---
def draw_text(x, y, text_string, r=1.0, g=1.0, b=1.0, font=GLUT_BITMAP_HELVETICA_18):
    glColor3f(r, g, b)
    glRasterPos2f(x, y)
    for character in text_string:
        glutBitmapCharacter(font, ord(character))

def draw_cube_primitive(size): # Simple cube using GL_QUADS
    s = size / 2.0
    glBegin(GL_QUADS)
    # Front face
    glNormal3f(0,0,1)
    glVertex3f(-s, -s, s); glVertex3f(s, -s, s); glVertex3f(s, s, s); glVertex3f(-s, s, s)
    # Back face
    glNormal3f(0,0,-1)
    glVertex3f(-s, -s, -s); glVertex3f(-s, s, -s); glVertex3f(s, s, -s); glVertex3f(s, -s, -s)
    # Top face
    glNormal3f(0,1,0)
    glVertex3f(-s, s, -s); glVertex3f(-s, s, s); glVertex3f(s, s, s); glVertex3f(s, s, -s)
    # Bottom face
    glNormal3f(0,-1,0)
    glVertex3f(-s, -s, -s); glVertex3f(s, -s, -s); glVertex3f(s, -s, s); glVertex3f(-s, -s, s)
    # Right face
    glNormal3f(1,0,0)
    glVertex3f(s, -s, -s); glVertex3f(s, s, -s); glVertex3f(s, s, s); glVertex3f(s, -s, s)
    # Left face
    glNormal3f(-1,0,0)
    glVertex3f(-s, -s, -s); glVertex3f(-s, -s, s); glVertex3f(-s, s, s); glVertex3f(-s, s, -s)
    glEnd()

def draw_player_model(): # Simple representation for 3rd person
    glPushMatrix()
    # Body
    glColor3f(0.1, 0.3, 0.8) # Blueish
    glScalef(0.8, 1.5, 0.5) # W, H, D
    glutSolidCube(1.0) # Using PLAYER_RADIUS as base
    glPopMatrix()

    # Head (optional, simple sphere)
    glPushMatrix()
    glTranslatef(0, 0.9, 0) # Above body center
    glColor3f(0.9, 0.7, 0.6) # Skin-ish
    glutSolidSphere(0.3, 10, 10)
    glPopMatrix()

def draw_dungeon():
    # Determine colors based on level
    floor_color = [0.5, 0.5, 0.5] # Default stone
    wall_color = [0.4, 0.4, 0.4]
    
    if 1 <= current_level <= 3: # Stone
        floor_color = [0.6, 0.55, 0.5]
        wall_color = [0.5, 0.45, 0.4]
    elif 4 <= current_level <= 6: # Lava
        floor_color = [0.7, 0.3, 0.1]
        wall_color = [0.5, 0.2, 0.05]
        if current_level == 10 and game_state == STATE_PLAYING and any(e.get('is_boss') for e in enemies): # Boss on lava level
             floor_color = [0.3, 0.05, 0.05] # Darker red for boss
             wall_color = [0.2, 0.0, 0.0]
    elif 7 <= current_level <= 10: # Ice/Shadow
        floor_color = [0.7, 0.8, 0.95]
        wall_color = [0.5, 0.6, 0.75]
        if current_level == 10 and game_state == STATE_PLAYING and any(e.get('is_boss') for e in enemies): # Boss on ice level
             floor_color = [0.2, 0.2, 0.4] # Darker blue/purple for boss
             wall_color = [0.1, 0.1, 0.3]


    # Floor
    glColor3fv(floor_color)
    glBegin(GL_QUADS)
    glNormal3f(0, 1, 0) # Normal pointing up
    glVertex3f(0, 0, 0)
    glVertex3f(DUNGEON_SIZE_X, 0, 0)
    glVertex3f(DUNGEON_SIZE_X, 0, DUNGEON_SIZE_Z)
    glVertex3f(0, 0, DUNGEON_SIZE_Z)
    glEnd()

    # Walls
    glColor3fv(wall_color)
    # Front wall (Z=0)
    glBegin(GL_QUADS); glNormal3f(0,0,1); glVertex3f(0,0,0); glVertex3f(DUNGEON_SIZE_X,0,0); glVertex3f(DUNGEON_SIZE_X,WALL_HEIGHT,0); glVertex3f(0,WALL_HEIGHT,0); glEnd()
    # Back wall (Z=DUNGEON_SIZE_Z)
    glBegin(GL_QUADS); glNormal3f(0,0,-1); glVertex3f(0,0,DUNGEON_SIZE_Z); glVertex3f(0,WALL_HEIGHT,DUNGEON_SIZE_Z); glVertex3f(DUNGEON_SIZE_X,WALL_HEIGHT,DUNGEON_SIZE_Z); glVertex3f(DUNGEON_SIZE_X,0,DUNGEON_SIZE_Z); glEnd()
    # Left wall (X=0)
    glBegin(GL_QUADS); glNormal3f(1,0,0); glVertex3f(0,0,0); glVertex3f(0,WALL_HEIGHT,0); glVertex3f(0,WALL_HEIGHT,DUNGEON_SIZE_Z); glVertex3f(0,0,DUNGEON_SIZE_Z); glEnd()
    # Right wall (X=DUNGEON_SIZE_X)
    glBegin(GL_QUADS); glNormal3f(-1,0,0); glVertex3f(DUNGEON_SIZE_X,0,0); glVertex3f(DUNGEON_SIZE_X,0,DUNGEON_SIZE_Z); glVertex3f(DUNGEON_SIZE_X,WALL_HEIGHT,DUNGEON_SIZE_Z); glVertex3f(DUNGEON_SIZE_X,WALL_HEIGHT,0); glEnd()

def draw_ui():
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT)
    
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_LIGHTING) # Text looks better without lighting

    # Health and Ammo
    health_text = f"Health: {player['health']}/{PLAYER_MAX_HEALTH}"
    ammo_text = f"Ammo: {'INF' if 'AMMO' in player['active_perks'] else player['ammo']}/{PLAYER_MAX_AMMO}"
    score_text = f"Score: {player['score']}"
    level_text = f"Level: {current_level}"

    draw_text(10, SCREEN_HEIGHT - 30, health_text, 1.0, 0.2, 0.2)
    draw_text(10, SCREEN_HEIGHT - 60, ammo_text, 0.2, 0.8, 0.2)
    draw_text(SCREEN_WIDTH - 150, SCREEN_HEIGHT - 30, score_text, 1.0, 1.0, 0.2)
    draw_text(SCREEN_WIDTH - 150, SCREEN_HEIGHT - 60, level_text, 0.8, 0.8, 0.8)

    # Active Perks
    perk_y_offset = 90
    for perk_type, end_time in player['active_perks'].items():
        remaining_time = max(0, int(end_time - time.time()))
        perk_display_text = f"{perk_type}: {remaining_time}s"
        if perk_type == "AMMO": draw_text(10, SCREEN_HEIGHT - perk_y_offset, perk_display_text, 0.0, 1.0, 1.0)
        elif perk_type == "HEALTH": draw_text(10, SCREEN_HEIGHT - perk_y_offset, perk_display_text, 0.0, 1.0, 0.0)
        elif perk_type == "DAMAGE": draw_text(10, SCREEN_HEIGHT - perk_y_offset, perk_display_text, 1.0, 0.0, 1.0)
        perk_y_offset += 30


    if game_state == STATE_YOU_WIN:
        draw_text(SCREEN_WIDTH / 2 - 100, SCREEN_HEIGHT / 2, "YOU WIN!", 0.2, 1.0, 0.2, GLUT_BITMAP_TIMES_ROMAN_24)
        draw_text(SCREEN_WIDTH / 2 - 150, SCREEN_HEIGHT / 2 - 30, f"Final Score: {player['score']}", 1.0, 1.0, 0.2, GLUT_BITMAP_HELVETICA_18)

    glEnable(GL_LIGHTING)
    glPopMatrix() # Modelview
    glMatrixMode(GL_PROJECTION)
    glPopMatrix() # Projection
    glMatrixMode(GL_MODELVIEW) # Restore modelview matrix for 3D rendering


# --- GLUT Callbacks ---
def display():
    global player, camera_mode, tp_camera_distance, tp_camera_pitch, tp_camera_yaw_offset
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()

    # Camera Setup
    if camera_mode == CAMERA_MODE_FIRST_PERSON:
        eye_x = player['pos'][0]
        eye_y = player['pos'][1] + PLAYER_EYE_HEIGHT - PLAYER_HEIGHT/2 
        eye_z = player['pos'][2]

        # Target calculation based on pitch and yaw
        pitch_rad = math.radians(player['rotation_x'])
        yaw_rad = math.radians(player['rotation_y'])
        
        look_at_x = eye_x + math.sin(yaw_rad) * math.cos(pitch_rad)
        look_at_y = eye_y - math.sin(pitch_rad) # Player pitch is inverted for looking up
        look_at_z = eye_z - math.cos(yaw_rad) * math.cos(pitch_rad)
        
        gluLookAt(eye_x, eye_y, eye_z, look_at_x, look_at_y, look_at_z, 0, 1, 0) # Up vector is Y
    
    elif camera_mode == CAMERA_MODE_THIRD_PERSON:
        # Camera orbits around player
        cam_x_offset = tp_camera_distance * math.cos(math.radians(tp_camera_pitch)) * math.sin(math.radians(player['rotation_y'] + tp_camera_yaw_offset))
        cam_y_offset = tp_camera_distance * math.sin(math.radians(-tp_camera_pitch)) # Pitch is negative for looking down
        cam_z_offset = -tp_camera_distance * math.cos(math.radians(tp_camera_pitch)) * math.cos(math.radians(player['rotation_y'] + tp_camera_yaw_offset))

        cam_x = player['pos'][0] + cam_x_offset
        cam_y = player['pos'][1] + PLAYER_HEIGHT/2 + cam_y_offset # Center view on player's mid-height
        cam_z = player['pos'][2] + cam_z_offset
        
        target_x = player['pos'][0]
        target_y = player['pos'][1] + PLAYER_HEIGHT/2
        target_z = player['pos'][2]
        gluLookAt(cam_x, cam_y, cam_z, target_x, target_y, target_z, 0, 1, 0)

    # Lighting
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    light_pos = [DUNGEON_SIZE_X / 2, WALL_HEIGHT * 1.5, DUNGEON_SIZE_Z / 2, 1.0] # Positional light from above center
    glLightfv(GL_LIGHT0, GL_POSITION, light_pos)
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0]) # Global ambient light
    glEnable(GL_COLOR_MATERIAL) # Use glColor for material diffuse
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)


    # Draw Dungeon
    draw_dungeon()

    # Draw Player (only in 3rd person)
    if camera_mode == CAMERA_MODE_THIRD_PERSON:
        glPushMatrix()
        glTranslatef(player['pos'][0], player['pos'][1], player['pos'][2])
        glRotatef(player['rotation_y'], 0, 1, 0)
        draw_player_model()
        glPopMatrix()

    # Draw Enemies
    for enemy in enemies:
        glPushMatrix()
        glTranslatef(enemy['pos'][0], enemy['pos'][1], enemy['pos'][2])
        # Face player (simple billboard-like rotation or full rotation)
        angle_to_player = math.degrees(math.atan2(player['pos'][0] - enemy['pos'][0], player['pos'][2] - enemy['pos'][2]))
        glRotatef(angle_to_player, 0, 1, 0) # Rotate around Y to face player (approx)
        
        glColor3fv(enemy['color'])
        if enemy.get('is_boss'):
             glutSolidSphere(enemy['size'], 20, 20) # Boss is a big sphere
        else:
             glutSolidCube(enemy['size'] * 2.0) # Other enemies are cubes (size is radius-like, so *2 for cube dim)
        glPopMatrix()
    
    # Draw Bullets
    for bullet in bullets:
        glPushMatrix()
        glTranslatef(bullet['pos'][0], bullet['pos'][1], bullet['pos'][2])
        glColor3fv(bullet['color'])
        glutSolidSphere(BULLET_RADIUS, 8, 8)
        glPopMatrix()

    # Draw Perks
    for perk in perks:
        glPushMatrix()
        glTranslatef(perk['pos'][0], perk['pos'][1], perk['pos'][2])
        glRotatef(perk['rotation_angle'], 0, 1, 0) # Rotate around Y axis
        glColor3fv(perk['color'])
        glutSolidCube(PERK_RADIUS * 2.0) # Cube perk
        glPopMatrix()

    # Transition Screen Overlay
    if game_state == STATE_LEVEL_TRANSITION or game_state == STATE_GAME_OVER_TRANSITION:
        glMatrixMode(GL_PROJECTION)
        glPushMatrix(); glLoadIdentity(); gluOrtho2D(0, 1, 0, 1); glPopMatrix() # Switch to simple ortho for fullscreen quad
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix(); glLoadIdentity()
        glDisable(GL_LIGHTING)
        glColor3fv(transition_color)
        glBegin(GL_QUADS)
        glVertex2f(0,0); glVertex2f(1,0); glVertex2f(1,1); glVertex2f(0,1)
        glEnd()
        glPopMatrix()
        glMatrixMode(GL_PROJECTION) # Must restore previous projection for UI
        glLoadIdentity()
        gluPerspective(45.0, float(SCREEN_WIDTH)/SCREEN_HEIGHT, 0.1, 200.0)
        glMatrixMode(GL_MODELVIEW) # Back to modelview
        # UI will be drawn over this

    # Draw UI (Health, Ammo, Score, Messages)
    draw_ui()

    glutSwapBuffers()

def reshape(w, h):
    global SCREEN_WIDTH, SCREEN_HEIGHT
    if h == 0: h = 1
    SCREEN_WIDTH, SCREEN_HEIGHT = w, h
    glViewport(0, 0, w, h)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45.0, float(w)/h, 0.1, 200.0) # Field of view, aspect ratio, near clip, far clip
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

def keyboard(key, x, y):
    global camera_mode
    keys_pressed[key.lower()] = True
    if key == b'\x1b': # Escape key
        glutLeaveMainLoop()
    if key.lower() == b'v': # Toggle camera view
        if camera_mode == CAMERA_MODE_FIRST_PERSON:
            camera_mode = CAMERA_MODE_THIRD_PERSON
        else:
            camera_mode = CAMERA_MODE_FIRST_PERSON

def keyboard_up(key, x, y):
    keys_pressed[key.lower()] = False

def special_keys_input(key, x, y):
    special_keys_pressed[key] = True

def special_keys_up(key, x, y):
    special_keys_pressed[key] = False
    
def idle():
    global last_time
    current_time_glut = glutGet(GLUT_ELAPSED_TIME) / 1000.0 # Time in seconds
    delta_time = current_time_glut - last_time
    last_time = current_time_glut

    # Cap delta_time to prevent physics explosions if frame rate drops drastically
    if delta_time > 0.1: delta_time = 0.1 
    
    update_game_state(delta_time)
    glutPostRedisplay()


# --- Main Function ---
def main():
    global last_time
    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(SCREEN_WIDTH, SCREEN_HEIGHT)
    glutCreateWindow(b"OpenGL 3D Dungeon Fighter")

    init_player()
    init_level(current_level) # Start at level 1
    
    last_time = glutGet(GLUT_ELAPSED_TIME) / 1000.0

    glEnable(GL_DEPTH_TEST)
    glShadeModel(GL_SMOOTH) # Smooth shading for better lighting
    glClearColor(0.1, 0.1, 0.2, 1.0) # Dark blue background

    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboard)
    glutKeyboardUpFunc(keyboard_up) # Handle key releases
    glutSpecialFunc(special_keys_input)
    glutSpecialUpFunc(special_keys_up) # Handle special key releases
    glutIdleFunc(idle)
    
    print("Controls:")
    print("W, A, S, D: Move Player")
    print("Space: Shoot")
    print("Arrow Keys: Control Camera (Rotate in 1st person, Orbit in 3rd person)")
    print("V: Toggle First/Third Person View")
    print("ESC: Exit Game")

    glutMainLoop()

if __name__ == "__main__":
    main()