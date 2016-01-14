import math

#SFM obviously Imperial; toolD in INCHES
def rpmFromSfm(sfm, toolD_in):
	return 12 * sfm / (math.pi * toolD_in)

#Feed in inches/minute, given imperial inputs, or mm/minute, given metric units
def feedFromRpmUpt(rpm, Upt, teeth):
	return ipt * rpm * teeth

#Material removal volume/minute, in mm**3 or in**3, depending on input units
def removalFromFeed(toolD, feed, cutDepth):
	return toolD * feed * cutDepth

#Some power estimates for material removal, given removal rate
#def powerFromVolumeRateMetric(volRate):
	

