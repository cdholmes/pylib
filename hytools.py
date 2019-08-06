#!/usr/bin/env python3

# Package of functions to read HYSPLIT output 

import numpy  as np
import pandas as pd
import datetime as dt
import os
import glob
import netCDF4 as nc

metroot = '/data/MetData/ARL/'

def tdump2nc( inFile, outFile, clobber=False, globalAtt=None ):
    # Convert a HYSPLIT tdump file to netCDF
    # Works with single point or ensemble trajectories

    import nctools as nct

    # Trajectory points
    traj = read_tdump( inFile )

    # Trajectory numbers; convert to int32
    tnums = traj.tnum.unique().astype('int32')

    # Number of trajectories (usually 1 or 27)
    ntraj = len( tnums )

    # Trajectory start time
    starttime = traj.time[0] 

    # Time along trajectory, hours since trajectory start
    ttime  = traj.thour.unique().astype('f4')

    # Number of times along trajectory
    nttime = len( ttime )

    # Empty arrays
    lat    = np.zeros( (ntraj, nttime), np.float32 )
    lon    = np.zeros( (ntraj, nttime), np.float32 )
    altMSL = np.zeros( (ntraj, nttime), np.float32 )
    altAGL = np.zeros( (ntraj, nttime), np.float32 )
    p      = np.zeros( (ntraj, nttime), np.float32 )
    T      = np.zeros( (ntraj, nttime), np.float32 )
    Q      = np.zeros( (ntraj, nttime), np.float32 )
    precip = np.zeros( (ntraj, nttime), np.float32 )
    inBL   = np.zeros( (ntraj, nttime), np.int8 ) 

    # Check if optional variables are present
    doP        = ('PRESSURE' in traj.columns)
    doMSL      = ('TERR_MSL' in traj.columns)
    doBL       = ('MIXDEPTH' in traj.columns)
    doT        = ('AIR_TEMP' in traj.columns)
    doQ        = ('SPCHUMID' in traj.columns)
    doPrecip   = ('RAINFALL' in traj.columns)

    for t in tnums:
        # Find entries for this trajectory 
        idx = traj.tnum==t

        # Save the coordinates
        lat[t-1,:]    = traj.lat[idx]
        lon[t-1,:]    = traj.lon[idx]
        altAGL[t-1,:] = traj.alt[idx]

        # Add optional variables
        if (doP):
            p[t-1,:] = traj.PRESSURE[idx]
        if (doT):
            T[t-1,:]      = traj.AIR_TEMP[idx]
        if (doQ):
            Q[t-1,:]      = traj.SPCHUMID[idx]
        if (doPrecip):
            precip[t-1,:] = traj.RAINFALL[idx]
        if (doMSL):
            altMSL[t-1,:] = traj.alt[idx] + traj.TERR_MSL[idx]
        if (doBL):
            inBL[t-1,:]   = (traj.alt[idx] < traj.MIXDEPTH[idx])
    
    # Put output variables into a list
    variables = [
        {'name':'lat',
            'long_name':'latitude of trajectory',
            'units':'degrees_north',
            'value':np.expand_dims(lat,axis=0)},
        {'name':'lon',
           'long_name':'longitude of trajectory',
           'units':'degrees_east',
           'value':np.expand_dims(lon, axis=0)},
        {'name':'altAGL',
           'long_name':'altitude of trajectory above ground level',
           'units':'m',
           'value':np.expand_dims(altAGL, axis=0)} ]

    # Add optional variables to output list
    if (doMSL):
        variables.append( 
           {'name':'altMSL',
           'long_name':'altitude of trajectory above mean sea level',
           'units':'m',
           'value':np.expand_dims(altMSL,axis=0)} )
    if (doP):
        variables.append(
            {'name':'p',
           'long_name':'pressure of trajectory',
           'units':'hPa',
           'value':np.expand_dims(p,axis=0)} )
    if (doT):
        variables.append(
            {'name':'T',
           'long_name':'temperature of trajectory',
           'units':'K',
           'value':np.expand_dims(T,axis=0)} )
    if (doQ):
        variables.append(
            {'name':'q',
           'long_name':'specific humidity of trajectory',
           'units':'g/kg',
           'value':np.expand_dims(Q,axis=0)} )
    if (doPrecip):
        variables.append(
            {'name':'precipitation',
           'long_name':'precipitation on trajectory',
           'units':'mm',
           'value':np.expand_dims(precip,axis=0)} )
    if (doBL):
        variables.append(
            {'name':'inBL',
           'long_name':'trajectory in boundary layer flag',
           'units':'unitless',
           'value':np.expand_dims(inBL,axis=0)} )

    # Construct global attributes
    # Start with default and add any provided by user input
    gAtt = {'Content': 'HYSPLIT trajectory'}
    if (type(globalAtt) is dict):
        gAtt.update(globalAtt)

    # Create the output file
    nct.write_geo_nc( outFile, variables,
        xDim={'name':'trajnum',
            'long_name':'trajectory number',
            'units':'unitless',
            'value':tnums},
        yDim={'name':'trajtime',
            'long_name':'time since trajectory start',
            'units':'hours',
            'value':ttime},
        tDim={'name':'time',
            'long_name':'time of trajectory start',
            'units':'hours since 2000-01-01 00:00:00',
            'calendar':'standard',
            'value':np.array([starttime]),
            'unlimited':True},
        globalAtt=gAtt,
        nc4=True, classic=True, clobber=clobber )



# Read trajectory file output from HYSPLIT
def read_tdump(file):

    # Open the file
    with open(file,"r") as fid:

        # First line gives number of met fields
        nmet = int(fid.readline().split()[0])
        
        # Skip the met file lines
        for i in range(nmet):
            next(fid)

        # Number of trajectories
        ntraj = int(fid.readline().split()[0])

        # Skip the next lines
        for i in range(ntraj):
            next(fid)

        # Read the variables that are included
        line = fid.readline()
        nvar = int(line.split()[0])
        vnames = line.split()[1:]
        
        # Read the data
        df = pd.read_csv( fid, delim_whitespace=True,
                          header=None, index_col=False,
                names=['tnum','metnum',
                       'year','month','day','hour','minute','fcasthr',
                       'thour','lat','lon','alt']+vnames )
        
        # Convert year to 4-digits
        df.loc[:,'year'] += 2000

        # Convert to time
        df['time'] = pd.to_datetime( df[['year','month','day','hour','minute']] )
        
        #print(df.iloc[-1,:])
        return df

# Directory and File names for GDAS 1 degree meteorology, for given date    
def get_gdas1_filename( time ):

    # Directory for GDAS 1 degree
    dirname = metroot+'gdas1/'

    # Filename template
    filetmp = 'gdas1.{mon:s}{yy:%y}.w{week:d}'

    # week number in the month
    wnum = ((time.day-1) // 7) + 1

    # GDAS 1 degree file
    filename = filetmp.format( mon=time.strftime("%b").lower(), yy=time, week=wnum )

    return dirname, filename

# Directory and File names for hrrr meteorology, for given date
def get_hrrr_filename( time ):

    # Directory
    dirname = metroot+'hrrr/'

    # Filename template
    filename = '{date:%Y%m%d}_*_hrrr'.format( date=time )

    # Find all the files that match these criteria
    files = glob.glob( dirname + filename )

    # When we find then, sort and combine into one list
    files = sorted( files )

    # Split into directory and file names
    dirnames  = [ os.path.dirname(f)+'/' for f in files ]
    filenames = [ os.path.basename(f)    for f in files ]

    # Return
    return dirnames, filenames


# Directory and file names for given meteorology and date
def get_met_filename( metversion, time ):

    # Ensure that time is a datetime object
    if (not isinstance( time, dt.date) ):
        raise TypeError( "get_met_filename: time must be a datetime object" )
    
    # Directory and filename template
    if (metversion == 'gdas1' ):
        # Special treatment
        dirname, filename = get_gdas1_filename( time )
    elif (metversion == 'gdas0p5'):
        dirname  = metroot+'gdas0p5/'
        filename = '{date:%Y%m%d}_gdas0p5'
    elif (metversion == 'gfs0p25'):
        dirname  = metroot+'gfs0p25/'
        filename = '{date:%Y%m%d}_gfs0p25'
    elif (metversion == 'nam3' ):
        dirname  = metroot+'nam3/'
        filename = '{date:%Y%m%d}_hysplit.namsa.CONUS'
    elif (metversion == 'nam12' ):
        dirname  = metroot+'nam12/'
        filename = '{date:%Y%m%d}_hysplit.t00z.namsa'
    elif (metversion == 'hrrr' ):
        # Special treatment
        dirname, filename = get_hrrr_filename( time )
        return dirname, filename
    else:
        raise NotImplementedError(
            "get_met_filename: {metversion:s} unrecognized".format(metversion) )

    # Build the filename
    filename = filename.format( date=time )

    return dirname, filename

# Get a list of met directories and files
# When there are two met version provided, the first result will be used
def get_met_filelist( metversion, time, useAll=True ):

    if isinstance( metversion, str ):

        # If metversion is a single string, then get value from appropriate function
        dirname, filename = get_met_filename( metversion, time )
        
    elif isinstance( metversion, list ):

        # If metversion is a list, then get files for each met version in list

        dirname  = []
        filename = []

        # Loop over all the metversions
        # Use the first one with a file present
        for met in metversion:

            # Find filename for this met version
            d, f = get_met_filename( met, time )

            if (useAll):
                # Append to the list so that all can be used
                dirname.append( d)
                filename.append(f)

            else:
                # Use just the first met file that exists
                dirname  = d
                filename = f
                break
                # If the file exists, use this and exit;
                # otherwise keep looking
                #if isinstance( f, str ):
                #    if ( os.path.isfile( d+f ) ):
                #        dirname  = d
                #        filename = f
                #        break
                #elif isinstance( f, list ):
                #    if ( os.path.isfile( d[0]+f[0] ) ):
                #        dirname  = d
                #        filename = f
                #        break

        # Raise an error if 
        if (filename is []):
            raise FileNotFoundError(
                "get_met_filename: no files found for " + ','.join(metversion) )

    else:
        raise TypeError( "get_met_filelist: metversion must be a string or list" )

    return dirname, filename

def get_forecast_template( metversion ):
    # Get filename template for forecast meteorology
    
    if (metversion == 'namsfCONUS'):
        # Filename template
        filetemplate = 'hysplit.t{:%H}z.namsf??.CONUS'
        nexpected = 8
    else:
        filetemplate = 'hysplit.t{:%H}z.'+metversion
        nexpected = 1

    return filetemplate, nexpected
    
def get_forecast_filename( metversion, cycle ): 
    # Find files for a particular met version and forecast cycle
    
    dirname  = metroot + 'forecast/{:%Y%m%d}/'.format(cycle)
    filename, nexpected  = get_forecast_template( metversion )

    # Filename for this cycle
    filename = filename.format(cycle)

    # Find all the files that match these criteria
    files = glob.glob( dirname + filename )

    # Check if we found the expected number of files
    if ( len(files) == nexpected ):

        # When we find then, sort and combine into one list
        files = sorted( files )
        
        # Split into directory and file names
        dirnames  = [ os.path.dirname(f)+'/' for f in files ]
        filenames = [ os.path.basename(f)    for f in files ]
        
        # Return
        return dirnames, filenames
        
    # Raise an error if no forecasts are found
    raise FileNotFoundError('ARL forecast meteorology found' )
    
def get_forecast_filename_latest( metversion ):
    # Find files for the latest available forecast cycle for the requested met version.
    
    # Filename template for forecast files
    filetemplate, nexpected = get_forecast_template( metversion )

    # Find all of the forecast directories, most recent first
    dirs = [item for item
            in sorted( glob.glob( metroot+'forecast/????????' ), reverse=True )
            if os.path.isdir(item) ]

    for d in dirs:
        
        # Loop backwards over the forecast cycles
        for hh in [18,12,6,0]:
            
            # Check if the forecast files exist
            files = glob.glob(d+'/'+filetemplate.format(dt.time(hh)))
            #'hysplit.t{:02d}z.{:s}'.format(hh,metsearch))

            # Check if we found the expected number of files
            if ( len(files) == nexpected ):

                # When we find then, sort and combine into one list
                files = sorted( files )
                
                # Split into directory and file names
                dirnames  = [ os.path.dirname(f)+'/' for f in files ]
                filenames = [ os.path.basename(f)    for f in files ]
                
                # Return
                return dirnames, filenames

    # Raise an error if no forecasts are found
    raise FileNotFoundError('No ARL forecast meteorology found' )

def get_forecast_filelist( metversion=['namsfCONUS','namf'], cycle=None ):

    # If metversion is a single string, then get value from appropriate function
    if isinstance( metversion, str ):

        if (cycle is None):
            dirnames, filenames = get_forecast_filename_latest( metversion )
        else:
            dirnames, filenames = get_forecast_filename( metversion, cycle )
            
    else:

        dirnames  = []
        filenames = []
        
        # Loop over the list of met types, combine them all
        for met in metversion:

            # Get directory and file names for one version
            d, f = get_forecast_filelist( met, cycle )

            # Combine them into one list
            dirnames  = dirnames  + d
            filenames = filenames + f            
            
    return dirnames, filenames


def write_control( time, lat, lon, alt, trajhours,
                   fname='CONTROL.000', metversion=['gdas0p5','gdas1'],
                   forecast=False, forecastcycle=None ):

    # Write a control file for trajectory starting at designated time and coordinates

    # Number of days of met data
    ndays = int( np.ceil( np.abs( trajhours ) / 24 ) + 1 )

    if ( trajhours < 0 ):
        d0 = -ndays+1
        d1 = 1
    else:
        d0 = 0
        d1 = ndays

    if (forecast is True):
        # Get the forecast meteorology
        metdirs, metfiles = get_forecast_filelist( metversion, forecastcycle )
        
        # Check if the forecast meteorology covers the entire trajectory duration
    else:

        # List of met directories and met files that will be used
        metdirs  = []
        metfiles = []
        for d in range(d0,d1):
            # date of met data
            metdate = time.date() + pd.Timedelta( d, "D" )

            dirname, filename = get_met_filelist( metversion, metdate )

            # Add the file, if it isn't already in the list
            if ( filename not in metfiles ):
                metdirs.append(  dirname  )
                metfiles.append( filename )

    # Number of met files
    nmet = len( metfiles )

    # Runs will fail if the initial time is not bracketed by met data.
    # When met resolution changes on the first day, this condition may not be met.
    # Starting the midnight trajectories at one 00:01 avoids this problem.
    if (time.hour==0 and time.minute == 0):
        time = time + pd.Timedelta( 1, "m" )

    # Start date-time, formatted as YY MM DD HH {mm}
    startdate = time.strftime( "%y %m %d %H %M" )

    f = open( fname, 'w' )

    f.write( startdate+'\n' )
    f.write( "1\n" )
    f.write( '{:<10.4f} {:<10.4f} {:<10.4f}\n'.format( lat, lon, alt ) )
    f.write( '{:d}\n'.format( trajhours ) )
    f.write( "0\n" )
    f.write( "10000.0\n" )
    f.write( '{:d}\n'.format( nmet ) )
    for i in range( nmet ):
        f.write( metdirs[i]+'\n' )
        f.write( metfiles[i]+'\n' )
    f.write( "./\n" )
    f.write( "tdump\n" )

    f.close()

