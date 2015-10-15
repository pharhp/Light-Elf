#-------------------------------------------------------------------------------
# Name:        lsptranslation.py
# Purpose:
#
# Author:      frank_reichstein
#
# Created:     23/08/2012
# Copyright:   (c) frank_reichstein 2012
# Licence:

"""
Copyright (C) 2011-2013 by Frank Reichstein

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
#-------------------------------------------------------------------------------
#!/usr/bin/env python
import xml.etree.cElementTree as ElementTree
###from xml.etree.ElementTree import
###import gc
import os
import random
import subprocess
import re

XLIGHTS_INTERVAL = 50
LSP_MS_PERIOD = 88.2
MAX_INTENSITY = 100

FPP_MINOR_V = 0
FPP_MAJOR_V = 1
FPP_DATA_OFFSET =28
FPP_HDR_LEN = 28
FPP_INTERVAL = XLIGHTS_INTERVAL
FPP_GAMMA = 1
FPP_COLOR_ENCODE = 2

##Controller Protocol
protoMap = {
         0:'LOR',
         1:'Entec Open',
         2:'Entec Pro',
         3:'Unknown',
         4:'Animated Lighting',
         5:'Renard',
         6:'e1.31',
         7:'Pixelnet',
}


################################################################################
class xNetwork:
    """A class to hold data about the xLight configuration on the local PC"""
    def __init__(self,file='C:\\xLights\\xlights_networks.xml'):
        self.file= file
        self.maxChan= 0
        self.networks= []
        self.ProcessNetworks()

    def ProcessNetworks(self):
        tree=ElementTree.parse(self.file)
        root = tree.getroot()
        networks = self.networks

        i = 0
        for net in root.findall('network'):
            networks.append({})
            for key in net.keys():
                if key == "LastChannel":
                    self.mapChans = True
                networks[i][key] = net.get(key)
            i+=1
            self.maxChan = self.maxChan + int(net.get('MaxChannels'))

    def getNetStartChan(self, net):
        chan = 0
        for i in range(net-1):
            chan += int(self.networks[i]['MaxChannels'])
        return chan

    def getNetCount(self):
        return self.networks.count()

    def getMaxChannels(self):
        return self.maxChan

################################################################################

def getColorVals(colorInt, pct=100):
    retval = {}
    retval['RED'] = (colorInt&0x00ff0000)>>16
    retval['GREEN'] = (colorInt&0x0000ff00)>>8
    retval['BLUE'] = (colorInt&0x000000ff)
    if pct != 100:
       for key in retval.keys():
           retval[key] = int(retval[key] * pct/100)
    return retval

def periodNum(lspPosVal):
    timeInMS = int(lspPosVal/LSP_MS_PERIOD)
    period = int(timeInMS/XLIGHTS_INTERVAL)
    return period

def normalizeIntensity(intensity):
    return intensity*255/MAX_INTENSITY

def main():
    netInfo = xNetwork()

    seq = Sequence('C:\\temp\\scuba', netInfo,
                   execDir=os.path.dirname(os.path.realpath(__file__)))
##    seq.extractSequence()
    seq.logFile = open('C:\\temp\\scuba.log','w')
    seq.procSequence()

    for (cur,total) in seq.convertLSPSequenceWStatus():
        print cur, total

    seq.outputxLights("C:\\xlights2012\\Frank R short sequence.xseq")


################################################################################
class Sequence():
    """Class representing a LSP Sequence read from an LSP file.  Currently
    this only works with LSP v2.5 files. Not sure of value of supporting older
    versions. Older versions will be more challenging to process. The class
    assumes that the sequence has been unzipped and stored in a directory.
    Initializing an object requires instantiation of an xNetwork object and the
    directory for the unzipped LSP sequence
    """

    def __init__(self, seqdir,netInf, tempDir="C:\\xlights\\temp", execDir = None):

        self.chanEffectCounts = {}
        self.effectCount = 0
        self.chanDict = {}
        self.seqdir = seqdir
        self.networks= netInf
        self.tempDir = tempDir
        self.execDir = execDir
        self.logLevel = 3
        #gc.enable()

#-------------------------------------------------------------------------------
    def procSequence(self):
        #start with a root directory. assume that we have a Sequnce file and a dir
        os.chdir(self.seqdir)
        sTree = ElementTree.parse('Sequence')
        self.getMediaInfo(sTree)
        del sTree

        self.log("Channels in Networks: %d"%self.networks.maxChan)
        self.log("50ms Periods in sequence: %d"%self.numPeriods)
        #we now know song length in periods and total expected channel count
        #initialize command buffer
        self.data = bytearray(self.networks.getMaxChannels()*self.numPeriods)

#-------------------------------------------------------------------------------
    def log(self, string):
        string += "\n"
        self.logFile.write(string)
##        print string

#-------------------------------------------------------------------------------
    def extractSequence(self):

        #if re.search(r'msq$',self.seqdir, re.I) != None:
            #not an MSQ file so assuem uncompressed already
        #    return 0

        if self.execDir == None:
            return 1
        cmd = self.execDir + "\\" + '7za.exe'

        if os.path.exists(cmd) == False:
            return 1
        seqName = re.split(r'\\', self.seqdir, flags=re.I)[-1]

        newDir = self.tempDir + '\\' + re.sub(r'\.msq$','',seqName,flags=re.I)
        print newDir
        self.logFile = open(newDir + ".log",'w')

        #self.log([cmd, "x", '"', self.seqdir, '"', "-o\"%s\""%newDir])

        retcode = subprocess.call((cmd +" x -aoa \"" + self.seqdir + "\" -o\"%s\""%newDir),stdout=self.logFile)
        self.seqdir = newDir
        return retcode

#-------------------------------------------------------------------------------
    def sendError(self):
        if self.statQ != None:
            self.statQ.put('Error')

#-------------------------------------------------------------------------------
    def convertLSPSequence(self):
        os.chdir('Controllers')
        for f in os.listdir(os.getcwd()):
            cTree=ElementTree(file=f)
            self.procController(cTree, outfile)
            del cTree

#-------------------------------------------------------------------------------
    def convertLSPSequenceWStatus(self):
        os.chdir('Controllers')
        dircontents = os.listdir(os.getcwd())
        totalFiles = len(dircontents)
        count = 0
        for f in dircontents:
            self.log( "Starting controller file: " + f )
            cTree=ElementTree.parse(f)
            self.procController(cTree)
            del cTree
            #gc.collect()
            count += 1
            yield (count,totalFiles)


#-------------------------------------------------------------------------------
    def getMediaInfo(self,tree):
        root = tree.getroot()
        mmf = root.find('MultiMediaFile')
        length = int(root.find('Length').text)

        self.numPeriods = periodNum(length)
        if mmf:
            self.songFile = mmf.find('MediaFileName').text
        else:
            self.songFile = "blank"
#-------------------------------------------------------------------------------
    def isValidChans(self, rchan, gchan, bchan, conZone, conID):
        """validate that the channels in current processing time are valid
           based on the existing xLights netowrk definition"""
        #TODO
        #at the moment just validate that the channel number is less than the
        #max channel (no overruns)

        return (self.networks.getMaxChannels >= \
                    max(rchan,gchan,bchan))

#TODO -- Need a function to calculate the actual channel based on network
# definition etc in the network file. spare me having to pass around zone and id

#-------------------------------------------------------------------------------
    def calcLORChan(self, netNum, chan, conID):
        if conID < 0:
           conID = conID - (1<<conID.bit_length())
        lorNetChanNum = (conID-1) *16 +chan
        return lorNetChanNum + self.networks.getNetStartChan(netNum)

#-------------------------------------------------------------------------------
    def procController(self, tree):
        rgbChans = {}
        root = tree.getroot()
        chans = root.find('Channels')
        conID = int(root.find('ControllerID').text)
        conZone = int(root.find('ControllerZone').text)
        conName = root.find('ControllerName').text
        conType = int(root.find('ControllerType').text)
        conProtocol = int(root.find('ControllerProtocol').text)

        if conType == 2:
            self.log( "%s is a Virtual Controller skipping"%conName)
            return
        self.log("Name: %s, ID: %d, Zone: %d, Prtocol: %s"%(
                 conName, conID, conZone, protoMap[conProtocol]))
        if conProtocol == 4:
           self.log("xLights does not understand Animated Lighting")
           return

        for chan in chans.findall('Channel'):
            intervals = chan.find('Tracks').find('Track').find('Intervals')
            #get channel IDs and convert to 0 based
            rchan = int(chan.find('ChannelID').text) - 1
            gchan = int(chan.find('GreenChannelID').text) - 1
            bchan = int(chan.find('BlueChannelID').text) -1
            if not self.isValidChans(rchan,gchan,bchan, conZone, conID):
                self.log( "Warning! one of channels %d,%d,%d out of valid range!"\
                    %(rchan,gchan,bchan))
                continue

            if conProtocol == 0:
               #process LOR Channel
               rchan = self.calcLORChan(conZone, rchan, conID)
               gchan = self.calcLORChan(conZone, gchan, conID)
               bchan = self.calcLORChan(conZone, bchan, conID)
            elif conZone > 1:
                rchan += self.networks.getNetStartChan(conZone)
                gchan += self.networks.getNetStartChan(conZone)
                bchan += self.networks.getNetStartChan(conZone)

            if gchan == bchan or conType == 0:
                #if gchan != -1 or bchan != -1:
                #   print "Warning! expected a non RGB channel but"\
                #          " green and blue have values."
##                if self.chanDict.has_key(rchan):
##                    self.log( "Warning! Channel %d has already been processed."
##                          " Duplicate Channel?" %(rchan) )
##                    string = "existing: "
##                    for val in self.chanDict[rchan]:
##                        string += str(val)
####                    self.log( "existing: " + self.chanDict[rchan])
##                    self.log(string)
##                    self.log( "current: normal ConID %d ConZone %d, ConName %s"%( conID,\
##                                           conZone, conName))
##                self.chanDict[rchan] = ["normal", conID, conZone, conName]
                self.procIntervals( rchan, intervals)
            else:
                rgbChans['RED'] = rchan
                rgbChans['GREEN'] = gchan
                rgbChans['BLUE'] = bchan
##                for color in rgbChans.keys():
##                    chan = rgbChans[color]
##                    if chan in self.chanDict.keys():
##                        self.log( "Warning! Channel %d has already been processed."
##                              " Duplicate Channel?" %(rchan))
##                        string = "Existing: "
##                        for val in self.chanDict[chan]:
##                            string += str(val)
##
##                        self.log( string)
##                        self.log( "current: RGB %s %d %d %s"%(color, conID,
##                                           conZone, conName ))
##                    self.chanDict[chan] = ["RGB %s"%(color), conID,\
##                                           conZone, conName]
                self.procRGBIntervals( rgbChans, intervals)
        del conProtocol
        del conType
        del conName
        del conZone
        del conID
        del chans
        del root







#-------------------------------------------------------------------------------
    def procIntervals(self, chan, intervals):
        timeIntervals = intervals.findall('TimeInterval')
        numInt = len(timeIntervals)

        for idx in range(numInt):
            startPer = periodNum(int(float(timeIntervals[idx].get('pos'))))

            if startPer < 0:
                #initial time period is always negative it seems. Log something here?
                # LOG
                continue
            elif startPer > self.numPeriods:
                #yes yes this could be handled above wiht an OR but I want to be
                # able to log them seperately.  Could change later.
                continue
            effect = int(timeIntervals[idx].get('eff'))

            if effect == 4:
                # this is an off... since we initialize to 0 do nothing
                # I think the negative periods and end periods are always
                # offs as well.
                continue

            endPer = periodNum(int(float(timeIntervals[idx+1].get('pos'))))
            try:
                startIntensity = \
                    normalizeIntensity(int(timeIntervals[idx].get('in')))
            except TypeError:
                startIntensity = 0
            try:
                endIntensity = \
                    normalizeIntensity(int(timeIntervals[idx].get('out')))
            except TypeError:
                endIntensity = 0

            perDiff = endPer - startPer #number of ticks for effect

            #Diagnostic code
##            if chan in self.chanEffectCounts.keys():
##                self.chanEffectCounts[chan] +=1
##            else:
##                self.chanEffectCounts[chan] = 1
            self.effectCount += 1
            self.procEffect(chan, effect, startPer, perDiff, \
                            startIntensity, endIntensity)


#-------------------------------------------------------------------------------
    def logStats(self):
        if len(self.chanEffectCounts.keys()) > 0:
            keys = self.chanEffectCounts.keys()
            keys.sort()
            if self.logLevel >= 2:
               self.log('Number of channels with effects: %d'%(len(self.chanEffectCounts.keys())))
##            if self.logLevel >=3:
##               string = ''
##               for key in keys:
##                   string += 'chan %d has %d effects'%(key, self.chanEffectCounts[key])
##                   if len(string) > 100:
##                      self.log(string)
##                      string = ''

#-------------------------------------------------------------------------------
    def procEffect(self, chan, effect, startPer, perDiff, \
                   startIntensity, endIntensity):
        """Handle single color effects generation"""
        temp = perDiff if perDiff != 0 else 1
        rampDiff = endIntensity - startIntensity
        intensityInc = float(rampDiff)/temp

        if effect == 1 or effect == 2 or effect == 3: #ramps or on
            rampDiff = endIntensity - startIntensity
            for i in range(perDiff):
                intensity = startIntensity if rampDiff == 0 else \
                           (int)(intensityInc*i) + startIntensity
                self.setChanData(chan, startPer+i,intensity)

        elif effect == 5: #handle twinkle effect
            twinklestate = random.randint(0,1)
            nexttwinkle = random.randint(2,10)

            for i in range(perDiff):
                intensity = (int)(intensityInc*i) + startIntensity
                self.setChanData(chan, startPer+i,intensity*twinklestate)

                nexttwinkle -= 1
                if nexttwinkle == 0:
                    twinklestate = random.randint(0,1)
                    nexttwinkle = random.randint(2,10)

        elif effect == 6: #handle shimmer

            for i in range(perDiff):
                intensity = (int)(intensityInc*i) + startIntensity
                shimmerstate = (perDiff + i) & 0x01
                self.setChanData(chan, startPer+i,intensity*shimmerstate)
        else:
            self.log("Warning! unhandled effect value %d. chan %d"%(effect,chan))
#-------------------------------------------------------------------------------
    def setChanData(self, chan, period, value):
        try:
            self.data[chan*self.numPeriods+period] = value
        except IndexError:
               self.log("Index out of range! Chan %d Period %d "%(chan,period))

#-------------------------------------------------------------------------------
    def procRGBIntervals( self, rgbChans, intervals):
        timeIntervals = intervals.findall('TimeInterval')
        numInt = len(timeIntervals)
        useHSV = False

        for idx in range(numInt):
            startPer = periodNum(int(float(timeIntervals[idx].get('pos'))))

            if startPer < 0:
                #initial time period is always negative it seems. Log something here?
                # LOG
                continue
            elif startPer > self.numPeriods:
                #yes yes this could be handled above wiht an OR but I want to be
                # able to log them seperately.  Could change later.
                continue
            effect = int(timeIntervals[idx].get('eff'))

            if effect == 4:
                # this is an off... since we initialize to 0 do nothing
                # I think the negative periods and end periods are always
                # offs as well.
                continue

            try:
                inpct = int(timeIntervals[idx].get('in'))
            except TypeError:
                inpct = 0
            try:
                outpct = int(timeIntervals[idx].get('out'))
            except TypeError:
                outpct = 0

            endPer = periodNum(int(float(timeIntervals[idx+1].get('pos'))))

            colorEnd = getColorVals(-1)
            colorStart = getColorVals(-1)
            try:
                if effect == 2 or effect == 1:
                    print "foo"
                    colorStart = getColorVals(int(timeIntervals[idx].get('bst')),
                                                                          inpct)
                    colorEnd   = getColorVals(int(timeIntervals[idx].get('ben')),
                                                                         outpct)
                   ## print "Color in %s, out %s: inpct %s: outpct: %s"%(colorStart['RED'], colorEnd['RED'], inpct, outpct)
                   ## debug code for fade calculation
                else:
                    colorStart = getColorVals(int(timeIntervals[idx].get('bst')))
                    colorEnd   = getColorVals(int(timeIntervals[idx].get('ben')))

            except:
                self.log("%d"%(idx))
                self.log(timeIntervals[idx].tostring())

            perDiff = endPer - startPer #number of ticks for effect

            twinklestate = shimmerstate = 1
            if effect == 5:
                twinklestate = random.randint(0,1)
                nexttwinkle = random.randint(2,10)
            rgbDel = {}
            rgbPer = {}
            for color in colorStart.keys():
                temp = perDiff if perDiff != 0 else 1
                if effect == 5 or effect == 6:
                   startInt = timeIntervals[idx].get('in')
                   endInt = timeIntervals[idx].get('out')
                   rgbDel[color] = ((colorStart[color]*(float(endInt)/100) -\
                                 (colorStart[color]*float(startInt)/100))/temp)
                else:
                     rgbDel[color] = float((colorEnd[color] - colorStart[color])) / temp
            for i in range(perDiff):
                if effect == 6:
                   shimmerstate = (perDiff+i) & 0x01
                for color in colorStart.keys():
                    #assert(rgbChans[color])
                    chan = rgbChans[color]
                    #Diagnostic code
##                    if chan in self.chanEffectCounts.keys():
##                        self.chanEffectCounts[chan] +=1
##                    else:
##                        self.chanEffectCounts[chan] = 1
                    self.effectCount += 1
                    val = (int(i*rgbDel[color])+colorStart[color]) \
                                                   * (shimmerstate*twinklestate)
                    self.setChanData(chan, startPer+i,val)

                if effect == 5:
                   nexttwinkle -= 1
                   if nexttwinkle == 0:
                      twinklestate = random.randint(0,1)
                      nexttwinkle = random.randint(2,10)

#-------------------------------------------------------------------------------
    def getChannelEvents(self, chanNum):
        chanEvents = bytearray(self.numPeriods)
        chanEvents = self.data[(chanNum-1)*self.numPeriods:
                                (chanNum*self.numPeriods)]
        return chanEvents

#-------------------------------------------------------------------------------
    def outputxLightsFileHDR(self, FH, nPer, sFile):

        FH.write(b'xLights  1 %8d %8d'%(self.networks.maxChan, nPer))
        FH.write(b'\x00\x00\x00\x00')
        FH.write(b'%s'%(sFile))

        # pad out to 512 bytes
        FH.write(b'\x00'*(512 - int(len(sFile)) -32))

#-------------------------------------------------------------------------------
    def outputxLights(self,outfile):
        print("Generating xseq")
        FH = open(outfile,'wb')
        self.outputxLightsFileHDR(FH, self.numPeriods, self.songFile)
        FH.write(self.data)
        FH.close()
#-------------------------------------------------------------------------------
    def outputFalconHDR(self, FH, nPer):
        chanCount = self.networks.getMaxChannels()
        stepSize = chanCount +(chanCount%4)
        stepData = bytearray(stepSize)
        periods = self.numPeriods
        buff = bytearray(FPP_DATA_OFFSET)

        buff[0:3]=b'FSEQ'
        buff[4:5]=(FPP_DATA_OFFSET%256, FPP_DATA_OFFSET/256)
        buff[6]=FPP_MINOR_V
        buff[7]=FPP_MAJOR_V
        buff[8:9]=(FPP_HDR_LEN%256,FPP_HDR_LEN/256)
        buff[10:13] = (stepSize & 0xFF, stepSize >> 8 & 0xFF, stepSize >> 16 & 0xFF, stepSize >> 24 & 0xFF)
        buff[14:17] =(nPer & 0xFF, nPer >> 8 & 0xFF, nPer >> 16 & 0xFF, nPer >> 24 & 0xFF)
        buff[18:19]=(FPP_INTERVAL%256,FPP_INTERVAL/256)
        buff[20:21]=(0,0)
        buff[22:23]=(0,0)
        buff[24]=FPP_GAMMA&0xff
        buff[25]=FPP_COLOR_ENCODE & 0xff
        buff[26:27]=(0,0)
        FH.write(buff)

#-------------------------------------------------------------------------------
    def outputFalconPlayer(self,outfile):

        print("Generating Falcon File")
        chanCount = self.networks.getMaxChannels()
        stepSize = chanCount +(chanCount%4)
        FH = open(outfile,'wb')
        self.outputFalconHDR(FH, self.numPeriods)
        self.writeFalconChanData(FH)

#-------------------------------------------------------------------------------
    def writeFalconChanData(self, FH):
        chanCount = self.networks.getMaxChannels()
        stepSize = chanCount +(chanCount%4)
        stepData = bytearray(stepSize)
        #FH.seek(FPP_DATA_OFFSET)

        for periodNum in range(self.numPeriods):
            for ch in range(stepSize):
                if ch < chanCount:
                   stepData[ch]=self.data[ch*self.numPeriods + periodNum]

                else:
                   stepData[ch]=0

            FH.write(stepData)
#
#-------------------------------------------------------------------------------
    def outputConductor(self, outfile):
        condData = bytearray(4)
        FH = open(outfile,'wb')
        chanCount = self.networks.getMaxChannels()
        #Conductor file format:
        #chxinuniverse1
        if chanCount != 16384:
           return False

        for period in range(self.numPeriods):
            for i in range(4096):
                for j in range(4):
                    ch = j * 4096 + i
                    condData[j] = self.data[ch*self.numPeriods + period] if ch<chanCount else 0
                FH.write(condData)

#-------------------------------------------------------------------------------
    def getConductorFormat(self):
        chanCount = self.networks.getMaxChannels()
        if chanCount != 16384:
           return False
        condData = bytearray(chanCount * self.numPeriods)

        for period in range(self.numPeriods):
            for i in range(4096):
                for j in range(4):
                    ch = j * 4096 + i
                    condData[period*16384 + i*4 + j] = self.data[ch*self.numPeriods + period] if ch<self.networks.maxChan else 0

        return condData
################################################################################
if __name__ == '__main__':

    main()
