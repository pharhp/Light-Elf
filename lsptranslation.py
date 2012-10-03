#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      frank_reichstein
#
# Created:     23/08/2012
# Copyright:   (c) frank_reichstein 2012
# Licence:     <your licence>
#-------------------------------------------------------------------------------
#!/usr/bin/env python
from xml.etree.ElementTree import ElementTree
import os
import random
import subprocess
import re

XLIGHTS_INTERVAL = 50
LSP_MS_PERIOD = 88.2
MAX_INTENSITY = 100

################################################################################
class xNetwork:
    """A class to hold data about the xLight configuration on the local PC"""
    def __init__(self,file='C:\\xLights\\xlights_networks.xml'):
        self.file= file
        self.maxChan= 0
        self.networks= []
        self.ProcessNetworks()

    def ProcessNetworks(self):
        tree=ElementTree(file=self.file)
        root = tree.getroot()
        networks = self.networks

        i = 0
        for net in root.findall('network'):
            networks.append({})
            for key in net.keys():
                networks[i][key] = net.get(key)
            i+=1
            self.maxChan = self.maxChan + int(net.get('MaxChannels'))


    def getNetCount(self):
        return self.networks.count()

    def getMaxChannels(self):
        return self.maxChan

################################################################################

def getColorVals(colorInt):
    retval = {}
    retval['RED'] = (colorInt&0x00ff0000)>>16
    retval['GREEN'] = (colorInt&0x0000ff00)>>8
    retval['BLUE'] = (colorInt&0x000000ff)
    return retval

def periodNum(lspPosVal):
    timeInMS = int(lspPosVal/LSP_MS_PERIOD)
    period = int(timeInMS/XLIGHTS_INTERVAL)
    return period

def normalizeIntensity(intensity):
    return intensity*255/MAX_INTENSITY

def main():
    netInfo = xNetwork()

    seq = Sequence('C:\\xlights2012\\Bass Hunter 4 EE', netInfo)

    for (cur,total) in seq.convertLSPSequenceWStatus():
        print cur, total

    seq.outputxLights("C:\\xlights2012\\Bass Hunter 4 EE.xseq")


################################################################################
class Sequence():
    """Class representing a LSP Sequence read from an LSP file.  Currently
    this only works with LSP v2.5 files. Not sure of value of supporting older
    versions. Older versions will be more challenging to process. The class
    assumes that the sequence has been unzipped and stored in a directory.
    Initializing an object requires instantiation of an xNetwork object and the
    directory for the unzipped LSP sequence
    """

    def __init__(self, seqdir,netInf, tempDir="C:\\xlights\\temp"):

        self.chanEffectCounts = {}
        self.effectCount = 0
        self.chanDict = {}
        self.seqdir = seqdir
        self.networks= netInf
        self.tempDir = tempDir

    def procSequence(self):
        #start with a root directory. assume that we have a Sequnce file and a dir
        os.chdir(self.seqdir)
        sTree = ElementTree(file='Sequence')
        self.getMediaInfo(sTree)
        del sTree

        #we now know song length in periods and total expected channel count
        #initialize command buffer
        self.data = bytearray(self.networks.getMaxChannels()*self.numPeriods)

    def extractSequence(self):
        print 'uno'
        #if re.search(r'\.msq',self.seqdir, re.I) != None:
            #not an MSQ file so assuem uncompressed already
        #    return 0
        print 'dos'
        if os.path.exists('7za.exe') == False:
            return 1
        newDir = re.sub(r'\.msq$','',self.seqdir,flags=re.I)

        print ["7za.exe", "x", '"', self.seqdir, '"', "-o\"%s\""%newDir]
        retcode = subprocess.call(("7za.exe x  \"" + self.seqdir + "\" -o\"%s\""%newDir))
        self.seqdir = newDir
        return retcode

    def convertLSPSequence(self):
        os.chdir('Controllers')
        for f in os.listdir(os.getcwd()):
            cTree=ElementTree(file=f)
            self.procController(cTree, outfile)
            del cTree

    def convertLSPSequenceWStatus(self):
        os.chdir('Controllers')
        dircontents = os.listdir(os.getcwd())
        totalFiles = len(dircontents)
        count = 0
        for f in dircontents:
            print f
            cTree=ElementTree(file=f)
            self.procController(cTree)
            del cTree
            count += 1
            yield (count,totalFiles)

    def getMediaInfo(self,tree):
        root = tree.getroot()
        mmf = root.find('MultiMediaFile')
        length = int(root.find('Length').text)

        self.numPeriods = periodNum(length)
        self.songFile = mmf.find('MediaFileName').text

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


    def procController(self, tree):
        rgbChans = {}
        root = tree.getroot()
        chans = root.find('Channels')
        conID = int(root.find('ControllerID').text)
        conZone = int(root.find('ControllerZone').text)
        conName = root.find('ControllerName').text

        for chan in chans.findall('Channel'):
            intervals = chan.find('Tracks').find('Track').find('Intervals')
            #get channel IDs and convert to 0 based
            rchan = int(chan.find('ChannelID').text) - 1
            gchan = int(chan.find('GreenChannelID').text) - 1
            bchan = int(chan.find('BlueChannelID').text) -1
            if not self.isValidChans(rchan,gchan,bchan, conZone, conID):
                print "Warning! one of channels %d,%d,%d out of valid range!"\
                    %(rchan,gchan,bchan)
                continue


            if gchan == bchan:
                #if gchan != -1 or bchan != -1:
                #   print "Warning! expected a non RGB channel but"\
                #          " green and blue have values."
                if self.chanDict.has_key(rchan):
                    print "Warning! Channel %d has already been processed."\
                          " Duplicate Channel?" %(rchan)
                    print "existing: ", self.chanDict[rchan]
                    print "current: ","normal ", conID,\
                                           conZone, conName
                self.chanDict[rchan] = ["normal", conID, conZone, conName]
                self.procIntervals( rchan, intervals)
            else:
                rgbChans['RED'] = rchan
                rgbChans['GREEN'] = gchan
                rgbChans['BLUE'] = bchan
                for color in rgbChans.keys():
                    chan = rgbChans[color]
                    if chan in self.chanDict.keys():
                        print "Warning! Channel %d has already been processed."\
                              " Duplicate Channel?" %(rchan)
                        print "existing: ", self.chanDict[chan]
                        print "current: ","RGB %s"%(color), conID,\
                                           conZone, conName
                    self.chanDict[chan] = ["RGB %s"%(color), conID,\
                                           conZone, conName]
                self.procRGBIntervals( rgbChans, intervals)

    def procIntervals(self, chan, intervals):
        timeIntervals = intervals.findall('TimeInterval')
        numInt = len(timeIntervals)

        for idx in range(numInt):
            startPer = periodNum(int(timeIntervals[idx].get('pos')))

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

            endPer = periodNum(int(timeIntervals[idx+1].get('pos')))
            startIntensity = \
                normalizeIntensity(int(timeIntervals[idx].get('in')))
            endIntensity = \
                normalizeIntensity(int(timeIntervals[idx].get('out')))
            perDiff = endPer - startPer #number of ticks for effect

            #Diagnostic code
            if chan in self.chanEffectCounts.keys():
                self.chanEffectCounts[chan] +=1
            else:
                self.chanEffectCounts[chan] = 1
            self.effectCount += 1
            self.procEffect(chan, effect, startPer, perDiff, \
                            startIntensity, endIntensity)



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
                try:
                    self.data[chan*self.numPeriods+startPer+i] = intensity
                except ValueError:
                       print "blah"

        elif effect == 5: #handle twinkle effect
            twinklestate = random.randint(0,1)
            nexttwinkle = random.randint(2,10)

            for i in range(perDiff):
                intensity = (int)(intensityInc*i) + startIntensity
                self.data[chan*self.numPeriods+startPer+i] = \
                                                intensity*twinklestate
                nexttwinkle -= 1
                if nexttwinkle == 0:
                    twinklestate = random.randint(0,1)
                    nexttwinkle = random.randint(2,10)

        elif effect == 6: #handle shimmer

            for i in range(perDiff):
                intensity = (int)(intensityInc*i) + startIntensity
                shimmerstate = (perDiff + i) & 0x01
                self.data[chan*self.numPeriods+startPer+i] = \
                                                intensity*shimmerstate
        else:
            print "Warning! unhandled effect value %d. chan %d"%(effect,chan)


    def procRGBIntervals( self, rgbChans, intervals):
        timeIntervals = intervals.findall('TimeInterval')
        numInt = len(timeIntervals)
        useHSV = False

        for idx in range(numInt):
            startPer = periodNum(int(timeIntervals[idx].get('pos')))

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

            endPer = periodNum(int(timeIntervals[idx+1].get('pos')))
            colorStart = getColorVals(int(timeIntervals[idx].get('bst')))
            colorEnd   = getColorVals(int(timeIntervals[idx].get('ben')))
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
                    if chan in self.chanEffectCounts.keys():
                        self.chanEffectCounts[chan] +=1
                    else:
                        self.chanEffectCounts[chan] = 1
                    self.effectCount += 1
                    try:
                        self.data[chan*self.numPeriods+startPer+i] = \
                                        (int(i*rgbDel[color])+colorStart[color]) \
                                                   * (shimmerstate*twinklestate)
                    except (ValueError, TypeError):
                           pass
                if effect == 5:
                   nexttwinkle -= 1
                   if nexttwinkle == 0:
                      twinklestate = random.randint(0,1)
                      nexttwinkle = random.randint(2,10)

    def getChannelEvents(self, chanNum):
        chanEvents = bytearray(self.numPeriods)
        chanEvents = self.data[(chanNum-1)*self.numPeriods:
                                (chanNum*self.numPeriods)]
        return chanEvents


    def outputxLights(self,outfile):
        print("Generating xseq")
        FH = open(outfile,'wb')
        FH.write(b'xLights  1 %8d %8d'%(self.networks.maxChan,\
                                         self.numPeriods))
        FH.write(b'\x00\x00\x00\x00')
        FH.write(b'%s'%(self.songFile))

        # pad out to 512 bytes
        FH.write(b'\x00'*(512 - int(len(self.songFile)) -32))

        FH.write(self.data)
        FH.close()

    def outputConductor(self, outfile):
        condData = bytearray(4)
        FH = open(outfile,'wb')
        #Conductor file format:
        #chxinuniverse1
        for period in range(self.numPeriods):
            for i in range(4096):
                for j in range(4):
                    ch = j * 4096 + i
                    condData[j] = self.data[ch*self.numPeriods + period] if ch<self.networks.maxChan else 0

                FH.write(condData)

if __name__ == '__main__':
    main()
