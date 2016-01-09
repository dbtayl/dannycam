#This file contains functions for writing GCode
#All of them are basically macros to output a GCode sequence

#FIXME: A lot of useless default arguments could be removed via
#http://stackoverflow.com/questions/14017996/python-optional-parameter 

import math

#Used basically to check if an argument was passed
DEFAULT_VAL = -100000

feedxy = 1
feedz = 1
zsafe = 100000

#Sets the XY or Z feed rates, in mm/min
def setFeedXY(f):
	global feedxy
	feedxy = f

def setFeedZ(f):
	global feedz
	feedz = f

	
#Perform a rapid move
def rapid(x=DEFAULT_VAL, y=DEFAULT_VAL, z=DEFAULT_VAL):
	retstr = "G00"
	if (x != DEFAULT_VAL) or (y != DEFAULT_VAL) or (z != DEFAULT_VAL):
		if (x != DEFAULT_VAL):
			retstr += " X" + str(x)
		if (y != DEFAULT_VAL):
			retstr += " Y" + str(y)
		if (z != DEFAULT_VAL):
			retstr += " Z" + str(z)
	else:
		return ""
	return retstr + "\n"

#Going to ZSafe might as well have its own function, save some typing
def goZsafe():
	return "G00 F" + str(feedz) + " Z" + str(zsafe) + "\n"

def setZsafe(z):
	global zsafe
	zsafe = z


#Perform a linear feed
def feed(x=DEFAULT_VAL, y=DEFAULT_VAL, z=DEFAULT_VAL):
	global feedxy
	retstr = "G01 F"
	if(x == DEFAULT_VAL) and (y == DEFAULT_VAL):
		retstr += str(feedz)
	else:
		retstr += str(feedxy)
	
	if (x != DEFAULT_VAL) or (y != DEFAULT_VAL) or (z != DEFAULT_VAL):
		if (x != DEFAULT_VAL):
			retstr += " X" + str(x)
		if (y != DEFAULT_VAL):
			retstr += " Y" + str(y)
		if (z != DEFAULT_VAL):
			retstr += " Z" + str(z)
	else:
		return ""
	return retstr + "\n"


#Perform an arc
#Assumes XY plane or helix around Z
#Don't worry about starting Z- assume that's dealt with elsewhere
def arc(cx, cy, sx, sy, ex, ey, ez=DEFAULT_VAL, ccw=False):
	#If start/end radii aren't within eps, abort
	eps = 0.01
	if (math.sqrt((cx - sx)**2 + (cy - sy)**2) - math.sqrt((cx - ex)**2 + (cy - ey)**2)) >= eps:
		print "ERROR: Illegal arc: Stand and end radii not equal"
		return ""
	
	#Set [C]CW and feed
	retstr = ""
	if ccw:
		retstr += "G03 F"
	else:
		retstr += "G02 F"
	retstr += str(feedxy)
	
	#End location
	retstr += " X" + str(ex) + " Y" + str(ey)
	
	#Helix if requested
	if ez != DEFAULT_VAL:
		retstr += " Z" + str(ez)
	
	#Append center offsets
	retstr += " I" + str(cx - sx) + " J" + str(cy - sy)
	
	return retstr + "\n"


#Function that calls all the others- parses a bunch of libarea curves denoting
#GCode paths, and generates the actual calls for them
def generate(curves, zsafe, zmin, zstep, zmax, feedxy, feedz, toolD, stepover, rpm):
	#Do some basic sanity checks
	if(feedxy <= 0):
		print "ERROR: FeedXY must be positive."
		return ""
	if(feedz <= 0):
		print "ERROR: FeedXY must be positive."
		return ""
	if(zsafe <= zmax):
		print "ERROR: ZSafe must be above milling height. ZSafe=" + str(zsafe) + ", zmax=" + str(zmax)
		return ""
	#FIXME: Check other variables as well...
	
	#G90 (absolute mode)
	#G91.1 (relative offsets for arcs)
	#G94 (Units per minute mode)
	#G97 S<SPEED> (Spindle speed in RPM)
	#G21 (mm units)
	#G40 (no cutter comp)
	#G64 P0.01 (set path tolerance to 0.01 mm of specified)
	#G17 (use XY plane)
	
	
	
	#FIXME: Add M[345] spindle control commands
	#FIXME: Make path tolerance an argument
	
	setZsafe(zsafe)
	setFeedXY(feedxy)
	setFeedZ(feedz)
	cmds = ""
	
	#Preamble
	cmds += "G90\t(Absolute mode)\n"
	cmds += "G91.1\t(Relative arc offsets)\n"
	cmds += "G94\t(Units/minute mode)\n"
	cmds += "G97 S" + str(rpm) + "\t(Set spindle speed)\n"
	cmds += "G21\t(units are mm)\n"
	cmds += "G40\t(no cutter comp)\n"
	cmds += "G64 P0.01\t(set path tolerance)\n"
	cmds += "G17\t(Use XY plane for arcs)\n"
	cmds += "\n"
	
	
	
	#FIXME: Will need to iterate over this
	workZ = max(zmax - zstep, zmin)
	for c in curves:
		verts = c.getVertices()
		#Stupid version of safety: Move to Zsafe before starting any curve
		#FIXME: A better version would check if that's actually necessary first
		cmds += goZsafe()
		
		last = verts[0].p
		
		#Go to the start of the curve
		cmds += rapid(verts[0].p.x, verts[0].p.y)
		#FIXME: Plunge here
		cmds += feed(z=workZ)
		i = 1
		while i < len(verts):
			#Linear feed
			if verts[i].type == 0:
				cmds += feed(verts[i].p.x, verts[i].p.y)
			#Arc; CW = 1, CCW = -1
			elif abs(verts[i].type) == 1:
				ccw = (verts[i].type == 1)
				cmds += arc(verts[i].c.x, verts[i].c.y, verts[i-1].p.x, verts[i-1].p.y, verts[i].p.x, verts[i].p.y, ccw=ccw)
			#No idea... abort
			else:
				print "Unknown vertex type found: " + str(vert[i].type)
				print "Aborting"
				return ""
			i += 1
	#At the end of the code, retract
	cmds += goZsafe()
	
	#Add "end of program
	cmds += "\nM2\n"
			
	return cmds
