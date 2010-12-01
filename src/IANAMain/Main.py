'''
This module serves as the entry point to the SuryaImageAnalyzer application.

It analyzes an input image to compute the Black Carbon Concetration.

Created on Oct 20, 2010

@author: surya
'''

import os.path
import logging
import pylab
import psyco
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageFont as ImageFont
 
from Logging.Logger import getLog
from IANASteps.Geometry.Point import Point
from IANASettings.Settings import ExitCode, MainConstants, CalibratorConstants
from IANASteps.QRDetector.QRDetector import detectQR
from IANASteps.StageDetector.StageDetector import detectStage, detectCalibrator
from IANASteps.ImageTransformer.ImageTransformer import transform
from IANASteps.Calibrator.Calibrator import getGrayBars
from IANASteps.BCFilterDetector.BCFilterDetector import splitToBands, detectBCFilter, select, PsycoInit
from IANASteps.BCCCalculator.BCCCalculator import rateFilter
from IANAUtil.Chart import plotChart

log = getLog("Main")
log.setLevel(logging.ERROR)

def Main(imagefile, filterRadius, bcGradient, exposedTime, airFlowRate, imageLogLevel, debugImageFile, chartFile, parenttags=None, level=logging.ERROR,):
    ''' This method analyzes the imageFile, and uses the given parameters to comptute the BCC
    
    Keyword Arguments:
    imagefile    -- The image file on which to perform the black carbon concentration analysis
    filterRadius -- The radius of the filter in the image
    bcGradient   -- The gradient values to be used in the interpolation to ind the BCVol.
    exposedTime  -- The time duration for which the filter was exposed.
    airFlowRate  -- The flowrate of the pump.
    imageLogLevel-- 0, no logging, 1 log image, 2 log and show image
    debugImageFile -- The name of the debugImage in which to store the image processing debug info.
    chartFile    -- The name of the chartFile in which to store the plotted results.
    parenttags   -- The tagstring of the calling function
    level        -- The logging level
    
    Returns:
    BCCResult object containing the results of the Image Analysis.
    
    '''
    
    # Set the logging level 
    log.setLevel(level)
    tags = parenttags + " IANAMAIN"
    
    log.info('Running SuryaImageAnalyzer', extra=tags)
    
    # Open the image file using PIL.Image
    if isinstance(imagefile, str):
        if not os.path.isfile(imagefile):
            log.error('imagefile ' + imagefile + ' does not exist')
            return None, ExitCode.FileNotExists
        
        image = Image.open(imagefile)
    elif isinstance(imagefile, file):
        try:
            image = Image.open(imagefile)
        except Exception, err:
            log.error('Error %s' % str(err))
        
            return None, ExitCode.UnknownError
    else:
        log.error('Error unknown filetype for input imagefile')
        return None, ExitCode.UnknownError
        
    
    if imageLogLevel:
        debugImage = image.copy()
        drawing = ImageDraw.Draw(debugImage)
        # For all the text that goes into the debug image
        font = ImageFont.truetype(MainConstants.fontfile, 45)
    
    # QR Detection Step
    qr, exitcode = detectQR(imagefile, tags, logging.DEBUG)

    if exitcode is not ExitCode.Success:
        log.error('Could not process for QR: ' + exitcode, extra=tags)
        return None, exitcode
    
    if imageLogLevel:
        qr.draw(drawing, 'red')
        
    # Stage detection Step
    stage, exitcode = detectStage(qr, tags, logging.DEBUG)
    
    if exitcode is not ExitCode.Success:
        log.error('Could not process for Stage: ' + exitcode, extra=tags)
        return None, exitcode
    
    # Calibrator detection Step
    calibrator, exitcode = detectCalibrator(qr, tags, logging.DEBUG)
    
    if exitcode is not ExitCode.Success:
        log.error('Could not process for Calibrator: ' + exitcode, extra=tags)
        return None, exitcode
    
    # Extract Data from the Calibrator
    grayBars, exitcode = getGrayBars(qr, image, tags, logging.DEBUG)
    
    if exitcode is not ExitCode.Success:
        log.error('Could not get grayBars from Calibrator ' + exitcode, extra=tags)
        return None, exitcode
    
    gradient = []
    for grayBar in grayBars:
        gradient.append(grayBar.sample(image))
            
    if imageLogLevel:
        # draw boxes on each graybar
        for grayBar in grayBars:
            grayBar.draw(drawing, 'magenta')
            
        #lines across the graybars columns
        boxsize = Point(CalibratorConstants.BoxSize, CalibratorConstants.BoxSize)
        for i in range(0,2):
            top = Point(grayBars[0 + i*6].box.coordinates[0:2])
            bottom = Point(grayBars[5 + i*6].box.coordinates[0:2])
        
            drawing.line(tuple(top + boxsize) + tuple(bottom+boxsize) , 'yellow')
            
    # Patch
    draw = ImageDraw.Draw(image)
    draw.polygon((calibrator.topLeft, calibrator.bottomLeft, calibrator.bottomRight, calibrator.topRight), fill='black')
    del draw
    
    # Image Transformation Step
    image, exitcode = transform(image, stage, tags, logging.DEBUG)

    if exitcode is not ExitCode.Success:
        log.error('Could not transform using Stage Coordinates: ' + exitcode, extra=tags)
        return None, exitcode
    
    if imageLogLevel:
        # Image Transformation Step
        debugImage, exitcode = transform(debugImage, stage, tags, logging.DEBUG)

        if exitcode is not ExitCode.Success:
            log.error('Could not transform debugImage using Stage Coordinates: ' + exitcode, extra=tags)
            return None, exitcode
    
        drawing = ImageDraw.Draw(debugImage)
        
    # Detect bcFilters
    PsycoInit(psyco)
    bands = splitToBands(image)
    if bands is None:
        log.error('Could not find the bcfilter in the image', extra=tags)
        return None, ExitCode.UnknownError

    bcFiltersPerBand = []
    
    if imageLogLevel:
        bandIndex = 0
    
    
    for band in bands:
        bcFilters, exitcode = detectBCFilter(band, None, tags, logging.DEBUG)
        
        if exitcode is not ExitCode.Success:
            log.error('Could not detect filters in the Image ' + exitcode, extra=tags)
            return None, exitcode
        
        if imageLogLevel:
            index = 1
            for bcFilter in bcFilters:
                drawing.text(bcFilter.center, str(index), MainConstants.bandnames[bandIndex], font)
                bcFilter.draw(drawing, MainConstants.bandnames[bandIndex])
                index += 1
            bandIndex += 1

        bcFiltersPerBand.append(bcFilters)
        
    bestBand = select(bcFiltersPerBand)
    
    if not bestBand:
        return None, ExitCode.UnknownError
    
    bestBcFilter = bestBand[0]
    
    sampledRGB = bestBcFilter.sample(image, bestBcFilter.radius/MainConstants.samplingfactor)
         
    # Compute BCC
    bccResult, exitcode = rateFilter(sampledRGB, filterRadius, exposedTime, airFlowRate, bcGradient, gradient, tags, logging.DEBUG)
    
    if exitcode is not ExitCode.Success:
        log.error('Could not compute BCC result for : ' + exitcode, extra=tags)
        return None, exitcode

    log.info('Done Running SuryaImageAnalyzer', extra=tags)
    
    if imageLogLevel:
        plotChart(filterRadius, exposedTime, airFlowRate, bcGradient, gradient, bccResult, sampledRGB, chartFile)
        debugImage.save(debugImageFile)
        
    if imageLogLevel > 1:
        debugImage.show()
     
    return bccResult, exitcode

if __name__ == '__main__':
# (imagefile, filterRadius, bcGradient, exposedTime, airFlowRate, imageLogLevel, debugImageFile, chartFile, level=logging.ERROR,):
    bccResult, exitcode = Main('/home/surya/Desktop/Surya_BC_Catalog-2010-10-13/Khairatpur-2010-08/09092010039.jpg',  # Los_Angeles-2010-06/0625101809.jpg 
                               5.45,
                               pylab.array([  0.53805296,   0.77764056,   
                                1.10252548,   1.54307503, 
                                2.14046781,   2.9505427 ,
                                4.04901822,   5.53856995,
                                7.55842775,  10.29738974]),
                               1150,
                               0.68,
                               2,
                               '/home/surya/Desktop/Surya_BC_Catalog-2010-10-13/Khairatpur-2010-08/09092010039.jpg.debug.png',
                               '/home/surya/Desktop/Surya_BC_Catalog-2010-10-13/Khairatpur-2010-08/09092010039.jpg.chart.png',
                               'Khairatpur-2010-08/09092010039.jpg',
                               logging.DEBUG)