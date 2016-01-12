#This file contains functions for writing GCode
#All of them are basically macros to output a GCode sequence

import math
import area

#Default to None, since these all should be set before making GCode
feedxy = None
feedz = None
zsafe = None

plungeStraight = 0
plungeHelical = 1
plungeRamp = 2

#Sets the XY or Z feed rates, in mm/min
def setFeedXY(f):
	global feedxy
	feedxy = f

def setFeedZ(f):
	global feedz
	feedz = f

	
#Perform a rapid move
def rapid(x=None, y=None, z=None):
	retstr = "G00"
	if (x != None) or (y != None) or (z != None):
		if (x != None):
			retstr += " X" + str(x)
		if (y != None):
			retstr += " Y" + str(y)
		if (z != None):
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
def feed(x=None, y=None, z=None):
	global feedxy
	retstr = "G01 F"
	if(x == None) and (y == None):
		retstr += str(feedz)
	else:
		retstr += str(feedxy)
	
	if (x != None) or (y != None) or (z != None):
		if (x != None):
			retstr += " X" + str(x)
		if (y != None):
			retstr += " Y" + str(y)
		if (z != None):
			retstr += " Z" + str(z)
	else:
		return ""
	return retstr + "\n"


#Perform an arc
#Assumes XY plane or helix around Z
#Don't worry about starting Z- assume that's dealt with elsewhere
def arc(cx, cy, sx, sy, ex, ey, ez=None, ccw=False):
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
	if ez != None:
		retstr += " Z" + str(ez)
	
	#Append center offsets
	retstr += " I" + str(cx - sx) + " J" + str(cy - sy)
	
	return retstr + "\n"



#Attempts to find a suitable location to helically plunge
#curve: a curve to find a plunge location for- this is a TOOLPATH, so we can touch the outside if we have to
#toolD: the diameter of the cutter to plunge with. Assume space needed is a circle ~2*toolD
#Returns: area.Point of the center of the plunge
def helixPos(curve, toolD):
	#Turn the milling curve into an area
	curveArea = area.Area()
	curveArea.append(curve)
	
	#Offset- "curveArea" is already at the limits of what we can machine-
	#toolD/2 from the edge. Since the helix is 2 toolD in diameter, we
	#need to be toolD from the edge of the pocket, or another toolD/2 from
	#the milling path.
	curveArea.Offset(toolD * 0.5)
	
	#Presumably this will be null if we can't shrink it enough
	if curveArea.num_curves() == 0:
		return None
	
	#Otherwise, it's all good, and we can just return the first point
	return curveArea.getCurves()[0].getVertices()[0].p


#Function that calls all the others- parses a bunch of libarea curves denoting
#GCode paths, and generates the actual calls for them
#NOTE: Some parameters are kind of redundant- like toolD. They're kept for
#future use (eg, for safely ramping or running sanity checks)
def generate(curves, zsafe, zmin, zstep, zmax, feedxy, feedz, toolD, stepover, rpm, plungeType):
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
	if(stepover > toolD):
		print "ERROR: Stepover should be less than the tool diameter! Tool: " + str(toolD) + ", stepover: " + str(stepover)
		return ""
	#Don't try to check IPT or zstep relative to toolD- assume user knows
	#what they're doing. We don't know their setup or material
	
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
		
		#Set our starting "previous" point
		last = verts[0].p
		
		#Go to the start of the curve
		cmds += rapid(verts[0].p.x, verts[0].p.y)
		
		#FIXME: Rapid move down to a little bit above the actual start of
		#the cut!
		
		#Straight plunge- hard on tools. Don't do this if it can be avoided
		if plungeType == plungeStraight:
			cmds += feed(z=workZ)
		#Helical plunge- good! Assuming there's space to do it...
		elif plungeType == plungeHelical:
			plungePos = helixPos(c, toolD)
			if plungePos == None:
				#FIXME: Go to linear ramp- not straight
				print "Couldn't find place to helix-plunge- defaulting to straight. FIXME!"
				cmds += feed(z=workZ)
			else:
				print "Should be able to helically plunge at " + str(plungePos.x) + ", " + str(plungePos.y)
				#FIXME: Want this fudge-factor in there? Constant offset? Variable?
				#Probably want SOMETHING so that we don't end up with a little chunk left in the middle
				fudge = 0.95
				helixX = plungePos.x + toolD/2. * fudge
				helixY = plungePos.y;
				
				#FIXME: Probably want variable ramp angle
				#Degrees
				rampAngle = 5
				helixCirc = math.pi * toolD * fudge
				dzPerRev = math.sin(rampAngle/180. * math.pi) * helixCirc
				
				#Go to the start of the helix position
				cmds += rapid(helixX, helixY)
				
				#FIXME: Iterate over Z here
				#FIXME: These will need to change!
				destZ = workZ
				curZ = max(zsafe - dzPerRev, destZ)
				done = False
				while not done:
					done = (curZ == destZ)
					cmds += arc(plungePos.x, plungePos.y, helixX, helixY, helixX, helixY, ez = curZ, ccw=True)
					curZ = max(curZ - dzPerRev, destZ)
					
				#FIXME: Remember to move back to the start of the curve!
				#This is really important... Maybe not the start of the
				#curve, but SOMEWHERE on it. And then somehow reset where
				#the start is so it machines everything out.
		#Linear ramp plunge- fallback from helical. Or if requested.
		elif plungeType == plungeRamp:
			print "Linear ramp plunging not supported; aborting"
			return ""
		else:
			print "Unknown plunge argument passed: " + str(plungeType)
			print "Aborting"
			return ""
		

		
		#Naive ramping: Follow the curve at a x% grade until you've ramped
		#zstep/2, then go backwards the other half
		#A smarter version would look for a place to helix in. How to do
		#that isn't obvious
		#Check that- maybe a probe grid and the "PointToPerim" function
		#could find a spot to helix in
		
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
