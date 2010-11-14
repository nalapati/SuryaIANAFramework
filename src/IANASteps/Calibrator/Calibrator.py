'''
The CalibratorFilter Module contains functionality to process the 
calibrator area in the image and extracts the:

 Color values from the ColorBar in the calibrator,
 Grayscale values from the GrayBar in the calibrator,
 Black value from the BlackBar in the calibrator.
 

Created on Oct 10, 2010

@author: surya
'''

import logging

from GrayBar import GrayBar
from ColorBar import ColorBar
from Logging.Logger import getLog
from IANASettings.Settings import ExitCode, CalibratorConstants

log = getLog("Calibrator")
log.setLevel(logging.ERROR)

def getColorBars(qr, image, parenttags=None, level=logging.ERROR):
    ''' Extracts the ColorBars from the Image and represents them
        as ColorBar objects.
    
    Keyword Arguments:
    qr    -- QRDetector.QR object
    image -- a PIL.Image object
    parenttags -- tag string of the calling function
    level -- the logging level
    
    Returns
    A list of Calibrator.ColorBar objects representing the three colorbars.
    '''
    
    # Set the logging level
    log.setLevel(level)
    tags = parenttags + " COLORBAR"
    
    log.info('Running ColorBar Detection', extra=tags)
    
    downL = qr.bottomLeft - qr.topLeft
    downR = qr.bottomRight - qr.topRight

    colorBars = []
    
    for colorBarOffset in CalibratorConstants.ColorBarOffsets:
        left = colorBarOffset * downL + qr.bottomLeft
        right = colorBarOffset * downR + qr.bottomRight

        #TODO: raise PointOutofBoundsError() in the block below
        try: 
            colorBars.append(ColorBar(left, right))
        except Exception, err:
            log.error('Error %s' % str(err), extra=tags)
            return None, ExitCode.ColorBarDetectionError
        
    log.info('Done Running ColorBar Detection', extra=tags)
    return colorBars, ExitCode.Success
        
def getGrayBars(qr, image, parenttags=None, level=logging.ERROR):
    ''' Extracts the GrayBars from the Image and represents them
        as GrayBar objects.
    
    Keyword Arguments:
    qr    -- QRDetector.QR object
    image -- a PIL.Image object
    parenttags -- tag string of the calling function
    level -- the logging level
    
    Returns
    A list of Calibrator.GrayBar objects.
    '''
    
    # Set the logging level
    log.setLevel(level)
    tags = parenttags + " GRAYBAR"
    
    log.info('Running GrayBar Detection', extra=tags)
    
    leftT = qr.topLeft - qr.topRight
    leftB = qr.bottomLeft - qr.bottomRight
        
    grayBars = []
    # For each coloumn of the GrayBars (there are two GrayBar columns to the left of the QR Code)
    for grayBarColumnOffset in CalibratorConstants.GrayBarColumnOffsets[:2]:
            top = grayBarColumnOffset * leftT + qr.topLeft
            bottom = grayBarColumnOffset * leftB + qr.bottomLeft
            down = (bottom - top) * CalibratorConstants.LastGrayBarOffset
            bottom = top + down

            blockOffset = (bottom - top) / 5
            block = top

            # For each GrayBar in the given GrayBarColumn
            for i in range(6):
                
                try:
                    grayBars.append(GrayBar(block))
                except Exception, err:
                    log.error('Error %s' % str(err), extra=tags)
                    return None, ExitCode.GrayBarDetectionError

                block += blockOffset
    log.info('grayBars: ', extra=tags)
    for grayBar in grayBars:
        log.info(grayBar.__str__(), extra=tags)
        
    grayBars.reverse()
    log.info('Done Running GrayBar Detection', extra=tags)
    return grayBars, ExitCode.Success

def getBlackBar(qr, image, parenttags=None, level=logging.ERROR):
    ''' Extracts the BlackBar from the Image and represents it
        as a ColorBar object.
    
    Keyword Arguments:
    qr    -- QRDetector.QR object
    image -- a PIL.Image object
    parenttags -- tag string of the parent function
    level -- the logging level
    
    Returns
    A Calibrator.ColorBar object representing the BlackBar.
    '''
    
    # Set the logging level
    log.setLevel(level)
    tags = parenttags + " BLACKBAR"
    
    log.info('Running BlackBar Detection', extra=tags)
                 
    leftT = qr.topLeft - qr.topRight
    leftB = qr.bottomLeft - qr.bottomRight
    
    top = CalibratorConstants.GrayBarColumnOffsets[2] * leftT + qr.topLeft
    bottom = CalibratorConstants.GrayBarColumnOffsets[2] * leftB + qr.bottomLeft
    
    try:
        blackBar = ColorBar(top, bottom)
            
    except Exception, err:
        log.error('Error %s' % str(err), extra=tags)
        return None, ExitCode.BlackBarDetectionError

    log.info('Done Running BlackBar Detection', extra=tags)
    return blackBar, ExitCode.Success
