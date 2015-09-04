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
        address = '192.168.1.128', 57120
        self.server = OSC.OSCServer(address)
        #self.server.addMsgHandler("default", self.handleDefault)
        self.server.addMsgHandler("/create", self.handleCreate)
        self.server.addMsgHandler("/kill", self.handleKill), 
        self.thread = Thread( target = self.server.serve_forever )
        self.thread.start()
    
    def handleCreate(self, addr, tags, stuff, source):
        self.space.addObject(stuff[0])
        address = "/sphere" + str(stuff[0]) + "/position"
        self.server.addMsgHandler(address, self.handleUpdate)
    
    def handleUpdate(self, addr, tags, stuff, source):
        index = int(addr[7:-9])
        self.space.updateObject(index, stuff[0], stuff[1], stuff[2], stuff[3])
    
    def handleKill(self, addr, tags, stuff, source):
        self.space.removeObject(stuff[0])
        #self.server.removeMsgHandler("/sphere" + stuff[0] + "/position")
    
    def stop(self):
        self.server.close()
        self.thread.join()

class Audio():
    
    def __init__(self):
        self.server = Server(buffersize=256).boot()
        self.server.start()
    
    def stop(self):
        self.server.stop()
        
        print "server stopped"

class SoundObject():
    
    def __init__(self, filename, amplitude=1, start=None, end=None, durationRatio=1, disto=None, reverb=None, pan=None):
        if start is None:
            self.snd = SndTable(filename)
        else:
            duration = durationRatio*(end-start)
            self.snd = SndTable(filename, start=start, stop=start+duration)
            self.snd.fadein(0.01)
            self.snd.fadeout(0.01)
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
    
    def play(self):
        signal = self.getSignal() #IMPLEMENT IN INHERITING CLASSES
        signal = Pan(signal, outs=2, pan=self.pan).out()
        self.out = Disto(signal, drive=self.disto, slope=.8, mul=.15).out()
        return self.out
    
    def isPlaying(self):
        return hasattr(self, 'out') and self.out.isPlaying()
    
    def stopAndClean(self):
        Thread( target = self.stopOut ).start()
    
    def stopOut(self):
        if hasattr(self, 'out'):
            self.out.setMul(Fader(fadein=0, fadeout=1, dur=0, mul=1).out())
            self.out.stop()
            time.sleep(1)
            #if still there, delete..
            if hasattr(self, 'out'):
                del self.out
                "DEL!"

class GranularSoundObject(SoundObject):
    
    def __init__(self, filename, amplitude=1, start=None, end=None, durationRatio=1, disto=None, reverb=None, pan=None):
        SoundObject.__init__(self, filename, amplitude, start, end, durationRatio, 0, 0.2, pan)
        self.position = 0
    
    def getSignal(self):
        self.granulator = Granulator(self.snd, HannTable(), [1, 1.001], grains=randint(10,20), dur=Noise(.001, .1), basedur=0.1, mul=self.amplitude)
        return self.granulator.out()
    
    def update(self, position, amplitude, duration=None, pitch=None):
        self.position = position
        if hasattr(self, 'granulator'):
            self.granulator.setPos(position*self.snd.getSize()[0])
            self.granulator.setMul(amplitude)
            if duration != None:
                self.granulator.setDur(duration*0.3)
            if pitch != None:
                self.granulator.setPitch(pitch)
    
    def getPosition(self):
        return self.position
    
    def stopOut(self):
        SoundObject.stopOut(self)
        if hasattr(self, 'granulator'):
            del self.granulator

class SampleSoundObject(SoundObject):
    
    def __init__(self, filename, amplitude=1, frequencyRatio=1, start=None, end=None, durationRatio=1, disto=None, reverb=None, pan=None):
        SoundObject.__init__(self, filename, amplitude, start, end, durationRatio, disto, reverb, pan)
        if self.snd.getDur() > 0:
            self.frequency = frequencyRatio*(1/self.snd.getDur())
        else:
            self.frequency = 1
        
    def getSignal(self):
        return TableRead(table=self.snd, freq=self.frequency, mul=self.amplitude).out()

class LoopSoundObject(SoundObject):
    
    def __init__(self, filename, amplitude=1, frequencyRatio=1, start=None, end=None, durationRatio=1, disto=None, reverb=None, pan=None):
        SoundObject.__init__(self, filename, amplitude, start, end, durationRatio, disto, reverb, pan)
        if self.snd.getDur() > 0:
            self.frequency = frequencyRatio*(1/self.snd.getDur())
        else:
            self.frequency = 1
        print start, end
    
    def getSignal(self):
        if not hasattr(self, 'tbl'):
            self.tbl = TableRead(table=self.snd, freq=self.frequency, loop=1, mul=self.amplitude)
        return self.tbl.out()
    
    def append(self, filename, start, end):
        duration = 1*(end-start)
        self.snd.append(filename, crossfade=0.1, start=start, stop=start+duration)
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
        self.objects[index] = GranularSoundObject(self.filename, 0.3, start, end, 0)
        self.objects[index].play()
    
    def updateObject(self, index, position, amplitude, duration, pitch):
        self.objects[index].update(position, amplitude, duration, pitch)
    
    def removeObject(self, index):
        self.objects[index].stopAndClean()

class Loop():
    
    def __init__(self, objects, duration, division, onsets):
        finegrainedness = 100
        self.objects = objects
        self.beatDuration = float(duration)/division/finegrainedness
        self.createOnsets(onsets, division, finegrainedness)
        self.createImprecisionDirections(finegrainedness)
        self.seq = Seq(time=self.beatDuration, seq=self.onsets, poly=1)
        #print onsets
        self.sparseness = 0
        self.index = 0
    
    def createOnsets(self, onsetCount, total, finegrainedness):
        dividers = sorted(random.sample(xrange(1, total), onsetCount - 1))
        self.onsets = [a - b for a, b in zip(dividers + [total], [0] + dividers)]
        self.onsets = (finegrainedness*numpy.array(self.onsets)).tolist()
    
    def createImprecisionDirections(self, finegrainedness):
        self.imprecisionDirections = [ random.uniform(-1,1) for o in self.onsets ]
    
    def getOnsets(self):
        return self.onsets
    
    def setImprecision(self, imprecision):
        newOnsets = []
        for i in range(len(self.onsets)):
            newOnsets.append(self.onsets[i]+(imprecision*self.imprecisionDirections[i]))
        self.seq.setSeq(newOnsets)
    
    def setTempo(self, tempoIncrease): #in percent
        self.seq.setTime(self.beatDuration/math.pow(2, 0.01*tempoIncrease))
    
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
            del x

class RhythmPattern():
    
    def __init__(self, durations):
        self.durations = durations
        self.loopCount = 5#randint(1,20)
        self.durationRatio = 1
        self.frequencyRatio = 1
        self.filenames = ["miroglio/808 Bass A-1.wav", "miroglio/garden3.wav"]
        self.loops = []
        self.imprecision = 0
        self.sparseness = 0
        self.tempo = 0
        tempoFactor = ((randint(1,5)-3)/10)+1 #0.8,0.9,1,1.1,1.2
        duration = randint(2,4)
        division = 8*duration
        self.loops.append(Loop(self.createSimpleObject(self.filenames[0]), duration, division, duration))
        for x in range(0, self.loopCount):
            onsets = randint(1,2*duration)
            self.loops.append(Loop(self.createNewObjects(self.filenames[1], onsets), duration, division, onsets))
    
    def createNewObjects(self, filename, objectsInSequence):
        objects = []
        for x in range(0, objectsInSequence):
            randomIndex = randint(0,len(self.durations)-2)
            start = self.durations[randomIndex]
            end = self.durations[randomIndex+1]
            objects.append(SampleSoundObject(filename, 0.6, self.frequencyRatio, start, end, randint(1,4))) #random.uniform(0,1)))
        return objects
    
    def createSimpleObject(self, filename):
        return [SampleSoundObject(filename, 1, random.uniform(0.6,1), pan=0.5, disto=0, reverb=0)]
    
    def replaceObjects(self):
        for x in range(0, len(self.loops)):
            f = min(x, 1)
            self.loops[x].setObjects(self.createNewObjects(self.filenames[f], self.loops[x].getObjectCount()))
    
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
    
    def updateTempo(self, delta):
        newValue = self.tempo + delta
        if newValue >= -100 and newValue <= 100:
            self.tempo = newValue
            for loop in self.loops:
                loop.setTempo(newValue)
    
    def play(self):
        for loop in self.loops:
            loop.play()
    
    def stop(self):
        for loop in self.loops:
            loop.stop()

class Player():
    
    def __init__(self, controller):
        self.controller = controller
        self.audio = Audio()
        self.durationRatio = 1
        self.frequencyRatio = 1
        self.patterns = {}
        self.currentPattern = None
        self.objects = {}
        self.granularObjects = {}
        self.loops = {}
        self.currentLoop = 0
        self.playingLoop = None
        self.updateDialInfo()
        self.currentSegmentsIndex = 0
        self.setFile("miroglio/garden3")
        self.mix = Mixer(outs=2, chnls=2, time=.025)
        #self.out = self.mix[0]
        self.reverbSend = Freeverb(self.mix[1], size=.8, damp=.2, bal=1, mul=1).out()
        #self.reverbSend = Freeverb(signal, size=self.reverb, bal=self.reverb).out()
    
    def setFile(self, filename):
        self.filename = filename + ".wav"
        self.durations = RdfReader().loadDurations(filename + "_onset.n3", "n3")
        self.deleteAllObjects()
        self.updateInfo()
    
    def changeSegmentsIndex(self, value):
        self.setSegmentsIndex(self.currentSegmentsIndex + value)
    
    def setSegmentsIndex(self, value):
        if 0 <= value and value < len(self.durations):
            self.currentSegmentsIndex = value
            self.deleteAllObjects()
            self.updateInfo()
    
    def updateDialInfo(self):
        if self.currentPattern is not None:
            self.controller.setDialStatus(0, "imp " + str(self.patterns[self.currentPattern].imprecision))
            self.controller.setDialStatus(1, "spa " + str(self.patterns[self.currentPattern].sparseness))
            self.controller.setDialStatus(2, "tmp " + str(self.patterns[self.currentPattern].tempo))
        else:
            self.controller.setDialStatus(0, "imp 0")
            self.controller.setDialStatus(1, "spa 0")
            self.controller.setDialStatus(2, "tmp 0")
        self.controller.setDialStatus(3, "bass 0")
    
    def updateInfo(self):
        info = self.filename + " " + str(self.currentSegmentsIndex) + " " + str(len(self.durations))
        info += "   (objects alive: " + str(self.audio.server.getNumberOfStreams()) + ")"
        self.controller.setDisplayLine(1, info)
    
    def playSound(self, index, velocity):
        index = self.currentSegmentsIndex + index
        amp = 0.99*velocity/127
        if index < len(self.durations)-1:
            if index in self.objects:
                self.deleteObject(self.objects, index)
            if velocity > 0:
                start = self.durations[index]
                end = self.durations[index+1]
                newObject = SampleSoundObject(self.filename, amp, self.frequencyRatio, start, end)
                self.mix.addInput(index, newObject.play())
                self.mix.setAmp(index, 1, newObject.reverb*10)
                self.objects[index] = newObject
    
    def playOrModifyGranularObject(self, index, amp):
        index = self.currentSegmentsIndex + index
        if index < len(self.durations)-1:
            amp = 0.99*amp/127
            if index in self.granularObjects and self.granularObjects[index].isPlaying():
                position = (self.granularObjects[index].getPosition()+0.002) % 1
                self.granularObjects[index].update(position, amp)
                if amp == 0:
                    self.deleteObject(self.granularObjects, index)
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
                self.loops[self.currentLoop].stop()
                self.loops[newIndex].play()
                self.playingLoop = newIndex
            self.currentLoop = newIndex
            self.controller.setStatusLine(0, "loop: " + str(self.currentLoop))
    
    def addSoundToLoop(self, index, velocity):
        #MEASURE TIME SINCE LAST ONE AND ADD!!
        #(MAKE SEAMLESS LOOPS STRETCH AND EXACTLY MIRROR RHYTHM!!!!)
        index = self.currentSegmentsIndex + index
        if index < len(self.durations)-1:
            amp = 0.99*velocity/127
            start = self.durations[index]
            end = self.durations[index+1]
            if self.currentLoop not in self.loops:
                self.loops[self.currentLoop] = LoopSoundObject(self.filename, amp, self.frequencyRatio, start, end, reverb=0)
                self.mix.addInput(index, self.loops[self.currentLoop].play())
                if self.playingLoop is not None:
                    self.loops[self.playingLoop].stop()
                self.playingLoop = self.currentLoop
                self.mix.setAmp(index, 1, self.loops[self.currentLoop].reverb*10)
            else:
                #INCLUDE DYNAMICS!!!!!
                self.loops[self.currentLoop].append(self.filename, start, end)
    
    def deleteAllObjects(self):
        existingIndices = self.objects.keys()
        for index in existingIndices:
            self.deleteObject(self.objects, index)
        existingIndices = self.granularObjects.keys()
        for index in existingIndices:
            self.deleteObject(self.granularObjects, index)
    
    def deleteObject(self, objects, index):
        objects[index].stopAndClean()
        if index in objects: #if still there, clean
            del objects[index]
        self.mix.delInput(index)
        self.updateInfo()
    
    def switchToPattern(self, index):
        #play new pattern or replace sounds
        if index == self.currentPattern:
            self.patterns[self.currentPattern].replaceObjects()
        if index not in self.patterns:
            self.patterns[index] = RhythmPattern(self.durations)
        self.patterns[index].play()
        #stop old pattern
        if self.currentPattern != None:
            self.patterns[self.currentPattern].stop()
            self.controller.setPadLight(self.currentPattern+36, 0)
        self.currentPattern = index
        self.controller.setPadLight(self.currentPattern+36, 127)
        self.updateInfo()
        self.updateDialInfo()
    
    def updatePatternParameter(self, index, delta):
        if index is 0:
            self.patterns[self.currentPattern].updateImprecision(delta)
        if index is 1:
            self.patterns[self.currentPattern].updateSparseness(delta)
        if index is 2:
            self.patterns[self.currentPattern].updateTempo(delta)
        self.updateDialInfo()
    
    def stop(self):
        for loop in self.loops:
            loop.stop()
        self.audio.stop()



def main():
    
    controller = PushMidi()
    rnn = LiveDoubleRNN(controller)
    player = Player(controller)
    controller.setNetAndPlayer(rnn, player)
    
    #durations = RdfReader().loadDurations("miroglio/garden3_onset.n3", "n3")
    #space = ObjectSpace("miroglio/garden3.wav", durations)
    #oscListener = OscListener(space)
    
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
        player.audio.server.stop()
        time.sleep(1)
        player.audio.server.shutdown()
        exit()

if __name__ == "__main__":
    main()