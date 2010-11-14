'''
Created on Oct 10, 2010

@author: surya
'''


from PIL.ImageStat import Stat
from IANASteps.Geometry.Point import Point
from IANASteps.Geometry.Rectangle import Rectangle
from IANASettings.Settings import CalibratorConstants

class GrayBar:
    '''
    This class represents a GrayBar on the Stage, and includes functionality to get
    a gradient involving gray-scale values on the GrayBar.
    '''
    
    def __init__(self, point):
        ''' Constructor
        
        Sets the logging level, and represents the GrayBar in terms
        of a small Rectangle relative the point param.
        
        Keyword Arguments:
        point  -- A point in the GrayBar
        '''
        
        #TODO: push this to settings
        self.boxSize = Point(CalibratorConstants.BoxSize,CalibratorConstants.BoxSize)
        
        # LeftBox - a nxn box on the left side of the ColorBar
        self.box = Rectangle([int(x) for x in point - self.boxSize] + [int(x) for x in point + self.boxSize]) 
    
    def __str__(self):
        ''' Returns a Human-Readable representation of the class
        '''
        return 'GrayBar: [ ' + self.box.__str__() + ' ]' 
    
    def sample(self, image):
        ''' Samples the GrayBar
        
        Keyword Arguments:
        image -- a PIL.Image object
        
        Returns:
        The RGB value of the GrayBar
        '''        
        
        color = Stat(image.crop(self.box.coordinates)).mean
        return color

    def draw(self, drawing, color):
        '''
        '''

        self.box.draw(drawing, color)