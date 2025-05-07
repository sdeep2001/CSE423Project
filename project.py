from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from OpenGL.GLUT import GLUT_BITMAP_HELVETICA_18, GLUT_BITMAP_TIMES_ROMAN_24
import math
import random
import time
import sys

# --- Constants and Global Game Variables ---
# Window
SCREEN_WIDTH, SCREEN_HEIGHT = 1024, 768
# Game States
STATE_PLAYING = 0
STATE_LEVEL_TRANSITION = 1
STATE_GAME_OVER_TRANSITION = 2
STATE_YOU_WIN = 3

game_state = STATE_PLAYING
current_level = 1
max_levels = 10

# Player settings
PLAYER_SPEED = 5.0
PLAYER_ROTATE_ANGLE = 0.5  # Changed from PLAYER_ROTATE_SPEED = 100.0
PLAYER_TOTAL_HEIGHT = 1.8
PLAYER_BODY_Y_OFFSET = PLAYER_TOTAL_HEIGHT / 2 
PLAYER_EYE_HEIGHT_FROM_MODEL_BASE = 1.6 
PLAYER_RADIUS = 0.5 
PLAYER_MAX_HEALTH = 100
PLAYER_BASE_SHOOT_COOLDOWN_TIME = 0.3

# Player model proportions
PLAYER_LEG_LENGTH = PLAYER_TOTAL_HEIGHT * 0.45
PLAYER_TORSO_HEIGHT = PLAYER_TOTAL_HEIGHT * 0.4
PLAYER_ARM_LENGTH = PLAYER_TOTAL_HEIGHT * 0.35
PLAYER_GUN_LENGTH = PLAYER_TOTAL_HEIGHT * 0.3

# Bullet settings
BULLET_SPEED = 30.0
BULLET_RADIUS = 0.1
BULLET_LIFESPAN = 2.5

# Enemy settings
ENEMY_MIN_DISTANCE_FROM_PLAYER = 3.5
ENEMY_BASE_COLLISION_RADIUS = 0.6 # This will be scaled by model height

# Perk System Variables
PERK_SCORE_MULTIPLIER_DURATION = 5.0
PERK_RAPID_FIRE_DURATION = 5.0

# Dungeon settings
DUNGEON_SIZE_X = 70.0
DUNGEON_SIZE_Z = 70.0
WALL_HEIGHT = 8.0

# Camera
CAMERA_MODE_FIRST_PERSON = 0
CAMERA_MODE_THIRD_PERSON = 1
camera_mode = CAMERA_MODE_THIRD_PERSON
tp_camera_distance = 8.0
tp_camera_pitch = -30.0
tp_camera_yaw_offset = 0.0

# Global lists for game objects
player = {}
enemies = []
bullets = []

# Level Management
level_configs = {}
enemies_killed_this_level = 0
enemies_spawned_this_level = 0
boss_entity = None

# Timing
last_time = 0.0
transition_timer = 0.0
TRANSITION_DURATION = 1.5
transition_color = [0.0, 0.0, 0.0]
next_game_state_after_transition = STATE_PLAYING

# Input states
keys_pressed = {}
special_keys_pressed = {}
mouse_buttons = {}

# GLU Quadric object for cylinders
glu_quadric = None

# --- Helper Functions (Math, etc.) ---
def vector_length(v):
    return math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)

def normalize_vector(v):
    l = vector_length(v)
    if l == 0:
        return [0,0,0]
    return [v[0]/l, v[1]/l, v[2]/l]

def distance_3d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)

def check_sphere_collision(pos1, radius1, pos2, radius2):
    dist = distance_3d(pos1, pos2)
    return dist < (radius1 + radius2)

# --- Game Object Initialization and Management ---
def init_player():
    global player
    player = {
        'pos': [DUNGEON_SIZE_X / 2, PLAYER_BODY_Y_OFFSET, DUNGEON_SIZE_Z / 2], 
        'rotation_y': 0.0, 'rotation_x': 0.0,
        'health': PLAYER_MAX_HEALTH, 'score': 0, 'speed': PLAYER_SPEED,
        'shoot_cooldown': 0.0, 'current_shoot_cooldown_time': PLAYER_BASE_SHOOT_COOLDOWN_TIME,
        'kills_for_health_perk': 0, 'kills_for_score_perk': 0, 'kills_for_gun_perk': 0,
        'health_perk_available': False, 'score_perk_available': False, 'gun_perk_available': False,
        'score_perk_active_until': 0, 'gun_perk_active_until': 0,
    }

def get_enemy_definition(enemy_type_id):
    if enemy_type_id == 1:
        return {'name':'Type1Wolf','health':3,'damage':3,'speed_mult':0.4,'model_height':1.5,'color':[0.6,0.5,0.4],'points':10}
    elif enemy_type_id == 2:
        return {'name':'Type2Wolf','health':4,'damage':4,'speed_mult':0.7,'model_height':1.6,'color':[0.5,0.6,0.4],'points':15}
    elif enemy_type_id == 3:
        return {'name':'Type3Wolf','health':5,'damage':5,'speed_mult':1.0,'model_height':1.7,'color':[0.4,0.5,0.6],'points':20}
    elif enemy_type_id == 'boss':
        return {'name':'BossWolf','health':15,'damage':7,'speed_mult':0.8,'model_height':2.5,'color':[0.3,0.3,0.3],'points':100,'is_boss':True}
    return {}

def init_level_configs():
    global level_configs
    level_configs = {
        1: {'total_enemies':5,'max_concurrent':1,'enemy_types':[1]}, 2: {'total_enemies':6,'max_concurrent':2,'enemy_types':[1]},
        3: {'total_enemies':9,'max_concurrent':3,'enemy_types':[1]}, 4: {'total_enemies':5,'max_concurrent':1,'enemy_types':[2]},
        5: {'total_enemies':6,'max_concurrent':2,'enemy_types':[2]}, 6: {'total_enemies':9,'max_concurrent':3,'enemy_types':[2]},
        7: {'total_enemies':5,'max_concurrent':1,'enemy_types':[3]}, 8: {'total_enemies':6,'max_concurrent':2,'enemy_types':[3]},
        9: {'total_enemies':9,'max_concurrent':3,'enemy_types':[3]},
        10: {'total_enemies':1+15,'max_concurrent_boss_phase':1+3,'enemy_types':['boss']+[1]*5+[2]*5+[3]*5,'is_boss_level':True}
    }
    for i in range(1, max_levels + 1):
        level_configs[i]['enemies_to_spawn_pool'] = list(level_configs[i]['enemy_types'])

def spawn_enemy():
    global enemies_spawned_this_level, boss_entity, enemies
    level_conf = level_configs[current_level]
    if enemies_spawned_this_level >= level_conf['total_enemies']: 
        return
    enemy_type_to_spawn = None
    is_spawning_boss = False
    if 'is_boss_level' in level_conf:
        if not boss_entity and 'boss' in level_conf['enemies_to_spawn_pool']:
            enemy_type_to_spawn = 'boss'
            level_conf['enemies_to_spawn_pool'].remove('boss')
            is_spawning_boss = True
        elif level_conf['enemies_to_spawn_pool']:
            pool = [t for t in level_conf['enemies_to_spawn_pool'] if t != 'boss']
            if pool: 
                enemy_type_to_spawn = random.choice(pool)
                level_conf['enemies_to_spawn_pool'].remove(enemy_type_to_spawn)
    else:
        if level_conf['enemies_to_spawn_pool']: 
            enemy_type_to_spawn = level_conf['enemy_types'][0] 
    if enemy_type_to_spawn is None: 
        return
    config = get_enemy_definition(enemy_type_to_spawn)
    if not config: 
        return
    margin=7.0
    x=random.uniform(margin,DUNGEON_SIZE_X-margin)
    enemy_base_y=config['model_height']/2
    z=random.uniform(margin,DUNGEON_SIZE_Z-margin)
    min_spawn_dist_player=15.0
    min_spawn_dist_enemy=5.0
    spawn_attempts=0
    valid_spawn=False
    while spawn_attempts < 20 and not valid_spawn:
        valid_spawn=True
        if distance_3d([x,enemy_base_y,z],[player['pos'][0],player['pos'][1],player['pos'][2]]) < min_spawn_dist_player:
            valid_spawn=False
        for ex_en in enemies:
            if distance_3d([x,enemy_base_y,z],[ex_en['pos'][0],ex_en['pos'][1],ex_en['pos'][2]]) < min_spawn_dist_enemy:
                valid_spawn=False
                break
        if not valid_spawn: 
            x=random.uniform(margin,DUNGEON_SIZE_X-margin)
            z=random.uniform(margin,DUNGEON_SIZE_Z-margin)
        spawn_attempts+=1
    if not valid_spawn:
        if is_spawning_boss: 
            level_conf['enemies_to_spawn_pool'].insert(0,'boss')
        elif enemy_type_to_spawn and enemy_type_to_spawn != 'boss' and 'is_boss_level' in level_conf:
            level_conf['enemies_to_spawn_pool'].append(enemy_type_to_spawn)
        return
    new_enemy = {
        'pos':[x,enemy_base_y,z],'enemy_type_id':enemy_type_to_spawn,
        'max_health':config['health'],'health':config['health'],'damage':config['damage'],'speed':PLAYER_SPEED*config['speed_mult'],
        'reload_time':1.5/(config['speed_mult']+0.5),'shoot_cooldown':random.uniform(1.0,3.0),'points':config['points'],
        'color':config['color'],'model_height':config['model_height'],
        'collision_radius':ENEMY_BASE_COLLISION_RADIUS*(config['model_height']/1.8),
        'is_boss':config.get('is_boss',False),'rotation_y':0.0
    }
    enemies.append(new_enemy)
    enemies_spawned_this_level+=1
    if is_spawning_boss:
        boss_entity = new_enemy

def init_level(level_num):
    global current_level,enemies,bullets,game_state,enemies_killed_this_level,enemies_spawned_this_level,boss_entity,player
    current_level=level_num
    enemies.clear()
    bullets.clear()
    boss_entity=None
    game_state=STATE_PLAYING
    enemies_killed_this_level=0
    enemies_spawned_this_level=0
    player['pos']=[DUNGEON_SIZE_X/2,PLAYER_BODY_Y_OFFSET,DUNGEON_SIZE_Z/2]
    player['rotation_y']=0.0
    player['rotation_x']=0.0
    player['health_perk_available']=False
    player['score_perk_available']=False
    player['gun_perk_available']=False
    player['score_perk_active_until']=0
    player['gun_perk_active_until']=0
    player['kills_for_health_perk']=0
    player['kills_for_score_perk']=0
    player['kills_for_gun_perk']=0
    level_configs[current_level]['enemies_to_spawn_pool'] = list(level_configs[current_level]['enemy_types'])

def create_bullet(start_pos,direction_vec,owner_type,damage_val,color_override=None):
    bullets.append({'pos':list(start_pos),'dir':direction_vec,'owner':owner_type,'damage':damage_val,'lifespan':BULLET_LIFESPAN,
                    'color':color_override if color_override else ([1.0,1.0,0.0] if owner_type=='PLAYER' else [1.0,0.5,0.0])})

# --- Update Functions ---
def update_player(delta_time):
    global player,camera_mode,tp_camera_pitch,tp_camera_yaw_offset
    if player['score_perk_active_until']>0 and time.time()>player['score_perk_active_until']:
        player['score_perk_active_until']=0
        print("Score Perk expired.")
    if player['gun_perk_active_until']>0:
        if time.time()>player['gun_perk_active_until']: 
            player['gun_perk_active_until']=0
            player['current_shoot_cooldown_time']=PLAYER_BASE_SHOOT_COOLDOWN_TIME
            print("Gun Perk expired.")
        else: 
            player['current_shoot_cooldown_time']=0.001
    else: 
        player['current_shoot_cooldown_time']=PLAYER_BASE_SHOOT_COOLDOWN_TIME
    speed=player['speed']*delta_time
    dx,dz=0,0
    forward_x=math.sin(math.radians(player['rotation_y']))
    forward_z=-math.cos(math.radians(player['rotation_y']))
    if keys_pressed.get(b'w'): 
        dx+=forward_x*speed
        dz+=forward_z*speed
    if keys_pressed.get(b's'): 
        dx-=forward_x*speed
        dz-=forward_z*speed
    if keys_pressed.get(b'a'): 
        player['rotation_y'] += PLAYER_ROTATE_ANGLE  # Fixed angle increment
    if keys_pressed.get(b'd'): 
        player['rotation_y'] -= PLAYER_ROTATE_ANGLE  # Fixed angle increment
    if camera_mode==CAMERA_MODE_FIRST_PERSON:
        if special_keys_pressed.get(GLUT_KEY_UP): 
            player['rotation_x']=max(-89.0,player['rotation_x']-PLAYER_ROTATE_ANGLE*0.7)
        if special_keys_pressed.get(GLUT_KEY_DOWN): 
            player['rotation_x']=min(89.0,player['rotation_x']+PLAYER_ROTATE_ANGLE*0.7)
    elif camera_mode==CAMERA_MODE_THIRD_PERSON: # Arrow keys orbit camera
        if special_keys_pressed.get(GLUT_KEY_UP): 
            tp_camera_pitch=max(-89.0,tp_camera_pitch-PLAYER_ROTATE_ANGLE*0.7)
        if special_keys_pressed.get(GLUT_KEY_DOWN): 
            tp_camera_pitch=min(0.0,tp_camera_pitch+PLAYER_ROTATE_ANGLE*0.7)
        if special_keys_pressed.get(GLUT_KEY_LEFT): 
            tp_camera_yaw_offset-=PLAYER_ROTATE_ANGLE
        if special_keys_pressed.get(GLUT_KEY_RIGHT): 
            tp_camera_yaw_offset+=PLAYER_ROTATE_ANGLE
    new_x=player['pos'][0]+dx
    new_z=player['pos'][2]+dz
    player['pos'][0]=max(PLAYER_RADIUS,min(new_x,DUNGEON_SIZE_X-PLAYER_RADIUS))
    player['pos'][2]=max(PLAYER_RADIUS,min(new_z,DUNGEON_SIZE_Z-PLAYER_RADIUS))
    if player['shoot_cooldown']>0: 
        player['shoot_cooldown']-=delta_time
    if mouse_buttons.get(GLUT_LEFT_BUTTON)==GLUT_DOWN and player['shoot_cooldown']<=0:
        player['shoot_cooldown'] = player['current_shoot_cooldown_time']
        
        # Get player's current orientation
        yaw_rad = math.radians(player['rotation_y'])
        
        # Calculate gun tip position matching the model's gun position
        shoulder_height = PLAYER_LEG_LENGTH + PLAYER_TORSO_HEIGHT * 0.8
        gun_forward_offset = 0.35 * PLAYER_TOTAL_HEIGHT + PLAYER_GUN_LENGTH
        
        # Calculate bullet start position at exact gun tip
        tip_world_x = player['pos'][0] + math.sin(yaw_rad) * gun_forward_offset
        tip_world_y = player['pos'][1] - PLAYER_BODY_Y_OFFSET + shoulder_height
        tip_world_z = player['pos'][2] - math.cos(yaw_rad) * gun_forward_offset
        
        # Direction matches gun direction
        direction = normalize_vector([math.sin(yaw_rad), 0, math.cos(yaw_rad)])
        
        create_bullet([tip_world_x, tip_world_y, tip_world_z], direction, 'PLAYER', 1)
        mouse_buttons[GLUT_LEFT_BUTTON]="PROCESSED"

def update_enemies(delta_time):
    global player,game_state
    level_conf=level_configs[current_level]
    max_c=level_conf.get('max_concurrent_boss_phase' if ('is_boss_level' in level_conf and boss_entity and boss_entity['health']>0) else 'max_concurrent',1)
    if len(enemies)<max_c and enemies_spawned_this_level<level_conf['total_enemies']: 
        spawn_enemy()
    for enemy in list(enemies):
        dist_player=distance_3d([player['pos'][0],player['pos'][1],player['pos'][2]],[enemy['pos'][0],enemy['pos'][1],enemy['pos'][2]])
        dir_to_p_vec=[player['pos'][0]-enemy['pos'][0],0,player['pos'][2]-enemy['pos'][2]]
        enemy['rotation_y']=math.degrees(math.atan2(dir_to_p_vec[0],dir_to_p_vec[2]))
        if dist_player > ENEMY_MIN_DISTANCE_FROM_PLAYER:
            dir_norm=normalize_vector(dir_to_p_vec)
            move_dist=enemy['speed']*delta_time
            enemy['pos'][0]+=dir_norm[0]*move_dist
            enemy['pos'][2]+=dir_norm[2]*move_dist
        er=enemy['collision_radius']
        enemy['pos'][0]=max(er,min(enemy['pos'][0],DUNGEON_SIZE_X-er))
        enemy['pos'][2]=max(er,min(enemy['pos'][2],DUNGEON_SIZE_Z-er))
        if enemy['shoot_cooldown']>0: enemy['shoot_cooldown']-=delta_time
        elif dist_player < 30.0:
            enemy['shoot_cooldown']=enemy['reload_time']
            player_center_y = player['pos'][1] - PLAYER_BODY_Y_OFFSET + PLAYER_TOTAL_HEIGHT/2
            target_pos=[player['pos'][0],player_center_y,player['pos'][2]]
            # Enemy gun is at its face, which is model_height/2 (body center) + some offset for face height
            enemy_face_center_y = enemy['pos'][1] # model_height/2 is base, so this is center of body
            gun_len_for_offset = 0.2 * enemy['model_height'] # Approx gun length for offsetting start point
            s_yaw_e=math.sin(math.radians(enemy['rotation_y']))
            c_yaw_e=math.cos(math.radians(enemy['rotation_y']))
            # Start bullet from tip of gun protruding from face
            start_x_e = enemy['pos'][0] + s_yaw_e * gun_len_for_offset
            start_z_e = enemy['pos'][2] + c_yaw_e * gun_len_for_offset 
            enemy_bullet_start_pos=[start_x_e,enemy_face_center_y,start_z_e]
            enemy_bullet_dir=normalize_vector([target_pos[0]-start_x_e,target_pos[1]-enemy_face_center_y,target_pos[2]-start_z_e])
            create_bullet(enemy_bullet_start_pos,enemy_bullet_dir,'ENEMY',enemy['damage'])

def update_bullets(delta_time):
    global player,game_state,enemies_killed_this_level,boss_entity
    for bullet in list(bullets):
        bullet['pos'][0]+=bullet['dir'][0]*BULLET_SPEED*delta_time
        bullet['pos'][1]+=bullet['dir'][1]*BULLET_SPEED*delta_time
        bullet['pos'][2]+=bullet['dir'][2]*BULLET_SPEED*delta_time
        bullet['lifespan']-=delta_time
        if bullet['lifespan']<=0 or not ( -BULLET_RADIUS < bullet['pos'][0] < DUNGEON_SIZE_X+BULLET_RADIUS and \
                                        -BULLET_RADIUS < bullet['pos'][1] < WALL_HEIGHT+BULLET_RADIUS and \
                                        -BULLET_RADIUS < bullet['pos'][2] < DUNGEON_SIZE_Z+BULLET_RADIUS ):
            if bullet in bullets:
                bullets.remove(bullet)
                continue
        if bullet['owner']=='PLAYER':
            for enemy in list(enemies):
                enemy_coll_y = enemy['pos'][1] # Collision with enemy body center
                if check_sphere_collision(bullet['pos'],BULLET_RADIUS,[enemy['pos'][0],enemy_coll_y,enemy['pos'][2]],enemy['collision_radius']):
                    if bullet in bullets: 
                        bullets.remove(bullet)
                    enemy['health']-=1 # Player bullet damage always 1
                    if enemy['health']<=0:
                        score_mult=2 if player['score_perk_active_until']>0 and time.time()<player['score_perk_active_until'] else 1
                        player['score']+=enemy['points']*score_mult
                        if enemy in enemies: 
                            enemies.remove(enemy)
                        if enemy is boss_entity: 
                            boss_entity=None
                        enemies_killed_this_level+=1
                        player['kills_for_health_perk']+=1
                        player['kills_for_score_perk']+=1
                        player['kills_for_gun_perk']+=1
                        if player['kills_for_health_perk']>=3 and not player['health_perk_available']: 
                            player['health_perk_available']=True
                            print("Health Perk!(H)")
                        if player['kills_for_score_perk']>=4 and not player['score_perk_available']: 
                            player['score_perk_available']=True
                            print("Score Perk!(C)")
                        if player['kills_for_gun_perk']>=5 and not player['gun_perk_available']: 
                            player['gun_perk_available']=True
                            print("Gun Perk!(G)")
                    break 
        elif bullet['owner']=='ENEMY':
            player_coll_y = player['pos'][1] # Collision with player body center
            if check_sphere_collision(bullet['pos'],BULLET_RADIUS,[player['pos'][0],player_coll_y,player['pos'][2]],PLAYER_RADIUS):
                player['health']-=bullet['damage']
                if bullet in bullets: 
                    bullets.remove(bullet)
                if player['health']<=0 and game_state==STATE_PLAYING: 
                    player['health']=0
                    start_transition(STATE_GAME_OVER_TRANSITION,[1.0,0.0,0.0])
                    break

def check_level_completion():
    global game_state
    level_conf=level_configs[current_level]
    if enemies_spawned_this_level>=level_conf['total_enemies'] and not enemies and game_state==STATE_PLAYING:
        if current_level==max_levels: 
            game_state=STATE_YOU_WIN
        else: 
            start_transition(STATE_LEVEL_TRANSITION,[0.0,1.0,0.0])

def start_transition(target_state,color):
    global game_state,transition_timer,transition_color,next_game_state_after_transition
    game_state=target_state
    transition_timer=TRANSITION_DURATION
    transition_color=color
    if target_state==STATE_LEVEL_TRANSITION: 
        next_game_state_after_transition=STATE_PLAYING 
    elif target_state==STATE_GAME_OVER_TRANSITION: 
        next_game_state_after_transition=STATE_PLAYING

def update_game_state(delta_time):
    if game_state==STATE_PLAYING: 
        update_player(delta_time)
        update_enemies(delta_time)
        update_bullets(delta_time)
        check_level_completion()
    elif game_state==STATE_LEVEL_TRANSITION:
        global transition_timer, current_level
        transition_timer-=delta_time
        if transition_timer<=0: 
            current_level+=1
            init_level(current_level)
    elif game_state==STATE_GAME_OVER_TRANSITION:
        global player
        transition_timer-=delta_time # Added player global here
        if transition_timer<=0: 
            player['health']=PLAYER_MAX_HEALTH
            init_level(current_level)

# --- Drawing Functions ---
def draw_text(x,y,text,r=1,g=1,b=1,font=GLUT_BITMAP_HELVETICA_18): 
    glColor3f(r,g,b)
    glRasterPos2f(x,y)
    [glutBitmapCharacter(font,ord(c)) for c in text]

def draw_cylinder(base_r,top_r,height,slices,stacks,color): # Draws cylinder along its local Y axis
    global glu_quadric
    glColor3fv(color)
    glPushMatrix()
    # Default GLU cylinder is along Z. Rotate it to be along Y for easier limb construction.
    glRotatef(-90,1,0,0) 
    gluCylinder(glu_quadric,base_r,top_r,height,slices,stacks)
    gluDisk(glu_quadric,0,base_r,slices,1) # Base cap at Z=0 (after rotation, this is Y=0)
    glTranslatef(0,0,height)
    gluDisk(glu_quadric,0,top_r,slices,1)
    glPopMatrix() # Top cap at Z=height (after rotation, Y=height)

def draw_tapered_cylinder(base_radius, top_radius, height, color):
    global glu_quadric
    glColor3fv(color)
    glPushMatrix()
    glRotatef(-90, 1, 0, 0)  # Rotate to point along Y
    gluCylinder(glu_quadric, base_radius, top_radius, height, 20, 8)
    # Base cap
    gluDisk(glu_quadric, 0, base_radius, 20, 8)
    # Top cap
    glTranslatef(0, 0, height)
    gluDisk(glu_quadric, 0, top_radius, 20, 8)
    glPopMatrix()

def draw_player_humanoid_model():
    glPushMatrix()
    
    # Scale everything relative to PLAYER_TOTAL_HEIGHT
    model_scale = PLAYER_TOTAL_HEIGHT
    
    # Body positioning constants - adjusted proportions
    torso_height = 0.45 * model_scale  # Increased height
    head_radius = 0.15 * model_scale
    
    # Body (centered at origin) - reduced width
    glPushMatrix()
    glTranslatef(0, PLAYER_LEG_LENGTH + torso_height/2, 0)
    glColor3f(0.5, 0.5, 0.0)
    glScalef(0.3 * model_scale, torso_height, 0.25 * model_scale)  # Reduced width from 0.4 to 0.3
    glutSolidCube(1.0)
    glPopMatrix()

    # Head (directly above body)
    glPushMatrix()
    glTranslatef(0, PLAYER_LEG_LENGTH + torso_height + head_radius, 0)
    glColor3f(0.8, 0.6, 0.4)
    glutSolidSphere(head_radius, 20, 20)
    glPopMatrix()

    # Arms (at shoulder height - moved forward)
    shoulder_height = PLAYER_LEG_LENGTH + torso_height * 0.8
    
    # Left arm - moved forward
    glPushMatrix()
    glTranslatef(-0.15 * model_scale, shoulder_height, 0.15 * model_scale)  # Reduced x-offset, added z-offset
    glRotatef(15, 0, 1, 0)  # Bank inward
    glRotatef(90, 1, 0, 0)  # Point forward
    draw_cylinder(0.05 * model_scale, 0.04 * model_scale, PLAYER_ARM_LENGTH * 0.7, 8, 1, (0.8, 0.6, 0.4))
    glPopMatrix()

    # Right arm - moved forward
    glPushMatrix()
    glTranslatef(0.15 * model_scale, shoulder_height, 0.15 * model_scale)  # Reduced x-offset, added z-offset
    glRotatef(-15, 0, 1, 0)  # Bank inward
    glRotatef(90, 1, 0, 0)  # Point forward
    draw_cylinder(0.05 * model_scale, 0.04 * model_scale, PLAYER_ARM_LENGTH * 0.7, 8, 1, (0.8, 0.6, 0.4))
    glPopMatrix()

    # Gun (centered between arms and moved forward)
    glPushMatrix()
    glTranslatef(0, shoulder_height, 0.35 * model_scale)  # Increased z-offset
    glRotatef(90, 1, 0, 0)  # Point forward
    draw_cylinder(0.05 * model_scale, 0.03 * model_scale, PLAYER_GUN_LENGTH, 8, 1, (0.3, 0.3, 0.3))
    glPopMatrix()

    # Legs (starting from bottom of body)
    leg_start_height = PLAYER_LEG_LENGTH
    
    # Left leg
    glPushMatrix()
    glTranslatef(-0.1 * model_scale, leg_start_height, 0)
    glRotatef(180, 1, 0, 0)
    draw_cylinder(0.06 * model_scale, 0.05 * model_scale, PLAYER_LEG_LENGTH, 8, 1, (0.3, 0.3, 0.8))
    glPopMatrix()

    # Right leg
    glPushMatrix()
    glTranslatef(0.1 * model_scale, leg_start_height, 0)
    glRotatef(180, 1, 0, 0)
    draw_cylinder(0.06 * model_scale, 0.05 * model_scale, PLAYER_LEG_LENGTH, 8, 1, (0.3, 0.3, 0.8))
    glPopMatrix()

    glPopMatrix()

def draw_revised_wolf_model(total_h, body_c, leg_c, face_c, gun_c):  # Model origin at base, Y-up
    # Adjusted proportions for better connection
    body_width = total_h * 0.35
    body_height = total_h * 0.35  # Reduced height
    body_depth = total_h * 0.7    # Length of wolf body
    face_size = total_h * 0.25    # Slightly smaller face
    leg_len = total_h * 0.4       # Shorter legs (reduced from 0.45)
    leg_r = total_h * 0.04        # Thinner legs (reduced from 0.06)
    gun_len = total_h * 0.3
    gun_r = total_h * 0.04        # Thinner gun (reduced from 0.05)

    # Body positioning
    body_center_y = leg_len + body_height/2

    # Body (main torso)
    glPushMatrix()
    glTranslatef(0, body_center_y, 0)
    glColor3fv(body_c)
    glScalef(body_width, body_height, body_depth)
    glutSolidCube(1.0)
    glPopMatrix()

    # Face (connected directly to body)
    face_center_y = body_center_y
    face_center_z = body_depth/2 + face_size/4
    glPushMatrix()
    glTranslatef(0, face_center_y, face_center_z)
    glColor3fv(face_c)
    glScalef(face_size, face_size, face_size * 0.5)
    glutSolidCube(1.0)
    glPopMatrix()

    # Gun (attached to face)
    gun_start_y = face_center_y
    gun_start_z = face_center_z + face_size/4
    glPushMatrix()
    glTranslatef(0, gun_start_y, gun_start_z)
    glRotatef(90, 1, 0, 0)
    draw_cylinder(gun_r, gun_r * 0.8, gun_len, 8, 1, gun_c)
    glPopMatrix()

    # Legs (attached to body corners)
    leg_attach_y = body_center_y - body_height/2
    front_leg_z = body_depth * 0.3
    rear_leg_z = -body_depth * 0.3
    leg_x = body_width * 0.4

    # Front Right Leg
    glPushMatrix()
    glTranslatef(leg_x, leg_attach_y, front_leg_z)
    glRotatef(180, 1, 0, 0)
    draw_tapered_cylinder(leg_r, leg_r * 0.7, leg_len, leg_c)  # More taper on legs
    glPopMatrix()

    # Front Left Leg
    glPushMatrix()
    glTranslatef(-leg_x, leg_attach_y, front_leg_z)
    glRotatef(180, 1, 0, 0)
    draw_tapered_cylinder(leg_r, leg_r * 0.7, leg_len, leg_c)
    glPopMatrix()

    # Rear Right Leg
    glPushMatrix()
    glTranslatef(leg_x, leg_attach_y, rear_leg_z)
    glRotatef(180, 1, 0, 0)
    draw_tapered_cylinder(leg_r, leg_r * 0.7, leg_len, leg_c)
    glPopMatrix()

    # Rear Left Leg
    glPushMatrix()
    glTranslatef(-leg_x, leg_attach_y, rear_leg_z)
    glRotatef(180, 1, 0, 0)
    draw_tapered_cylinder(leg_r, leg_r * 0.7, leg_len, leg_c)
    glPopMatrix()


def draw_dungeon():
    floor_color=[0.5,0.5,0.5]
    wall_color=[0.4,0.4,0.4]
    boss_active=boss_entity and boss_entity['health']>0
    if 1<=current_level<=3: 
        floor_color=[0.6,0.55,0.5]
        wall_color=[0.5,0.45,0.4]
    elif 4<=current_level<=6: 
        floor_color=[0.7,0.3,0.1]
        wall_color=[0.5,0.2,0.05]
    elif 7<=current_level<=10: 
        floor_color=[0.7,0.8,0.95]
        wall_color=[0.5,0.6,0.75]
    if current_level==10 and boss_active: 
        floor_color=[0.2,0.2,0.4]
        wall_color=[0.1,0.1,0.3]
    glColor3fv(floor_color)
    glBegin(GL_QUADS)
    glNormal3f(0,1,0)
    glVertex3f(0,0,0)
    glVertex3f(DUNGEON_SIZE_X,0,0)
    glVertex3f(DUNGEON_SIZE_X,0,DUNGEON_SIZE_Z)
    glVertex3f(0,0,DUNGEON_SIZE_Z)
    glEnd()
    glColor3fv(wall_color)
    glBegin(GL_QUADS)
    glNormal3f(0,0,1)
    glVertex3f(0,0,0)
    glVertex3f(DUNGEON_SIZE_X,0,0)
    glVertex3f(DUNGEON_SIZE_X,WALL_HEIGHT,0)
    glVertex3f(0,WALL_HEIGHT,0)
    glEnd()
    glBegin(GL_QUADS)
    glNormal3f(0,0,-1)
    glVertex3f(0,0,DUNGEON_SIZE_Z)
    glVertex3f(0,WALL_HEIGHT,DUNGEON_SIZE_Z)
    glVertex3f(DUNGEON_SIZE_X,WALL_HEIGHT,DUNGEON_SIZE_Z)
    glVertex3f(DUNGEON_SIZE_X,0,DUNGEON_SIZE_Z)
    glEnd()
    glBegin(GL_QUADS)
    glNormal3f(1,0,0)
    glVertex3f(0,0,0)
    glVertex3f(0,WALL_HEIGHT,0)
    glVertex3f(0,WALL_HEIGHT,DUNGEON_SIZE_Z)
    glVertex3f(0,0,DUNGEON_SIZE_Z)
    glEnd()
    glBegin(GL_QUADS)
    glNormal3f(-1,0,0)
    glVertex3f(DUNGEON_SIZE_X,0,0)
    glVertex3f(DUNGEON_SIZE_X,0,DUNGEON_SIZE_Z)
    glVertex3f(DUNGEON_SIZE_X,WALL_HEIGHT,DUNGEON_SIZE_Z)
    glVertex3f(DUNGEON_SIZE_X,WALL_HEIGHT,0)
    glEnd()

def draw_ui():
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0,SCREEN_WIDTH,0,SCREEN_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    draw_text(10,SCREEN_HEIGHT-30,f"Health: {player['health']}/{PLAYER_MAX_HEALTH}",1,0.2,0.2)
    draw_text(10,SCREEN_HEIGHT-60,f"Score: {player['score']}",1,1,0.2)
    draw_text(SCREEN_WIDTH-200,SCREEN_HEIGHT-30,f"Level: {current_level}",0.8,0.8,0.8)
    perk_y=SCREEN_HEIGHT-90
    if player['health_perk_available']: 
        draw_text(10,perk_y,"Health Perk Ready!(H)",0,1,0)
        perk_y-=25
    if player['score_perk_available']:
        draw_text(10,perk_y,"Score Perk Ready!(C)",1,1,0)
        perk_y-=25
    if player['gun_perk_available']: 
        draw_text(10,perk_y,"Gun Perk Ready!(G)",1,0.5,0)
        perk_y-=25
    active_perk_y=SCREEN_HEIGHT-90
    if player['score_perk_active_until']>0 and time.time()<player['score_perk_active_until']: 
        rem=int(player['score_perk_active_until']-time.time())
        draw_text(SCREEN_WIDTH-250,active_perk_y,f"Score x2: {rem}s",1,1,0)
        active_perk_y-=25
    if player['gun_perk_active_until']>0 and time.time()<player['gun_perk_active_until']: 
        rem=int(player['gun_perk_active_until']-time.time())
        draw_text(SCREEN_WIDTH-250,active_perk_y,f"Rapid Fire: {rem}s",1,0.5,0)
        active_perk_y-=25
    if game_state==STATE_YOU_WIN: 
        draw_text(SCREEN_WIDTH/2-100,SCREEN_HEIGHT/2,"YOU WIN!",0.2,1,0.2,GLUT_BITMAP_TIMES_ROMAN_24)
        draw_text(SCREEN_WIDTH/2-150,SCREEN_HEIGHT/2-30,f"Final Score: {player['score']}",1,1,0.2)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

# --- GLUT Callbacks ---
def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    player_base_x,player_base_y,player_base_z = player['pos']
    if camera_mode==CAMERA_MODE_FIRST_PERSON:
        eye_x=player_base_x
        eye_y=player_base_y-PLAYER_BODY_Y_OFFSET+PLAYER_EYE_HEIGHT_FROM_MODEL_BASE
        eye_z=player_base_z
        pitch_r=math.radians(player['rotation_x'])
        yaw_r=math.radians(player['rotation_y'])
        look_x=eye_x+math.sin(yaw_r)*math.cos(pitch_r)
        look_y=eye_y-math.sin(pitch_r)
        look_z=eye_z-math.cos(yaw_r)*math.cos(pitch_r)
        gluLookAt(eye_x,eye_y,eye_z,look_x,look_y,look_z,0,1,0)
    elif camera_mode==CAMERA_MODE_THIRD_PERSON:
        target_foc_y = player_base_y - PLAYER_BODY_Y_OFFSET + PLAYER_TOTAL_HEIGHT/2
        # Use only tp_camera_yaw_offset for camera rotation, not player rotation
        cam_x_off = tp_camera_distance * math.cos(math.radians(tp_camera_pitch)) * math.sin(math.radians(tp_camera_yaw_offset))
        cam_y_off = tp_camera_distance * math.sin(math.radians(-tp_camera_pitch))
        cam_z_off = -tp_camera_distance * math.cos(math.radians(tp_camera_pitch)) * math.cos(math.radians(tp_camera_yaw_offset))
        cam_x = player_base_x + cam_x_off
        cam_y = target_foc_y + cam_y_off
        cam_z = player_base_z + cam_z_off
        gluLookAt(cam_x, cam_y, cam_z, player_base_x, target_foc_y, player_base_z, 0, 1, 0)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    light_pos=[DUNGEON_SIZE_X/2,WALL_HEIGHT*1.8,DUNGEON_SIZE_Z/2,1.0]
    glLightfv(GL_LIGHT0,GL_POSITION,light_pos)
    glLightfv(GL_LIGHT0,GL_DIFFUSE,[0.9,0.9,0.8,1])
    glLightfv(GL_LIGHT0,GL_AMBIENT,[0.35,0.35,0.35,1])
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK,GL_AMBIENT_AND_DIFFUSE)
    draw_dungeon()
    if camera_mode == CAMERA_MODE_THIRD_PERSON:
        glPushMatrix()
        glTranslatef(player['pos'][0], player['pos'][1] - PLAYER_BODY_Y_OFFSET, player['pos'][2])
        glRotatef(player['rotation_y'], 0, 1, 0)
        draw_player_humanoid_model()
        
        # Calculate laser start position (gun tip)
        yaw_rad = math.radians(player['rotation_y'])
        shoulder_height = PLAYER_LEG_LENGTH + PLAYER_TORSO_HEIGHT * 0.8
        gun_forward_offset = 0.35 * PLAYER_TOTAL_HEIGHT + PLAYER_GUN_LENGTH
        glPopMatrix()
        
    for enemy in enemies: # Enemy model origin is at its feet (Y=0 locally)
        glPushMatrix()
        glTranslatef(enemy['pos'][0],enemy['pos'][1]-enemy['model_height']/2,enemy['pos'][2])
        glRotatef(enemy['rotation_y'],0,1,0)
        draw_revised_wolf_model(enemy['model_height'],enemy['color'],[c*0.8 for c in enemy['color']],[c*1.1 for c in enemy['color']],[0.1,0.1,0.1]); glPopMatrix()
    for bullet in bullets: 
        glPushMatrix()
        glTranslatef(bullet['pos'][0],bullet['pos'][1],bullet['pos'][2])
        glColor3fv(bullet['color'])
        glutSolidSphere(BULLET_RADIUS,6,6)
        glPopMatrix()
    if game_state==STATE_LEVEL_TRANSITION or game_state==STATE_GAME_OVER_TRANSITION:
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0,1,0,1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glColor4f(transition_color[0],transition_color[1],transition_color[2],0.85)
        glBegin(GL_QUADS)
        glVertex2f(0,0)
        glVertex2f(1,0)
        glVertex2f(1,1)
        glVertex2f(0,1)
        glEnd()
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
    draw_ui()
    glutSwapBuffers()

def reshape(w,h):
    global SCREEN_WIDTH,SCREEN_HEIGHT
    SCREEN_WIDTH,SCREEN_HEIGHT=w,h
    glViewport(0,0,w,h if h else 1)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45.0,float(w)/(h if h else 1),0.1,500.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

def keyboard(key,x,y):
    global camera_mode,player
    k=key.lower()
    keys_pressed[k]=True
    if key==b'\x1b': 
        glutLeaveMainLoop()
    if k==b'f': 
        camera_mode = 1-camera_mode # Toggle 0 and 1
    if k==b'h' and player['health_perk_available']: 
        player['health']=PLAYER_MAX_HEALTH
        player['health_perk_available']=False
        player['kills_for_health_perk']=0
        print("Health Perk!")
    if k==b'c' and player['score_perk_available']:
        player['score_perk_active_until']=time.time()+PERK_SCORE_MULTIPLIER_DURATION
        player['score_perk_available']=False
        player['kills_for_score_perk']=0
        print("Score Perk!")
    if k==b'g' and player['gun_perk_available']: 
        player['gun_perk_active_until']=time.time()+PERK_RAPID_FIRE_DURATION
        player['gun_perk_available']=False
        player['kills_for_gun_perk']=0
        print("Gun Perk!")

def keyboard_up(key,x,y): 
    keys_pressed[key.lower()]=False
def special_keys_input(key,x,y): 
    special_keys_pressed[key]=True
def special_keys_up(key,x,y): 
    special_keys_pressed[key]=False
def mouse_click(button,state,x,y): 
    global mouse_buttons
    mouse_buttons[button]=state # Store exact state
    
def idle():
    global last_time
    current_t=glutGet(GLUT_ELAPSED_TIME)/1000.0
    delta_t=current_t-last_time
    last_time=current_t
    if delta_t > 0.1: 
        delta_t=0.1
    if delta_t <= 0: 
        delta_t=1/60.0
    update_game_state(delta_t)
    glutPostRedisplay()

def main():
    global last_time,glu_quadric
    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH|GLUT_ALPHA)
    glutInitWindowSize(SCREEN_WIDTH,SCREEN_HEIGHT)
    glutCreateWindow(b"OpenGL Dungeon Crawler - Wolf Refined")
    glEnable(GL_DEPTH_TEST)
    glShadeModel(GL_SMOOTH)
    glClearColor(0.05,0.05,0.15,1.0)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA)
    glu_quadric=gluNewQuadric()
    gluQuadricNormals(glu_quadric,GLU_SMOOTH)
    gluQuadricTexture(glu_quadric,GL_FALSE)
    init_level_configs()
    init_player()
    init_level(current_level)
    last_time=glutGet(GLUT_ELAPSED_TIME)/1000.0
    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboard)
    glutKeyboardUpFunc(keyboard_up)
    glutSpecialFunc(special_keys_input)
    glutSpecialUpFunc(special_keys_up)
    glutMouseFunc(mouse_click)
    glutIdleFunc(idle)
    print("--- Game Controls ---")
    print("W,S:Move | A,D:Rotate | MouseLeft:Shoot | Arrows:Cam | F:View | H,C,G:Perks | ESC:Exit")
    glutMainLoop()

if __name__ == "__main__": main()
