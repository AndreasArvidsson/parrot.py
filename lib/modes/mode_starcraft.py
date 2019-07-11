from lib.detection_strategies import *
import threading
import numpy as np
import pyautogui
from pyautogui import press, hotkey, click, scroll, typewrite, moveRel, moveTo, position, keyUp, keyDown, mouseUp, mouseDown
from time import sleep
from subprocess import call
from lib.system_toggles import toggle_eyetracker, turn_on_sound, mute_sound, toggle_speechrec
from lib.pattern_detector import PatternDetector
from config.config import *
import os
import pythoncom
from lib.overlay_manipulation import update_overlay_image
from lib.grammar.chat_grammar import *

class StarcraftMode:
			
	def __init__(self, modeSwitcher):
		if( SPEECHREC_ENABLED == True ):
			self.grammar = Grammar("Starcraft")
			self.chatCommandRule = ChatCommandRule()
			self.chatCommandRule.set_callback( self.toggle_speech )
			self.grammar.add_rule( self.chatCommandRule )		
	
		self.mode = "regular"
		self.modeSwitcher = modeSwitcher
		self.detector = PatternDetector({
			'select': {
				'strategy': 'continuous',
				'sound': 'sibilant_s',
				'percentage': 70,
				'intensity': 800,
				'lowest_percentage': 40,
				'lowest_intensity': 800,
				'throttle': 0.01
			},
			'click': {
				'strategy': 'rapid',
				'sound': 'click_alveolar',
				'percentage': 70,
				'intensity': 2000,
				'throttle': 0.15
			},
			'toggle_speech': {
				'strategy': 'rapid',
				'sound': 'hand_finger_snap',
				'percentage': 80,
				'intensity': 20000,
				'throttle': 0.2
			},			
			'movement': {
				'strategy': 'rapid',
				'sound': 'whistle',
				'percentage': 80,
				'intensity': 1000,
				'throttle': 0.2
			},
			'control': {
				'strategy': 'rapid',
				'sound': 'vowel_oh',
				'percentage': 72,
				'intensity': 1000,
				'throttle': 0.2
			},
			'shift': {
				'strategy': 'rapid',
				'sound': 'sibilant_sh',
				'percentage': 70,
				'intensity': 1500,
				'throttle': 0.2
			},
			'alt': {
				'strategy': 'rapid',
				'sound': 'fricative_f',
				'percentage': 70,
				'intensity': 1000,
				'throttle': 0.2
			},
			'camera': {
				'strategy': 'rapid',
				'sound': 'vowel_y',
				'percentage': 90,
				'intensity': 1000,
				'throttle': 0.18
			},
			'q': {
				'strategy': 'combined',
				'sound': 'vowel_ow',
				'secondary_sound': 'vowel_aa',				
				'percentage': 80,
				'intensity': 1000,
				'ratio': 3,
				'throttle': 0.15
			},
			'w': {
				'strategy': 'rapid',
				'sound': 'vowel_ae',
				'percentage': 80,
				'intensity': 1100,
				'throttle': 0.15
			},
			'grid_ability': {
				'strategy': 'continuous',
				'sound': 'vowel_aa',
				'percentage': 60,
				'intensity': 1500,
				'lowest_percentage': 20,
				'lowest_intensity': 500
			},
			'r': {
				'strategy': 'rapid',
				'sound': 'sibilant_z',
				'percentage': 85,
				'intensity': 1000,
				'throttle': 0.2
			},
			'numbers': {
				'strategy': 'combined',
				'sound': 'vowel_iy',
				'secondary_sound': 'vowel_e',				
				'percentage': 70,
				'intensity': 1000,
				'ratio': 1,
				'throttle': 0.1
			},
			'menu': {
				'strategy': 'rapid',
				'sound': 'call_bell',
				'percentage': 80,
				'intensity': 5000,
				'throttle': 0.3
			}
		})

		self.KEY_DELAY_THROTTLE = 0.4
		
		self.pressed_keys = []
		self.should_follow = False
		self.should_drag = False
		self.last_control_group = -1
		self.ability_selected = False
		self.ctrlKey = False
		self.shiftKey = False
		self.altKey = False
		self.hold_down_start_timer = 0
		
		self.hold_key = ""

	def toggle_speech( self ):
		if( self.mode == "regular" ):
			self.mode = "speech"
			self.grammar.load()
		else:
			self.mode = "regular"
			self.grammar.unload()
			
		toggle_speechrec()
		
	def start( self ):
		mute_sound()
		toggle_eyetracker()
		update_overlay_image( "default" )
		
	def cast_ability( self, ability ):
		self.press_ability( ability )
		self.ability_selected = True
	
	def hold_shift( self, shift ):
		if( self.shiftKey != shift ):
			if( shift == True ):
				keyDown('shift')
				self.shiftKey = shift			
				print( 'Holding SHIFT' )
				self.update_overlay()				
			else:
				keyUp('shift')
				self.shiftKey = shift
				print( 'Releasing SHIFT' )				
				self.update_overlay()
	
	def hold_alt( self, alt ):
		if( self.altKey != alt ):
			if( alt == True ):
				keyDown('alt')
				self.altKey = alt			
				print( 'Holding ALT' )
				self.update_overlay()				
			else:
				keyUp('alt')
				self.altKey = alt
				print( 'Releasing ALT' )				
				self.update_overlay()
	
	def hold_control( self, ctrlKey ):
		if( self.ctrlKey != ctrlKey ):
			if( ctrlKey == True ):
				keyDown('ctrl')
				print( 'Holding CTRL' )
				self.ctrlKey = ctrlKey
				self.update_overlay()				
			else:
				keyUp('ctrl')
				print( 'Releasing CTRL' )
				self.ctrlKey = ctrlKey
				self.update_overlay()
		
	def release_hold_keys( self ):
		self.ability_selected = False
		self.hold_control( False )
		if( self.shiftKey and self.altKey ):
			self.hold_shift( False )
		self.hold_alt( False )
		self.update_overlay()
	
	def handle_input( self, dataDicts ):
		self.detector.tick( dataDicts )
		
		# Always allow switching between speech and regular mode
		if( self.detector.detect("toggle_speech" ) ):
			self.release_hold_keys()
			self.toggle_speech()

			return self.detector.tickActions			
		# Recognize speech commands in speech mode
		elif( self.mode == "speech" ):
			pythoncom.PumpWaitingMessages()
			
			return self.detector.tickActions			
			
		# Regular quick command mode
		elif( self.mode == "regular" ):
			self.handle_quick_commands( dataDicts )
			
		return self.detector.tickActions
	
	def handle_quick_commands( self, dataDicts ):
		# Early escape for performance
		if( self.detector.detect_silence() ):
			self.drag_mouse( False )
			self.hold_down_start_timer = 0
			return
			
		# Selecting units
		selecting = self.detector.detect( "select" )
		self.drag_mouse( selecting )
		
		## Press Grid ability
		if( self.detector.detect("grid_ability") ):
			quadrant4x3 = self.detector.detect_mouse_quadrant( 4, 3 )
			if( time.time() - self.hold_down_start_timer > self.KEY_DELAY_THROTTLE ):
				self.use_ability( quadrant4x3 )
				self.release_hold_keys()
				self.hold_shift( False )
			
			if( self.hold_down_start_timer == 0 ):
				self.hold_down_start_timer = time.time()
		else:
			self.hold_down_start_timer = 0
		
		if( selecting ):
			self.ability_selected = False	
			self.hold_control( False )

		elif( self.detector.detect( "click" ) ):
		
			# Cast selected ability or Ctrl+click
			if( self.detect_command_area() or self.ability_selected == True or self.ctrlKey == True or self.altKey == True or ( self.shiftKey and self.detect_selection_tray() ) ):
				click(button='left')
			else:
				click(button='right')
				
			# Release the held keys - except when shift-alt clicking units in the selection tray ( for easy removing from the unit group )
			if( not( self.shiftKey and self.detect_selection_tray() ) ):
				self.release_hold_keys()
			
		# CTRL KEY holding
		elif( self.detector.detect( "control" ) ):
			self.hold_control( True )
			
		# SHIFT KEY holding / toggling
		elif( self.detector.detect( "shift" ) ):
			self.hold_shift( not self.shiftKey )
	
		# ALT KEY holding / toggling
		elif( self.detector.detect( "alt" ) ):
			self.hold_alt( not self.altKey )

		## Movement options
		elif( self.detector.detect( "movement" ) ):
			quadrant3x3 = self.detector.detect_mouse_quadrant( 3, 3 )
			if( quadrant3x3 <= 6 ):
				self.cast_ability( 'a' )
			elif( quadrant3x3 == 7 ):
				self.press_ability( 'h' )
			elif( quadrant3x3 == 8 ):
				self.press_ability( 's' )
			elif( quadrant3x3 == 9 ):
				self.cast_ability( 'p' )
		## Press Q
		elif( self.detector.detect( "q" ) ):
			self.cast_ability( 'q' )
		## Press W
		elif( self.detector.detect( "w") ):
			self.cast_ability( 'w' )
		## Press R ( Burrow )
		elif( self.detector.detect( "r") ):
			self.press_ability( 'r' )
		elif( self.detector.detect( "menu" ) ):
			self.release_hold_keys()
			
			quadrant3x3 = self.detector.detect_mouse_quadrant( 3, 3 )
			if( quadrant3x3 == 9 ):
				self.press_ability( 'f10' )
			else:
				self.press_ability( 'esc' )
			
		## Move the camera
		elif( self.detector.detect( "camera" ) ):
			quadrant3x3 = self.detector.detect_mouse_quadrant( 3, 3 )
			self.camera_movement( quadrant3x3 )
			self.hold_shift( False )			
						
		## Press control group
		elif( self.detector.detect( "numbers" ) ):
			quadrant3x3 = self.detector.detect_mouse_quadrant( 3, 3 )
			self.use_control_group( quadrant3x3 )
			self.release_hold_keys()
			self.hold_shift( False )

		return		
	
	def use_control_group( self, quadrant ):
		if( quadrant == 1 ):
			self.press_ability('1')
		elif( quadrant == 2 ):
			self.press_ability('2')
		elif( quadrant == 3 ):
			self.press_ability('3')
		elif( quadrant == 4 ):
			self.press_ability('4')
		elif( quadrant == 5 ):
			self.press_ability('5')
		elif( quadrant == 6 ):
			self.press_ability('6')			
		elif( quadrant == 7 ):
			self.press_ability('7')
		elif( quadrant == 8 ):
			self.press_ability('8')			
		elif( quadrant == 9 ):
			self.press_ability('9')
			
		self.last_control_group = quadrant
		
	def use_ability( self, quadrant ):
		if( quadrant == 1 ):
			self.press_ability('q')
		elif( quadrant == 2 ):
			self.press_ability('w')
		elif( quadrant == 3 ):
			self.press_ability('e')
		elif( quadrant == 4 ):
			self.press_ability('r')
		elif( quadrant == 5 ):
			self.press_ability('a')
		elif( quadrant == 6 ):
			self.press_ability('s')			
		elif( quadrant == 7 ):
			self.press_ability('d')
		elif( quadrant == 8 ):
			self.press_ability('f')			
		elif( quadrant == 9 ):
			self.press_ability('z')
		elif( quadrant == 10 ):
			self.press_ability('x')
		elif( quadrant == 11 ):
			self.press_ability('c')
		elif( quadrant == 12 ):
			self.press_ability('v')
		
	def press_ability( self, key ):
		print( "pressing " + key )
		press( key )
		self.release_hold_keys()
		
	def camera_movement( self, quadrant ):
		## Move camera to kerrigan when looking above the UI
		if( quadrant < 4 ):
			self.press_ability( "f1" )
		
		elif( quadrant > 3 and quadrant < 7 ):
			self.press_ability( "backspace" )
		
		## Move camera to danger when when looking at the minimap or unit selection
		elif( quadrant == 7 or quadrant == 8 ):
			self.press_ability( "space" )
			
		## Follow the unit when looking near the command card
		elif( quadrant == 9 ):
			self.press_ability( "." )
				
	# Detect when the cursor is inside the command area
	def detect_command_area( self ):
		return self.detector.detect_inside_minimap( 1521, 815, 396, 266 )

	# Detect when the cursor is inside the command area
	def detect_selection_tray( self ):
		return self.detector.detect_inside_minimap( 360, 865, 1000, 215 )		
				
	# Drag mouse for selection purposes
	def drag_mouse( self, should_drag ):
		if( self.should_drag != should_drag ):
			if( should_drag == True ):
				mouseDown()
			else:
				mouseUp()
				
		self.should_drag = should_drag

	def update_overlay( self ):
		if( not( self.ctrlKey or self.shiftKey or self.altKey ) ):
			update_overlay_image( "default" )
		else:
			modes = []
			if( self.ctrlKey ):
				modes.append( "ctrl" )
			if( self.shiftKey ):
				modes.append( "shift" )
			if( self.altKey ):
				modes.append( "alt" )
				
			update_overlay_image( "mode-starcraft-%s" % ( "-".join( modes ) ) )

	def exit( self ):
		if( self.mode == "speech" ):
			self.toggle_speech()
	
		self.mode = "regular"
		turn_on_sound()
		update_overlay_image( "default" )
		toggle_eyetracker()
		