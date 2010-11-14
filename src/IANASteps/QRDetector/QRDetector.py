'''
The QRFilter Module contains functionality to extract data from a 
QR code(aux_id), and the co-ordinates of the QR code itself.

It essentially takes a filename (absolute path to the input image),
uses Popen to spawn a new sub-process to execute:

     java -jar pathToFindQRCode/FindQRCode.jar [options] filename
   
And parses out a the aux_id and a set of QR coordinates from the output pipe.


Created on Oct 8, 2010

@author: surya
'''

import os
import logging

from subprocess import PIPE, Popen
from Logging.Logger import getLog
from IANASteps.Geometry.Point import Point
from QR import QR
from IANASettings.Settings import ExitCode

    
log = getLog("QRFilter")
log.setLevel(logging.ERROR)    
        
    
def detectQR(file_, parenttags=None, level=logging.ERROR):
    '''Call FindQRCode.jar to see whether QR code is correct.

    Keyword arguments:
    file_      -- The full file name toward the image file to be processed.
    parenttags -- The tag string of the calling method.
    level      -- The logging level.

    Returns:
    QR       -- an object of QRDetector.QR type.
    exitcode -- exit code returning from FindQRCode.jar.

    '''
    
    try:
        # Set the logging level 
        log.setLevel(level)
        tags = parenttags + " QR"
        
        log.info("Running QR Detection", extra=tags)
        
        if isinstance(file_, str):
            qrCommand = ['java', '-jar', os.path.join(os.path.dirname(__file__), 'FindQRCode.jar'),
                             'http://www.projectsurya.org/', file_]
                
                
            QRFinder = Popen(qrCommand, stdout=PIPE, close_fds=True)
            QRFinder_out = QRFinder.stdout
        else:
            qrCommand = ['java', '-jar', os.path.join(os.path.dirname(__file__), 'FindQRCode.jar'),
                             'http://www.projectsurya.org/']
                
            QRFinder = Popen(qrCommand, stdout=PIPE, stdin=PIPE, close_fds=True)
            QRFinder_out = QRFinder.communicate(input=file_.read())[0].splitlines()
        
        exitcode = QRFinder.wait()
        #Extracting QR code
        points = []
            
        qrLine = None
        for line in QRFinder_out:
            if qrLine is None:
                qrLine = line[:-1]
                log.info("Finding QRCode: " + str(qrLine), extra=tags)
                continue
            x, y = line[:-1].split(',')
            points.append(Point((float(x), float(y))))
            log.info("QR point (x, y): {0:s}, {1:s}".format(x, y), extra=tags)
            # eg. Points: [(653.0, 412.0), (653.5, 282.5), (782.5, 283.5), (763.5, 395.5)]
    
        QRFinder.stdout.close()
    
        if not points:
            log.error("Cannot extract QR info, check FindQRCode.jar, " + 
                      "exitcode of FindQRCode.jar is " + str(exitcode), extra=tags)
            return None, ExitCode.QRDetectionError
                
        aux = ""
        if qrLine:
            aux = str(qrLine)
            try:
                aux = aux[aux.rindex("v=")+2:]
            except Exception, err:
                log.error('Error %s' % str(err), extra=tags)
                
        log.info("QR Aux info. (aux_id) " + aux, extra=tags)
            
        log.info("Done Running QR Detection", extra=tags)
        
        return QR(aux, points), exitcode
    except Exception, err:
        log.error("QR Detection Failed %s", str(err), extra=tags)
        return None, ExitCode.QRDetectionError