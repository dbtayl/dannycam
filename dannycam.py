#!/usr/bin/env python2

#If you build libarea from source and get undefined symbol errors, pull
#in CMakeLists.txt from here: https://github.com/aewallin/libarea
#and rebuild (cmake/make/make install)

#Otherwise, you should just use my modified version: https://github.com/dbtayl/libarea
#This version is modified to have the correct CMakeLists.txt, as well as
#to correctly read units from DXF files

#Next comment left below so it gets committed, at least for a bit, but
#the DXF "correctness" issues were definitely in part libarea's fault.
#My version (above) also has a fix

#Inkscape doesn't export DXF files quite as nicely as it should, at least
#not any sort of complex stuff (eg, arcs)- look for DXF export plugins...
#even then it's kinda iffy. Big Blue Saw DXF Exporter seems to kinda work.
#it needs to be fixed, though (as of version 0.2):

#http://www.inkscapeforum.com/viewtopic.php?t=19161
#Essentially, the line in "inch_dxf_outlines.py" in the extensions folder,
#h = inkex.unittouu(self.document.getroot().xpath('@height',namespaces=inkex.NSS)[0])
#should read
#h = self.unittouu(self.document.getroot().xpath('@height',namespaces=inkex.NSS)[0])
#that is, replace the first "inkex" with "self", and save the file. Ensure that Inkscape isn't running while making the change.

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


toold = 6.35
#toold = 3.175
feed = (40 * 25.4)
stepover = toold/2
screenW = 800
screenH = 480

#Defaults
DEFAULT_ZSAFE=25.4
DEFAULT_FEED=30*25.4
DEFAULT_TOOLD=6.35
DEFAULT_STEPOVER=-1


#Nicely handle command-line arguments
parser=argparse.ArgumentParser(description="Create toolpaths and (hopefully someday) GCode from DXF files")
parser.add_argument("inputfile", metavar="FILE.dxf", type=str, help="DXF file to generate toolpaths for")
parser.add_argument("-f","--feed", metavar="FEED", default=DEFAULT_FEED, type=float, help=("Sets the feed rate (mm/min) for machining. Default " + str(DEFAULT_FEED) + " mm/min"))
parser.add_argument("-z","--zsafe", metavar="HEIGHT", default=DEFAULT_ZSAFE, type=float, help=("Sets the safe height (mm) for rapid travel. Default " + str(DEFAULT_ZSAFE) + " mm"))
parser.add_argument("-t","--toold", metavar="DIA", default=DEFAULT_TOOLD, type=float, help=("Sets the tool diameter (mm). Default " + str(DEFAULT_TOOLD) + " mm"))
parser.add_argument("-s","--stepover", metavar="STEP", default=DEFAULT_STEPOVER, type=float, help=("Sets how much lateral material is removed per pass (mm). Default ToolD/2 mm"))
args = parser.parse_args()


#Copy arguments into useful variables
inputfile = args.inputfile
toold = args.toold
feed = args.feed
zsafe = args.zsafe

#Stepover needs special handling- it can't be bigger than the tool
if args.stepover <= 0:
	print "Stepover either not specified or negative; using default ToolD/2 (" + str(toold/2) + " mm)"
	stepover = toold/2
else:
	if args.stepover > toold:
		print "ERROR: Specified stepover (" + str(args.stepover) + " mm) is greater than the tool diameter (" + str(toold) + " mm). Aborting!"
		exit(-1)
	stepover = args.stepover

print ""
print "Input file is: " + str(inputfile)
print "Feed rate is: " + str(feed) + " mm/min"
print "ZSafe is: " + str(zsafe) + " mm"
print "ToolD is: " + str(toold) + " mm"
print "Stepover is: " + str(stepover) + " mm"
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
			if verts[i].type == 1:
				if startangle > endangle:
					canvas.create_arc(centerx - radius, centery-radius, centerx+radius, centery+radius, start=endangle, extent=extent, style = wedgestyle)
				else:
					canvas.create_arc(centerx - radius, centery-radius, centerx+radius, centery+radius, start=endangle, extent=360-extent, style = wedgestyle)
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






#a.MakePocketToolpath(toold/2, 0.0, 3.0, False, 0, 5.0)


if not os.path.isfile(inputfile):
	print "Couldn't open file \"" + inputfile + "\""
	exit(-1)

#set_units doesn't actually seem to do anything
#area.set_units(1)
newarea = area.AreaFromDxf(inputfile)
newarea.Reorder();

#One area for each polygon
areas = newarea.Split();

if len(areas) == 0:
	print "No areas in DXF file"
	exit(-1)

print "Split read DXF into " + str(len(areas)) + " section(s). Performing XOR operations",


#XOR all of the sub-areas. Kind of hack-y, but should give a good approximation
#of what was intended with the DXF
if(len(areas) > 1):
	j = 1;
	while j < len(areas):
		print ".",
		if type(areas[j]) == None:
			print "NoneType... continue!"
			continue
		union = deepcopy_area(areas[j])
		union.Union(areas[0])
		#print "Len union: " + str(len(union.getCurves()))
		
		intersect = deepcopy_area(areas[j])
		intersect.Intersect(areas[0])
		#print "Len intersect: " + str(len(intersect.getCurves()))
		
		if len(intersect.getCurves()) > 0:
			union.Subtract(intersect)
		#else:
			#print "No intersect"
		
		areas[0] = union
		
		j += 1

print " Done"

#Returns a list of curves that form the pocket. Args:
#	cutter radius- mm
#	extra material- mm?
#	stepover- mm
#	from center (bool)- doesn't seem to do anything
#	pocket mode (bool?) (????)
#	zig angle
#Each part of the returned list is a disjoint chunk of the path?
curvelist = areas[0].MakePocketToolpath(toold/2, 0.0, stepover, False, False, 0.0)

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
	addLine(p,4)
	pathlength += sumLength(p)


#Print out some useful information about the job
print ""
print "Total path length: " + str("%.2f" % pathlength) + "mm\tCut time at " + str(feed) + "mm/min is " + str("%.2f" % (pathlength/feed)) + " min"
box = area.Box()
newarea.GetBox(box);
print "Bounding box: " + str("%.2f" % (box.MaxX() - box.MinX())) + " x " + str("%.2f" % (box.MaxY() - box.MinY())) + "mm, LL corner at (" + str("%.2f" % box.MinX()) + ", " + str("%.2f" % box.MinY()) + ") mm"

root.mainloop();
