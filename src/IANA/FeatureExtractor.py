'''
Created on Nov 2, 2010

@author: surya
'''

import os.path
import StringIO
import logging
import psyco
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageFont as ImageFont
 
from Logging.Logger import getLog
from IANASteps.Geometry.Point import Point
from IANASteps.QRDetector.QRDetector import detectQR
from IANASteps.Calibrator.Calibrator import getGrayBars
from IANASteps.StageDetector.StageDetector import detectStage
from IANASteps.ImageTransformer.ImageTransformer import transform
from IANASettings.Settings import ExitCode, MainConstants, CalibratorConstants
from IANASteps.BCFilterDetector.BCFilterDetector import splitToBands, detectBCFilter, select, PsycoInit

log = getLog("FeatureExtractor")
log.setLevel(logging.ERROR)

# TODO: This method returns an image make it return the samples value
def featureExtractor(imagefile, imageLogLevel, debugImagefile, parenttags=None, level=logging.ERROR,):
    ''' This method analyzes the imageFile, and extracts the grayscale gradient, samples
        the filter in the image and returns the aux_id contained in the QR Code
    
        Keyword Arguments:
        imagefile      -- The image file on which to perform the black carbon concentration analysis
        imageLogLevel  -- 0, no logging, 1 log image, 2 log and show image
        debugImagefile -- The image file in which to store the image processing debug info.
        parenttags     -- tag string of the calling function
        level          -- The logging level
        
        Returns:
        image, aux_id, gradient, bcfilter, exitcode
    '''
    ##
    # Set the logging level 
    log.setLevel(level)
    tags = parenttags + " FEATUREEXTRACTION"
    
    try: 
        ###
        # Open the image file using PIL.Image
        ###
        if isinstance(imagefile, str):
            if not os.path.isfile(imagefile):
                log.error('imagefile ' + imagefile + ' does not exist', extra=tags)
                return None, ExitCode.FileNotExists
            image = Image.open(imagefile)
        else:
            image = Image.open(StringIO.StringIO(imagefile.read()))
        
        ###
        # If the ImageLogLevel > 1, copy the original image for image logging
        ###
        if imageLogLevel:
            debugImage = image.copy()
            drawing = ImageDraw.Draw(debugImage)
            # For all the text that goes into the debug image
            font = ImageFont.truetype(MainConstants.fontfile, 45)
    
        ###   
        # QR Detection Step
        ###
        qr, exitcode = detectQR(imagefile, tags, logging.DEBUG)
    
        if exitcode is not ExitCode.Success:
            log.error('Could not process imagefile for QR: ' + ExitCode.toString[exitcode], extra=tags)
            return None, exitcode
        
        if imageLogLevel:
            qr.draw(drawing, 'red')
        
        ###
        # Stage detection Step
        ###
        stage, exitcode = detectStage(qr, tags, logging.DEBUG)
        
        if exitcode is not ExitCode.Success:
            log.error('Could not process imagefile for Stage: ' + ExitCode.toString[exitcode], extra=tags)
            return None, exitcode
        
        ###
        # Extract Data from the Calibrator, i.e. Gradient
        ###
        grayBars, exitcode = getGrayBars(qr, image, tags, logging.DEBUG)
        
        if exitcode is not ExitCode.Success:
            log.error('Could not get grayBars from imagefile Calibrator ' + ExitCode.toString[exitcode], extra=tags)
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
        
        ###        
        # Image Transformation Step
        ###
        image, exitcode = transform(image, stage, tags, logging.DEBUG)
    
        if exitcode is not ExitCode.Success:
            log.error('Could not transform imagefile using Stage Coordinates: ' + ExitCode.toString[exitcode], extra=tags)
            return None, exitcode
        
        if imageLogLevel:
            # Image Transformation Step
            debugImage, exitcode = transform(debugImage, stage, tags, logging.DEBUG)
    
            if exitcode is not ExitCode.Success:
                log.error('Could not transform debugImage using Stage Coordinates: ' + ExitCode.toString[exitcode], extra=tags)
                return None, exitcode
        
            drawing = ImageDraw.Draw(debugImage)
        
        ###    
        # Detect bcFilters
        ###
        PsycoInit(psyco)
        bands = splitToBands(image)
        log.info("Split the image into bands", extra=tags)
        if bands is None:
            log.error('Could not find the bcfilter in the image', extra=tags)
            return None, ExitCode.UnknownError
    
        bcFiltersPerBand = []
        
        if imageLogLevel:
            bandIndex = 0
        
        
        for band in bands:
            bcFilters, exitcode = detectBCFilter(band, tags, logging.DEBUG)
            
            if exitcode is not ExitCode.Success:
                log.error('Could not detect filters in the Image ' + ExitCode.toString[exitcode], extra=tags)
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
        
        ###
        # Save the debug image
        ###
        if imageLogLevel:
            if isinstance(debugImagefile, str):
                debugImage.save(debugImagefile)
            else:
                try:
                    debugImage.save(debugImagefile, 'png')
                    debugImagefile.close()
                except Exception, err:
                    log.error('Error %s' % str(err), extra=tags)
                
                    return None, ExitCode.UnknownError        
            
        if imageLogLevel > 1:
            if isinstance(debugImagefile, str):
                debugImage.show()
        
        sampledRGB = bestBcFilter.sample(image, bestBcFilter.radius/MainConstants.samplingfactor) 
        
        return (sampledRGB, qr.aux, gradient), exitcode

    except Exception, err:
        log.error('Error %s' % str(err), extra=tags)
        return None, ExitCode.UnknownError