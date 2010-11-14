'''
Created on Oct 13, 2010

@author: surya
'''

import logging

from PIL.Image import QUAD, BICUBIC
from Logging.Logger import getLog
from IANASettings.Settings import ExitCode

log = getLog("ImageTransformer")
log.setLevel(logging.ERROR)

def transform(image, stage, parenttags=None, level=logging.ERROR):
    ''' Performs the skew correction in the image.
        
    Keyword Arguments:
    image -- PIL.Image instance
    stage -- Absolute coordinates of the stage
    parentttags -- tag string of the calling function
    
    Returns:
    PIL.Image, The cropped image containing the stage.    
    '''
    
    # Set the logging level
    log.setLevel(level)
    tags = parenttags + " TRANSFORM"
    
    height = ((stage.topRight - stage.bottomRight).distance()
                + (stage.topLeft - stage.bottomLeft).distance()) / 2
    width = ((stage.topRight - stage.topLeft).distance()
                + (stage.bottomRight - stage.bottomLeft).distance()) / 2

    log.info('Running Image Transformation - Skew Correction', extra=tags)

    try:
        img = image.transform((int(width), int(height)), QUAD,
                                (stage.topLeft[0], stage.topLeft[1], stage.bottomLeft[0], stage.bottomLeft[1],
                                 stage.bottomRight[0], stage.bottomRight[1], stage.topRight[0], stage.topRight[1]),
                                 BICUBIC)
        
    except Exception, err:
        log.error('Error %s' % str(err), extra=tags)
        return None, ExitCode.ImageTransformationError
    
    return img, ExitCode.Success