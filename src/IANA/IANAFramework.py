'''
Created on Nov 11, 2010

@author: surya
'''

import json
import logging
import datetime

from gridfs import *
from mongoengine import *
from Logging.Logger import getLog
from bson.objectid import ObjectId
from IANASettings.Settings import ExitCode
from mongoengine.connection import _get_db
from DANA.DANAFramework import DANAFramework
from FeatureExtractor import featureExtractor
from Collections.SuryaProcessResult import *
from Collections.SuryaProcessingList import *
from Collections.SuryaDeploymentData import *
from Collections.SuryaCalibrationData import *
from BCCResultComputation import bccResultComputation
from DANAExceptions.ResultSavingError import ResultSavingError
from DANAExceptions.PreProcessingError import PreProcessingError
from DANAExceptions.PprocCalibrationError import PprocCalibrationError
from DANAExceptions.CompuCalibrationError import CompuCalibrationError
from DANAExceptions.ResultComputationError import ResultComputationError

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
        """ Refer DANAFramework.getDataItems() for documentation
        """
        
        return SuryaIANAProcessingList.objects(processedFlag=False)
    
    def getItemName(self, dataItem):
        """ Refer DanaFramework.getItemName() for documentation
        """
        return dataItem.processEntity.file.name
        
    def isValid(self, dataItem):
        """ Refer DANAFramework.isValid() for documentation
        """
        return dataItem.processEntity.validFlag
    
    def getPreProcessingConfiguration(self, itemname, dataItem):
        """ Refer DANAFramework.getPreProcessingConfiguration for documentation
        """
        try:
            # Set the logging tags
            tags = self.ianatags + itemname + " PPROCCALIB"
            
            self.log.info("Done Running PPROCCALIB", extra=tags)

            # here we actually fetch and store the updated preProcessing config
        except Exception, err:
            raise PprocCalibrationError(err)
    
    def preProcessDataItem(self, itemname, dataItem):
        """ Refer DANAFramework.preProcessDataItem() for documentation
        """
        try:
            # Set the logging tags
            tags = self.ianatags + itemname + " PPROC"
            
            self.log.info("Running PPROC", extra=tags)
            
            # Create a new pre-processin result object
            result = SuryaImagePreProcessingResult()

            # Fetch the image
            imagefile = dataItem.processEntity.file
            
            # Fetch the debugImage
            debugImagename = (itemname + ".debug." + str(dataItem.preProcessingConfiguration.calibrationId) + ".png")
            
            # Check if the image already exists, delete it
            if self.fs.exists(filename=debugImagename):
                debugImage = self.fs.get_last_version(debugImagename)
                self.fs.delete(debugImage.__getattr__("_id"))
             
            result.debugImage.new_file(filename=debugImagename, content_type='image/png')
        
            # Get the Features from the image
            features, exitcode = featureExtractor(imagefile, 1, result.debugImage, dataItem.preProcessingConfiguration, tags, logging.DEBUG)
    
            # Set the result status
            result.status = ExitCode.toString[exitcode]
            
            if exitcode is not ExitCode.Success:
                result.validFlag = False
                raise PreProcessingError(ExitCode.toString[exitcode], result, None)
                    
            result.validFlag = True
            result.sampled = features[0]
            
            self.log.info("Done Running PPROC", extra=tags)
            return PreProcessingResult(features, result)
        except Exception, err:
            if isinstance(err, PreProcessingError):
                raise err
            result = SuryaImagePreProcessingResult()
            result.item                       = dataItem.processEntity
            result.preProcessingConfiguration = dataItem.preProcessingConfiguration
            result.validFlag                  = False
            result.status                     = str(err)
            raise PreProcessingError(None, result, None)
             
            
    def getComputationConfiguration(self, itemname, dataItem, preProcessingResult):
        """ Refer DANAFramework.getComputationConfiguration for documentation
        """
            
        try:
            # Set the logging tags
            tags = self.ianatags + itemname + " COMPUCALIB"
            
            self.log.info("Running COMPUCALIB", extra=tags)
            if dataItem.overrideFlag:
                # TODO: 
                # a) from pre-processing result get aux_id : the aux_id, dataItem.deploymentId as the key
                #    fetch an air_flow_rate from the pumps table.
                # b) from the misc field fetch any calibration data.
                # combining a) and b) over the defaut calibration data, get and add a new calibration entry
                # to the calibration data table.
                # and use this new calibration entry for computing BCVol
                #
                try:
                    misc = dataItem.processEntity.misc
                    misc_dict = json.loads(misc)
                except ValueError as ve:
                    self.log.error('[ Sanity ] The misc input is not a json syntax string. Store it as { "rawstring": (...input...)} . The orignial Input:' + str(misc)+ "Reason:" + str(ve), extra=tags)
                    
                # Get the exposedtime, flowrate, filterradius params
                isnew = False
                if misc_dict.has_key("exposedtime"):
                    exposedtime = float(misc_dict['exposedtime'])
                    isnew = True
                else:
                    exposedtime = dataItem.computationConfiguration.exposedTime
                if misc_dict.has_key("filterradius"):
                    filterradius = float(misc_dict['filterradius'])
                    isnew = True
                else:
                    filterradius = dataItem.computationConfiguration.filterRadius
                if misc_dict.has_key("flowrate"):
                    flowrate = float(misc_dict['flowrate'])
                    isnew = True
                else:
                    flowrate = dataItem.computationConfiguration.airFlowRate
                bcarea = 3.14 * filterradius * filterradius # NOTE: unused to remove
                
                if isnew:
                    calibId = 0
                    calibId = SuryaCalibrationData.objects.order_by('-calibrationId').first().calibrationId #Todo change this
                    if calibId > 0:
                        calibId = calibId + 1
                        SuryaImageAnalysisCalibrationData(calibrationId=calibId,
                                                          exposedTime=exposedtime,
                                                          filterRadius=filterradius,
                                                          airFlowRate=flowrate,
                                                          bcArea=bcarea).save()
                                             
                        dataItem.computationConfiguration = SuryaCalibrationData.objects.order_by('-calibrationId').first() 
                    # done overriding
                
            self.log.info("Done Running COMPUCALIB", extra=tags)        
            return dataItem.computationConfiguration, dataItem.bcStrips
        except Exception, err:
            raise CompuCalibrationError(err, preProcessingResult)
        
    def computeDANAResult(self, itemname, dataItem, preProcessingResult):
        """ Refer DANAFramework.computeDANAResult for documentation
        """
        
        try:
            # Set the logging tags
            tags = self.ianatags + itemname + " COMPU"
            
            self.log.info("Running COMPU", extra=tags)
            
            result = SuryaImageAnalysisResult()
            chartFileName = (itemname + ".chart." + str(dataItem.computationConfiguration.calibrationId) + ".png")
             
            # Check if the image already exists if not create a new file
            if self.fs.exists(filename=chartFileName):
                chartImg = self.fs.get_last_version(chartFileName)
                self.fs.delete(chartImg.__getattr__("_id"))
                
            result.chartImage.new_file(filename=chartFileName, content_type='image/png')
                
            chartImage = result.chartImage
            sampledRGB, aux, gradient = preProcessingResult.features
            
            filterRadius = dataItem.computationConfiguration.filterRadius
            exposedTime = dataItem.computationConfiguration.exposedTime
            airFlowRate = dataItem.computationConfiguration.airFlowRate
            bcGradient = dataItem.bcStrips.bcStrips
            
            
            # Compute the BCCResult
            bccResult, exitcode = bccResultComputation(sampledRGB, filterRadius, exposedTime, airFlowRate, bcGradient, gradient, chartImage, tags, logging.DEBUG)
            chartImage.close()
            if exitcode is not ExitCode.Success:
                result.status    = ExitCode.toString[exitcode] 
                result.validFlag = False
                raise ResultComputationError(result.status, preProcessingResult, result)
                
            bccResult_ = BccResult(fitRed         = bccResult.fitRed, 
                                   fitGreen       = bccResult.fitGreen,
                                   fitBlue        = bccResult.fitBlue,
                                   rSquaredRed    = bccResult.rSquaredRed,
                                   rSquaredGreen  = bccResult.rSquaredGreen,
                                   rSquaredBlue   = bccResult.rSquaredBlue,
                                   BCAreaRed      = bccResult.BCAreaRed,
                                   BCAreaGreen    = bccResult.BCAreaGreen,
                                   BCAreaBlue     = bccResult.BCAreaBlue,
                                   BCVolRed       = bccResult.BCVolRed,
                                   BCVolGreen     = bccResult.BCVolGreen,
                                   BCVolBlue      = bccResult.BCVolBlue)
            result.result = bccResult_
            result.status = ExitCode.toString[exitcode]
            result.validFlag = True
        
            self.log.info("Done Running COMPU", extra=tags)
            return result
        except Exception, err:
            if isinstance(err, ResultComputationError):
                raise err
            result = SuryaImageAnalysisResult()
            result.validFlag                = False
            result.status                   = str(err)
            raise ResultComputationError(err, preProcessingResult, result)
    
    def saveDANAResult(self, itemname, dataItem, preProcessingResult, computationResult):
        """ Result DANAFramework.saveDANAResult fro documentation
        """
        try:
            dataItem.processedFlag = True
            dataItem.save()
            
            # Set the logging tags
            tags = self.ianatags + itemname + " SAVIN"
            
            self.log.info("Running SAVIN", extra=tags)
            
            result = SuryaIANAResult()
    
            result.item                       = dataItem.processEntity    
            result.preProcessingConfiguration = dataItem.preProcessingConfiguration
            result.preProcessingResult        = preProcessingResult.result
            result.computationConfiguration   = dataItem.computationConfiguration
            result.bcStrips                   = dataItem.bcStrips
            result.computationResult          = computationResult 
            result.status                     = "COMPLETE"
            result.isEmailed                  = False
            result.date                       = datetime.datetime.now()
            result.save()
            
            self.log.info("Done Running SAVIN", extra=tags)
        except Exception, err:
            raise ResultSavingError(err)
            
    def onError(self, itemname, dataItem, err, phase):
        """ Refer DANAFramework.onError for documentation
        """
        
        dataItem.processedFlag = True
        dataItem.save()
        
        # Set the logging tags
        tags = self.ianatags + itemname + " " + phase
        
        self.log.error(phase + " Failed, cause: "+ str(err), extra=tags)
        
        failedResult = SuryaIANAFailedResult()
        
        failedResult.item      = dataItem.processEntity
        failedResult.isEmailed = False
        failedResult.status    = phase 
        failedResult.date      = datetime.datetime.now()
        
        if phase == "PPROCCALIB" or phase == "SAVIN":
            failedResult.save()
            
        if phase == "PPROC" or phase == "COMPUCALIB":
            failedResult.preProcessingConfiguration = dataItem.preProcessingConfiguration
            failedResult.preProcessingResult = err.result
            failedResult.save()

        if phase == "COMPU":
            failedResult.preProcessingConfiguration = dataItem.preProcessingConfiguration
            failedResult.preProcessingResult        = err.preProcessingResult
            failedResult.computationConfiguration   = dataItem.computationConfiguration
            failedResult.bcStrips                   = dataItem.bcStrips
            failedResult.computationResult          = err.computationResult
            failedResult.save()        
        
if __name__ == "__main__":
    connect("SuryaDB")
    iana = IANAFramework(logging.DEBUG)
    iana.run("IANAFramework.pid", "IANAFramework", 10)
    