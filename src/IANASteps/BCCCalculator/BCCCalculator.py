'''
Created on Oct 12, 2010

@author: surya
'''

import pylab
import logging

from BCCResult import BCCResult
from Logging.Logger import getLog
from IANAUtil.Rating import Rating
from Scientific.Functions.LeastSquares import leastSquaresFit
from IANASettings.Settings import ExitCode, BCCCalculatorConstants

log = getLog("BCCCalculator")
log.setLevel(logging.ERROR)

def computeBCC(bcFilterRadius, bcLoading, exposedTime, flowRate):
    ''' Computes the black carbon concentration(ug/cm^3) according to the formula
        
        BCC(ug/L) = (bcFilterArea(cm^2) * bcLoading(ug/cm^2)) / (exposedTime(min) * flowRate(L/min))
        
        NOTE : since cm^3 = L/1000
        
        BCC(ug/cm^3) = BCC(ug/L) * 1000
        
        Keyword arguments:
        bcFilterArea  -- The Radius of the filter in cm
        bcLoading     -- The black carbin loading value in ug/cm^2
        exposedTime   -- The exposure time of the bcfilter in mins
        flowRate      -- The flowrate of the pump in L/min
        
        Returns:
        Black Carbon Concentration(ug/cm^3)
    '''
    
    return (BCCCalculatorConstants.Pi * bcFilterRadius**2 * bcLoading * 1000) / (exposedTime * flowRate)  

def rateFilter(sampledRGB, filterRadius, exposedTime, flowRate, bcgradient, gradient, parenttags=None, level=logging.ERROR):
    ''' Computes the BCArea and BCVolume subject to the params
    
    Keyword arguments:
    sampledRGB  -- The sampled RGB values of the BCFilter
    exposedTime -- The duration for which the filter was exposed to air from the pump 
    flowRate    -- The flow rate of the pump
    bcgradient  -- The calibration value obtained from the database
    gradient    -- The values corresponding to the color values from GrayBar objects
    parenttags  -- The tag string of the calling function
    level       -- The logging level
    
    Returns:
    BCCResult object
    '''
    
    # Set the logging level
    log.setLevel(level)
    tags = parenttags + " BCCCOMPUTATION"
        
    try:
        fitParam = BCCCalculatorConstants.FittingParameters
        stop     = BCCCalculatorConstants.StoppingLimit
        expmod   = Rating.expmod
        rsquared = Rating.rsquared
    
        # The results of this computation
        bccResult = BCCResult()
    
        # separate by color leaving off the black and white
        gradientRed, gradientGreen, gradientBlue = zip(*gradient[1:-1])
    
        # fit the gradient
        bccResult.fitRed, chi = leastSquaresFit(expmod, fitParam, zip(gradientRed, bcgradient), stopping_limit=stop)
        bccResult.fitGreen, chi = leastSquaresFit(expmod, fitParam, zip(gradientGreen, bcgradient), stopping_limit=stop)
        bccResult.fitBlue, chi = leastSquaresFit(expmod, fitParam, zip(gradientBlue, bcgradient), stopping_limit=stop)
    
        # compute the rsquared value
        bccResult.rSquaredRed = rsquared(expmod, bccResult.fitRed, pylab.array(gradientRed), bcgradient)
        bccResult.rSquaredGreen = rsquared(expmod, bccResult.fitGreen, pylab.array(gradientRed), bcgradient)
        bccResult.rSquaredBlue = rsquared(expmod, bccResult.fitBlue, pylab.array(gradientRed), bcgradient)
    
        red, green, blue = bccResult.sample = sampledRGB
        
        bccResult.BCAreaRed = expmod(bccResult.fitRed, red)
        bccResult.BCAreaGreen = expmod(bccResult.fitGreen, green)
        bccResult.BCAreaBlue = expmod(bccResult.fitBlue, blue)
    
        log.info('Computing Black Carbon Concentration: ', extra=tags)
        bccResult.BCVolRed   = computeBCC(filterRadius, bccResult.BCAreaRed, exposedTime ,flowRate)
        bccResult.BCVolGreen = computeBCC(filterRadius, bccResult.BCAreaGreen, exposedTime, flowRate)
        bccResult.BCVolBlue = computeBCC(filterRadius, bccResult.BCAreaBlue, exposedTime, flowRate)
    
        log.info('Black carbon per cm^2: %s', ([bccResult.BCAreaRed, bccResult.BCAreaGreen, bccResult.BCAreaBlue],), extra=tags)
        log.info('Black carbon per cm^3: %s', ([bccResult.BCVolRed, bccResult.BCVolGreen, bccResult.BCVolBlue],), extra=tags)
        
        log.info('Done Computing Black Carbon Concentration: ', extra=tags)
        return bccResult, ExitCode.Success
    
    except Exception, err:
        log.error('Error %s' % str(err), extra=tags)
        return None, ExitCode.BCCComputationError