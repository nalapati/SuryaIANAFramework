'''
Created on Nov 11, 2010

@author: surya
'''

import logging

from mongoengine import *
from mongoengine.connection import _get_db
from gridfs import *
from DANA.DANAFramework import DANAFramework
from Logging.Logger import getLog
from IANASettings.Settings import ExitCode
from bson.objectid import ObjectId
from BCCResultComputation import bccResultComputation
from FeatureExtractor import featureExtractor
from Collections.SuryaProcessingList import *
from Collections.SuryaDeploymentData import *
from Collections.SuryaCalibrationData import *
from Collections.SuryaProcessResult import *
from DANAExceptions.CalibrationError import CalibrationError
from DANAExceptions.PreProcessingError import PreProcessingError
from DANAExceptions import ResultComputationError
from DANAExceptions.ResultSavingError import ResultSavingError

class PreProcessingResult:
    """ Results after the Image has been preprocessed.
    """
    
    def __init__(self, features, result):
        """ Constructor
        
            Keyword Arguments:
            features -- The features extracted from the Image
            result   -- The SuryaImagePreProcessingResult 
                        Embedded Document
        """
        self.features = features
        self.result = result
    
class DanaResult:
    """ Results after the computation of Black Carbon Concentration (BCVol)
    """
    
    def __init__(self, bccResult, exitcode, result):
        """ Constructor
        
            Keyword Arguments:
            bccResult -- The Collections.SuryaProcessResult.BccResult object
            exitcode  -- The result on computation of a the BCVol
            result    -- A partially constructed SuryaImageAnalysisResult object
        """
        self.bccResult = bccResult
        self.exitcode  = exitcode
        self.result    = result # Partially constructed SuryaImageAnalysisResult object with the ChartImage Field set
    

class IANAFramework(DANAFramework):
    """                 The Image ANAlysis Framework Implementation
                        -------------------------------------------
        This class implementss functionality to analyze Uploaded Images to compute the
        black carbon concentration(BCVol) in those images.
    """
    
    log = getLog("IANAFramework")
    
    def __init__(self, level=logging.DEBUG):
        """ Constructor
        
            Keyword Arguments:
            level -- The logging level
        """
        
        self.log.setLevel(level)
        self.ianatags = self.danatags + " IANA "
        self.fs = GridFS(_get_db())
    
    def getDataItems(self):
        """ Step 0: 
            Refer DANAFramework.getDataItems() for documentation
        """
        
        return SuryaProcessingList.objects
    
    def getItemName(self, dataItem):
        """ Refer DanaFramework.getItemName() for documentation
        """
        return dataItem.processEntity.file.name
        
    def isValid(self, dataItem):
        """ Step 1:
            Refer DANAFramework.isValid() for documentation
        """
        return dataItem.processEntity.validFlag
    
    def preProcessDataItem(self, itemname, dataItem, epoch):
        """ Step 2:
            Refer DANAFramework.preProcessDataItem() for documentation
        """
        
        # Set the logging tags
        tags = self.ianatags + itemname + " PPROC"
        
        # Create a new pre-processin result object
        result = SuryaImagePreProcessingResult()
        
        # Fetch the image
        imagefile = dataItem.processEntity.file
        
        # Fetch the debugImage
        debugImagename = (itemname + ".debug." + str(epoch) + ".png")
        
        # Check if the image already exists, delete it
        if self.fs.exists(filename=debugImagename):
            debugImage = self.fs.get_last_version(debugImagename)
            self.fs.delete(debugImage.__getattr__("_id"))
        
        result.debugImage.new_file(filename=debugImagename, content_type='image/png')
        
        self.log.info("Running PPROC", extra=tags)
        
        # Get the Features from the image
        features, exitcode = featureExtractor(imagefile, 1, result.debugImage, tags, logging.DEBUG)
        
        # Set the result status
        result.status = ExitCode.toString[exitcode]
        result.isEmailed = False
        dataItem.preProcessResultList.append(result)
        
        if exitcode is not ExitCode.Success:
            raise PreProcessingError(ExitCode.toString[exitcode], result)
        
        self.log.info("Done Running PPROC", extra=tags)
        return PreProcessingResult(features, result)
        
        
    def getCalibrationConfigurations(self, itemname, dataItem, preProcessingResult):
        """ Step 3:
            Refer DANAFramework.getCalibrationConfigurations for documentation
        """
        try:
            
            # Set the logging tags
            tags = self.ianatags + itemname + " CALIB"
            
            self.log.info("Running CALIB", extra=tags)
            calibrationIdList = []
            # Fetch a list of SuryaCalibrationData calibrationIds that are currently associated with 
            # the item
            for configuration in dataItem.configurations:
                calibrationIdList.append(configuration.calibrationData.calibrationId)
            
            # Check the Deployment table to see if there are any new configurations for this item
            newCalibrationDataList = []
            for deploymentData in SuryaDeploymentData.objects(deploymentId=dataItem.processEntity.deploymentId):
                # For the current deploymentDataRecord check if any calibration configurations have been activated
                if dataItem.processEntity.recordDatetime >= deploymentData.activateDatetime:
                    newCalibrationDataList.append(deploymentData.calibrationId)
            
            # For all calibrations obtained from the deployment table check if they
            # are already associated with the item, if not append to the list of known 
            # calibration configurations
            for newCalibrationData in newCalibrationDataList:
                if newCalibrationData.calibrationId not in calibrationIdList:
                    dataItem.configurations.append(SuryaConfiguration(calibrationData=newCalibrationData,
                                                                      resultList=[]))
            
            self.log.info("Done Running CALIB", extra=tags)        
            return dataItem.configurations
        
        except Exception, err:
            raise CalibrationError(err)
    
    def getCurrentEpoch(self, dataItem):
        """ Refer DANAFramework.getCurrentEpoch for documentation
        """
    
        return (dataItem.epoch + 1)
    
    def isProcessed(self, dataItem):
        """ Refer DANAFramework.isProcessed for documentation
        """
        
        return dataItem.processedFlag
    
    def computeDANAResult(self, itemname, dataItem, epoch, calibrationConfiguration, preProcessingResult):
        """ Refer DANAFramework.computeDANAResult for documentation
        """
        
        try:
            # Set the logging tags
            tags = self.ianatags + itemname + " COMPU"
            
            self.log.info("Running COMPU", extra=tags)
            
            result = SuryaImageAnalysisResult()
            chartFileName = (itemname + ".chart." + str(epoch) + ".png")
             
            # Check if the image already exists if not create a new file
            if self.fs.exists(filename=chartFileName):
                chartImg = self.fs.get_last_version(chartFileName)
                self.fs.delete(chartImg.__getattr__("_id"))
                
            result.chartImage.new_file(filename=chartFileName, content_type='image/png')
                
            chartImage = result.chartImage
            sampledRGB, aux, gradient = preProcessingResult.features
            
            calibrationData = calibrationConfiguration.calibrationData
            
            filterRadius = calibrationData.filterRadius
            exposedTime = calibrationData.exposedTime
            airFlowRate = calibrationData.airFlowRate
            bcGradient = calibrationData.bcStrips
            
            
            # Compute the BCCResult
            bccResult, exitcode = bccResultComputation(sampledRGB, filterRadius, exposedTime, airFlowRate, bcGradient, gradient, chartImage, tags, logging.DEBUG)
            chartImage.close()
            bccResult_ = BccResult(fitRed         = bccResult.fitRed, 
                                   fitGreen       = bccResult.fitGreen,
                                   fitBlue        = bccResult.fitBlue,
                                   rSquaredRed    = bccResult.rSquaredRed,
                                   rSquaredGreen  = bccResult.rSquaredGreen,
                                   rSquaredBlue   = bccResult.rSquaredBlue,
                                   sample         = bccResult.sample,
                                   BCAreaRed      = bccResult.BCAreaRed,
                                   BCAreaGreen    = bccResult.BCAreaGreen,
                                   BCAreaBlue     = bccResult.BCAreaBlue,
                                   BCVolRed       = bccResult.BCVolRed,
                                   BCVolGreen     = bccResult.BCVolGreen,
                                   BCVolBlue      = bccResult.BCVolBlue)
            result.result = bccResult_
            result.status = ExitCode.toString[exitcode]
            result.isEmailed = False
            result.epoch = epoch
            calibrationConfiguration.resultList.append(result)
            
            self.log.info("Done Running COMPU", extra=tags)
            
        except Exception, err:
            raise ResultComputationError(err)
    
    def saveDANAResult(self, itemname, dataItem, epoch):
        """ Result DANAFramework.saveDANAResult fro documentation
        """
    
        try:
            # Set the logging tags
            tags = self.ianatags + itemname + " SAVIN"
            
            self.log.info("Running SAVIN", extra=tags)
            
            dataItem.processEntity.validFlag = True
            dataItem.processEntity.save()
            dataItem.processedFlag = True 
            dataItem.epoch = epoch
            dataItem.save()
            
            self.log.info("Done Running SAVIN", extra=tags)
            
        except Exception, err:
            raise ResultSavingError(err)
    
    def onError(self, itemname, dataItem, epoch, err, phase):
        """ Refer DANAFramework.onError for documentation
        """
        
        # Set the logging tags
        tags = self.ianatags + itemname + " " + phase
        
        self.log.error(phase + " Failed, cause: "+ str(err), extra=tags)
        
        
        dataItem.processEntity.validFlag = False
        dataItem.processEntity.invalidReason = phase + " Failed"
        dataItem.processEntity.save()
        
        if phase == "SAVIN":
            return
        
        dataItem.processedFlag = False
        dataItem.epoch = epoch
        dataItem.save()
        
if __name__ == "__main__":
    connect("SuryaDB")
    iana = IANAFramework(logging.DEBUG)
    iana.run("IANAFramework.pid", "IANAFramework", 10, False)
    