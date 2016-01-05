#!/usr/bin/env python2

#If you build libarea from source and get errors, pull in CMakeLists.txt from here:
#https://github.com/aewallin/libarea
#and rebuild (cmake/make/make install)

#Inkscape doesn't export DXF files quite as nicely as it should- look for DXF
#export plugins... even then it's kinda iffy. Big Blue Saw DXF Exporter
#seems to kinda work. Units are wonky, though that may well be this code...

import area
import copy
import copy_reg
import os.path
import math
#from Tkinter import Tk, Canvas, Frame, BOTH
from Tkinter import *

#really just a copy function- doesn't actually use pickle
def pickle_area(do):
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

def lmouse_callback(event):
	print "YAY!"
	
def rmouse_callback(event):
	print "BOO!"

root = Tk()
canvas = Canvas(root, width=screenW, height=screenH)
canvas.pack()
canvas.bind("<Button-1>", lmouse_callback);
canvas.bind("<Button-3>", rmouse_callback);



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
				print "WARNING: Clockwise arc detected! This is only loosly tested!"
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




#Returns a list of curves that form the pocket
#cutter radius- mm
#extra material- mm?
#stepover- mm
#from center (bool)- doesn't seem to do anything
#pocket mode (bool?) (????)
#zig angle

#a.MakePocketToolpath(toold/2, 0.0, 3.0, False, 0, 5.0)

filename = "/tmp/novena-x-section3.dxf"

if not os.path.isfile(filename):
	print "Couldn't open DXF"
	exit(-1)

newarea = area.AreaFromDxf(filename)
area.set_units(1)
newarea.Reorder();

#One area for each polygon
areas = newarea.Split();

if len(areas) == 0:
	print "No areas in DXF file"
	exit(-1)

print "Split read DXF into " + str(len(areas)) + " section(s)"


#Assume the first area we find is a negative- something to cut out
#Well, maybe not- really want the XOR operation...
if(len(areas) > 1):
	j = 1;
	while j < len(areas):
		if type(areas[j]) == None:
			print "NoneType... continue!"
			continue
		union = pickle_area(areas[j])
		union.Union(areas[0])
		print "Len union: " + str(len(union.getCurves()))
		
		intersect = pickle_area(areas[j])
		intersect.Intersect(areas[0])
		print "Len intersect: " + str(len(intersect.getCurves()))
		
		if len(intersect.getCurves()) > 0:
			union.Subtract(intersect)
		else:
			print "No intersect"
		
		areas[0] = union
		
		j += 1

print "Done merging sections"

#Returns a list of curves comprising the toolpath
#Each part of the list is a disjoint chunk of the path?
curvelist = areas[0].MakePocketToolpath(toold/2, 0.0, toold/2+0.5, False, False, 0.0)

#print type(curvelist[0])
print "Found " + str(len(curvelist)) + " discrete section(s) to machine"


pathlength = 0

def sumLength(curve):
	global pathlength
	for span in curve.GetSpans():
		pathlength += span.Length()

for p in curvelist:
	print "Curvelist iteration"
	addLine(p,2)
	sumLength(p)

#print area.get_units()
print "Total path length: " + str(pathlength) + "mm\tCut time at " + str(feed) + "mm/min is " + str(pathlength/feed) + " min"

root.mainloop();
