#This file contains functions for writing GCode
#All of them are basically macros to output a GCode sequence

#Used basically to check if an argument was passed
DEFAULT_VAL = -100000

feedxy = 1
feedz = 1
zsafe = 100000

#Sets the XY or Z feed rates, in mm/min
def setFeedXY(f):
	feedxy = f

def setFeedZ(f):
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
	zsafe = z


#Perform a linear feed
def feed(x=DEFAULT_VAL, y=DEFAULT_VAL, z=DEFAULT_VAL):
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
	
	#FIXME: Need to generate setup GCode (units, tolerance, spindle speed, relative/absolute coords)
	
	setZsafe(zsafe)
	setFeedXY(feedxy)
	setFeedZ(feedz)
	cmds = ""
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
			#FIXME: Handle arcs here!
			cmds += feed(verts[i].p.x, verts[i].p.y)
			i += 1
	#At the end of the code, retract
	cmds += goZsafe()
			
	print cmds
