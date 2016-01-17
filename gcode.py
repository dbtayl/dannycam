#This file contains functions for writing GCode
#All of them are basically macros to output a GCode sequence

import math
import area

#Default to None, since these all should be set before making GCode
feedxy = None
feedz = None
zsafe = None

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
			retstr += " X" + str("%.3f" % x)
		if (y != None):
			retstr += " Y" + str("%.3f" % y)
		if (z != None):
			retstr += " Z" + str("%.3f" % z)
	else:
		return ""
	return retstr + "\n"

#Going to ZSafe might as well have its own function, save some typing
def goZsafe():
	return "G00 F" + str("%.3f" % feedz) + " Z" + str("%.3f" % zsafe) + "\n"

def setZsafe(z):
	global zsafe
	zsafe = z


#Perform a linear feed
def feed(x=None, y=None, z=None):
	global feedxy
	retstr = "G01 F"
	if(x == None) and (y == None):
		retstr += str("%.3f" % feedz)
	else:
		retstr += str("%.3f" % feedxy)
	
	if (x != None) or (y != None) or (z != None):
		if (x != None):
			retstr += " X" + str("%.3f" % x)
		if (y != None):
			retstr += " Y" + str("%.3f" % y)
		if (z != None):
			retstr += " Z" + str("%.3f" % z)
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
	retstr += " X" + str("%.3f" % ex) + " Y" + str("%.3f" % ey)
	
	#Helix if requested
	if ez != None:
		retstr += " Z" + str("%.3f" % ez)
	
	#Append center offsets
	retstr += " I" + str("%.3f" % (cx - sx)) + " J" + str("%.3f" % (cy - sy))
	
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
	helixPt = curveArea.getCurves()[0].getVertices()[0].p
	
	#We'll also need to find the index of the original curve that's closest
	#to our helix so we don't end up machining a line to the old starting
	#point
	
	#Find the closest point... or one close enough
	i = 0;
	bestd = 1000000000
	nv = curve.getNumVertices()
	verts = curve.getVertices()
	bestidx = 0
	while i < nv:
		d = verts[i].p.dist(helixPt)
		if d < toolD/2.:
			bestidx = i
			break
		elif d < bestd:
			bestd = d
			bestidx = i
		i += 1
	
	#Adjust the curve to start at that point
	#setCurveStart(curve, bestidx)
	curve.shiftStart(bestidx)
	verts = curve.getVertices()
	
	return helixPt


#Returns code to helically plunge, if possible
#destZ is the milling level
#startZ is the height we can safely feed down to before helix-ing
def helicalPlunge(curve, toolD, rampangle, destZ, startZ):
	helixCmds = ""
	plungePos = helixPos(curve, toolD)
	if(plungePos == None):
		return None
	
	#FIXME: Want this fudge-factor in there? Constant offset? Variable?
	#Probably want SOMETHING so that we don't end up with a little chunk left in the middle
	fudge = 0.95
	helixX = plungePos.x + toolD/2. * fudge
	helixY = plungePos.y;
	
	helixCirc = math.pi * toolD * fudge
	dzPerRev = math.sin(rampangle/180. * math.pi) * helixCirc

	#Go to the start of the helix position
	helixCmds += rapid(helixX, helixY)
	helixCmds += rapid(z=startZ)
	
	#Helix as required to get to the requested depth
	curZ = max(startZ-dzPerRev, destZ)
	done = False
	while not done:
		done = (curZ == destZ)
		helixCmds += arc(plungePos.x, plungePos.y, helixX, helixY, helixX, helixY, ez = curZ, ccw=True)
		curZ = max(curZ - dzPerRev, destZ)
	
	#Feed back to the start of the curve. This shouldn't be far
	helixCmds += feed(curve.getVertices()[0].p.x, curve.getVertices()[0].p.y)
	
	return helixCmds


def rampPlunge(curve, toolD, rampangle, destZ, startZ):	
	#How long our desired ramp is
	rampLen = toolD #FIXME: Should have this configurable
	
	verts = curve.getVertices()
	
	#If the first segment isn't long enough, give up
	#FIXME: This is dumb
	dist = verts[0].p.dist(verts[1].p)
	if dist < toolD:
		print "FIXME: Ramp failure for stupid reasons"
		return None
	
	startP = verts[0].p
	
	#Otherwise, iterate back and forth along the path
	#Want to ramp by toolD, so normalize vector
	vect = verts[1].p - verts[0].p
	vect.normalize()
	vect *= toolD
	
	endP = startP + vect
	
	dzPerRamp = math.sin(rampangle/180. * math.pi) * rampLen
	
	cmd = ""
	
	#Start by rapid-moving to the start location
	cmd += rapid(startP.x, startP.y)
	cmd += rapid(z=startZ)
	
	#Rapid down most of the way to the cut
	
	curZ = max(startZ-dzPerRamp, destZ)
	while curZ > destZ:
		#Linear feed
		if verts[1].type == 0:
			cmd += feed(endP.x, endP.y, curZ)
			cmd += feed(startP.x, startP.y)
		#CCW arc
		else:
			t = verts[1].type
			cmd += arc(verts[1].c.x, verts[1].c.y, startP.x, startP.y, endP.x, endP.y, ez=curZ, ccw=(t == 1))
			cmd += arc(verts[1].c.x, verts[1].c.y, endP.x, endP.y, startP.x, startP.y, ccw=(t == -1))
			
		curZ = max(curZ - dzPerRamp, destZ)
	
	return cmd
	
	
#Function that calls all the others- parses a bunch of libarea curves denoting
#GCode paths, and generates the actual calls for them
#NOTE: Some parameters are kind of redundant- like toolD. They're kept for
#future use (eg, for safely ramping or running sanity checks)
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
	if(stepover > toolD):
		print "ERROR: Stepover should be less than the tool diameter! Tool: " + str(toolD) + ", stepover: " + str(stepover)
		return ""
	#Don't try to check IPT or zstep relative to toolD- assume user knows
	#what they're doing. We don't know their setup or material
	
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
	
	#FIXME: Add M[345] spindle control commands
	#FIXME: Make path tolerance an argument
	
	
	
	#FIXME: Will need to iterate over this- well, maybe  INSIDE the curve loop
	workZ = max(zmax - zstep, zmin)
	for c in curves:
		verts = c.getVertices()
		#Stupid version of safety: Move to Zsafe before starting any curve
		#FIXME: A better version would check if that's actually necessary first
		cmds += goZsafe()
		
		#Set our starting "previous" point
		last = verts[0].p
		
		#Helical plunge- good! Assuming there's space to do it...
		#FIXME: This "zmax" bit will probably need to change...
		plungeCmds = helicalPlunge(c, toolD, 5, workZ, zmax)
		
		#If helix feed doesn't work, try linear ramp
		if(plungeCmds == None):
			plungeCmds = rampPlunge(c, toolD, 5, workZ, zmax)

		
		#if linear ramp fails for some reason, default to straight plunge
		if(plungeCmds == None):
			plungeCmds = rapid(verts[0].p.x, verts[0].p.y)
			plungeCmds += rapid(z=zmax) #FIXME: zmax will need to change
			plungeCmds += feed(z=workZ)
		
		#Add the plunge to the command list
		cmds += plungeCmds
		
		i = 1
		#Get a fresh copy of vertices- we've (maybe) tweaked them with plunges!
		#FIXME: There has to be a better way to do this
		verts = c.getVertices()
		while i < len(verts):
			#Linear feed
			if verts[i].type == 0:
				cmds += feed(verts[i].p.x, verts[i].p.y)
			#Arc; CCW = 1, CW = -1
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
