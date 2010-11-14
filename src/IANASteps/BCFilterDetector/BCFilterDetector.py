'''
The CircleFilter Module uses the Hough Transform to detect circles in a given image

Created on Oct 5, 2010

@author: surya
'''

import opencv
import logging

from BCFilter import BCFilter
from Logging.Logger import getLog
from IANASettings.Settings import BCFilterConstants
from IANASettings.Settings import ExitCode

log = getLog("BCFilterDetector")
log.setLevel(logging.ERROR)

def splitToBands(image):
    ''' Split the given image into separate bands
    
    Keyword Arguments:
    image -- a PIL.Image object
    
    Returns:
    if the Image is RGB bands corresponding to R,G,B bands of the image
    if the Image is GrayScale then a single band containing the iage itself  
    '''

    if image.mode == 'L':
        bands = (image,)
    else:
        if image.mode != 'RGB':
            image = image.convert('RGB')

        bands = image.split()
        
    return bands

def detectBCFilter(image, parenttags=None, level=logging.ERROR):
    ''' Detects circles in an image
    
    Keyword Arguments:
    image -- Image instance
    level -- The logging level
    parenttags -- tag string of the calling function
    
    Returns:
    list of CirclesFilter_.BCFilter objects
    '''
    
    # Sets the logging level
    log.setLevel(level)
    tags = parenttags + " BCFILTER"
        
    try:
        log.info('Running BCFilter Detection', extra=tags)
        circles = houghTransform(image, tags)

        width, height = image.size

        # if more than about half the filter spot would
        # be cut off reject the match
        bcFilters = [BCFilter(*cir) for cir in circles
                            if 0 <= cir[0] <= width and 0 <= cir[1] <= height]

        log.info('Done Running BCFilter Detection', extra=tags)
        return bcFilters, ExitCode.Success
    
    except Exception, err:
        log.error('Error %s' % str(err))        
        return None, ExitCode.FilterDetectionError

def houghTransform(image, parenttags=None):
    """ Runs the hough circle detection against the image
    
    Keyword Arguments:
    image -- Image instance
    parenttags -- tag string of the calling function
    
    Returns:
    a list of CirclesFilter_.Circle objects
    """

    cvImage = opencv.PIL2Ipl(image)
    
    # smoothen the Image
    # opencv.cvSmooth( cvImage, cvImage, opencv.CV_GAUSSIAN, BCFilterConstants.masksize, BCFilterConstants.masksize);
    
    storage = opencv.cvCreateMemStorage(0)

    # print the settings that were used to detect circles
    log.info(BCFilterConstants.str(), extra=parenttags)
    
    circles = opencv.cvHoughCircles(cvImage, 
                                    storage,
                                    opencv.CV_HOUGH_GRADIENT,
                                    BCFilterConstants.dp, 
                                    BCFilterConstants.minimumDistance,
                                    BCFilterConstants.highThreshold, 
                                    BCFilterConstants.accumulatorThreshold,
                                    BCFilterConstants.minimumRadius, 
                                    BCFilterConstants.maximumRadius)

    # unpack the circle into a generic tuple
    # !!something wrong with circle.__getitem__ (don't use "tuple(circle)")
    if BCFilterConstants.maximumRadius != 0:
        # neither minimumRadius nor maximumRadius seem to be an absolue
        circles = [(float(circle[0]), float(circle[1]), float(circle[2]))
                        for circle in circles
                        if BCFilterConstants.minimumRadius <= circle[2] <= BCFilterConstants.maximumRadius]
    else:
        circles = [(float(circle[0]), float(circle[1]), float(circle[2]))
                        for circle in circles]

    log.debug('Found circles: %s', circles, extra=parenttags)

    return circles


def select(bands):
    """ Select the best circles based on the color bands
    
    Keyword Arguments:
    bands  -- Circle detections from bands: [red, green, blue]
    
    Returns:
    the selected CirclesFilter_.Circle object
    """

    # Check the circles detected in the red band. 
    if len(bands[0]) > 0:
        return bands[0]
    elif len(bands[2]) > 0:
        return bands[2]
    elif len(bands[1]) > 0:
        return bands[1]
    else: 
        return None

##
# Initializes Psyco
def PsycoInit(psyco):
    # !!Will cause segfault without this
    psyco.cannotcompile(houghTransform)
    psyco.cannotcompile(opencv.cvHoughCircles)