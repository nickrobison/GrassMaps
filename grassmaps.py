import os
import sys
import subprocess

# Initial Variable Definition
data_directory = "/Users/nrobison/Desktop"
points_file = "atlanta.txt"
output_file = "heatmap.tif"
grass7bin = "grass70"
vector_location = "hm_pts"
raster_location = "hm"
mapset = "PERMANENT"
map_prefix = "heatmap"
radius = 500.

# Derive these variables
points_location = os.path.join(data_directory, points_file)
vector_layer = map_prefix + "_pts"
raster_layer = map_prefix + "_500"
recoded_raster_layer = map_prefix + "_500_recode"

# Have GRASS get its own GISBASE
startcmd = grass7bin + " --config path"
p = subprocess.Popen(startcmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

out, err = p.communicate()
if p.returncode != 0:
    print "ERROR: Cannot find GRASS GIS 7 start script (%s)" % startcmd
    sys.exit(-1)
gisbase = out.strip("\n")

# Set GISBASE environment variable

os.environ["GISBASE"] = gisbase
gpydir = os.path.join(gisbase, "etc", "python")
sys.path.append(gpydir)

# Define GRASS DATABASE
gisdb = os.path.join(os.path.expanduser("~"), "grassdata")
# Set GISDBASE environment variable
os.environ["GISDBASE"] = gisdb

# Import GRASS Python bindings
import grass.script as g
import grass.script.setup as gsetup

# Create new location for point data
# I get an error when I try call run_command without first running init.
# But then it doesn't actually create the location, so why not call it twice.
print "Creating location: %s" % vector_location
gsetup.init(gisbase, gisdb, vector_location, mapset)
# Remember, we need to set the EPSG code to whatever the input data is.
g.run_command('g.proj', location=vector_location, epsg=4326)
gsetup.init(gisbase, gisdb, vector_location, mapset)

# Now we can import the pygrass modules
from grass.pygrass.modules.shortcuts import raster as r
from grass.pygrass.modules.shortcuts import vector as v

# Import the points data
print "Importing Vector Data from: %s" % points_location
v.in_ascii(input=points_location, output=vector_layer, skip=1, x=2, y=3)

# Create the Raster location and switch to it.
print "Creating location %s" % raster_location
g.run_command('g.proj', location=raster_location, epsg=3395)
gsetup.init(gisbase, gisdb, raster_location, mapset)

# Import the points from the vector location and set the region bounds
print "Importing points from vector location"
v.proj(input=vector_layer, location=vector_location, mapset="PERMANENT")
g.run_command("g.region", vect=vector_layer)

# Build the Heatmap
print "Building heatmap: %s" % raster_layer
v.kernel(input=vector_layer, output=raster_layer, radius=radius)

# Generate the layer statistics and extract the maximum value
# Since we're doing some sorting ourselves, we'll be using r.stats
# instead of r.report
print "Getting layer stats"
vals = []
output = g.pipe_command('r.stats', input=raster_layer)
for line in output.stdout:
    vals.append(float(line.rstrip('\r\n').split('-')[1]))

print "Layer maximum value: %s" % vals[-1]

# Recode the raster using these rules
# A better solution would be to read in a rules file, but I'm too lazy.
# If you want to do that, you'll need to specify a file location
#   and remove the write_command call.
# We're also going to be really snarky and recode to the maximum int value (255).
    #That's mostly because I don't know how to programmatically
    #rescale a float to an int
print "Recoding raster layer"
rules = "0.0:" + str(vals[-1]) + ":0:255"
#r.recode(input=raster_layer, rules=rules, output=recoded_raster_layer)
g.write_command('r.recode', input=raster_layer, rule='-', output=recoded_raster_layer, stdin=rules)

# Now, we apply our color table
# Again, we'll pipe this from stdin, but you should probably use a file.
# These rules get way more complicated, since we need multiple lines,
    # but I'm still too lazy to write to a file. Also, \n's are fun.
print "Applying new color table"
color_rules = "0% blue\n33.33% green\n66.67% yellow\n100% red"
g.write_command('r.colors', map=recoded_raster_layer, rules='-', stdin=color_rules)

# Set NULL values to remove noise
# I'm doing a fairly aggressive data purge, use respnsibly
print "Nullifying nulls"
r.null(map=recoded_raster_layer, setnull="0-20")

# Finally, write it to a GeoTiff
print "Writing file: %s" % os.path.join(data_directory, output_file)
r.out_gdal(input=recoded_raster_layer,
           format="GTiff",
           type="Byte",
           output=os.path.join(data_directory, output_file),
           createopt="INTERLEAVE=PIXEL, TFW=YES, PROFILE=GeoTIFF")

# That's all folks!
print "Congrats, it is finished."
