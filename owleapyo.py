import os, sys, inspect, thread, time, math, numpy
from threading import Thread
from random import randint

src_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
arch_dir = '../lib/x64' if sys.maxsize > 2**32 else '../lib/x86'
sys.path.insert(0, os.path.abspath(os.path.join(src_dir, arch_dir)))
sys.path += ["/Developer/LeapSDK/lib/"]

import Leap
from Leap import CircleGesture, KeyTapGesture, ScreenTapGesture, SwipeGesture
from pyo import *
import rdflib
from rdflib import XSD
import OSC

from pushmidi import PushMidi, MockMidi
from livernns import LiveDoubleRNN

class RdfReader():
    
    def parseXSDDuration(self, duration):
        return float(duration[2:-1])
    
    def loadDurations(self, filename, format):
        g = rdflib.Graph()
        g.load(filename, format=format)
        result = g.query(
            """SELECT DISTINCT ?dur
               WHERE {
                  ?a tl:at ?dur .
               }""")
        durations = []
        for row in result:
            durations.append(self.parseXSDDuration(row[0]))
        durations.sort()
        return durations

class LeapListener(Leap.Listener):
    
    def __init__(self, player):
        self.player = player
        super(LeapListener, self).__init__()

    def on_connect(self, controller):
        print "Connected"

    def on_frame(self, controller):
        frame = controller.frame()
        position = frame.hands.rightmost.palm_position
        if position.x != 0:
            self.player.waitTime = (position.y) / 1000
            self.player.durationRatio = (position.x +300) / 500
            self.player.frequencyRatio = (-position.z +300) / 300




class OscListener():
    
    def __init__(self, space):
        self.space = space
        address = '10.19.87.212', 57120
        self.server = OSC.OSCServer(address)
        #self.server.addMsgHandler("default", self.handleDefault)
        self.server.addMsgHandler("/create", self.handleCreate)
        self.server.addMsgHandler("/kill", self.handleKill), 
        self.thread = Thread( target = self.server.serve_forever )
        self.thread.start()
        self.skip = 0
    
    def handleCreate(self, addr, tags, stuff, source):
        self.space.addObject(stuff[0])
        address = "/sphere" + str(stuff[0]) + "/position"
        self.server.addMsgHandler(address, self.handleUpdate)
    
    def handleUpdate(self, addr, tags, stuff, source):
        index = int(addr[7:-9])
        self.space.updateObject(index, stuff[0], stuff[1], stuff[2], stuff[3], stuff[4])
    
    def handleKill(self, addr, tags, stuff, source):
        self.space.removeObject(stuff[0])
        #self.server.removeMsgHandler("/sphere" + stuff[0] + "/position")
    
    def stop(self):
        self.server.close()
        time.sleep(1)
        self.thread.join()



class Audio():
    
    def __init__(self):
        self.server = Server(buffersize=512)
        devices = pa_get_output_devices()
        try:
            duetIndex = devices[0].index('Duet USB')
            self.server.setOutputDevice(devices[1][duetIndex])
        except ValueError:
            pass
        self.server.boot()
        self.server.start()
    
    def stop(self):
        self.server.stop()
        print "server stopped"




class SoundObject():
    
    def __init__(self, filename, amplitude=1, start=None, end=None, durationRatio=1, disto=None, reverb=None, pan=None):
        self.filename = filename
        self.start = start
        self.end = end
        if start is None:
            self.snd = SndTable(filename)
            self.snd.fadein(0.01)
            self.snd.fadeout(0.01)
        else:
            self.initTable(durationRatio)
        if pan is None:
            pan = random.uniform(0,1)
        if reverb is None:
            reverb = random.uniform(0.3,1)
        if disto is None:
            disto = random.uniform(0,1)
        self.pan = pan
        self.disto = 0
        self.reverb = reverb
        self.amplitude = amplitude
    
    def initTable(self, durationRatio):
        duration = durationRatio*(self.end-self.start)
        newTable = SndTable(self.filename, start=self.start, stop=self.start+duration)
        newTable.fadein(0.01)
        newTable.fadeout(0.01)
        self.snd = newTable
    
    def setDurationRatio(self, durationRatio):
        if self.start is not None:
            self.initTable(durationRatio)
    
    def play(self):
        signal = self.getSignal() #IMPLEMENT IN INHERITING CLASSES
        signal = Disto(signal, drive=self.disto, slope=.8, mul=1).out()
        self.panner = Pan(signal, outs=2, pan=self.pan).out()
        self.out = self.panner
        return self.out
    
    def isPlaying(self):
        return hasattr(self, 'out') and self.out.isPlaying()
    
    def stopAndClean(self):
        Thread( target = self.stopOut ).start()
    
    def stopOut(self):
        if hasattr(self, 'out'):
            if hasattr(self, 'f'):
                self.f.stop()
            self.out.stop()
            time.sleep(1)
            ##bad design but sounds much better if done here in thread
            if hasattr(self, 'panner'):
                self.panner.stop()
                del self.panner
            if hasattr(self, 'f'):
                del self.f
            if hasattr(self, 'tbl'):
                self.tbl.stop()
                del self.tbl
            if hasattr(self, 'granulator'):
                self.granulator.stop()
                del self.granulator
            if hasattr(self, 'ampRamp'):
                self.ampRamp.stop()
                del self.ampRamp
            if hasattr(self, 'posRamp'):
                self.posRamp.stop()
                del self.posRamp
            #if still there, delete..
            if hasattr(self, 'out'):
                del self.out




class GranularSoundObject(SoundObject):
    
    def __init__(self, filename, amplitude=1, start=None, end=None, durationRatio=1, disto=None, reverb=None, pan=None):
        SoundObject.__init__(self, filename, amplitude, start, end, durationRatio, 0, 0.2, pan)
        self.position = 0
    
    def getSignal(self):
        self.posRamp = SigTo(value=0, time=0.02)
        self.ampRamp = SigTo(value=self.amplitude, time=0.02)
        self.granulator = Granulator(self.snd, HannTable(), [1, 1.001], self.posRamp, grains=randint(10,20), dur=Noise(.001, .1), basedur=0.1, mul=self.ampRamp)
        return self.granulator.out()
    
    def update(self, position, amplitude, pan=None, duration=None, pitch=None):
        self.position = position
        if hasattr(self, 'granulator'):
            self.posRamp.setValue(position)
            #self.granulator.setPos(position*self.snd.getSize()[0])
            self.ampRamp.setValue(amplitude)
            if pan != None:
                self.panner.setPan(pan)
            if duration != None:
                self.granulator.setDur(duration*0.3)
            if pitch != None:
                self.granulator.setPitch(pitch)
    
    def getPosition(self):
        return self.position
    
    def stop(self):
        self.granulator.stop()




class SampleSoundObject(SoundObject):
    
    def __init__(self, filename, amplitude=1, frequencyRatio=1, start=None, end=None, durationRatio=1, disto=None, reverb=None, pan=None):
        SoundObject.__init__(self, filename, amplitude, start, end, durationRatio, disto, reverb, pan)
        self.frequencyRatio = frequencyRatio
    
    def setFrequencyRatio(self, frequencyRatio):
        self.frequencyRatio = frequencyRatio
        frequency = self.frequencyRatio*(1/self.snd.getDur())
        if hasattr(self, 'tbl'):
            self.tbl.setFreq(frequency)
    
    def setDurationRatio(self, durationRatio):
        SoundObject.setDurationRatio(self, durationRatio)
    
    def getSignal(self):
        frequency = self.frequencyRatio*(1/self.snd.getDur())
        self.f = Fader(fadein=0.01, fadeout=1, dur=0, mul=self.amplitude)
        self.tbl = TableRead(table=self.snd, freq=frequency, mul=self.f).out()
        self.f.play()
        return self.tbl




class LoopSoundObject(SoundObject):
    
    def __init__(self, filename, amplitude=1, frequencyRatio=1, start=None, end=None, durationRatio=1, disto=None, reverb=None, pan=None):
        SoundObject.__init__(self, filename, amplitude, start, end, durationRatio, disto, reverb, pan)
        if self.snd.getDur() > 0:
            self.frequency = frequencyRatio*(1/self.snd.getDur())
        else:
            self.frequency = 1
    
    def getSignal(self):
        if not hasattr(self, 'tbl'):
            self.tbl = TableRead(table=self.snd, freq=self.frequency, loop=1, mul=self.amplitude)
        return self.tbl.out()
    
    def append(self, filename, start, end):
        duration = 1*(end-start)
        self.snd.append(filename, crossfade=0.1, start=start, stop=start+duration)
        self.snd.fadeout(0.01)
        self.tbl.setFreq(self.snd.getRate())
        #print self.snd.getSize(), self.snd.getRate()
    
    def stop(self):
        self.tbl.stop()







class ObjectSpace():
    
    def __init__(self, filename, durations):
        self.filename = filename
        self.durations = durations
        self.objects = {}
    
    def addObject(self, index):
        randomIndex = randint(0,len(self.durations)-2)
        start = self.durations[randomIndex]
        end = self.durations[randomIndex+1]
        self.objects[index] = GranularSoundObject(self.filename, 0.1, start, end)
        self.objects[index].play()
    
    def updateObject(self, index, pan, position, amplitude, duration, pitch):
        self.objects[index].update(position, amplitude, pan, duration, pitch)
    
    def removeObject(self, index):
        self.objects[index].stop()
    
    def removeObjects(self):
        for o in self.objects:
            self.objects[o].stop()







class Loop():
    
    def __init__(self, objects, duration=1, division=8, onsets=None, manual=False):
        finegrainedness = 100
        self.objects = objects
        self.duration = duration
        if not manual:
            self.beatDuration = float(duration)/division/finegrainedness
            self.createOnsets(onsets, division, finegrainedness)
            self.createImprecisionDirections(finegrainedness)
            self.seq = Seq(time=self.beatDuration, seq=self.onsets, poly=1)
        else:
            self.onsets = []
        #print self.onsets
        self.sparseness = 0
        self.index = 0
    
    def createOnsets(self, onsetCount, total, finegrainedness):
        dividers = sorted(random.sample(xrange(1, total), onsetCount - 1))
        self.onsets = [a - b for a, b in zip(dividers + [total], [0] + dividers)]
        self.onsets = (finegrainedness*numpy.array(self.onsets)).tolist()
    
    def addOnset(self, onset):
        self.onsets.append()
    
    def finalize(self, duration):
        self.beatDuration = float(duration)/division/finegrainedness
        self.createImprecisionDirections(finegrainedness)
        self.seq = Seq(time=self.beatDuration, seq=self.onsets, poly=1)
    
    def createImprecisionDirections(self, finegrainedness):
        self.imprecisionDirections = [ random.uniform(-1,1) for o in self.onsets ]
    
    def getOnsets(self):
        return self.onsets
    
    def setFrequencyRatio(self, frequencyRatio):
        for o in self.objects:
            o.setFrequencyRatio(frequencyRatio)
    
    def setDurationRatio(self, durationRatio):
        for o in self.objects:
            o.setDurationRatio(durationRatio)
    
    def setImprecision(self, imprecision):
        newOnsets = []
        for i in range(len(self.onsets)):
            newOnsets.append(self.onsets[i]+(imprecision*self.imprecisionDirections[i]))
        self.seq.setSeq(newOnsets)
    
    def setDuration(self, newDuration):
        newOnsets = []
        i = 0
        beatsSoFar = 0
        totalBeats = int(round(1.0*newDuration/self.beatDuration))
        while beatsSoFar < totalBeats:
            if len(newOnsets) < len(self.onsets):
                timeAfterOnset = beatsSoFar+self.onsets[i]
                if timeAfterOnset < totalBeats:
                    newOnsets.append(self.onsets[i])
                    i += 1
                    beatsSoFar = timeAfterOnset
                else:
                    newOnsets.append((totalBeats-beatsSoFar))
                    beatsSoFar = totalBeats
            else:
                newOnsets[-1] += totalBeats-beatsSoFar
                beatsSoFar = totalBeats
        self.seq.setSeq(newOnsets)
    
    def setTempoModifier(self, tempoModifier): #in percent
        self.seq.setTime(self.beatDuration/math.pow(2, 0.01*tempoModifier))
    
    def getObjectCount(self):
        return len(self.objects)
    
    def setObjects(self, objects):
        self.oldObjects = self.objects #temp save last objects to not stop them immediately
        self.objects = objects
        for x in self.oldObjects:
            x.stopAndClean()
    
    def playNextObject(self):
        #only play some if sparse..
        if random.uniform(0,100) > self.sparseness:
            self.objects[self.index].play()
        self.index = (self.index+1) % len(self.objects)
    
    def play(self):
        self.seq.play() #seq=[2,1,3,1,1,1,2,1], poly=1).play()
        self.trig = TrigFunc(self.seq, self.playNextObject)
    
    def stop(self):
        self.seq.stop()
        for x in self.objects:
            x.stopAndClean()
            #del x
    
    def stopAndClean(self):
        self.stop()
        del self.seq
        del self.trig





class RhythmPattern():
    
    def __init__(self, bassFilename, otherFilename, durations, manual=False):
        self.bassFilename = bassFilename
        self.otherFilename = otherFilename
        self.durations = durations
        self.durationRatio = 1
        self.frequencyRatio = 1
        self.loops = []
        self.imprecision = 0
        self.sparseness = 0
        if not manual:
            self.loopCount = 5#randint(1,20)
            self.createLoops()
        else:
            self.hitsRecorded = 0
    
    def addHit(self, index, velocity):
        if self.hitsRecorded == 0:
            self.startTime = time.time()
            self.firstHitIndex = index
        if index is self.firstHitIndex:
            self.hitsRecorded += 1
        if self.hitsRecorded == 5:
            self.finalize()
        else:
            if index not in self.loops:
                if index == 0:
                    self.loops[0] = Loop(self.createSimpleObject(self.bassFilename), self.duration, division, self.duration)
                
    
    def finalize(self):
        pass
    
    def createLoops(self):
        tempoFactor = ((randint(1,5)-3)/10)+1 #0.8,0.9,1,1.1,1.2
        self.duration = randint(2,4)
        division = 8*self.duration
        self.loops.append(Loop(self.createSimpleObject(self.bassFilename), self.duration, division, self.duration))
        for x in range(0, self.loopCount):
            onsets = randint(1,2*self.duration)
            self.loops.append(Loop(self.createNewObjects(self.otherFilename, onsets), self.duration, division, onsets))
    
    def createNewObjects(self, filename, objectsInSequence):
        objects = []
        for x in range(0, objectsInSequence):
            randomIndex = randint(0,len(self.durations)-2)
            start = self.durations[randomIndex]
            end = self.durations[randomIndex+1]
            objects.append(SampleSoundObject(filename, 0.5, self.frequencyRatio, start, end, randint(1,4))) #random.uniform(0,1)))
        return objects
    
    def createSimpleObject(self, filename):
        return [SampleSoundObject(filename, 0.7, random.uniform(0.6,1), pan=0.5, disto=0, reverb=0)]
    
    def replaceObjects(self):
        self.loops[0].setObjects(self.createNewObjects(self.bassFilename, self.loops[0].getObjectCount()))
        for x in range(1, len(self.loops)):
            self.loops[x].setObjects(self.createNewObjects(self.otherFilename, self.loops[x].getObjectCount()))
    
    def updateImprecision(self, delta):
        newValue = self.imprecision + delta
        if newValue >= 0:
            self.imprecision = newValue
            for loop in self.loops:
                loop.setImprecision(newValue)
    
    def updateSparseness(self, delta):
        newValue = self.sparseness + delta
        if newValue >= 0 and newValue <= 100:
            self.sparseness = newValue
            for loop in self.loops:
                loop.sparseness = newValue
    
    def modifySparseness(self, sparsenessMod):
        newValue = self.sparseness + sparsenessMod
        if newValue >= 0 and newValue <= 100:
            for loop in self.loops:
                loop.sparseness = newValue
    
    def updateDuration(self, durationModifier):
        newDuration = self.duration*math.pow(2, 0.01*durationModifier)
        for loop in self.loops:
            loop.setDuration(newDuration)
    
    def setTempoModifier(self, tempoModifier):
        for loop in self.loops:
            loop.setTempoModifier(tempoModifier)
    
    def setDurationRatio(self, durationRatio):
        for loop in self.loops:
            loop.setDurationRatio(durationRatio)
    
    def setFrequencyRatio(self, frequencyRatio):
        #all but the bass
        for i in range(1,len(self.loops)):
            self.loops[i].setFrequencyRatio(frequencyRatio)
    
    def setBassTuning(self, bassTuning):
        self.loops[0].setFrequencyRatio(bassTuning)
    
    def play(self, tempoModifier, durationRatio, durationModifier):
        self.updateDuration(durationModifier)
        for loop in self.loops:
            loop.setTempoModifier(tempoModifier)
            loop.setDurationRatio(durationRatio)
            loop.play()
    
    def stop(self):
        for loop in self.loops:
            loop.stop()
    
    def stopAndClean(self):
        for loop in self.loops:
            loop.stopAndClean()












class Player():
    
    def __init__(self, controller):
        self.controller = controller
        self.audio = Audio()
        self.durationRatio = 1
        self.bassTuningRatio = 1
        self.frequencyRatio = 1
        self.patternDurationModifier = 0
        self.tempoModifier = 0
        self.resetObjectMaps()
        self.updateDialInfo()
        self.currentSegmentsIndex = 0
        self.bassFilename = "miroglio/808 Bass A-1.wav"
        self.setFile("miroglio/garden1")
        self.mix = Mixer(outs=2, chnls=2, time=.025)
        #c = Clip(self.mix[0], min=0.5, max=2, mul=.4).mix(2).out()
        #self.out = self.mix[0]
        self.reverbSend = Freeverb(self.mix[1], size=.8, damp=.2, bal=1, mul=1).out()
        #self.reverbSend = Freeverb(signal, size=self.reverb, bal=self.reverb).out()
        #self.oscListener = OscListener(self.space)
    
    def resetObjectMaps(self):
        self.patterns = {}
        self.currentPattern = None
        self.objects = {}
        self.granularObjects = {}
        self.loops = {}
        self.currentLoop = 0
        self.playingLoop = None
    
    def setFile(self, filename):
        self.filename = filename + ".wav"
        self.durations = RdfReader().loadDurations(filename + "_onset.n3", "n3")
        self.space = ObjectSpace(self.filename, self.durations)
        self.deleteAllObjects()
        self.updateInfo()
    
    def changeSegmentsIndex(self, value):
        self.setSegmentsIndex(self.currentSegmentsIndex + value)
    
    def setSegmentsIndex(self, value):
        if 0 <= value and value < len(self.durations):
            self.currentSegmentsIndex = value
            self.deleteAllSimpleObjects()
            self.updateInfo()
    
    def updateDialInfo(self):
        if self.currentPattern is not None:
            self.controller.setDialStatus(0, "imp " + str(self.patterns[self.currentPattern].imprecision))
            self.controller.setDialStatus(1, "spa " + str(self.patterns[self.currentPattern].sparseness))
        else:
            self.controller.setDialStatus(0, "imp 0")
            self.controller.setDialStatus(1, "spa 0")
        self.controller.setDialStatus(2, "dur " + str(self.patternDurationModifier))
        self.controller.setDialStatus(3, "tmp " + str(self.tempoModifier))
        self.controller.setDialStatus(4, "bass " + str(self.bassTuningRatio))
        self.controller.setDialStatus(5, "frq " + str(self.frequencyRatio))
        self.controller.setDialStatus(6, "len " + str(self.durationRatio))
    
    def updateInfo(self):
        info = self.filename + " " + str(self.currentSegmentsIndex) + " " + str(len(self.durations))
        info += "   (objects alive: " + str(self.audio.server.getNumberOfStreams()) + ")"
        self.controller.setDisplayLine(1, info)
    
    def playSound(self, index, velocity):
        if index > 0:
            index = self.currentSegmentsIndex + index
        amp = 0.99*velocity/127
        if index < len(self.durations)-1:
            if index in self.objects:
                self.deleteObject(self.objects, index)
            if velocity > 0:
                if index == 0:
                    newObject = SampleSoundObject(self.bassFilename, 0.7*amp, self.bassTuningRatio, 0, 2, pan=0.5, disto=0, reverb=0)
                    self.mix.addInput(index, newObject.play())
                    self.mix.setAmp(index, 1, newObject.reverb*10)
                    self.objects[index] = newObject
                else:
                    start = self.durations[index]
                    end = self.durations[index+1]
                    newObject = SampleSoundObject(self.filename, amp, self.frequencyRatio, start, end, self.durationRatio)
                    self.mix.addInput(index, newObject.play())
                    self.mix.setAmp(index, 1, newObject.reverb*10)
                    self.objects[index] = newObject
    
    def playOrModifyGranularObject(self, index, amp):
        if index > 0:
            index = self.currentSegmentsIndex + index
        if index < len(self.durations)-1:
            amp = 0.99*amp/127
            if index in self.granularObjects and self.granularObjects[index].isPlaying():
                position = (self.granularObjects[index].getPosition()+0.002) % 1
                self.granularObjects[index].update(position, amp)
                if amp == 0:
                    self.deleteObject(self.granularObjects, index)
            elif index == 0:
                self.granularObjects[index] = GranularSoundObject(self.bassFilename, amp, pan=0.5, disto=0, reverb=0)
                self.granularObjects[index].play()
                self.mix.addInput(index, self.granularObjects[index].play())
                self.mix.setAmp(index, 0, 0)
                self.mix.setAmp(index, 1, self.granularObjects[index].reverb*10)
            else:
                start = self.durations[index]
                end = self.durations[index+1]
                self.granularObjects[index] = GranularSoundObject(self.filename, amp, start, end)
                self.granularObjects[index].play()
                self.mix.addInput(index, self.granularObjects[index].play())
                self.mix.setAmp(index, 0, 0)
                self.mix.setAmp(index, 1, self.granularObjects[index].reverb*10)
    
    def switchLoop(self, deltaIndex):
        newIndex = self.currentLoop + deltaIndex
        if newIndex >= 0:
            if newIndex in self.loops:
                if self.currentLoop in self.loops:
                    self.loops[self.currentLoop].stop()
                self.loops[newIndex].play()
                self.playingLoop = newIndex
            self.currentLoop = newIndex
            self.controller.setStatusLine(0, "loop: " + str(self.currentLoop))
        if newIndex == -1:
            self.loops[self.currentLoop].stop()
            self.currentLoop = -1
    
    def addSoundToLoop(self, index, velocity):
        #MEASURE TIME SINCE LAST ONE AND ADD!!
        #(MAKE SEAMLESS LOOPS STRETCH AND EXACTLY MIRROR RHYTHM!!!!)
        index = self.currentSegmentsIndex + index
        if index < len(self.durations)-1:
            amp = 0.99*velocity/127
            start = self.durations[index]
            end = self.durations[index+1]
            if self.currentLoop not in self.loops:
                self.loops[self.currentLoop] = LoopSoundObject(self.filename, 1, self.frequencyRatio, start, end, reverb=0)
                self.mix.addInput(index, self.loops[self.currentLoop].play())
                if self.playingLoop is not None:
                    self.loops[self.playingLoop].stop()
                self.playingLoop = self.currentLoop
                self.mix.setAmp(index, 1, self.loops[self.currentLoop].reverb*10)
            else:
                #INCLUDE DYNAMICS!!!!!
                self.loops[self.currentLoop].append(self.filename, start, end)
    
    def deleteAllObjects(self):
        self.deleteAllSimpleObjects()
        self.space.removeObjects()
        #del loops
        existingIndices = self.loops.keys()
        for index in existingIndices:
            self.deleteObject(self.loops, index)
        #del patterns
        self.stopPatterns()
        #reset indices
        self.resetObjectMaps()
    
    def deleteAllSimpleObjects(self):
        #del sample objects
        existingIndices = self.objects.keys()
        for index in existingIndices:
            self.deleteObject(self.objects, index)
        #del granular objects
        existingIndices = self.granularObjects.keys()
        for index in existingIndices:
            self.deleteObject(self.granularObjects, index)
    
    def deleteObject(self, objects, index):
        objects[index].stopAndClean()
        if index in objects: #if still there, clean
            del objects[index]
        self.mix.delInput(index)
        self.updateInfo()
    
    def recordPattern(self, index):
        self.userPattern = RhythmPattern(self.bassFilename, self.filename, self.durations, True)
    
    def switchToPattern(self, index):
        #play new pattern or replace sounds
        if index == self.currentPattern:
            self.patterns[self.currentPattern].replaceObjects()
        if index not in self.patterns:
            self.patterns[index] = RhythmPattern(self.bassFilename, self.filename, self.durations)
        self.patterns[index].play(self.tempoModifier, self.durationRatio, self.patternDurationModifier)
        #stop old pattern
        if self.currentPattern != None and self.currentPattern in self.patterns:
            self.patterns[self.currentPattern].stop()
            self.controller.setPadLight(self.currentPattern+36, 0)
        self.currentPattern = index
        self.controller.setPadLight(self.currentPattern+36, 127)
        self.updateInfo()
        self.updateDialInfo()
    
    def stopPatterns(self):
        existingIndices = self.patterns.keys()
        for index in existingIndices:
            self.deleteObject(self.patterns, index)
        if self.currentPattern is not None:
            self.controller.setPadLight(self.currentPattern+36, 0)
    
    def updateParameter(self, index, delta):
        if index is 0 and self.currentPattern is not None:
            self.patterns[self.currentPattern].updateImprecision(delta)
        if index is 1 and self.currentPattern is not None:
            self.patterns[self.currentPattern].updateSparseness(delta)
        if index is 2:
            self.patternDurationModifier += delta
            if self.currentPattern is not None:
                self.patterns[self.currentPattern].updateDuration(self.patternDurationModifier)
        if index is 3:
            self.tempoModifier += delta
            if self.currentPattern is not None:
                self.patterns[self.currentPattern].setTempoModifier(self.tempoModifier)
        if index is 4:
            self.bassTuningRatio *= math.pow(2, 0.01*delta)
            if self.currentPattern is not None:
                self.patterns[self.currentPattern].setBassTuning(self.bassTuningRatio)
        if index is 5:
            self.frequencyRatio *= math.pow(2, 0.01*delta)
            if self.currentPattern is not None:
                self.patterns[self.currentPattern].setFrequencyRatio(self.frequencyRatio)
        if index is 6:
            self.durationRatio *= math.pow(2, 0.05*delta)
            if self.currentPattern is not None:
                self.patterns[self.currentPattern].setDurationRatio(self.durationRatio)
        if index is 7:
            self.mix *= math.pow(2, 0.05*delta)
            if self.currentPattern is not None:
                self.patterns[self.currentPattern].setDurationRatio(self.durationRatio)
        self.updateDialInfo()
    
    def updateBend(self, value):
        if self.currentPattern is not None:
            if value <= 0:
                self.patterns[self.currentPattern].setTempoModifier(self.tempoModifier+value/20)
                #self.patterns[self.currentPattern].setFrequencyModifier(0.001*value)
                self.controller.setDialStatus(3, "tmp " + str(self.tempoModifier+value/20))
            if value >= 0:
                self.patterns[self.currentPattern].modifySparseness(value/80)
                self.controller.setDialStatus(1, "spa " + str(self.patterns[self.currentPattern].sparseness+(value/80)))
    
    def stop(self):
        for loop in self.loops:
            loop.stop()
        self.audio.stop()



def main():
    
    controller = PushMidi()
    rnn = LiveDoubleRNN(controller)
    player = Player(controller)
    controller.setNetAndPlayer(rnn, player)
    player.audio.server.gui(locals(), exit=True)
    
    #durations = RdfReader().loadDurations("miroglio/garden3_onset.n3", "n3")
    
    """randomIndex = randint(0,len(durations)-2)
    start = durations[randomIndex]
    end = durations[randomIndex+1]
    g = GranularSoundObject("miroglio/garden3.wav", 0.3, start, end, 1)
    g.play()"""
    
    
    # Create a listener and controller
    #listener = LeapListener(player)
    #controller = Leap.Controller()

    # Have the sample listener receive events from the controller
    #controller.add_listener(listener)
    
    #oscListener = OscListener(player)
    
    #player.audio.server.gui(locals(), exit=True)
    
    #midiListener.stop()
    
    """s.stop()
    time.sleep(1)
    exit()"""
    
    try:
        while True:
            pass
    except KeyboardInterrupt:
        controller.stop()
        rnn.stop()
        player.oscListener.stop()
        player.audio.server.stop()
        time.sleep(1)
        player.audio.server.shutdown()
        exit()

if __name__ == "__main__":
    main()