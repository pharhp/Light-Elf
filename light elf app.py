#-------------------------------------------------------------------------------
# Name:        Light elf app.py
# Purpose:
#
# Author:      frank_reichstein
#
# Created:     23/08/2012
# Copyright:   (c) frank_reichstein 2012
# Licence:
License = \
"""
Copyright (C) 2011-2012 by Frank Reichstein

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
Version = "0.0.2 Beta"


#-------------------------------------------------------------------------------

import wx, os, inspect, sys
from multiprocessing import Process, cpu_count, Queue
import  wx.lib.scrolledpanel as scrolled
import re, time, logging
import pickle



from lsptranslation import Sequence, xNetwork

################################################################################
class LightingElf(wx.Frame):
    SEQUENCE_NAME = 'SN'
    SEQUENCE_FILE = 'SF'
    SEQUENCE_STATUS = 'SS'
    SEQUENCE_PROGRESS = 'SP'
    SEQUENCE_COMPLETE = 'SC'
    SEQUENCE_OBJ = 'SO'
    PROC_STATUS = 'PS'
    PROCESS = 'PRO'
    PROC_INQ = 'PIQ'
    PROC_OUTQ = 'POQ'
    PROC_STATQ = 'PSQ'
    PROC_INFO = 'PIF'
    PROC_XNET = 'XNET'
    EXEC_DIR = 'ED'

    sequences = []
    completeSeq = []

#-------------------------------------------------------------------------------
    def __init__(self, *args, **kwds):
        # begin wxGlade: LightingElf.__init__
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.maxProc = cpu_count() # * 2
        self.activeProc = 0
        self.execPath = os.path.dirname(os.path.realpath(__file__))

        ico = wx.Icon('tree.ico',wx.BITMAP_TYPE_ICO)
        self.SetLabel("Lighting elf")
        self.SetIcon(ico)

        #set Config File
        self.cfgFile = self.execPath +"\\elf.cfg"

        ## Menu Bar
        self.menuBar = wx.MenuBar()

        #file Menu setup
        fileMenu = wx.Menu()
        fileMenu.Append(101,"&Export Sequence","Export currently processed sequences.")
        fileMenu.AppendSeparator()
        fileMenu.Append(103,"E&xit", "Say good bye to the elf")
        self.menuBar.Append(fileMenu, "&File")

        #Sequences Menu setup
        seqMenu = wx.Menu()
        self.miAddSeq = seqMenu.Append(201,"&Add Sequences",
                                       "Select LSP Sequences to convert")
        seqMenu.Append(202, "&Clear Sequences", "Delete current Sequences")
        self.menuBar.Append(seqMenu,"&Sequences")

        #Options menu setup
        optionsMenu = wx.Menu()
        optionsMenu.Append(301,"Individual Sequence",
                           "Proces each sequence as an individual sequence.",
                           wx.ITEM_RADIO)
        optionsMenu.Append(302,"Combine Sequences",
                           "Combine all selected sequences into one seamless sequence",
                           wx.ITEM_RADIO )
        optionsMenu.AppendSeparator()
        optionsMenu.Append(303,"Settings", "Set directories used by the elf",
                           wx.ITEM_NORMAL)
        self.menuBar.Append(optionsMenu,"&Options")

        #Help Menu Setup
        helpMenu = wx.Menu()
        helpMenu.Append(401, "About", "", wx.ITEM_NORMAL)
        self.menuBar.Append(helpMenu, "&Help")
        self.SetMenuBar(self.menuBar)
        ## Menu Bar end
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        ## Menu event connections
        self.Bind(wx.EVT_MENU, self.exportSequence, id=101)
        self.Bind(wx.EVT_MENU, self.CloseWindow, id=103)

        self.Bind(wx.EVT_MENU, self.addSequences, id=201)
        self.Bind(wx.EVT_MENU, self.clearSequences, id=202)

        self.Bind(wx.EVT_MENU, self.seqOptionIndividual, id=301)
        self.Bind(wx.EVT_MENU, self.seqOptionCombine, id=302)
        self.Bind(wx.EVT_MENU, self.updateSettings, id=303)

        self.Bind(wx.EVT_MENU, self.aboutElf, id=401)
        ## Menu event connections end

        #need to read default config and set this correctly... For now hard code it
        self.seqOptionIndividual(None)

        self.frame_1_statusbar = self.CreateStatusBar(1, 0)
        self.sequencesPanel = scrolled.ScrolledPanel(self, -1,
                              style=wx.DOUBLE_BORDER | wx.TAB_TRAVERSAL, size=(800,200))
        self.lbSequenceName = wx.StaticText(self.sequencesPanel, -1,
                            "Sequence Name                                                                          ",
                            style = wx.RAISED_BORDER | wx.ALL |
                            wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_LEFT,
                            size=(400,20)
                            )
        self.lbSequenceStatusText = wx.StaticText(self.sequencesPanel, -1, "Activity",
                                  style = wx.RAISED_BORDER,
                                  size=(100,20)
                                  )
        self.lbStatusGauge = wx.StaticText(self.sequencesPanel, -1, "Import Status",
                           style = wx.RAISED_BORDER,
                           size=(100,20)
                           )
##        self.lbComplete = wx.StaticText(self.sequencesPanel, -1, "Complete",
##                        style = wx.RAISED_BORDER,
##                        size=(100,20))


        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update, self.timer)


        if os.path.exists(self.cfgFile):
            config = pickle.load(open(self.cfgFile,'rb'))
            if config['SEQ_MODE'] == 'combine':
                self.seqOptionCombine(None)
                optionsMenu.Check(302,True)

        if os.path.exists('C:\\xLights\\xlights_networks.xml'):
           self.netInfo = xNetwork()
        else:
            dlg = wx.MessageBox('xlights_network.xml file not found at C:\\xLights\\xlights_networks.xml'
                + ' if you already have a configured xlights network make sure options->xlights directory is '
                + 'is set properly' )
        self.__set_properties()
        self.__do_layout()

        # end wxGlade

#-------------------------------------------------------------------------------
    def markComplete(self, seq):
##        seqgrid = self.sequencesPanel.GetSizer()
##        newBitmap = wx.StaticBitmap(self.sequencesPanel, -1,
##                        wx.Bitmap(self.execPath + "\\checked.ico", wx.BITMAP_TYPE_ANY))
##        seqgrid.Hide(seq[self.SEQUENCE_COMPLETE])
##        seqgrid.Replace(seq[self.SEQUENCE_COMPLETE],newBitmap)
##        seq[self.SEQUENCE_COMPLETE].Destroy()
##        seq[self.SEQUENCE_COMPLETE] = newBitmap
##        self.Layout()
##        self.Refresh()
        pass

#-------------------------------------------------------------------------------
    def update(self, timers):

        if len(self.sequences) != 0:
            for seq in self.sequences:
                if seq.has_key(self.PROCESS):
                    temp = seq[self.PROC_INFO]
                    try:
                        stat = temp[self.PROC_STATQ].get_nowait()
                    except:
                        continue
                    if stat == 'Done':
                        result = temp[self.PROC_OUTQ].get()
                        while not result != None and isinstance(result, Sequence):
                              try:
                                  result = temp[self.PROC_OUTQ].get()
                              except:
                                  seq[self.SEQUENCE_STATUS].ChangeValue('Error No Seq')
                                  return
                        assert(isinstance(result,Sequence))
                        self.activeProc -= 1
                        seq[self.SEQUENCE_OBJ] = result
                        seq[self.SEQUENCE_STATUS].ChangeValue(stat)
                        self.markComplete(seq)
                    elif stat == "Error":
                         seq[self.SEQUENCE_STATUS].ChangeValue(stat)
                         self.activeProc -= 1
                    elif re.match(r'Proc',stat,re.I) != None :
                        try:
                            cur = temp[self.PROC_OUTQ].get()
                            total = temp[self.PROC_OUTQ].get()
                            prog = int(cur/float(total) * 100)

                        except:
                            continue
                            pass
                        seq[self.SEQUENCE_PROGRESS].SetValue(prog)
                        seq[self.SEQUENCE_STATUS].ChangeValue(stat)
                    else:
                         seq[self.SEQUENCE_STATUS].ChangeValue(stat)
                elif self.activeProc < self.maxProc:
                    self.activeProc +=1
                    temp =  seq[self.PROC_INFO]
                    temp[self.EXEC_DIR] = self.execPath
                    temp[self.PROC_INQ] = Queue()
                    temp[self.PROC_OUTQ] = Queue()
                    temp[self.PROC_STATQ] = Queue()
                    temp[self.PROC_XNET] = self.netInfo
                    seq[self.PROCESS] = Process(target=seqWorker,kwargs=temp)
                    seq[self.PROCESS].start()

        self.Refresh()
        self.Layout()

#-------------------------------------------------------------------------------
    def __set_properties(self):
        # begin wxGlade: LightingElf.__set_properties
        self.SetBackgroundColour(wx.Colour(240, 240, 240))
        self.frame_1_statusbar.SetStatusWidths([-1])
        # statusbar fields
        frame_1_statusbar_fields = [""]
        for i in range(len(frame_1_statusbar_fields)):
            self.frame_1_statusbar.SetStatusText(frame_1_statusbar_fields[i], i)
        self.sequencesPanel.SetScrollRate(10, 10)

#-------------------------------------------------------------------------------
    def __do_layout(self):
        sizerH = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_1 = wx.FlexGridSizer(1, 3, 1, 1)
        grid_sizer_1.Add(self.lbSequenceName, 0, wx.ALL, 3)
        grid_sizer_1.Add(self.lbSequenceStatusText, 0, wx.ALL, 3)
        grid_sizer_1.Add(self.lbStatusGauge, 0, wx.ALL, 3)
##        grid_sizer_1.Add(self.lbComplete, 0, wx.ALL, 3)
        self.sequencesPanel.SetSizer(grid_sizer_1)
        self.sequencesPanel.SetAutoLayout(1)
        self.sequencesPanel.SetupScrolling()
        sizerH.Add(self.sequencesPanel,1, wx.EXPAND, 0)
        self.SetSizer(sizerH)
        sizerH.Fit(self)
        self.Layout()

#-------------------------------------------------------------------------------
    def addSequences(self, event):  # wxGlade: LightingElf.<event_handler>
        """
        Create and show the Open FileDialog
        """

        dlg = wx.FileDialog(
            self, message="Select LSP Sequences to Convert",
            defaultFile="",
            defaultDir="C:\\xlights",
            wildcard='*.msq',
            style=wx.OPEN | wx.MULTIPLE | wx.CHANGE_DIR
            )
        if dlg.ShowModal() == wx.ID_OK:
            grid = self.sequencesPanel.GetSizer()
            paths = dlg.GetPaths()
            print "adding sequences"

            for path in paths:
                grid.SetRows(grid.GetRows()+1)
                self.sequences.append({})
                tempDict = self.sequences[-1]
                tempDict[self.PROC_INFO] = {}
                procDict = tempDict[self.PROC_INFO]
                procDict[self.SEQUENCE_FILE] = path
                tempDict[self.SEQUENCE_NAME] = wx.TextCtrl(
                                                       self.sequencesPanel, -1, path)
                tempDict[self.SEQUENCE_STATUS] = wx.TextCtrl(self.sequencesPanel, -1, "waiting")
                tempDict[self.SEQUENCE_PROGRESS] = wx.Gauge(self.sequencesPanel, -1, 100)
##                tempDict[self.SEQUENCE_COMPLETE] = wx.StaticBitmap(self.sequencesPanel, -1,
##                              wx.Bitmap(self.execPath + "\\notchecked.ico", wx.BITMAP_TYPE_ANY))
                grid.Add(tempDict[self.SEQUENCE_NAME], 0, wx.ALL | wx.EXPAND, 3)
                grid.Add(tempDict[self.SEQUENCE_STATUS], 0, wx.ALL, 3)
                grid.Add(tempDict[self.SEQUENCE_PROGRESS], 0, wx.ALL, 3)
##                grid.Add(tempDict[self.SEQUENCE_COMPLETE], 0, 0, 0)

##                print path
            self.numSequences = len(paths)
            self.timer.Start(500)
            self.miAddSeq.Enable(False)

        dlg.Destroy()
        self.sequencesPanel.SetSizer(grid)
        self.sequencesPanel.SetAutoLayout(1)
        self.sequencesPanel.SetupScrolling()

        self.Refresh()
        self.Layout()

#-------------------------------------------------------------------------------
    def exportSequence(self, event):
        if self.activeProc != 0:
            dial = wx.MessageDialog(None, 'Sequences still being processed.',
                'Not Ready', wx.OK | wx.ICON_ERROR )
            status = dial.ShowModal()
            dial.Destroy()
        elif self.individualSeq == True:
            #Export each sequence individually
            for seq in self.sequences:
                fname = seq[self.PROC_INFO][self.SEQUENCE_FILE]
                fname = re.sub(r'msq$','xseq',fname)
                seq[self.SEQUENCE_OBJ].outputxLights(fname)
                if self.netInfo.maxChan == 16384:
                   fname = re.sub(r'xseq$','seq',fname)
                   seq[self.SEQUENCE_OBJ].outputConductor

        else:
            #Export single combines sequence. get Audio file first
            if not self.getAudioFileFromUser():
                dial = wx.MessageDialog(None, 'No Audio File Selected',
                'Error', wx.OK | wx.ICON_ERROR )
                status = dial.ShowModal()
                dial.Destroy()
            else:
                #have an audio file get export name
                dlg = wx.FileDialog(
                    self, message="Exported Filename", defaultFile="",
                    defaultDir="C:\\xlights", wildcard='*.xseq',
                    style=wx.SAVE | wx.CHANGE_DIR)
                if dlg.ShowModal() == wx.ID_OK:
                    exportFile = dlg.GetPath()
                    dlg.Destroy()
                else:
                    dial = wx.MessageDialog(None, 'No export file selected',
                     'Error', wx.OK | wx.ICON_ERROR )
                    status = dial.ShowModal()
                    dial.Destroy()
                    dlg.Destroy()
                    return
                #get the total number of periods we are goign to export
                numPeriods = 0
                for seq in self.sequences:
                    numPeriods += seq[self.SEQUENCE_OBJ].numPeriods
                #Open file and output header
                FH = open(exportFile, 'wb')
                FH.write(b'xLights  1 %8d %8d'%(self.netInfo.maxChan, numPeriods))
                FH.write(b'\x00\x00\x00\x00')
                FH.write(b'%s'%self.audioFile)
                #Pad out to 512 bytes
                FH.write(b'\x00'*(512 - int(len(self.audioFile)) -32))
                for chan in range(self.netInfo.maxChan):
                    for seq in self.sequences:
                        FH.write(seq[self.SEQUENCE_OBJ].getChannelEvents(chan))
        pass

#-------------------------------------------------------------------------------
    def getAudioFileFromUser(self):
        retVal = False
        dlg = wx.FileDialog(
            self, message="Select Sequence Audio File",
            defaultFile="",
            defaultDir="C:\\xlights",
            wildcard='Audio Files (*.mp3;*.wav)|*.mp3;*.wav|All Files (*.*)|*.*',
            style=wx.OPEN | wx.CHANGE_DIR
            )
        if dlg.ShowModal() == wx.ID_OK:
            audioPath = dlg.GetPath()
            self.audioFile = audioPath
            retVal = True
        return retVal

#-------------------------------------------------------------------------------
    def CloseWindow(self, event):
        self.Close()

#-------------------------------------------------------------------------------
    def OnClose(self, event):
        config = {}
        if self.individualSeq == True:
            config['SEQ_MODE'] = 'Individual'
        else:
            config['SEQ_MODE'] = 'combine'
        pickle.dump(config,open(self.cfgFile,'wb'))
        self.Destroy()

#-------------------------------------------------------------------------------
    def clearSequences(self, event):

        dial = wx.MessageDialog(None, 'Currently in memory sequences will be'+
                                'erased and sequences being processed will be stopped.'+
                                ' Are you sure you want to proceed?'+
                                '(No files will be deleted)',
         'Confirm clear', wx.OK | wx.ICON_EXCLAMATION | wx.CANCEL)
        status = dial.ShowModal() == wx.ID_OK

        if status:

            seqgrid = self.sequencesPanel.GetSizer()
            for seqGuiObjs in self.sequences:

                if seqGuiObjs.has_key(self.PROCESS):
                   if seqGuiObjs[self.PROCESS].is_alive():
                      seqGuiObjs[self.PROCESS].terminate()
                seqgrid.Hide(seqGuiObjs[self.SEQUENCE_NAME])
                seqgrid.Hide(seqGuiObjs[self.SEQUENCE_STATUS])
                seqgrid.Hide(seqGuiObjs[self.SEQUENCE_PROGRESS])
                seqgrid.Hide(seqGuiObjs[self.SEQUENCE_COMPLETE])
                seqgrid.Remove(seqGuiObjs[self.SEQUENCE_NAME])
                seqgrid.Remove(seqGuiObjs[self.SEQUENCE_STATUS])
                seqgrid.Remove(seqGuiObjs[self.SEQUENCE_PROGRESS])
                seqgrid.Remove(seqGuiObjs[self.SEQUENCE_COMPLETE])

            self.miAddSeq.Enable(True)
            seqgrid.SetRows(1)
            self.sequences = []

        self.Refresh()
        self.Layout()
        dial.Destroy()

#-------------------------------------------------------------------------------
    def seqOptionIndividual(self, event):
        self.individualSeq = True

#-------------------------------------------------------------------------------
    def seqOptionCombine(self, event):
        self.individualSeq = False

#-------------------------------------------------------------------------------
    def updateSettings(self, event):
        pass

#-------------------------------------------------------------------------------
    def aboutElf(self, event):
        dlg = AboutBox()

################################################################################
#-------------------------------------------------------------------------------
#

class AboutBox(wx.Dialog):
   def __init__(self):
        info = wx.AboutDialogInfo()
        info.Name = "Light Elf"
        info.Version = Version
        info.Copyright = "(C) 2012 Frank Reichstein"
        info.Description = \
"""This program converts Light Show Pro 2.5 sequences
directly to xLights format.  In addition it can combine sequences
into a single sequence for seamless playback of huge sequences."""
        #info.WebSite = ("http://www.pythonlibrary.org", "My Home Page")
        info.Developers = ["Frank Reichstein"]
        info.License = License
        # Show the wx.AboutBox
        wx.AboutBox(info)

################################################################################
#-------------------------------------------------------------------------------
# function to handle the sub processes that do translations
#
#-------------------------------------------------------------------------------
def seqWorker(**kwargs):

    procInfo = kwargs

    xSeq = Sequence(procInfo[LightingElf.SEQUENCE_FILE],
                    procInfo[LightingElf.PROC_XNET],
                    execDir=procInfo[LightingElf.EXEC_DIR])

    procInfo[LightingElf.PROC_STATQ].put('Extracting')
    if xSeq.extractSequence() == 1:
       procInfo[LightingElf.PROC_STATQ].put('error')
       exit

    procInfo[LightingElf.PROC_STATQ].put('Analyzing')
    xSeq.procSequence()

    dots = "."
    for (cur,total) in xSeq.convertLSPSequenceWStatus():
        dots = "." if len(dots) > 4 else dots + "."
        try:
            procInfo[LightingElf.PROC_STATQ].put_nowait('Processing'+dots)
            procInfo[LightingElf.PROC_OUTQ].put_nowait(cur)
            procInfo[LightingElf.PROC_OUTQ].put_nowait(total)
        except:
            pass

    try:
        procInfo[LightingElf.PROC_STATQ].put_nowait('Done')
        procInfo[LightingElf.PROC_OUTQ].put_nowait(xSeq)
    except:
        pass

################################################################################
if __name__ == "__main__":

    #app = wx.PySimpleApp(0)
    app = wx.App(filename='log.txt')

    wx.InitAllImageHandlers()
    frame_1 = LightingElf(None, -1, title="Lighting Elf", size=(800,300))
    app.SetTopWindow(frame_1)

    frame_1.Show()
    app.MainLoop()
