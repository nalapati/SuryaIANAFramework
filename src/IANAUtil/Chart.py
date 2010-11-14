'''
Created on Oct 12, 2010

@author: surya
'''

import pylab

from IANAUtil.Rating import Rating

def plotChart(filterRadius, exposedTime, flowRate, bcgradient, gradient, bccResult, chartName):
    ''' Plot the results onto a Chart
    '''
        
    BCGradient = pylab.array(bcgradient)

    gradientRed, gradientGreen, gradientBlue = zip(*gradient[1:-1])
    redSample, greenSample, blueSample = bccResult.sample


    fig = pylab.figure()

    # plot the RGB vals of the test strip
    pylab.plot(gradientRed, BCGradient, 'rx',
               gradientGreen, BCGradient, 'gx',
               gradientBlue, BCGradient, 'bx')

    plotrange = pylab.array(range(50, 220))

    # plot the lines fit to the RGB vals of the test strip
    pylab.plot(plotrange, Rating.expmod(bccResult.fitRed, plotrange), 'r-',
               plotrange, Rating.expmod(bccResult.fitGreen, plotrange), 'g-',
               plotrange, Rating.expmod(bccResult.fitBlue, plotrange), 'b-')

    # plot the sample point
    red, green, blue = bccResult.sample
    pylab.plot(red, -1, 'rs', green, -1, 'gs', blue, -1, 'bs')

    pylab.plot(redSample, bccResult.BCAreaRed, 'ks', greenSample, bccResult.BCAreaGreen, 'ks',
               blueSample, bccResult.BCAreaBlue, 'ks')

    message = ("$\\mu g/m^3$ (*'s):\n"
               'R {red:0.9f} ,\n'
               'G {green:0.9f} ,\n'
               'B {blue:0.9f}' ).format(red=bccResult.BCVolRed, green=bccResult.BCVolGreen, blue=bccResult.BCVolBlue) #divide by 1000 cm^3 -> m^3
    pylab.text(120, 12, message)


    # legend with the r^2 values
    #pylab.legend(('R %0.3f' % RSquared.red, 'G %0.3f' % RSquared.green, 'B %0.3f' % RSquared.blue))
    pylab.xlabel('RGB')
    pylab.xlim([0, 255])
    pylab.ylim([-2, 28])
    pylab.ylabel(r'$\mu g/cm^2$')
    
    bcstrip_float = [float(s.strip()) for s in str(BCGradient).strip()[1:-1].split()] # the str(BCBCGradient) is "[ x.xx ... ]"
    bcstrip_short = ""
    for f in bcstrip_float:
        bcstrip_short += "{val:0.2f} ".format(val=f)
    
    pylab.title('ExposedTime: {0}, FlowRate:{1} , FilterRadius:{2} \n BCStrip: {3}'
                .format(str(exposedTime), str(flowRate),
                        str(filterRadius), bcstrip_short))

    fig.savefig(chartName, format="PNG")
    pylab.close(fig)    
