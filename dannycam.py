#!/usr/bin/env python2

#If you build libarea from source and get undefined symbol errors, pull
#in CMakeLists.txt from here: https://github.com/aewallin/libarea
#and rebuild (cmake/make/make install)

#Otherwise, you should just use my modified version: https://github.com/dbtayl/libarea
#This version is modified to have the correct CMakeLists.txt, as well as
#to correctly read units from DXF files

#For exporting slices from FreeCAD (for an STL), see:
#http://forum.freecadweb.org/viewtopic.php?t=2891
#m=App.ActiveDocument.ActiveObject.Mesh
#s=m.crossSections([(App.Vector(0,0,0),App.Vector(0,0,1)),(App.Vector(0,0,1),App.Vector(0,0,1)),(App.Vector(0,0,2),App.Vector(0,0,1))])
#for i in s:
#    for j in i:
#        if len(j) > 1:
#            Part.show(Part.makePolygon(j))

#Or, directly:
#from FreeCAD import Base
#
#wires=list()
#shape=FreeCAD.getDocument("Unnamed").Fusion.Shape
#
#for i in shape.slice(Base.Vector(0,0,1),5):
#	wires.append(i)
#
#comp=Part.Compound(wires)
#slice=FreeCAD.getDocument("Unnamed").addObject("Part::Feature","Fusion_cs")
#slice.Shape=comp
#slice.purgeTouched()
#del slice,comp,wires,shape

import area
import argparse
import gcode
import os.path
import math
#from Tkinter import Tk, Canvas, Frame, BOTH
from Tkinter import *

#Make a clone of an Area object
def deepcopy_area(do):
	a = area.Area()
	for c in do.getCurves():
		a.append(c)
	return a


#Defaults
DEFAULT_ZSAFE=25.4
DEFAULT_FEED=30*25.4
DEFAULT_TOOLD=6.35
DEFAULT_STEPOVER=-1
DEFAULT_CUTDEPTH=-1
DEFAULT_RPM=10000
screenW = 800
screenH = 600


#Nicely handle command-line arguments
parser=argparse.ArgumentParser(description="Create toolpaths and (hopefully someday) GCode from DXF files")
parser.add_argument("inputfile", metavar="IN.dxf", type=str, help="DXF file to generate toolpaths for")
parser.add_argument("outputfile", metavar="OUT.ngc", type=str, help='GCode output file, default ${IN%%.dxf}.ngc', nargs="?")
parser.add_argument("--climb", dest="climb", action="store_true", help="Use climb milling instead of conventional (default: conventional)")
parser.add_argument("-c","--cutdepth", metavar="DEPTH", default=DEFAULT_CUTDEPTH, type=float, help=("Sets the cut depth of each pass (mm) for machining. Default ToolD/2 mm"))
parser.add_argument("-f","--feed", metavar="FEED", default=DEFAULT_FEED, type=float, help=("Sets the feed rate (mm/min) for machining in the XY plane. Default " + str(DEFAULT_FEED) + " mm/min"))
#parser.add_argument("--helix", dest="helix", action="store_true", help="Enable helical plunging (EXPERIMENTAL) (default: straight plunge)")
parser.add_argument("-s","--stepover", metavar="STEP", default=DEFAULT_STEPOVER, type=float, help=("Sets how much lateral material is removed per pass (mm). Default ToolD/2 mm"))
parser.add_argument("-t","--toold", metavar="DIA", default=DEFAULT_TOOLD, type=float, help=("Sets the tool diameter (mm). Default " + str(DEFAULT_TOOLD) + " mm"))
parser.add_argument("-w","--rpm", metavar="RPM", default=DEFAULT_TOOLD, type=int, help=("Sets the spindle angular velocity (RPM). Default " + str(DEFAULT_RPM) + " RPM"))
parser.add_argument("-z","--zsafe", metavar="HEIGHT", default=DEFAULT_ZSAFE, type=float, help=("Sets the safe height (mm) for rapid travel. Default " + str(DEFAULT_ZSAFE) + " mm"))
args = parser.parse_args()


#Copy arguments into useful variables
inputfile = args.inputfile
toold = args.toold
feed = args.feed
zsafe = args.zsafe
rpm = args.rpm
climb = args.climb

#This may need to be handled differently if we support linear ramps
#if args.helix:
#	plungetype = gcode.plungeHelical
#else:
#	plungetype = gcode.plungeStraight

#Output file may need special handling- if not passed, use input filename,
#replacing ".dxf" with".ngc"
#Otherwise, use argument passed
if args.outputfile == None:
	outputfile = inputfile.split(".dxf")[0] + ".ngc"
else:
	outputfile = args.outputfile

#Before doing too much work, check to see if we can even open the requested output file
fout = open(outputfile, 'w');
if fout.closed:
	print "Couldn't open output file " + outputfile + "; aborting"
	exit(-1)

#Stepover needs special handling- it can't be bigger than the tool
if args.stepover <= 0:
	print "Stepover either not specified or negative; using default ToolD/2 (" + str(toold/2) + " mm)"
	stepover = toold/2
else:
	if args.stepover > toold:
		print "ERROR: Specified stepover (" + str(args.stepover) + " mm) is greater than the tool diameter (" + str(toold) + " mm). Aborting!"
		exit(-1)
	stepover = args.stepover

#Similarly, cutdepth needs special handling- default based on tool size
if args.cutdepth <= 0:
	print "Cut depth either not specified or negative; using default ToolD/10 (" + str(toold/10) + " mm)"
	cutdepth = toold/10
else:
	if args.cutdepth > toold/2:
		print "########"
		print "WARNING: Specified cut depth (" + str(args.cutdepth) + " mm) is greater than ToolD/2 (" + str(toold/2) + " mm). This is generally frowned upon unless you're cutting very soft materials!"
		print "########"
	cutdepth = args.cutdepth

print ""
print "Input file is: " + str(inputfile)
print "Feed rate is: " + str(feed) + " mm/min"
print "ZSafe is: " + str(zsafe) + " mm"
print "ToolD is: " + str(toold) + " mm"
print "Stepover is: " + str(stepover) + " mm"
print "Spindle RPM is: " + str(rpm) + " RPM"
print ""




def lmouse_callback(event):
	print "YAY!"
	
def rmouse_callback(event):
	print "BOO!"

root = Tk()
canvas = Canvas(root, width=screenW, height=screenH)
canvas.pack()
canvas.bind("<Button-1>", lmouse_callback);
canvas.bind("<Button-3>", rmouse_callback);


#Processes the segments of a curve and renders them to the screen
#Also handles arcs
#This has nothing to do with generating GCode
def addLine(curve, scale=1.0):
	lastx = 0
	lasty = 0
	verts = curve.getVertices();
	lastx = verts[0].p.x * scale
	lasty = verts[0].p.y * scale
	i = 1;
	while i < len(verts):
		cx = verts[i].p.x * scale
		cy = verts[i].p.y * scale
		#Lines are easy- point to point
		if verts[i].type == 0:
			canvas.create_line(lastx, lasty, cx, cy)
		#Arcs are a pain- find the center+radius, calculate end points, ...
		#The directions, addition vs subtraction, start vs end points, etc. were largely trial-and-error to get right
		#They may well be done in a logically-correct, but humanl-readably-awful manner
		#1 is CCW, -1 is CW
		elif verts[i].type == 1 or verts[i].type == -1:
			centerx = verts[i].c.x * scale
			centery = verts[i].c.y * scale
			radius = math.sqrt((centerx - cx)**2 + (centery - cy)**2)
			dy = cy - centery;
			dx = cx - centerx;
			endangle = math.atan2(-dy, dx) * 180 / math.pi
			dy = lasty - centery;
			dx = lastx - centerx;
			startangle = math.atan2(-dy, dx) * 180 / math.pi
			#print "Radius: " + str(radius) + "\tStart: " + str(startangle) + "\tStop: " + str(endangle) + "\tCenter: " + str(centerx) + "," + str(centery)
			#wedgestyle = PIESLICE
			wedgestyle = ARC
			extent = endangle - startangle;
			#print "Calculated extent: " + str(extent)
			if extent < 0:
				extent = startangle - endangle
			#CCW
			if verts[i].type == 1:
				if startangle > endangle:
					canvas.create_arc(centerx - radius, centery-radius, centerx+radius, centery+radius, start=endangle, extent=extent, style = wedgestyle)
				else:
					canvas.create_arc(centerx - radius, centery-radius, centerx+radius, centery+radius, start=endangle, extent=360-extent, style = wedgestyle)
			#CW
			else:
				#print "WARNING: Clockwise arc detected! This is only loosely tested!"
				if startangle > endangle:
					canvas.create_arc(centerx - radius, centery-radius, centerx+radius, centery+radius, start=startangle, extent=360-extent, style = wedgestyle)
				else:
					canvas.create_arc(centerx - radius, centery-radius, centerx+radius, centery+radius, start=startangle, extent=extent, style = wedgestyle)
		else:
			print "Invalid vertex type " + str(verts[i].type) + " found in vertex " + str(i)
			exit(-1)
		lastx = cx
		lasty = cy
		i += 1





if not os.path.isfile(inputfile):
	print "Couldn't open file \"" + inputfile + "\""
	exit(-1)

#set_units doesn't actually seem to do anything
#area.set_units(1)
newarea = area.AreaFromDxf(inputfile)

#This makes sure curves are set up for climb milling
newarea.Reorder();

#One area for each polygon
areas = newarea.Split();

if len(areas) == 0:
	print "No areas in DXF file"
	exit(-1)

print "Split read DXF into " + str(len(areas)) + " section(s). Performing XOR operations"


#XOR all of the sub-areas. Kind of hack-y, but should give a good approximation
#of what was intended with the DXF
if(len(areas) > 1):
	j = 1;
	count = len(areas)
	while j < count:
		#Flush the buffer so we know something is happening without waiting for newline
		print str(j) + " / " + str(count - 1)
		sys.stdout.flush()
		if type(areas[j]) == None:
			print "NoneType... continue!"
			continue
		
		#First add to the existing area
		union = deepcopy_area(areas[j])
		union.Union(areas[0])
		#print "Len union: " + str(len(union.getCurves()))
		
		#Calculate parts to subtract, if any
		intersect = deepcopy_area(areas[j])
		intersect.Intersect(areas[0])
		#print "Len intersect: " + str(len(intersect.getCurves()))
		
		#If there's something we should cut out, do it
		if len(intersect.getCurves()) > 0:
			union.Subtract(intersect)
		
		areas[0] = union
		
		j += 1


#Returns a list of curves that form the pocket. Args:
#	cutter radius- mm
#	extra material- mm?
#	stepover- mm
#	from center (bool)- doesn't seem to do anything
#	pocket mode (bool?) (true = zig_zag, false=spiral)
#	zig angle
#Each part of the returned list is a disjoint chunk of the path
#The first element in the array is the one we XOR'd everything with to get the final result

print "Generating toolpaths"

curvelist = areas[0].MakePocketToolpath(toold/2., 0.0, stepover, False, False, 0.0)

#Make sure curves go in the direction we want
#We're either cutting full-width slots OR reducing profiles- thus CLOCKWISE
#is CLIMB milling, and COUNTERCLOCKWISE is CONVENTIONAL milling
for c in curvelist:
	if(climb):
		if not c.IsClockwise():
			c.Reverse()
	else:
		if c.IsClockwise():
			c.Reverse()

#print type(curvelist[0])
print "Found " + str(len(curvelist)) + " discrete section(s) to machine"


pathlength = 0

#Calculates the total length of all segments in the curve
def sumLength(curve):
	length = 0
	for span in curve.GetSpans():
		length += span.Length()
	return length

for p in curvelist:
	#print "Curvelist iteration"
	addLine(p,2)
	pathlength += sumLength(p)



#Generate actual gcode listing
print "Generating gcode"
#def generate(curves, zsafe, zmin, zstep, zmax, feedxy, feedz, toolD, stepover, rpm):
cmds = gcode.generate(curvelist, zsafe, 0, 0.5, 1, feed, 50, toold, stepover, rpm)

#Write it out to a file
print "Writing file"
fout.write(cmds)
fout.close()



#Print out some useful information about the job
minutes = pathlength / feed
hours = int(minutes) / 60
minutes -= hours * 60

print ""
print "Total path length: " + str("%.2f" % pathlength) + "mm\tCut time at " + str(feed) + "mm/min is " + str("%.2f" % (pathlength/feed)) + " min (" + str(hours) + "h " + str(int(minutes+0.5)) + "m)"
box = area.Box()
newarea.GetBox(box);
print "Bounding box: " + str("%.2f" % (box.MaxX() - box.MinX())) + " x " + str("%.2f" % (box.MaxY() - box.MinY())) + "mm, LL corner at (" + str("%.2f" % box.MinX()) + ", " + str("%.2f" % box.MinY()) + ") mm"
print ""


#Show plot of generated toolpaths
root.mainloop();
